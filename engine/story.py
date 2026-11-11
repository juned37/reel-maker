import json
import os
import time
import urllib.error
import urllib.request

from pathlib import Path

from .quality import validate_script


PROMPT = """Create a historically responsible cinematic documentary.

TOPIC: {topic}

TARGET DURATION: {minutes} minutes.
TARGET SPOKEN WORDS: approximately {words}.

Return ONLY valid JSON with:
title, watermark, voice, rate, claims_to_verify, scenes.

Each scene must contain:
narration, clear, show, visual_query, camera, transition, source_notes.

Requirements:
- Use 10 to 24 scenes.
- Match the total narration to the target word count.
- Every scene needs a distinct visual_query.
- Use only existing art.py visuals:
  figures, arches, scale, crescent, sun, book, mosque, kaaba,
  calendar, question, hourglass, heart, lantern, globe, text.
- Camera: slow_push, pan_left or pan_right.
- Transition: crossfade or cut.
- Prefer maps, architecture, artefacts, manuscripts and landscapes.
- Do not invent quotations, dates or historical certainty.
- Distinguish established evidence from tradition or disputed reports.
- Never depict Prophet Muhammad ﷺ.
- Do not portray pre-Islamic Arabia as a world without religions.
- Label artistic reconstructions.
"""


def call_model(model, prompt, key):

    url = (
        "https://generativelanguage.googleapis.com/"
        f"v1beta/models/{model}:generateContent"
    )

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

    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": key
        },
        method="POST"
    )

    with urllib.request.urlopen(request, timeout=120) as response:
        result = json.load(response)

    candidates = result.get("candidates", [])

    if not candidates:
        raise RuntimeError(f"{model} returned no candidates")

    parts = candidates[0].get("content", {}).get("parts", [])

    text = "".join(
        part.get("text", "")
        for part in parts
    ).strip()

    if text.startswith("```"):
        text = (
            text.removeprefix("```json")
            .removeprefix("```")
            .removesuffix("```")
            .strip()
        )

    if not text:
        raise RuntimeError(f"{model} returned no text")

    return text


def generate_documentary(topic, output, minutes=3):

    minutes = max(2, min(5, float(minutes)))

    key = os.getenv("GEMINI_API_KEY")

    if not key:
        raise RuntimeError("GEMINI_API_KEY secret is missing")

    prompt = PROMPT.format(
        topic=topic,
        minutes=minutes,
        words=round(minutes * 135)
    )

    models = [
        os.getenv("GEMINI_MODEL"),
        "gemini-3.5-flash-lite",
        "gemini-3.8-flash"
    ]

    errors = []
    data = None

    for model in dict.fromkeys(m for m in models if m):

        for attempt in range(2):

            try:
                data = json.loads(
                    call_model(model, prompt, key)
                )
                break

            except urllib.error.HTTPError as exc:

                detail = exc.read().decode(
                    "utf-8",
                    "replace"
                )[:400]

                errors.append(
                    f"{model}: HTTP {exc.code}: {detail}"
                )

                if exc.code == 404 or attempt:
                    break

                time.sleep(5)

            except (
                urllib.error.URLError,
                TimeoutError,
                ValueError,
                RuntimeError
            ) as exc:

                errors.append(f"{model}: {exc}")

                if attempt:
                    break

                time.sleep(2)

        if data is not None:
            break

    if data is None:
        raise RuntimeError(
            "Gemini models failed:\n" + "\n".join(errors)
        )

    data.setdefault("voice", os.getenv("VOICE", "en-US-GuyNeural"))
    data.setdefault("rate", "-3%")
    data.setdefault("watermark", os.getenv("WATERMARK", ""))
    data.setdefault("claims_to_verify", [])

    validate_script(data)

    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    return data
