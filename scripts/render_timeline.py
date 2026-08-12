#!/usr/bin/env python3
"""Render a validated scene plan into a frame-exact, video-only rapid timeline."""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageColor, ImageDraw, ImageFont

from lib import fps_fraction, target_frame_count, validate_plan


def font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def ease(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return 1.0 - (1.0 - value) ** 3


def fit_text(draw: ImageDraw.ImageDraw, text: str, max_width: int, start_size: int, minimum: int = 42) -> ImageFont.FreeTypeFont:
    size = start_size
    while size > minimum:
        selected = font(size)
        if draw.textbbox((0, 0), text, font=selected)[2] <= max_width:
            return selected
        size -= 4
    return font(minimum)


def centered_text(draw: ImageDraw.ImageDraw, text: str, y: float, selected: ImageFont.FreeTypeFont, fill: str) -> None:
    bounds = draw.textbbox((0, 0), text, font=selected)
    draw.text(((1080 - (bounds[2] - bounds[0])) / 2, y), text, font=selected, fill=fill)


def icon(draw: ImageDraw.ImageDraw, name: str, cx: int, cy: int, size: int, accent: str, progress: float) -> None:
    p = ease(progress)
    radius = max(8, int(size * p / 2))
    dark = "#11151C"
    light = "#F6F8FA"
    if name in {"health", "science"}:
        arm = int(radius * 0.72)
        thickness = max(8, radius // 3)
        draw.rounded_rectangle((cx-thickness, cy-arm, cx+thickness, cy+arm), thickness, fill=accent)
        draw.rounded_rectangle((cx-arm, cy-thickness, cx+arm, cy+thickness), thickness, fill=accent)
        if name == "science":
            draw.arc((cx-radius, cy-radius, cx+radius, cy+radius), 20, 330, fill=light, width=max(5, radius//12))
    elif name == "warning":
        draw.polygon([(cx, cy-radius), (cx-radius, cy+radius), (cx+radius, cy+radius)], fill=accent)
        draw.polygon([(cx, cy-int(radius*.72)), (cx-int(radius*.68), cy+int(radius*.72)), (cx+int(radius*.68), cy+int(radius*.72))], fill=dark)
        draw.rounded_rectangle((cx-radius//10, cy-radius//3, cx+radius//10, cy+radius//3), radius//10, fill=accent)
        draw.ellipse((cx-radius//10, cy+radius//2, cx+radius//10, cy+int(radius*.7)), fill=accent)
    elif name == "book":
        for index, color in enumerate((accent, "#4C8DFF", "#42D77D", "#F1C94B")):
            y = cy + radius - index * int(radius * .52)
            draw.rounded_rectangle((cx-radius, y-int(radius*.42), cx+radius, y), radius//8, fill=color)
            draw.rectangle((cx-int(radius*.8), y-int(radius*.32), cx-int(radius*.65), y-int(radius*.08)), fill=light)
    elif name == "money":
        draw.ellipse((cx-radius, cy-radius, cx+radius, cy+radius), fill="#123624", outline=accent, width=max(6, radius//12))
        selected = fit_text(draw, "$", radius, radius)
        bounds = draw.textbbox((0, 0), "$", font=selected)
        draw.text((cx-(bounds[2]-bounds[0])/2, cy-(bounds[3]-bounds[1])/2-bounds[1]), "$", font=selected, fill=accent)
    elif name == "chart":
        draw.line((cx-radius, cy+radius, cx-radius, cy-radius), fill="#7D8794", width=max(5, radius//18))
        draw.line((cx-radius, cy+radius, cx+radius, cy+radius), fill="#7D8794", width=max(5, radius//18))
        points = [(cx-radius, cy), (cx-int(radius*.4), cy-int(radius*.35)), (cx, cy+int(radius*.12)), (cx+int(radius*.45), cy-int(radius*.52)), (cx+radius, cy-int(radius*.78))]
        visible = max(2, int(2 + p * (len(points)-2)))
        draw.line(points[:visible], fill=accent, width=max(8, radius//10), joint="curve")
    elif name == "question":
        draw.ellipse((cx-radius, cy-radius, cx+radius, cy+radius), outline=accent, width=max(8, radius//10))
        selected = fit_text(draw, "?", radius, int(radius*1.4))
        bounds = draw.textbbox((0, 0), "?", font=selected)
        draw.text((cx-(bounds[2]-bounds[0])/2, cy-(bounds[3]-bounds[1])/2-bounds[1]), "?", font=selected, fill=light)
    elif name == "globe":
        draw.ellipse((cx-radius, cy-radius, cx+radius, cy+radius), fill="#1D78C8", outline=accent, width=max(6, radius//14))
        draw.arc((cx-radius, cy-radius//2, cx+radius, cy+radius//2), 0, 360, fill=accent, width=max(5, radius//18))
        draw.arc((cx-radius//2, cy-radius, cx+radius//2, cy+radius), 90, 270, fill=accent, width=max(5, radius//18))
    elif name == "shield":
        points = [(cx, cy-radius), (cx-radius, cy-int(radius*.55)), (cx-int(radius*.8), cy+int(radius*.55)), (cx, cy+radius), (cx+int(radius*.8), cy+int(radius*.55)), (cx+radius, cy-int(radius*.55))]
        draw.polygon(points, fill="#17392E")
        draw.line(points + [points[0]], fill=accent, width=max(7, radius//12), joint="curve")
        draw.ellipse((cx-int(radius*.36), cy-int(radius*.35), cx-int(radius*.05), cy-int(radius*.04)), fill=light)
        draw.rounded_rectangle((cx-int(radius*.42), cy-int(radius*.02), cx, cy+int(radius*.55)), radius//8, fill=light)
        draw.ellipse((cx+int(radius*.08), cy-int(radius*.15), cx+int(radius*.34), cy+int(radius*.11)), fill=accent)
        draw.rounded_rectangle((cx+int(radius*.04), cy+int(radius*.12), cx+int(radius*.38), cy+int(radius*.55)), radius//8, fill=accent)
    elif name == "food":
        draw.ellipse((cx-radius, cy-radius, cx+radius, cy+radius), outline=light, width=max(7, radius//12))
        draw.ellipse((cx-int(radius*.65), cy-int(radius*.55), cx-int(radius*.05), cy+int(radius*.05)), fill=accent)
        draw.ellipse((cx+int(radius*.05), cy-int(radius*.2), cx+int(radius*.62), cy+int(radius*.38)), fill="#FF765F")
        draw.ellipse((cx-int(radius*.5), cy+int(radius*.15), cx+int(radius*.12), cy+int(radius*.7)), fill="#42D77D")
    elif name == "policy":
        draw.rounded_rectangle((cx-radius, cy-radius, cx+radius, cy+radius), radius//8, fill=light)
        for row in range(4):
            y = cy-int(radius*.55)+row*int(radius*.36)
            draw.rounded_rectangle((cx-int(radius*.65), y, cx+int(radius*.45), y+max(8, radius//10)), radius//20, fill="#707B89")
        draw.ellipse((cx+int(radius*.42), cy+int(radius*.34), cx+int(radius*.8), cy+int(radius*.72)), fill=accent)
    elif name == "people":
        for offset, color, scale in ((-int(radius*.38), light, 1.0), (int(radius*.38), accent, .82)):
            rr = int(radius*.28*scale)
            draw.ellipse((cx+offset-rr, cy-int(radius*.55)-rr, cx+offset+rr, cy-int(radius*.55)+rr), fill=color)
            draw.rounded_rectangle((cx+offset-int(radius*.36*scale), cy-int(radius*.2), cx+offset+int(radius*.36*scale), cy+int(radius*.75)), radius//5, fill=color)
    else:
        draw.ellipse((cx-radius, cy-radius, cx+radius, cy+radius), fill=accent)
        draw.ellipse((cx-int(radius*.48), cy-int(radius*.48), cx+int(radius*.48), cy+int(radius*.48)), fill=dark)


def card_frame(scene: dict, progress: float) -> Image.Image:
    accent = str(scene.get("accent", "#EFFF32"))
    accent_rgb = ImageColor.getrgb(accent)
    image = Image.new("RGB", (1080, 1920), "#0D1016")
    draw = ImageDraw.Draw(image)
    for radius, alpha in ((620, .08), (380, .11)):
        color = tuple(int(13 + channel * alpha) for channel in accent_rgb)
        draw.ellipse((540-radius, 850-radius, 540+radius, 850+radius), fill=color)
    motion = scene.get("motion", "reveal")
    p = ease(progress / .7)
    dx, dy = 0, 0
    if motion == "rise":
        dy = int((1-p) * 480)
    elif motion == "slide-left":
        dx = int((1-p) * 700)
    elif motion == "slide-right":
        dx = -int((1-p) * 700)
    elif motion == "pulse":
        p = min(1.0, p * (1.0 + .035 * math.sin(progress * math.pi * 4)))
    title = str(scene.get("title", "")).strip()
    subtitle = str(scene.get("subtitle", "")).strip()
    if title:
        selected = fit_text(draw, title, 900, 108)
        centered_text(draw, title, 230 + dy, selected, "#F7F8FA")
    if subtitle:
        selected = fit_text(draw, subtitle, 860, 54, 34)
        centered_text(draw, subtitle, 375 + dy, selected, "#AAB2BF")
    icon(draw, str(scene.get("icon", "generic")), 540+dx, 920+dy, 500, accent, p)
    return image


def run(command: list[str]) -> None:
    print("$ " + " ".join(str(part) for part in command))
    subprocess.run(command, check=True)


def render_live(scene: dict, source: Path, frames: int, fps: str, width: int, height: int, output: Path) -> None:
    kind = scene["kind"]
    media = source if kind == "source" else Path(scene["file"])
    offset = float(scene.get("offset", scene["start"] if kind == "source" else 0.0))
    x = float(scene.get("crop_x", .5))
    y = float(scene.get("crop_y", .5))
    if scene.get("effect", "normal") == "punch":
        scale_w, scale_h = int(width * 1.16), int(height * 1.16)
        visual = f"scale={scale_w}:{scale_h}:force_original_aspect_ratio=increase,crop={width}:{height}:(iw-ow)*{x:.4f}:(ih-oh)*{y:.4f}"
    else:
        visual = f"scale={width}:{height}:force_original_aspect_ratio=increase:flags=lanczos,crop={width}:{height}:(iw-ow)*{x:.4f}:(ih-oh)*{y:.4f}"
    vf = f"{visual},setsar=1,fps={fps},trim=end_frame={frames},setpts=PTS-STARTPTS,format=yuv420p"
    numerator = str(fps).split("/", 1)[0]
    keyint = max(1, round(float(fps_fraction({"streams": [{"codec_type": "video", "avg_frame_rate": fps}]}))))
    run([
        "ffmpeg", "-hide_banner", "-loglevel", "warning", "-y", "-ss", f"{offset:.6f}", "-i", str(media),
        "-map", "0:v:0", "-an", "-vf", vf, "-frames:v", str(frames), "-c:v", "libx264",
        "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-r", fps,
        "-video_track_timescale", numerator, "-g", str(keyint), "-keyint_min", str(keyint), "-sc_threshold", "0", str(output),
    ])


def render_card(scene: dict, frames: int, fps: str, output: Path, frame_dir: Path) -> None:
    if frame_dir.exists():
        shutil.rmtree(frame_dir)
    frame_dir.mkdir(parents=True)
    for index in range(frames):
        image = card_frame(scene, index / max(1, frames - 1))
        image.save(frame_dir / f"{index:05d}.png", compress_level=2)
    numerator = str(fps).split("/", 1)[0]
    run([
        "ffmpeg", "-hide_banner", "-loglevel", "warning", "-y", "-framerate", fps,
        "-i", str(frame_dir / "%05d.png"), "-an", "-frames:v", str(frames), "-c:v", "libx264",
        "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-r", fps,
        "-video_track_timescale", numerator, "-g", "30", "-keyint_min", "30", "-sc_threshold", "0", str(output),
    ])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    plan_path = args.plan.expanduser().resolve()
    plan, probe, ranges = validate_plan(plan_path)
    source = Path(plan["source"])
    edit = plan_path.parent
    slot = edit / "animations" / "slot_rapid_timeline"
    scene_dir = slot / "scenes"
    frames_dir = slot / "frames"
    scene_dir.mkdir(parents=True, exist_ok=True)
    frames_dir.mkdir(parents=True, exist_ok=True)
    fps = str(fps_fraction(probe))
    width, height = int(plan["width"]), int(plan["height"])
    manifest = []
    outputs = []

    for index, (scene, bounds) in enumerate(zip(plan["scenes"], ranges, strict=True)):
        frame_count = bounds[1] - bounds[0]
        output = scene_dir / f"scene_{index:04d}.mp4"
        if scene["kind"] == "card":
            render_card(scene, frame_count, fps, output, frames_dir / f"scene_{index:04d}")
        else:
            render_live(scene, source, frame_count, fps, width, height, output)
        outputs.append(output)
        manifest.append({
            "index": index,
            "start_frame": bounds[0],
            "end_frame": bounds[1],
            "frames": frame_count,
            "duration_seconds": frame_count / float(fps_fraction(probe)),
            "description": scene["description"],
            "kind": scene["kind"],
            "file": str(output),
        })

    concat = slot / "concat.txt"
    concat.write_text("".join(f"file '{path}'\n" for path in outputs), encoding="utf-8")
    final = (args.output or slot / "render.mp4").expanduser().resolve()
    run(["ffmpeg", "-hide_banner", "-loglevel", "warning", "-y", "-f", "concat", "-safe", "0", "-i", str(concat), "-map", "0:v:0", "-an", "-c", "copy", "-movflags", "+faststart", str(final)])
    result = {
        "source": str(source),
        "output": str(final),
        "fps": fps,
        "frame_count": target_frame_count(probe),
        "resolution": [width, height],
        "scene_count": len(manifest),
        "scenes": manifest,
    }
    (slot / "scene_manifest.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    check = subprocess.run([
        "ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,width,height,pix_fmt,r_frame_rate,sample_aspect_ratio,nb_read_frames,duration",
        "-show_entries", "format=duration", "-of", "json", str(final),
    ], check=True, text=True, capture_output=True)
    (slot / "ffprobe_proof.json").write_text(check.stdout, encoding="utf-8")
    print(final)


if __name__ == "__main__":
    main()
