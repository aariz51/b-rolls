#!/usr/bin/env python3
"""Shared helpers for the B-Rolls skill."""

from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any


VIDEO_USE_REPOSITORY = "https://github.com/browser-use/video-use.git"
VIDEO_USE_COMMIT = "92c2b34e44c205cbc2acae7f6ca7c1c219d5dd66"


def run(command: list[str], *, capture: bool = False, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    print("$ " + " ".join(str(part) for part in command), file=sys.stderr)
    return subprocess.run(
        command,
        cwd=cwd,
        check=True,
        text=True,
        capture_output=capture,
    )


def repository_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_video_use_dir() -> Path:
    cache_base = Path(os.environ.get("B_ROLLS_CACHE_DIR", Path.home() / ".cache" / "b-rolls"))
    return cache_base / f"video-use-{VIDEO_USE_COMMIT[:12]}"


def ffprobe(path: Path, *, count_frames: bool = True) -> dict[str, Any]:
    command = ["ffprobe", "-v", "error"]
    if count_frames:
        command += ["-count_frames"]
    command += ["-show_streams", "-show_format", "-of", "json", str(path)]
    result = run(command, capture=True)
    return json.loads(result.stdout)


def video_stream(probe: dict[str, Any]) -> dict[str, Any]:
    for stream in probe.get("streams", []):
        if stream.get("codec_type") == "video":
            return stream
    raise ValueError("input has no video stream")


def audio_stream(probe: dict[str, Any]) -> dict[str, Any] | None:
    for stream in probe.get("streams", []):
        if stream.get("codec_type") == "audio":
            return stream
    return None


def fps_fraction(probe: dict[str, Any]) -> Fraction:
    stream = video_stream(probe)
    raw = stream.get("avg_frame_rate") or stream.get("r_frame_rate") or "30/1"
    value = Fraction(raw)
    if value <= 0:
        return Fraction(30, 1)
    return value


def duration_seconds(probe: dict[str, Any]) -> float:
    stream = video_stream(probe)
    value = stream.get("duration") or probe.get("format", {}).get("duration")
    if value is None:
        raise ValueError("could not determine video duration")
    return float(value)


def target_frame_count(probe: dict[str, Any]) -> int:
    stream = video_stream(probe)
    for key in ("nb_read_frames", "nb_frames"):
        value = stream.get(key)
        if value and value != "N/A":
            return int(value)
    return round(duration_seconds(probe) * float(fps_fraction(probe)))


def load_plan(plan_path: Path) -> dict[str, Any]:
    return json.loads(plan_path.read_text(encoding="utf-8"))


def frame_ranges(plan: dict[str, Any], probe: dict[str, Any]) -> list[tuple[int, int]]:
    fps = float(fps_fraction(probe))
    total = target_frame_count(probe)
    ranges: list[tuple[int, int]] = []
    previous = 0
    scenes = plan["scenes"]
    for index, scene in enumerate(scenes):
        end = total if index == len(scenes) - 1 else round(float(scene["end"]) * fps)
        ranges.append((previous, end))
        previous = end
    return ranges


def validate_plan(plan_path: Path) -> tuple[dict[str, Any], dict[str, Any], list[tuple[int, int]]]:
    plan = load_plan(plan_path)
    if plan.get("version") != 1:
        raise ValueError("scene plan version must be 1")
    source = Path(plan.get("source", ""))
    output = Path(plan.get("output", ""))
    if not source.is_absolute() or not source.exists():
        raise ValueError("source must be an existing absolute path")
    if not output.is_absolute():
        raise ValueError("output must be an absolute path")
    if int(plan.get("width", 0)) != 1080 or int(plan.get("height", 0)) != 1920:
        raise ValueError("the proven pipeline requires a 1080x1920 output")
    scenes = plan.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise ValueError("scenes must be a non-empty list")

    probe = ffprobe(source)
    fps = float(fps_fraction(probe))
    tolerance = 1.1 / fps
    duration = duration_seconds(probe)
    max_scene = float(plan.get("max_scene_seconds", 1.0))
    previous_end = 0.0
    allowed_icons = {"generic", "food", "health", "warning", "science", "book", "money", "chart", "question", "globe", "shield", "policy", "people"}
    allowed_motion = {"reveal", "rise", "pulse", "slide-left", "slide-right"}
    for index, scene in enumerate(scenes):
        start = float(scene.get("start", -1))
        end = float(scene.get("end", -1))
        if abs(start - previous_end) > tolerance:
            raise ValueError(f"scene {index} is not contiguous: {start} != {previous_end}")
        if end <= start:
            raise ValueError(f"scene {index} has a non-positive duration")
        if end - start > max_scene + tolerance:
            raise ValueError(f"scene {index} exceeds max_scene_seconds")
        if not str(scene.get("description", "")).strip():
            raise ValueError(f"scene {index} needs a description")
        kind = scene.get("kind")
        if kind not in {"source", "video", "card"}:
            raise ValueError(f"scene {index} has unsupported kind {kind!r}")
        if kind == "video":
            asset = Path(scene.get("file", ""))
            if not asset.is_absolute() or not asset.exists():
                raise ValueError(f"scene {index} video file must be an existing absolute path")
        if kind in {"video", "source"}:
            for key in ("crop_x", "crop_y"):
                value = float(scene.get(key, 0.5))
                if not 0.0 <= value <= 1.0:
                    raise ValueError(f"scene {index} {key} must be between 0 and 1")
            if scene.get("effect", "normal") not in {"normal", "punch"}:
                raise ValueError(f"scene {index} effect must be normal or punch")
        if kind == "card":
            if scene.get("icon", "generic") not in allowed_icons:
                raise ValueError(f"scene {index} has an unsupported card icon")
            if scene.get("motion", "reveal") not in allowed_motion:
                raise ValueError(f"scene {index} has an unsupported card motion")
        previous_end = end

    if abs(previous_end - duration) > tolerance:
        raise ValueError(f"scene coverage ends at {previous_end:.6f}s, source ends at {duration:.6f}s")
    ranges = frame_ranges(plan, probe)
    for index, (start_frame, end_frame) in enumerate(ranges):
        if end_frame <= start_frame:
            raise ValueError(f"scene {index} rounds to zero frames")
    if ranges[-1][1] != target_frame_count(probe):
        raise ValueError("frame coverage does not match source frame count")
    return plan, probe, ranges


def stream_hash(path: Path, selector: str) -> str | None:
    command = [
        "ffmpeg", "-v", "error", "-i", str(path), "-map", selector,
        "-c", "copy", "-f", "streamhash", "-hash", "sha256", "-",
    ]
    result = subprocess.run(command, text=True, capture_output=True)
    if result.returncode != 0:
        return None
    line = result.stdout.strip().splitlines()
    return line[-1].split("=", 1)[-1] if line else None


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ceil_div_duration(duration: float, maximum: float) -> int:
    return max(1, math.ceil(duration / maximum - 1e-9))
