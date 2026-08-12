#!/usr/bin/env python3
"""Clone the pinned video-use revision and apply the proven render patch."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from lib import VIDEO_USE_COMMIT, VIDEO_USE_REPOSITORY, default_video_use_dir, repository_root, run


def output(command: list[str], cwd: Path | None = None) -> str:
    return subprocess.run(command, cwd=cwd, check=True, text=True, capture_output=True).stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dest", type=Path, default=default_video_use_dir())
    parser.add_argument("--uv-sync", action="store_true")
    args = parser.parse_args()
    destination = args.dest.expanduser().resolve()
    patch = repository_root() / "patches" / "video-use-render.patch"
    destination.parent.mkdir(parents=True, exist_ok=True)

    if not (destination / ".git").exists():
        run(["git", "clone", "--no-checkout", VIDEO_USE_REPOSITORY, str(destination)])
        run(["git", "checkout", VIDEO_USE_COMMIT], cwd=destination)
    current = output(["git", "rev-parse", "HEAD"], destination)
    if current != VIDEO_USE_COMMIT:
        raise SystemExit(f"existing checkout is at {current}; expected {VIDEO_USE_COMMIT}: {destination}")

    check = subprocess.run(
        ["git", "apply", "--check", str(patch)], cwd=destination,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    if check.returncode == 0:
        run(["git", "apply", str(patch)], cwd=destination)
    else:
        reverse = subprocess.run(
            ["git", "apply", "--reverse", "--check", str(patch)], cwd=destination,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        if reverse.returncode != 0:
            raise SystemExit("video-use render patch is neither applicable nor already applied")

    if args.uv_sync:
        run(["uv", "sync"], cwd=destination)
    print(destination)


if __name__ == "__main__":
    main()
