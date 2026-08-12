# Scene plan schema

`scene_plan.json` is the editable contract between semantic editing and deterministic rendering.

```json
{
  "version": 1,
  "source": "/absolute/path/raw.mp4",
  "output": "/absolute/path/edit/final_broll.mp4",
  "width": 1080,
  "height": 1920,
  "max_scene_seconds": 1.0,
  "caption": {
    "preserve": true,
    "color": "0xFFFF00",
    "y": 1090,
    "height": 260,
    "similarity": 0.22,
    "blend": 0.08,
    "outline_dilation": 4
  },
  "scenes": [
    {
      "start": 0.0,
      "end": 1.0,
      "kind": "source",
      "description": "speaker hook",
      "effect": "normal"
    },
    {
      "start": 1.0,
      "end": 2.0,
      "kind": "video",
      "file": "/absolute/path/edit/downloads/food.mp4",
      "offset": 3.2,
      "crop_x": 0.35,
      "crop_y": 0.5,
      "description": "grocery aisle",
      "source_url": "https://example.com/source-page"
    },
    {
      "start": 2.0,
      "end": 3.0,
      "kind": "card",
      "title": "WHY?",
      "subtitle": "",
      "icon": "question",
      "accent": "#EFFF32",
      "motion": "reveal",
      "description": "question explainer"
    }
  ]
}
```

## Invariants

- Use absolute paths for `source`, `output`, and every `video.file`.
- Start the first scene at `0.0` and end the last scene at the source duration.
- Keep scenes contiguous and ordered. No gaps or overlaps.
- Keep each duration at or below `max_scene_seconds`, allowing one source-frame period of rounding tolerance.
- Give every scene a useful `description`.
- Use `offset` only for `video`; `source` automatically uses its timeline start unless explicitly overridden.
- Set `effect` to `normal` or `punch` for live video.
- Keep `crop_x` and `crop_y` between `0.0` and `1.0`.
- Supported card icons: `generic`, `food`, `health`, `warning`, `science`, `book`, `money`, `chart`, `question`, `globe`, `shield`, `policy`, `people`.
- Supported card motions: `reveal`, `rise`, `pulse`, `slide-left`, `slide-right`.
