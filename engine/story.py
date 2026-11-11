from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path


PROMPT = """Create a historically responsible cinematic documentary.

TOPIC: {topic}

TARGET LENGTH: {minutes} minutes.
TARGET WORDS: approximately {words} spoken words.

Return ONLY valid JSON with:

title
watermark
voice
claims_to_verify
scenes

Each scene must contain:

narration
clear
show
visual_query
camera
transition
source_notes

Rules:

- Use 10 to 22 scenes.
- Match total narration to target length.
- Every scene needs a unique historical visual_query.
- Use existing art.py visual names in show.
- Camera options: slow_push, pan_left, pan_right.
- Transition: crossfade.
- Do not invent quotations, dates or historical certainty.
- Distinguish established historical evidence from tradition.
- Never depict Prophet Muhammad ﷺ.
- Prefer artifacts, maps, architecture and landscapes.
- Avoid anachronistic visuals.
- Clearly label artistic reconstructions.
"""


def _generate(prompt, key):

    models = []

    for model in (
        os.getenv("GEMINI_MODEL"),
        "gemini-2.5-flash-lite",
        "gemini-2.5-flash"
    ):

        if model and model not in models:
            models.append(model)

    last = "No response"

    for model in models:

        body = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt}
                    ]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.55
            }
        }

        req = urllib.request.Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            data=json.dumps(body).encode(),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": key
            },
            method="POST"
        )

        try:

            with urllib.request.urlopen(req, timeout=120) as response:
                data = json.load(response)

            parts = (
                data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [])
            )

            text = "".join(
                part.get("text", "")
                for part in parts
            ).strip()

            if text:
                return re.sub(
                    r"^```(?:json)?\s*|\s*```$",
                    "",
                    text
                ).strip()

            last = f"{model} returned no text"

        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
            TimeoutError,
            ValueError
        ) as exc:

            last = f"{model}: {exc}"

    raise RuntimeError(
        f"Gemini generation failed: {last}"
    )


def generate_documentary(
    topic,
    output,
    minutes=3.0,
    api_key=None
):

    minutes = min(5.0, max(2.0, float(minutes)))
    words = round(minutes * 135)

    key = api_key or os.getenv("GEMINI_API_KEY")

    if not key:
        raise RuntimeError(
            "Set GEMINI_API_KEY before generation."
        )

    prompt = PROMPT.format(
        topic=topic,
        minutes=minutes,
        words=words
    )

    data = json.loads(
        _generate(prompt, key)
    )

    scenes = data.get("scenes")

    if not isinstance(scenes, list) or not scenes:
        raise ValueError(
            "Generated script has no scenes."
        )

    data["scenes"] = scenes[:22]

    for i, scene in enumerate(data["scenes"], 1):

        if not str(scene.get("narration", "")).strip():
            raise ValueError(
                f"Scene {i} narration is empty."
            )

        scene.setdefault("show", [])
        scene.setdefault("clear", i == 1)
        scene.setdefault("camera", "slow_push")
        scene.setdefault("transition", "crossfade")

    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    return data
