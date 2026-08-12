#!/usr/bin/env python3
"""Check local requirements for the B-Rolls skill."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys


def main() -> None:
    tools = {}
    for name in ("ffmpeg", "ffprobe", "git"):
        path = shutil.which(name)
        tools[name] = {"ok": bool(path), "path": path}
    optional = {}
    for name in ("yt-dlp", "swift", "uv"):
        path = shutil.which(name)
        optional[name] = {"ok": bool(path), "path": path}
    modules = {name: bool(importlib.util.find_spec(name)) for name in ("numpy", "PIL")}
    report = {"required_tools": tools, "optional_tools": optional, "python_modules": modules}
    print(json.dumps(report, indent=2))
    missing = [name for name, data in tools.items() if not data["ok"]]
    missing += [name for name, ok in modules.items() if not ok]
    if missing:
        print("Missing required dependencies: " + ", ".join(missing), file=sys.stderr)
        print("Install Python modules with: python -m pip install -r requirements.txt", file=sys.stderr)
        raise SystemExit(1)
    subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)


if __name__ == "__main__":
    main()
