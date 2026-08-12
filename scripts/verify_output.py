#!/usr/bin/env python3
"""Verify the rendered video, every planned cut, captions, and untouched audio."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np

from lib import audio_stream, default_video_use_dir, ffprobe, file_sha256, fps_fraction, stream_hash, target_frame_count, validate_plan, video_stream


def decode_gray(path: Path) -> np.ndarray:
    raw = subprocess.check_output([
        "ffmpeg", "-v", "error", "-i", str(path), "-vf", "scale=160:284,format=gray",
        "-fps_mode", "passthrough", "-f", "rawvideo", "-",
    ])
    return np.frombuffer(raw, np.uint8).reshape(-1, 284, 160).astype(np.int16)


def create_contact_sheets(output: Path, verify: Path, duration: float) -> list[str]:
    paths = []
    page_count = max(1, math.ceil(duration / 30.0))
    if page_count > 1 and duration - (page_count - 1) * 30.0 < 1.0:
        page_count -= 1
    for page in range(page_count):
        start = page * 30.0
        page_duration = min(30.0, max(0.01, duration - start))
        destination = verify / f"contact_sheet_{page:03d}.jpg"
        subprocess.run([
            "ffmpeg", "-v", "error", "-y", "-ss", f"{start + min(.5, page_duration/2):.3f}",
            "-i", str(output), "-t", f"{page_duration:.3f}",
            "-vf", "fps=1,scale=216:384,tile=6x5", "-frames:v", "1", str(destination),
        ], check=True)
        paths.append(str(destination))
    return paths


def create_timeline_views(output: Path, verify: Path, boundaries: list[float], duration: float, video_use: Path) -> list[str]:
    helper = video_use / "helpers" / "timeline_view.py"
    if not helper.exists():
        raise SystemExit(f"timeline_view helper not found: {helper}")
    paths = []
    safe_end = max(0.0, duration - .04)
    for index, boundary in enumerate(boundaries, start=1):
        start = max(0.0, boundary - 1.5)
        end = min(safe_end, boundary + 1.5)
        destination = verify / f"cut_{index:04d}.png"
        subprocess.run([
            sys.executable, str(helper), str(output), f"{start:.6f}", f"{end:.6f}",
            "--n-frames", "6", "-o", str(destination),
        ], check=True, stdout=subprocess.DEVNULL)
        paths.append(str(destination))
    return paths


def caption_recall(source: Path, output: Path, caption: dict, source_intervals: list[tuple[float, float]], duration: float) -> dict | None:
    if not caption.get("preserve"):
        return None
    y = int(caption["y"])
    height = int(caption["height"])
    sample_rate = min(2.0, max(0.1, 120.0 / max(duration, 0.1)))
    small_y = y // 2
    small_height = max(2, height // 2)
    source_filter = f"scale=540:960:force_original_aspect_ratio=increase,crop=540:960,crop=540:{small_height}:0:{small_y},fps={sample_rate:.6f},format=rgb24"
    output_filter = f"scale=540:960,crop=540:{small_height}:0:{small_y},fps={sample_rate:.6f},format=rgb24"
    def decode(path: Path, visual_filter: str) -> np.ndarray:
        raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", str(path), "-vf", visual_filter, "-f", "rawvideo", "-"])
        return np.frombuffer(raw, np.uint8).reshape(-1, small_height, 540, 3)
    original = decode(source, source_filter)
    final = decode(output, output_filter)
    recalls = []
    for index in range(min(len(original), len(final))):
        time = index / sample_rate
        if any(start <= time < end for start, end in source_intervals):
            continue
        src = original[index]
        dst = final[index]
        src_yellow = (src[..., 0] > 180) & (src[..., 1] > 165) & (src[..., 2] < 125)
        dst_yellow = (dst[..., 0] > 165) & (dst[..., 1] > 145) & (dst[..., 2] < 145)
        count = int(src_yellow.sum())
        if count > 30:
            recalls.append(float((src_yellow & dst_yellow).sum() / count))
    if not recalls:
        return {"samples": 0}
    return {
        "samples": len(recalls),
        "mean": float(np.mean(recalls)),
        "p10": float(np.percentile(recalls, 10)),
        "minimum": float(np.min(recalls)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--video-use-dir", type=Path, default=default_video_use_dir())
    parser.add_argument("--timeline-views", action="store_true")
    parser.add_argument("--min-cut-mad", type=float, default=6.0)
    args = parser.parse_args()
    plan_path = args.plan.expanduser().resolve()
    plan, source_probe, ranges = validate_plan(plan_path)
    source = Path(plan["source"])
    output = (args.output or Path(plan["output"])).expanduser().resolve()
    if not output.exists():
        raise SystemExit(f"rendered output not found: {output}")
    edit = plan_path.parent
    verify = edit / "verify"
    verify.mkdir(parents=True, exist_ok=True)

    subprocess.run(["ffmpeg", "-v", "error", "-i", str(output), "-f", "null", "-"], check=True)
    output_probe = ffprobe(output)
    stream = video_stream(output_probe)
    fps = float(fps_fraction(source_probe))
    expected_frames = target_frame_count(source_probe)
    actual_frames = target_frame_count(output_probe)
    if actual_frames != expected_frames:
        raise SystemExit(f"frame count mismatch: {actual_frames} != {expected_frames}")
    required = {
        "codec_name": "h264",
        "width": 1080,
        "height": 1920,
        "pix_fmt": "yuv420p",
        "sample_aspect_ratio": "1:1",
    }
    for key, expected in required.items():
        if stream.get(key) != expected:
            raise SystemExit(f"output {key} is {stream.get(key)!r}; expected {expected!r}")

    source_audio = stream_hash(source, "0:a:0") if audio_stream(source_probe) else None
    output_audio = stream_hash(output, "0:a:0") if audio_stream(source_probe) else None
    if source_audio != output_audio:
        raise SystemExit("source and final audio packet hashes differ")

    frames = decode_gray(output)
    deltas = np.abs(frames[1:] - frames[:-1]).mean(axis=(1, 2))
    boundary_frames = [end for _, end in ranges[:-1]]
    cut_peaks = []
    cut_locations = []
    for boundary in boundary_frames:
        low = max(0, boundary - 4)
        high = min(len(deltas), boundary + 4)
        local = deltas[low:high]
        location = low + int(np.argmax(local))
        cut_locations.append(location + 1)
        cut_peaks.append(float(local.max()))
    if cut_peaks and min(cut_peaks) < args.min_cut_mad:
        raise SystemExit(f"a planned scene boundary lacks a visible change: minimum MAD {min(cut_peaks):.3f}")

    duration = expected_frames / fps
    contact_sheets = create_contact_sheets(output, verify, duration)
    boundaries_seconds = [frame / fps for frame in boundary_frames]
    timeline_views = create_timeline_views(output, verify, boundaries_seconds, duration, args.video_use_dir.expanduser().resolve()) if args.timeline_views else []
    source_intervals = [
        (start / fps, end / fps)
        for scene, (start, end) in zip(plan["scenes"], ranges, strict=True)
        if scene["kind"] == "source"
    ]
    captions = caption_recall(source, output, plan.get("caption") or {}, source_intervals, duration)
    report = {
        "ok": True,
        "source": str(source),
        "output": str(output),
        "output_sha256": file_sha256(output),
        "expected_frames": expected_frames,
        "actual_frames": actual_frames,
        "fps": str(fps_fraction(source_probe)),
        "duration_seconds": duration,
        "video": {key: stream.get(key) for key in required},
        "source_audio_sha256": source_audio,
        "output_audio_sha256": output_audio,
        "scene_count": len(plan["scenes"]),
        "boundary_count": len(boundary_frames),
        "cut_peak_mad": cut_peaks,
        "cut_frame_locations": cut_locations,
        "minimum_cut_peak_mad": min(cut_peaks) if cut_peaks else None,
        "median_cut_peak_mad": float(np.median(cut_peaks)) if cut_peaks else None,
        "caption_recall": captions,
        "contact_sheets": contact_sheets,
        "timeline_views": timeline_views,
    }
    destination = verify / "report.json"
    destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(destination)


if __name__ == "__main__":
    main()
