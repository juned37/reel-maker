
"""Generate documentary scripts and scene-specific illustration plans."""

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from .quality import validate_script


PROMPT = r"""
Create a compelling, accurate documentary for vertical video.

TOPIC: {topic}
TARGET DURATION: {minutes} minutes.
TARGET WORDS: approximately {words}.
ACCEPTABLE WORD RANGE: {minimum_words} to {maximum_words}.

Return ONLY valid JSON. Do not use Markdown fences.

Required top-level fields:
title, watermark, voice, rate, claims_to_verify, visual_style, scenes.

Set visual_style to "illustrated".

Create 10 to 24 scenes. Each scene must contain:
onscreen_title, narration, clear, show, visual_query, camera,
transition, source_notes, visual_plan.

STORY:
- Open with a strong hook.
- Build a logical narrative with clear progression.
- Each scene must add new information.
- End with a meaningful conclusion.
- Write natural narration suitable for spoken delivery.
- Avoid repetition and unsupported claims.
- Match the requested word count.

VISUAL STORYTELLING — CRITICAL:
The video uses hand-drawn animated illustrations, NOT web photographs.
Every scene must visually explain the specific narration being spoken.
Do not reuse one generic drawing across unrelated scenes.
Think like a documentary storyboard artist.
Identify the key objects, places, people (where appropriate), actions,
relationships, and processes in the narration.
Translate those ideas into a clear illustration that can be drawn with
simple shapes and lines.
The visual plan must be specific to this scene and topic.

Each visual_plan must be an object with:
{
  "elements": [
    {
      "type": "line | path | polyline | polygon | circle | ellipse | rect | text | arc",
      "x": 50,
      "y": 50,
      "size": 20,
      "points": [[10,20],[30,40]],
      "color": "ink | gold | paper | pale | muted | blue | green | red | white | dark",
      "fill": "pale",
      "width": 5,
      "text": "optional short label",
      "font_size": 32,
      "bold": true,
      "draw_at": 0.0,
      "draw_duration": 0.25,
      "move_x": 0,
      "move_y": 0,
      "pulse": 0
    }
  ]
}

COORDINATES:
- Use a 0 to 100 coordinate system.
- x=0 is left, x=100 is right.
- y=0 is top, y=100 is bottom.
- For circle, ellipse and rect, x and y are the centre.
- size is the approximate diameter/width in percentage units.
- For paths and polygons, use points as [x,y] pairs.
- Use 5 to 20 elements per scene where useful.
- Use short labels only when they help explain the drawing.
- Use draw_at to sequence elements during the narration (0 to 1).
- Use draw_duration to control how quickly an element is revealed.
- Use move_x and move_y for subtle motion over the scene.
- Use pulse sparingly.
- Keep important drawing content around y=28 to y=68, leaving room
  for the heading and subtitles.
- Make drawings large, balanced and easy to understand on a phone.
- Use only the supported element types and palette names above.
- Do not output code, SVG, HTML or arbitrary drawing instructions.

VISUAL DESIGN:
- Warm parchment background.
- Hand-drawn dark outlines.
- Restrained gold accents.
- Muted natural colours.
- Elegant, simple documentary illustration.
- Prefer a few clear, recognisable objects over abstract decoration.
- Use a coherent illustration style across all scenes.
- The visual should change as the narration develops.
- Show cause and effect, movement, comparisons, routes, structures,
  processes and relationships when the narration describes them.
- Avoid generic decorative circles, random lines or repeated icons.

TOPIC ADAPTATION:
For science, illustrate the relevant scientific objects and processes.
For history, illustrate period-appropriate maps, artefacts, buildings,
tools, trade, landscapes and documented cultural details.
For biographies, illustrate places, objects, timelines and events.
For technology, illustrate devices, systems, components and processes.
For geography, illustrate maps, terrain, rivers, routes and locations.
For other topics, choose visual metaphors and objects that accurately
explain the subject.
Do not force every topic into a map, building or human figure.

PEOPLE AND SENSITIVE HISTORICAL TOPICS:
- Never depict Prophet Muhammad ﷺ in any form, including silhouette,
  shadow, imagined appearance or symbolic human representation.
- Do not create fabricated portraits of historical people.
- Do not present imagined reconstructions as authentic evidence.
- Avoid anachronistic clothing, objects, buildings and technology.
- Distinguish established evidence, tradition and disputed reports.
- Do not invent quotations, dates, events or certainty.
- Put important uncertain claims in claims_to_verify.

VISUAL QUERY:
Keep visual_query as a short optional reference-search phrase for
backward compatibility. It is NOT used as the primary scene visual.
Do not let a web image determine the illustration.

CAMERA:
Use only slow_push, pan_left, pan_right, pan_up, pan_down.

TRANSITION:
Use only crossfade or cut.

OTHER FIELDS:
- clear must be true.
- show must be an empty list unless a legacy art element is genuinely useful.
- source_notes should explain evidence and visual caveats.
- Use voice "en-US-GuyNeural" unless specified otherwise.
- Use rate "-3%".
- Include claims_to_verify as a list.
- Each scene's visual_plan must contain 5 to 20 elements.
- Return valid JSON only.
"""


def extract_json(text):
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

    if start < 0 or end <= start:
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
                    "You are a documentary writer and storyboard artist. "
                    "Create accurate topic-specific visual plans. "
                    "Return valid JSON only."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.45,
        "max_tokens": 12000,
        "response_format": {"type": "json_object"},
    }

    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
            "User-Agent": "reel-maker/1.0",
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=180) as response:
        result = json.load(response)

    choices = result.get("choices", [])

    if not choices:
        raise RuntimeError("Groq returned no choices.")

    content = choices[0].get("message", {}).get("content")

    if not content:
        raise RuntimeError("Groq returned empty content.")

    return content.strip()


def call_gemini(model, prompt, key):
    url = (
        "https://generativelanguage.googleapis.com/"
        f"v1beta/models/{model}:generateContent"
    )

    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.45,
            "maxOutputTokens": 12000,
        },
    }

    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": key,
            "User-Agent": "reel-maker/1.0",
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
        raise RuntimeError(
            "Gemini response was cut off by the output token limit."
        )

    parts = candidate.get("content", {}).get("parts", [])

    content = "".join(
        part.get("text", "") for part in parts
    ).strip()

    if not content:
        raise RuntimeError("Gemini returned empty content.")

    return content


def provider_configuration():
    providers = []

    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()

    if groq_key:
        providers.append({
            "name": "Groq",
            "model": os.getenv("GROQ_MODEL", "").strip()
            or "openai/gpt-oss-120b",
            "key": groq_key,
            "call": call_groq,
        })

    if gemini_key:
        providers.append({
            "name": "Gemini",
            "model": os.getenv("GEMINI_MODEL", "").strip()
            or "gemini-3.5-flash-lite",
            "key": gemini_key,
            "call": call_gemini,
        })

    return providers


def generate_with_provider(provider, prompt, minutes):
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

            missing = [
                i for i, scene in enumerate(candidate["scenes"], 1)
                if not isinstance(scene.get("visual_plan"), dict)
            ]

            if missing:
                raise ValueError(
                    "Missing visual_plan in scene(s): "
                    + ", ".join(map(str, missing))
                )

            return candidate

        except urllib.error.HTTPError as exc:
            errors.append(
                f"{provider['name']} ({provider['model']}): "
                f"HTTP {exc.code}: {read_http_error(exc)}"
            )

            if exc.code not in (408, 429, 500, 502, 503, 504):
                break

            if attempt == 0:
                try:
                    delay = min(
                        max(float(exc.headers.get("Retry-After", 5)), 1),
                        30,
                    )
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
    topic = str(topic).strip()

    if not topic:
        raise ValueError("Please provide a documentary topic.")

    minutes = float(minutes)

    if not 2 <= minutes <= 5:
        raise ValueError(
            "Documentary duration must be between 2 and 5 minutes."
        )

    providers = provider_configuration()

    if not providers:
        raise RuntimeError(
            "No AI provider key found. Add GROQ_API_KEY or GEMINI_API_KEY "
            "to your environment or GitHub Actions secrets."
        )

    target_words = round(minutes * 135)

    # Replace only intended placeholders.
    # This preserves the literal JSON braces in PROMPT.
    prompt = (
        PROMPT
        .replace("{topic}", topic)
        .replace("{minutes}", str(minutes))
        .replace("{words}", str(target_words))
        .replace(
            "{minimum_words}",
            str(round(target_words * 0.80)),
        )
        .replace(
            "{maximum_words}",
            str(round(target_words * 1.20)),
        )
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
                f"{provider['name']} failed. Trying next provider."
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
    data.setdefault("watermark", os.getenv("WATERMARK", ""))
    data.setdefault("claims_to_verify", [])

    data["visual_style"] = "illustrated"

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
