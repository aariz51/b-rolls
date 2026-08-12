#!/usr/bin/env python3
"""Render a complete B-roll project through the pinned video-use workflow."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from lib import audio_stream, default_video_use_dir, duration_seconds, fps_fraction, repository_root, stream_hash, validate_plan


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", type=Path)
    parser.add_argument("--video-use-dir", type=Path)
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--skip-timeline", action="store_true")
    args = parser.parse_args()
    plan_path = args.plan.expanduser().resolve()
    plan, probe, ranges = validate_plan(plan_path)
    source = Path(plan["source"])
    output = Path(plan["output"])
    output.parent.mkdir(parents=True, exist_ok=True)
    edit = plan_path.parent
    slot_render = edit / "animations" / "slot_rapid_timeline" / "render.mp4"

    video_use = (args.video_use_dir or default_video_use_dir()).expanduser().resolve()
    if args.video_use_dir is None:
        subprocess.run([sys.executable, str(repository_root() / "scripts" / "bootstrap_video_use.py"), "--dest", str(video_use)], check=True)
    if not (video_use / "helpers" / "render.py").exists():
        raise SystemExit(f"video-use renderer not found: {video_use}")

    if not args.skip_timeline:
        subprocess.run([sys.executable, str(repository_root() / "scripts" / "render_timeline.py"), str(plan_path)], check=True)
    if not slot_render.exists():
        raise SystemExit(f"rapid timeline missing: {slot_render}")

    fps = float(fps_fraction(probe))
    timeline_duration = ranges[-1][1] / fps
    caption = dict(plan.get("caption") or {})
    if caption.get("preserve"):
        disabled = []
        for scene, (start_frame, end_frame) in zip(plan["scenes"], ranges, strict=True):
            if scene["kind"] == "source":
                disabled.append([start_frame / fps, end_frame / fps])
        caption["disable_intervals"] = disabled
        caption.pop("preserve", None)
    else:
        caption = None

    edl = {
        "version": 1,
        "sources": {"raw": str(source)},
        "ranges": [{
            "source": "raw",
            "start": 0.0,
            "end": duration_seconds(probe),
            "beat": "FULL_UNCHANGED_AUDIO_TIMELINE",
            "reason": "Preserve the complete source timing and voiceover; replace only the visual layer.",
        }],
        "grade": "scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos,crop=1080:1920,setsar=1",
        "overlays": [{
            "file": str(slot_render),
            "start_in_output": 0.0,
            "duration": timeline_duration,
            "x": 0,
            "y": 0,
        }],
        "total_duration_s": duration_seconds(probe),
    }
    if caption:
        edl["preserve_burned_captions"] = caption
    edl_path = edit / "edl_broll.json"
    edl_path.write_text(json.dumps(edl, indent=2) + "\n", encoding="utf-8")

    visual_master = edit / ("visual_master_preview.mp4" if args.preview else "visual_master.mp4")
    command = [
        sys.executable, str(video_use / "helpers" / "render.py"), str(edl_path),
        "-o", str(visual_master), "--no-subtitles", "--no-loudnorm",
    ]
    if args.preview:
        command.append("--preview")
    subprocess.run(command, check=True)

    if audio_stream(probe):
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "warning", "-y", "-i", str(visual_master), "-i", str(source),
            "-map", "0:v:0", "-map", "1:a:0", "-c", "copy", "-movflags", "+faststart", str(output),
        ], check=True)
    else:
        subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "warning", "-y", "-i", str(visual_master),
            "-map", "0:v:0", "-c", "copy", "-movflags", "+faststart", str(output),
        ], check=True)

    metadata = {
        "source": str(source),
        "plan": str(plan_path),
        "edl": str(edl_path),
        "video_use": str(video_use),
        "video_use_commit": "92c2b34e44c205cbc2acae7f6ca7c1c219d5dd66",
        "visual_master": str(visual_master),
        "output": str(output),
        "source_audio_hash": stream_hash(source, "0:a:0") if audio_stream(probe) else None,
        "output_audio_hash": stream_hash(output, "0:a:0") if audio_stream(probe) else None,
    }
    (edit / "render_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    if metadata["source_audio_hash"] != metadata["output_audio_hash"]:
        raise SystemExit("final audio stream does not match the source")
    print(output)


if __name__ == "__main__":
    main()
