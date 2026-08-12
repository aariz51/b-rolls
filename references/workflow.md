# End-to-end editorial workflow

## 1. Inventory and transcript

Run `prepare_project.py`. It records codec, dimensions, duration, frame rate, frame count, and audio streams. It also detects the likely yellow-caption band after normalizing the video to 1080×1920.

Prefer the upstream `video-use` word-timestamp transcript when `ELEVENLABS_API_KEY` is available:

```bash
python VIDEO_USE/helpers/transcribe.py /absolute/raw.mp4
python VIDEO_USE/helpers/pack_transcripts.py --edit-dir /absolute/video-dir/edit
```

For a captioned clip on macOS, `prepare_project.py --ocr` runs the bundled Vision OCR sampler and writes both `transcripts/<stem>_caption_ocr.tsv` and `takes_packed.md`. Treat OCR as a semantic map, not word-accurate cut timing. The rapid overlay does not alter the source audio timeline.

## 2. Source B-roll

Search for literal, reusable footage that closely matches each spoken beat. Prefer Pexels, Pixabay, Mixkit, Wikimedia Commons, official public-domain sources, or assets explicitly supplied by the user. Record the page URL in every `video` scene's `source_url` field.

Use independent source moments and different pan/crop values when one asset serves adjacent beats. Never present a repeated plate as a new scene without a materially different moment or crop. Avoid watermarks, logos, duplicated captions, and unlicensed social-media reposts.

Download into `<video-dir>/edit/downloads/`. Do not download into the skill repository.

## 3. Plan scenes

Map the full source duration without gaps. Default to one scene per second. Use shorter beats when the speech changes rapidly; never exceed `max_scene_seconds`.

Use this editorial rhythm as a starting point:

- 0s: source speaker for identity and hook continuity.
- Next 3–5s: literal B-roll or concise explainers following each phrase.
- Then 1s source return for expression and human continuity.
- Repeat, reserving a source return or clean explainer for the final phrase.

Select scene kinds:

- `source`: the original speaker at that timeline position. Existing captions are already present.
- `video`: downloaded or user-supplied B-roll. Set a source offset and intentional crop.
- `card`: a generated animated explainer with a short title, optional subtitle, accent, icon, and motion variant.

## 4. Render

`render_project.py` performs the exact sequence:

1. Validate complete, contiguous, frame-aligned coverage.
2. Render every scene independently to H.264/yuv420p at source FPS.
3. Losslessly concatenate the scene files into a video-only rapid timeline.
4. Generate a `video-use` EDL retaining the complete source range.
5. Render through the patched upstream `helpers/render.py`, with the rapid timeline as a full-screen overlay and caption restoration after it.
6. Remux the original source audio stream over the rendered visual master without re-encoding.

## 5. Verify

`verify_output.py` must prove:

- output video decodes cleanly;
- resolution is 1080×1920, square-pixel, H.264/yuv420p;
- output duration and frame count match the plan;
- source and final audio packet-stream hashes are identical;
- a real visual change exists near every scene boundary;
- contact sheets contain full-frame, correctly cropped, topic-matched visuals;
- restored captions are visible, single-layer, and unobstructed;
- `video-use` timeline views exist for every cut boundary when `--timeline-views` is used.

If a technical check or visual inspection fails, fix the plan or render code and rerun. Stop after three failed review passes and report the remaining issue rather than silently shipping it.
