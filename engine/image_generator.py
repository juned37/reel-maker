
"""Generate and cache cinematic scene artwork with Gemini."""

import base64
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image


DEFAULT_MODEL = "gemini-3.1-flash-image"
IMAGE_SIZE = "1K"
ASPECT_RATIO = "9:16"


STYLE_GUIDE = """
Create a cinematic, hand-painted historical documentary illustration.

VISUAL DIRECTION:
- Detailed cinematic composition with foreground, middle ground and background.
- Historically appropriate architecture, landscapes, materials and objects.
- Painterly brushwork, subtle canvas texture and atmospheric depth.
- Dramatic but believable documentary lighting.
- Restrained earth tones, warm gold, muted blue and deep shadows.
- Professional documentary art direction.
- Portrait composition for a 9:16 vertical video.

STRICT RULES:
- Depict the actual scene, not generic decorative symbols.
- Do not create a collage, infographic, poster or storyboard.
- Do not include text, letters, captions, subtitles, logos or watermarks.
- Do not add modern objects to historical scenes.
- Do not invent identifiable portraits of historical people.
- Never depict Prophet Muhammad ﷺ in any form: no face, body,
  silhouette, shadow or symbolic human representation.
- Do not depict any named prophet.
- For sacred figures, show only the surrounding setting, architecture,
  landscape or historically appropriate objects.
- Do not present imagined visual details as proven historical evidence.
- Keep important subjects away from extreme image edges.
"""


def _scene_prompt(scene, index, total, documentary_title):
    title = str(scene.get("onscreen_title", "")).strip()
    narration = str(scene.get("narration", "")).strip()
    brief = str(scene.get("visual_brief", "")).strip()
    source_notes = str(scene.get("source_notes", "")).strip()

    subject = brief or (
        f"Scene heading: {title}. Narration: {narration}"
    )

    return f"""
{STYLE_GUIDE}

DOCUMENTARY:
{documentary_title}

SCENE:
{index} of {total}

SCENE HEADING:
{title}

SCENE VISUAL BRIEF:
{subject}

NARRATION CONTEXT:
{narration}

HISTORICAL OR EVIDENCE NOTES:
{source_notes}

COMPOSITION:
Create one coherent cinematic scene communicating the specific
subject of this narration. Use appropriate period, geography,
architecture, materials and environmental details.

Leave breathing room near the upper and lower portions for video
titles and subtitles. Do not draw any text.

Output one finished portrait illustration.
"""


def _cache_path(cache_dir, prompt):
    digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:24]
    return cache_dir / f"scene-{digest}.png"


def _request_image(prompt, api_key, model, timeout=240):
    url = (
        "https://generativelanguage.googleapis.com/"
        f"v1beta/models/{model}:generateContent"
    )

    payload = {
        "contents": [
            {"parts": [{"text": prompt}]}
        ],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
            "responseFormat": {
                "image": {
                    "aspectRatio": ASPECT_RATIO,
                    "imageSize": IMAGE_SIZE,
                }
            },
        },
    }

    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
            "User-Agent": "reel-maker/1.0",
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:
        result = json.load(response)

    candidates = result.get("candidates", [])

    if not candidates:
        raise RuntimeError("Gemini returned no image candidates.")

    parts = candidates[0].get("content", {}).get("parts", [])

    for part in parts:
        inline = part.get("inlineData") or part.get("inline_data")

        if inline and inline.get("data"):
            return base64.b64decode(inline["data"])

    raise RuntimeError("Gemini response did not contain image data.")


def _save_valid_image(image_bytes, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.stem + ".tmp.png")

    try:
        temporary.write_bytes(image_bytes)

        with Image.open(temporary) as image:
            image.verify()

        with Image.open(temporary) as image:
            image.convert("RGB").save(destination, format="PNG")

    finally:
        temporary.unlink(missing_ok=True)


def generate_scene_images(script_data, script_path, force=False):
    """Generate one cached image for every scene.

    Returns image paths or None entries. Existing images are preserved
    unless force=True.
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    scenes = script_data.get("scenes", [])

    if not api_key:
        print(
            "INFO: GEMINI_API_KEY is not configured. "
            "Using vector/art.py fallback visuals."
        )
        return [None] * len(scenes)

    model = (
        os.getenv("GEMINI_IMAGE_MODEL", "").strip()
        or DEFAULT_MODEL
    )

    script_path = Path(script_path).resolve()
    cache_dir = script_path.parent / "generated_visuals"
    cache_dir.mkdir(parents=True, exist_ok=True)

    title = script_data.get("title", [])
    if isinstance(title, list):
        documentary_title = " ".join(str(item) for item in title)
    else:
        documentary_title = str(title)

    generated = []

    for index, scene in enumerate(scenes, 1):
        existing = scene.get("image")

        if existing and not force:
            existing_path = Path(existing)
            if not existing_path.is_absolute():
                existing_path = script_path.parent / existing_path

            if existing_path.is_file():
                generated.append(str(existing_path))
                print(f"Scene {index}: using existing image.")
                continue

        prompt = _scene_prompt(
            scene,
            index,
            len(scenes),
            documentary_title,
        )

        destination = _cache_path(cache_dir, prompt)

        if destination.is_file() and not force:
            scene["image"] = str(destination)
            generated.append(str(destination))
            print(f"Scene {index}: using cached artwork.")
            continue

        print(f"Scene {index}/{len(scenes)}: generating artwork...")

        last_error = None

        for attempt in range(3):
            try:
                image_bytes = _request_image(prompt, api_key, model)
                _save_valid_image(image_bytes, destination)
                last_error = None
                break

            except (
                urllib.error.HTTPError,
                urllib.error.URLError,
                TimeoutError,
                OSError,
                ValueError,
                RuntimeError,
            ) as exc:
                last_error = exc
                print(
                    f"Scene {index}: attempt {attempt + 1}/3 failed: {exc}"
                )

                if attempt < 2:
                    time.sleep(3 * (attempt + 1))

        if last_error is not None:
            print(
                f"WARNING: Scene {index} image generation failed. "
                "Using fallback visuals."
            )
            generated.append(None)
            continue

        scene["image"] = str(destination)
        generated.append(str(destination))
        print(f"Scene {index}: saved {destination}")

    return generated
