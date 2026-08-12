#!/usr/bin/env python3
"""Inventory a raw video and create a source-only editable B-roll project."""

from __future__ import annotations

import argparse
import json
import math
import platform
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from lib import ceil_div_duration, duration_seconds, ffprobe, fps_fraction, repository_root, target_frame_count, video_stream


def detect_yellow_caption_band(source: Path, duration: float) -> dict:
    sample_duration = min(duration, 120.0)
    command = [
        "ffmpeg", "-v", "error", "-i", str(source), "-t", f"{sample_duration:.3f}",
        "-vf", "fps=1,scale=540:960:force_original_aspect_ratio=increase,crop=540:960,format=rgb24",
        "-f", "rawvideo", "-",
    ]
    raw = subprocess.check_output(command)
    frame_bytes = 540 * 960 * 3
    count = len(raw) // frame_bytes
    if count == 0:
        return {"preserve": False}
    frames = np.frombuffer(raw[:count * frame_bytes], np.uint8).reshape(count, 960, 540, 3)
    yellow = (frames[..., 0] > 175) & (frames[..., 1] > 155) & (frames[..., 2] < 135)
    row_presence = (yellow.sum(axis=2) >= 12).sum(axis=0)
    minimum = max(2, math.ceil(count * 0.08))
    candidates = np.flatnonzero((row_presence >= minimum) & (np.arange(960) >= 300) & (np.arange(960) <= 820))
    if candidates.size == 0:
        return {"preserve": False}
    groups = np.split(candidates, np.where(np.diff(candidates) > 5)[0] + 1)
    group = max(groups, key=lambda values: (row_presence[values].sum(), len(values)))
    y0 = max(0, int(group.min()) * 2 - 42)
    y1 = min(1920, int(group.max() + 1) * 2 + 42)
    return {
        "preserve": True,
        "color": "0xFFFF00",
        "y": y0,
        "height": y1 - y0,
        "similarity": 0.22,
        "blend": 0.08,
        "outline_dilation": 4,
    }


def run_ocr(source: Path, edit_dir: Path) -> None:
    if platform.system() != "Darwin" or subprocess.run(["which", "swift"], capture_output=True).returncode != 0:
        print("OCR skipped: macOS Swift/Vision is unavailable")
        return
    transcript_dir = edit_dir / "transcripts"
    transcript_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="broll-ocr-") as temporary:
        frames = Path(temporary)
        subprocess.run([
            "ffmpeg", "-v", "error", "-i", str(source), "-vf", "fps=2", "-q:v", "3",
            str(frames / "%06d.jpg"),
        ], check=True)
        result = subprocess.run(
            ["swift", str(repository_root() / "scripts" / "ocr_captions.swift"), str(frames)],
            check=True, text=True, capture_output=True,
        )
    tsv = transcript_dir / f"{source.stem}_caption_ocr.tsv"
    tsv.write_text(result.stdout, encoding="utf-8")
    lines = []
    previous = ""
    for raw_line in result.stdout.splitlines():
        time, _, text = raw_line.partition("\t")
        text = text.strip()
        if text and text != previous:
            lines.append(f"  [{float(time):07.2f}] {text}")
            previous = text
    packed = "# Packed caption timeline\n\n## " + source.name + "\n\n" + "\n".join(lines) + "\n"
    (edit_dir / "takes_packed.md").write_text(packed, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--edit-dir", type=Path)
    parser.add_argument("--ocr", action="store_true")
    parser.add_argument("--max-scene-seconds", type=float, default=1.0)
    args = parser.parse_args()
    source = args.source.expanduser().resolve()
    if not source.exists():
        raise SystemExit(f"source not found: {source}")
    edit = (args.edit_dir or source.parent / "edit").expanduser().resolve()
    for name in ("animations/slot_rapid_timeline", "downloads", "transcripts", "verify"):
        (edit / name).mkdir(parents=True, exist_ok=True)

    probe = ffprobe(source)
    stream = video_stream(probe)
    duration = duration_seconds(probe)
    fps = fps_fraction(probe)
    caption = detect_yellow_caption_band(source, duration)
    analysis = {
        "source": str(source),
        "duration": duration,
        "fps": str(fps),
        "frame_count": target_frame_count(probe),
        "width": stream.get("width"),
        "height": stream.get("height"),
        "codec": stream.get("codec_name"),
        "caption_detection": caption,
        "ffprobe": probe,
    }
    (edit / "source_analysis.json").write_text(json.dumps(analysis, indent=2) + "\n", encoding="utf-8")

    count = ceil_div_duration(duration, args.max_scene_seconds)
    scenes = []
    for index in range(count):
        start = index * duration / count
        end = (index + 1) * duration / count
        scenes.append({
            "start": round(start, 6),
            "end": round(end, 6) if index < count - 1 else duration,
            "kind": "source",
            "description": f"source placeholder {index + 1}; replace with topic-matched B-roll or keep as a deliberate speaker return",
            "effect": "normal",
            "crop_x": 0.5,
            "crop_y": 0.5,
        })
    plan = {
        "version": 1,
        "source": str(source),
        "output": str(edit / "final_broll.mp4"),
        "width": 1080,
        "height": 1920,
        "max_scene_seconds": args.max_scene_seconds,
        "caption": caption,
        "scenes": scenes,
    }
    (edit / "scene_plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    project = (
        "# B-Rolls Project\n\n"
        "## Session 1\n\n"
        f"**Source:** `{source}`\n\n"
        "**Strategy:** Pending semantic transcript review and scene-plan replacement.\n\n"
        "**Sources:** Pending.\n\n"
        "**Verification:** Pending.\n\n"
        "**Outstanding:** Replace source placeholders, render, and verify.\n"
    )
    (edit / "project.md").write_text(project, encoding="utf-8")
    if args.ocr:
        run_ocr(source, edit)
    print(edit / "scene_plan.json")


if __name__ == "__main__":
    main()
