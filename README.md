# Reel Maker — illustrated documentary reels

A Python/FFmpeg pipeline for 9:16 narrated documentaries. The default **editorial** style is designed around the supplied visual references: warm parchment, muted gold and dark-brown serif typography, thin hand-drawn illustrations, restrained captions, and gentle crossfades.

## Visual styles

- `editorial` (default): uses the original `art.py` illustration library and keeps a consistent parchment look. Downloaded photographs are deliberately ignored in this mode.
- `photographic`: downloads Wikimedia Commons images, applies gentle camera motion, and displays full-screen photographs. Review image relevance and license credits before publishing.

## Run locally

Requirements: Python 3.10+, FFmpeg/ffprobe, and either Edge TTS network access or `espeak-ng` as a fallback.

```bash
python -m pip install -r requirements.txt pytest
python -m pytest -q
python reel.py render scripts/world-before-islam.json out/documentary.mp4 --tts edge --style editorial
```

To use Wikimedia photographs instead:

```bash
python -m engine.prepare_assets scripts/world-before-islam.json
python reel.py render scripts/world-before-islam.json out/documentary.mp4 --tts edge --style photographic
```

## Generate a new documentary with Gemini

Set `GEMINI_API_KEY`, then:

```bash
python reel.py generate "Your documentary topic" out/generated.json --minutes 3
python reel.py render out/generated.json out/generated.mp4 --tts edge --style editorial
```

The model identifier can be set with `GEMINI_MODEL` to a model currently enabled for your Google AI Studio API key. Generated historical claims and all visual assets should be reviewed before publication.

## GitHub Actions

Open **Actions → Make vertical documentary video → Run workflow**.

- Leave `topic` blank to use the selected JSON script (no Gemini API key required).
- Set `topic` to generate a new script (requires the `GEMINI_API_KEY` repository secret).
- Keep `visual_style` as `editorial` to match the supplied references. Choose `photographic` only when you want Wikimedia image assets.

The workflow uploads the MP4, script, and render notes as the `vertical-documentary-video` artifact.

## Project layout

- `art.py` — parchment canvas, typography, and hand-drawn illustrations.
- `reel.py` — narration timing, captions, scene composition, transitions, and FFmpeg rendering.
- `engine/audio.py` — Edge TTS with espeak-ng fallback.
- `engine/story.py` — Gemini script generation and historical visual guidance.
- `engine/quality.py` — script structure and duration checks.
- `engine/commons.py`, `engine/prepare_assets.py` — optional Wikimedia asset retrieval and credits.
- `engine/motion.py` — optional photographic camera movement.
- `engine/transitions.py` — cut and crossfade helpers.
- `scripts/` — documentary JSON files.

## Notes

The renderer estimates narration duration from the generated audio at render time; word-count checks are only an estimate. A successful local preview does not guarantee that GitHub Actions can reach Edge TTS or Ubuntu package mirrors. The workflow validates the final MP4 streams and uploads the artifact only after those checks pass.
