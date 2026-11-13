# Reel Maker — cinematic documentary reels

A Python and FFmpeg pipeline for creating narrated vertical documentaries
for Instagram Reels, YouTube Shorts and similar platforms.

The project supports AI-generated scripts, scene-specific cinematic artwork,
animated vector overlays, narration, captions, camera movement and transitions.

## Visual styles

### Cinematic (recommended)

Uses Gemini to generate a unique hand-painted cinematic illustration for
each scene.

Features:

- Scene-specific artwork generated from the script's `visual_brief`.
- Portrait 9:16 compositions.
- Foreground, middle-ground and background depth.
- Historical environments, architecture, objects and landscapes.
- Gentle camera movement, including slow push and directional pans.
- Optional animated vector overlays for maps, timelines, routes,
  diagrams and comparisons.
- Cached generated artwork to avoid regenerating images unnecessarily.

Cinematic mode requires `GEMINI_API_KEY`.

The default image model is `gemini-3.1-flash-image`.
You can override it with the `GEMINI_IMAGE_MODEL` environment variable.

### Illustrated

Uses the hand-drawn illustration library in `art.py`.

This mode is useful when you want a consistent illustrated look without
calling an image-generation model.

### Editorial

Uses the original parchment-style visual system, typography and
hand-drawn illustrations.

### Photographic

Downloads relevant photographs from Wikimedia Commons and applies
camera movement.

Review image relevance, licensing and attribution before publishing.

## Requirements

- Python 3.10 or newer
- FFmpeg and ffprobe
- Pillow
- NumPy
- Edge TTS network access, or espeak-ng as a fallback

Install Python dependencies:

```bash
python -m pip install -r requirements.txt
python -m pip install pytest
