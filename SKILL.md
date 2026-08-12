---
name: b-rolls
description: Create a finished rapid B-roll edit from any raw video using the pinned browser-use/video-use workflow. Use when the user asks to add topic-matched B-roll, animated explainers, frequent full-screen scene changes, podcast/talking-head returns, preservation of existing burned-in captions, preservation of the original voiceover, vertical-video rendering, or cut-by-cut video self-evaluation for MP4/MOV footage.
---

# B-Rolls

Turn one raw video into a rendered, self-evaluated B-roll edit. Use the exact `browser-use/video-use` pipeline pinned in `references/video-use.md`; use the bundled scripts for deterministic frame, caption, audio, and verification behavior.

## Required workflow

1. Read `references/workflow.md` completely.
2. Run `scripts/doctor.py` and resolve missing required tools.
3. Run `scripts/bootstrap_video_use.py` to clone and patch the pinned `video-use` checkout.
4. Run `scripts/prepare_project.py /absolute/path/to/raw.mp4 --ocr`.
5. Read `<video-dir>/edit/takes_packed.md` and inspect one `video-use/helpers/timeline_view.py` view for the source.
6. Describe the proposed pacing, B-roll language, podcast-return frequency, caption behavior, and output format. Obtain confirmation before editing unless the user already specified those choices.
7. Research reusable B-roll that matches the spoken topic. Store downloads under `<video-dir>/edit/downloads/`, retain source URLs, and follow the sourcing rules in `references/workflow.md`.
8. Replace the source-only draft scenes in `<video-dir>/edit/scene_plan.json` with speech-matched scenes. Read `references/scene-plan.md` for the schema. Keep every scene at or below `max_scene_seconds`; use `source` scenes for podcast/talking-head returns.
9. Build original animated explainers when literal footage would be weak. If multiple custom animations are required and parallel agents are available, build independent animation slots concurrently as required by `video-use`.
10. Run `scripts/render_project.py <video-dir>/edit/scene_plan.json`.
11. Run `scripts/verify_output.py <video-dir>/edit/scene_plan.json --timeline-views` on the rendered file. Inspect every contact-sheet page and representative boundary views. Fix and rerender up to three times if any captions are missing, scenes repeat unintentionally, cuts flash, or topic matching is poor.
12. Append the strategy, sources, decisions, and verification evidence to `<video-dir>/edit/project.md`. Deliver only the verified final MP4.

## Non-negotiable output rules

- Preserve the complete original voiceover unless the user explicitly asks for dialogue edits.
- Remux the source audio stream without re-encoding. Verify its packet-stream SHA-256 matches the source.
- Preserve existing burned-in captions. Restore their original colored glyphs and outline above full-screen B-roll. Disable restoration only for source-return scenes that already contain those captions.
- Put every B-roll scene full-frame at 1080×1920 by default. Use aspect-fill crop with intentional horizontal and vertical pan values.
- Change the visual at least as often as requested. For rapid social edits, default to one semantic visual beat per second and deliberately return to the speaker every 4–6 seconds.
- Use hard cuts for rapid B-roll unless the content calls for a motivated transition.
- Keep generated explainers recognizable at playback speed. Prefer one strong icon or relationship over dense text.
- Apply subtitles or preserved captions last in the filter chain.
- Run self-evaluation on the rendered output, not only intermediate scene files.
- Keep every project artifact inside the raw video's sibling `edit/` directory.

## Bundled commands

```bash
python scripts/doctor.py
python scripts/bootstrap_video_use.py
python scripts/prepare_project.py /absolute/path/to/raw.mp4 --ocr
python scripts/render_timeline.py /absolute/path/to/edit/scene_plan.json
python scripts/render_project.py /absolute/path/to/edit/scene_plan.json
python scripts/verify_output.py /absolute/path/to/edit/scene_plan.json --timeline-views
```

Use absolute paths in plans and commands. Do not place footage or generated outputs inside this skill repository.
