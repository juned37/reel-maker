
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
onscreen_title, narration, clear, show, visual_query, camera,
transition, source_notes.

ON-SCREEN TITLES:
- Every scene MUST include a concise, non-empty onscreen_title.
- Keep it between 2 and 6 words where practical.
- Use a clear editorial chapter heading, not a full sentence.
- Do not include quotation marks or narration text in the heading.

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
  records unless supported by evidence.
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

Examples:
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


def extract_json(text):
    """Extract a JSON object from a model response."""
    text = (text or "").strip()

    if text.startswith("```"):
        lines = text.splitlines()

        if lines and lines[0].startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        text = "\n".join(lines).strip()

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or end <= start:
        raise ValueError("Model response does not contain a JSON object.")

    return json.loads(text[start:end + 1])


def read_http_error(exc):
    try:
        detail = exc.read().decode("utf-8", "replace")
    except Exception:
        detail = str(exc)

    return detail[:1000]


def call_groq(model, prompt, key):
    url = "https://api.groq.com/openai/v1/chat/completions"

    body = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You write historically responsible documentaries. "
                    "Follow the user's instructions and return valid JSON only."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "temperature": 0.45,
        "max_tokens": 6000,
        "response_format": {"type": "json_object"},
    }

    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=180) as response:
        result = json.load(response)

    choices = result.get("choices", [])

    if not choices:
        raise RuntimeError("Groq returned no choices.")

    message = choices[0].get("message", {})
    content = message.get("content")

    if not content:
        raise RuntimeError("Groq returned empty content.")

    return content.strip()


def call_gemini(model, prompt, key):
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
            "temperature": 0.45,
            "maxOutputTokens": 6000,
        },
    }

    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": key,
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=180) as response:
        result = json.load(response)

    candidates = result.get("candidates", [])

    if not candidates:
        raise RuntimeError("Gemini returned no candidates.")

    candidate = candidates[0]

    if candidate.get("finishReason") == "MAX_TOKENS":
        raise RuntimeError("Gemini response was cut off by the output token limit.")

    parts = candidate.get("content", {}).get("parts", [])

    content = "".join(
        part.get("text", "")
        for part in parts
    ).strip()

    if not content:
        raise RuntimeError("Gemini returned empty content.")

    return content


def provider_configuration():
    """Return configured providers in fallback order."""
    providers = []

    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()

    if groq_key:
        providers.append({
            "name": "Groq",
            "model": (
                os.getenv("GROQ_MODEL", "").strip()
                or "openai/gpt-oss-120b"
            ),
            "key": groq_key,
            "call": call_groq,
        })

    if gemini_key:
        providers.append({
            "name": "Gemini",
            "model": (
                os.getenv("GEMINI_MODEL", "").strip()
                or "gemini-2.5-flash"
            ),
            "key": gemini_key,
            "call": call_gemini,
        })

    return providers


def generate_with_provider(provider, prompt, minutes):
    """Try a provider twice, then let the next provider take over."""
    errors = []

    for attempt in range(2):
        try:
            response_text = provider["call"](
                provider["model"],
                prompt,
                provider["key"],
            )

            candidate = extract_json(response_text)

            validate_script(
                candidate,
                target_minutes=minutes,
            )

            return candidate

        except urllib.error.HTTPError as exc:
            detail = read_http_error(exc)
            message = (
                f"{provider['name']} ({provider['model']}): "
                f"HTTP {exc.code}: {detail}"
            )
            errors.append(message)

            # Retry only temporary server/rate-limit errors.
            if exc.code not in (408, 429, 500, 502, 503, 504):
                break

            if attempt == 0:
                retry_after = exc.headers.get("Retry-After", "5")

                try:
                    delay = min(max(float(retry_after), 1), 30)
                except (TypeError, ValueError):
                    delay = 5

                time.sleep(delay)

        except (
            urllib.error.URLError,
            TimeoutError,
            ValueError,
            RuntimeError,
        ) as exc:
            errors.append(
                f"{provider['name']} ({provider['model']}): {exc}"
            )

            if attempt == 0:
                time.sleep(3)

    raise RuntimeError("\n".join(errors))


def generate_documentary(topic, output, minutes=3):
    minutes = float(minutes)

    if not 2 <= minutes <= 5:
        raise ValueError(
            "Documentary duration must be between 2 and 5 minutes."
        )

    providers = provider_configuration()

    if not providers:
        raise RuntimeError(
            "No AI provider API key found. Add GROQ_API_KEY "
            "or GEMINI_API_KEY to GitHub Actions secrets."
        )

    target_words = round(minutes * 135)
    minimum_words = round(target_words * 0.80)
    maximum_words = round(target_words * 1.20)

    prompt = PROMPT.format(
        topic=topic,
        minutes=minutes,
        words=target_words,
        minimum_words=minimum_words,
        maximum_words=maximum_words,
    )

    errors = []
    data = None

    for provider in providers:
        try:
            data = generate_with_provider(
                provider,
                prompt,
                minutes,
            )

            print(
                f"Documentary generated using "
                f"{provider['name']} ({provider['model']})."
            )
            break

        except RuntimeError as exc:
            errors.append(str(exc))
            print(
                f"{provider['name']} failed. "
                "Trying the next configured provider."
            )

    if data is None:
        raise RuntimeError(
            "All configured AI providers failed:\n"
            + "\n".join(errors)
        )

    data.setdefault(
        "voice",
        os.getenv("VOICE", "en-US-GuyNeural"),
    )

    data.setdefault("rate", "-3%")

    data.setdefault(
        "watermark",
        os.getenv("WATERMARK", ""),
    )

    data.setdefault("claims_to_verify", [])

    validate_script(
        data,
        target_minutes=minutes,
    )

    path = Path(output)
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        f"Script saved: {path}\n"
        f"Words: {data['word_count']}\n"
        f"Estimated narration: {data['estimated_minutes']} minutes"
    )

    return data
