
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
TARGET WORD COUNT RANGE: {minimum_words} to {maximum_words} words.

Return ONLY valid JSON with these fields:
title, watermark, voice, rate, claims_to_verify, scenes.

Each scene must contain:
narration, clear, show, visual_query, camera,
transition, source_notes.

DOCUMENTARY STRUCTURE:
- Create 10 to 24 scenes.
- Begin with a compelling historical opening.
- Build a chronological and understandable narrative.
- Use clear transitions between historical periods.
- End with a meaningful conclusion.
- Keep narration natural and suitable for spoken delivery.
- Match the target narration word count.
- Avoid repeating the same information in different scenes.

HISTORICAL ACCURACY:
- Do not invent quotations, dates, people, events or historical certainty.
- Distinguish archaeological evidence, established historical evidence,
  religious tradition and disputed reports.
- Use cautious language when evidence is uncertain.
- Do not present later religious traditions as contemporary eyewitness
  records unless that is supported by evidence.
- Do not portray pre-Islamic Arabia as a world without religion,
  culture, trade, poetry or political organisation.
- Explain the diversity of religious communities and beliefs where relevant.
- Never depict Prophet Muhammad ﷺ in any form.
- Do not generate a human representation, silhouette, shadow or imagined
  appearance of Prophet Muhammad ﷺ.
- Avoid fabricated historical quotations.
- Put important uncertain claims in claims_to_verify.

VISUAL QUERY REQUIREMENTS:
Every scene must have a distinct, specific visual_query.

The visual_query is used to search Wikimedia Commons for a real image.
Write it as a concise search phrase describing a subject that could
reasonably exist as a photograph, archaeological image, map, artefact,
manuscript image or historical illustration.

Do not use generic queries such as:
"ancient history", "old world", "historical background",
"beautiful desert", "ancient civilization".

Prefer queries with:
- Specific historical period or approximate century.
- Specific region, city or archaeological site.
- Specific object, building, inscription or landscape.
- Asset type, such as archaeological site, museum artefact,
  historical map, manuscript, inscription or architecture.

Examples of useful query styles:
- "Petra Jordan Nabataean rock cut architecture archaeological site"
- "Hegra Mada'in Salih Nabataean tombs Saudi Arabia"
- "ancient South Arabian Sabaean inscription stone"
- "late antique Byzantine mosaic architecture"
- "Sasanian Persian silver coin museum collection"
- "Red Sea ancient maritime trade route historical map"
- "pre Islamic Arabian frankincense trade archaeological artefacts"
- "late antique manuscript parchment museum collection"

For each scene:
- Choose a visual subject that directly supports the narration.
- Avoid repeating the same visual subject across scenes.
- Do not ask for an image of a person unless it is a clearly
  identified historical figure and the image is appropriate.
- Do not ask for images of Prophet Muhammad ﷺ.
- Do not imply an artistic reconstruction is an authentic photograph.
- If no reliable image is likely to exist, use a relevant map,
  landscape, artefact or architecture instead.
- Label artistic reconstructions in source_notes.

VISUAL ELEMENTS:
Use only existing art.py visuals:
figures, arches, scale, crescent, sun, book, mosque, kaaba,
calendar, question, hourglass, heart, lantern, globe, text.

The show field must be a list of valid visual specifications.
Examples:
["arches", "text:Arabia|before Islam"]
["globe", "text:Trade routes"]
["crescent", "book"]

CAMERA:
Use only:
slow_push, pan_left, pan_right.

TRANSITION:
Use only:
crossfade, cut.

OUTPUT:
- Include claims_to_verify as a list.
- Include source_notes for each scene.
- Use voice "en-US-GuyNeural" unless another voice is specified.
- Use rate "-3%".
- Return valid JSON only. No Markdown fences.
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
            "temperature": 0.45
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

    with urllib.request.urlopen(request, timeout=180) as response:
        result = json.load(response)

    candidates = result.get("candidates", [])

    if not candidates:
        raise RuntimeError(
            f"{model} returned no candidates."
        )

    parts = candidates[0].get(
        "content", {}
    ).get("parts", [])

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
        raise RuntimeError(
            f"{model} returned empty text."
        )

    return text


def generate_documentary(topic, output, minutes=3):

    minutes = float(minutes)

    if not 2 <= minutes <= 5:
        raise ValueError(
            "Documentary duration must be between 2 and 5 minutes."
        )

    key = os.getenv("GEMINI_API_KEY")

    if not key:
        raise RuntimeError(
            "GEMINI_API_KEY secret is missing."
        )

    target_words = round(minutes * 135)

    minimum_words = round(target_words * 0.80)
    maximum_words = round(target_words * 1.20)

    prompt = PROMPT.format(
        topic=topic,
        minutes=minutes,
        words=target_words,
        minimum_words=minimum_words,
        maximum_words=maximum_words
    )

    models = [
        os.getenv("GEMINI_MODEL"),
        "gemini-3.5-flash-lite",
        "gemini-3.8-flash"
    ]

    errors = []
    data = None

    for model in dict.fromkeys(
        item for item in models if item
    ):

        for attempt in range(2):

            try:
                response_text = call_model(
                    model,
                    prompt,
                    key
                )

                candidate = json.loads(response_text)

                # Enforce requested duration before accepting
                # the generated documentary.
                validate_script(
                    candidate,
                    target_minutes=minutes
                )

                data = candidate
                print(f"Documentary generated using {model}.")
                break

            except urllib.error.HTTPError as exc:

                detail = exc.read().decode(
                    "utf-8",
                    "replace"
                )[:500]

                errors.append(
                    f"{model}: HTTP {exc.code}: {detail}"
                )

                # A missing model should not be retried.
                if exc.code == 404:
                    break

                if attempt == 0:
                    time.sleep(4)

            except (
                urllib.error.URLError,
                TimeoutError,
                ValueError,
                RuntimeError
            ) as exc:

                errors.append(
                    f"{model}: {exc}"
                )

                if attempt == 0:
                    time.sleep(3)

        if data is not None:
            break

    if data is None:
        raise RuntimeError(
            "Gemini generation failed for all configured models:\n"
            + "\n".join(errors)
        )

    data.setdefault(
        "voice",
        os.getenv("VOICE", "en-US-GuyNeural")
    )

    data.setdefault("rate", "-3%")

    data.setdefault(
        "watermark",
        os.getenv("WATERMARK", "")
    )

    data.setdefault("claims_to_verify", [])

    # Validate once more after adding defaults.
    validate_script(
        data,
        target_minutes=minutes
    )

    path = Path(output)
    path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    print(
        f"Script saved: {path}\n"
        f"Words: {data['word_count']}\n"
        f"Estimated narration: {data['estimated_minutes']} minutes"
    )

    return data
