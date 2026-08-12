# Pinned video-use integration

- Upstream: `https://github.com/browser-use/video-use.git`
- Commit: `92c2b34e44c205cbc2acae7f6ca7c1c219d5dd66`
- Local patch: `patches/video-use-render.patch`

The patch contains only the behavior proven in the reference edits:

1. Preserve the source frame rate instead of forcing 24 fps.
2. Support explicit overlay `x` and `y` placement.
3. Extract yellow burned-in caption pixels from the normalized base, dilate the mask to retain their native dark outline, and composite them after all overlays.
4. Allow caption restoration to be disabled during source-return intervals to prevent duplicated captions.
5. Treat the base audio map as optional so silent source videos render correctly.

`scripts/bootstrap_video_use.py` clones the exact commit and applies this patch idempotently. Do not silently use another upstream revision; update the pin and retest the full pipeline intentionally.
