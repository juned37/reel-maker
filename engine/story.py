
"""Generate documentary scripts and scene-specific illustration plans."""

import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

from .quality import validate_script


PROMPT = """
Create an accurate, engaging documentary for vertical video.

TOPIC: {topic}
DURATION: {minutes} minutes.
TARGET NARRATION: {words} words.
ACCEPTABLE WORD RANGE: {minimum_words}-{maximum_words} words.

Return one valid JSON object only. No Markdown fences or explanations.

JSON structure:
{
  "title": ["Documentary title"],
  "watermark": "",
  "voice": "en-US-GuyNeural",
  "rate": "-3%",
  "claims_to_verify": [],
  "visual_style": "illustrated",
  "scenes": [
    {
      "onscreen_title": "Scene heading",
      "narration": "Spoken narration",
      "clear": true,
      "show": [],
      "visual_query": "",
      "camera": "slow_push",
      "transition": "crossfade",
      "source_notes": "",
      "visual_plan": {
        "elements": [
          {
            "type": "line",
            "points": [[15, 35], [50, 55]],
            "color": "ink",
            "width": 5,
            "draw_at": 0.0,
            "draw_duration": 0.3
          }
        ]
      }
    }
  ]
}

NARRATION:
- Write approximately {words} spoken words in total.
- Stay inside the acceptable word range.
- Divide narration across 8 to 12 scenes.
- Give every scene meaningful narration.
- Do not use one-sentence scenes merely to increase scene count.
- Open with a strong hook and end with a meaningful conclusion.
- Use natural spoken language.
- Avoid repetition and unsupported claims.

VISUALS:
- The video uses hand-drawn illustrations, NOT web photographs.
- Every scene must have its own topic-specific visual_plan.
- Use 5 to 10 useful drawing elements per scene.
- Use only these types: line, path, polyline, polygon, arrow,
  circle, ellipse, rect, text, arc.
- Use only these colours: ink, gold, paper, pale, muted, blue,
  green, red, white, dark.
- Use coordinates from 0 to 100.
- For line, path, polyline, polygon and arrow, provide points as
  [x,y] pairs. Arrow requires at least two points.
- For circle, ellipse, rect and arc, use x, y and size.
- For text, use x, y and a short text value.
- Use draw_at and draw_duration between 0 and 1.
- Keep important content around y=28 to y=68.
- Prefer recognisable objects, structures, maps, tools and processes.
- Show relationships and actions described by the narration.
- Do not fill scenes with random decorative shapes.
- Keep a consistent warm parchment, dark outline and restrained
  gold-accent illustration style.

TOPIC ADAPTATION:
Choose visuals that genuinely explain the topic.
History: period-appropriate places, maps, artefacts and buildings.
Science: scientific objects, systems and processes.
Religion: relevant architecture, objects, maps and practices.
Technology: devices, systems and components.
Geography: terrain, routes, rivers and locations.
Other topics: select accurate and meaningful visual metaphors.

ISLAMIC CONTENT AND HISTORICAL SAFEGUARDS:
- Never depict Prophet Muhammad ﷺ in any form, including silhouette,
  shadow or symbolic human representation.
- Do not invent portraits or appearances of historical people.
- Do not present imagined reconstructions as historical evidence.
- Avoid anachronistic clothing, objects and buildings.
- Distinguish established evidence, tradition and disputed reports.
- Do not invent quotations, dates or religious rulings.
- Put important uncertain claims in claims_to_verify.

FIELDS:
- clear must be true.
- show must be an empty list.
- visual_query is only for backward compatibility.
- camera must be slow_push, pan_left, pan_right, pan_up or pan_down.
- transition must be crossfade or cut.
- source_notes should identify evidence limitations when relevant.

Return valid JSON only. Ensure all braces, quotes and commas are
valid JSON syntax. Do not add comments or trailing commas.
"""


def build_prompt(topic, minutes):
    target_words = round(minutes * 135)

    return (
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


def extract_json(response_text):
    text = (response_text or "").strip()

    if text.startswith("```"):
        lines = text.splitlines()

        if lines and lines[0].startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        text = "\n".join(lines).strip()

    # First try parsing the complete response.
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Then try extracting the outer JSON object.
    start = text.find("{")
    end = text.rfind("}")

    if start < 0 or end <= start:
        raise ValueError(
            "AI response does not contain a complete JSON object."
        )

    return json.loads(text[start:end + 1])


def read_http_error(exc):
    try:
        detail = exc.read().decode("utf-8", "replace")
    except Exception:
        detail = str(exc)

    return detail[:1500]


def retry_delay(exc, default=12):
    """Read Retry-After or the wait time from a provider error."""
    headers = getattr(exc, "headers", None)

    if headers:
        value = headers.get("Retry-After")

        if value:
            try:
                return min(max(float(value), 2), 90)
            except (TypeError, ValueError):
                pass

    detail = read_http_error(exc)

    match = re.search(
        r"try again in ([0-9.]+)s",
        detail,
        re.IGNORECASE,
    )

    if match:
        return min(max(float(match.group(1)) + 2, 2), 90)

    return default


def call_groq(model, prompt, key):
    url = "https://api.groq.com/openai/v1/chat/completions"

    body = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are an accurate documentary writer and "
                    "visual storyboard artist. Return valid JSON only."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "temperature": 0.3,
        "max_tokens": 6500,
        "response_format": {
            "type": "json_object",
        },
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

    choice = choices[0]

    if choice.get("finish_reason") == "length":
        raise RuntimeError(
            "Groq output was truncated. Increase the output token limit "
            "or simplify the requested visual plans."
        )

    content = choice.get("message", {}).get("content")

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
                    {
                        "text": prompt,
                    }
                ]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.3,
            "maxOutputTokens": 10000,
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

    finish_reason = candidate.get("finishReason", "")

    if finish_reason == "MAX_TOKENS":
        raise RuntimeError(
            "Gemini output was truncated by the token limit."
        )

    parts = candidate.get("content", {}).get("parts", [])

    content = "".join(
        part.get("text", "")
        for part in parts
    ).strip()

    if not content:
        raise RuntimeError("Gemini returned empty content.")

    return content


def provider_configuration():
    providers = []

    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    groq_key = os.getenv("GROQ_API_KEY", "").strip()

    # Gemini is the primary provider.
    if gemini_key:
        providers.append({
            "name": "Gemini",
            "model": (
                os.getenv("GEMINI_MODEL", "").strip()
                or "gemini-3.5-flash-lite"
            ),
            "key": gemini_key,
            "call": call_gemini,
        })

    # Groq is the fallback provider.
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

    return providers


def validate_generated_script(candidate, minutes):
    validate_script(
        candidate,
        target_minutes=minutes,
    )

    missing = []

    for index, scene in enumerate(candidate["scenes"], 1):
        if not isinstance(scene.get("visual_plan"), dict):
            missing.append(index)

    if missing:
        raise ValueError(
            "Missing visual_plan in scene(s): "
            + ", ".join(map(str, missing))
        )

    return candidate


def generate_with_provider(provider, prompt, minutes):
    errors = []

    attempt_prompt = prompt

    for attempt in range(3):
        try:
            print(
                f"Generating with {provider['name']} "
                f"({provider['model']}), attempt {attempt + 1}/3..."
            )

            response_text = provider["call"](
                provider["model"],
                attempt_prompt,
                provider["key"],
            )

            candidate = extract_json(response_text)

            validate_generated_script(
                candidate,
                minutes,
            )

            return candidate

        except urllib.error.HTTPError as exc:
            detail = read_http_error(exc)

            errors.append(
                f"HTTP {exc.code}: {detail}"
            )

            # Retry rate limits using the provider's suggested wait.
            if exc.code == 429 and attempt < 2:
                delay = retry_delay(exc)

                print(
                    f"{provider['name']} rate limited. "
                    f"Waiting {delay:.1f} seconds."
                )

                time.sleep(delay)
                continue

            # Temporary server errors.
            if exc.code in (408, 500, 502, 503, 504) and attempt < 2:
                time.sleep(5 * (attempt + 1))
                continue

            break

        except (
            urllib.error.URLError,
            TimeoutError,
            ValueError,
            RuntimeError,
        ) as exc:
            errors.append(str(exc))

            if attempt < 2:
                # Give the provider a more explicit correction instruction.
                attempt_prompt = (
                    prompt
                    + "\n\nIMPORTANT CORRECTION:\n"
                    "Your previous response did not pass validation. "
                    "Return a complete valid JSON object. "
                    "Do not shorten the narration. "
                    "Meet the requested total word count exactly within "
                    "the specified acceptable range. "
                    "Every scene must contain a valid visual_plan. "
                    "Use only supported visual element types. "
                    "Do not add Markdown or explanations."
                )

                time.sleep(2)

    raise RuntimeError(
        f"{provider['name']} ({provider['model']}) failed:\n"
        + "\n".join(errors)
    )


def generate_documentary(topic, output, minutes=3):
    topic = str(topic).strip()

    if not topic:
        raise ValueError(
            "Please provide a documentary topic."
        )

    minutes = float(minutes)

    if not 2 <= minutes <= 5:
        raise ValueError(
            "Documentary duration must be between 2 and 5 minutes."
        )

    providers = provider_configuration()

    if not providers:
        raise RuntimeError(
            "No AI provider key found. Add GEMINI_API_KEY or "
            "GROQ_API_KEY to GitHub Actions secrets."
        )

    prompt = build_prompt(topic, minutes)

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

    data.setdefault(
        "rate",
        "-3%",
    )

    data.setdefault(
        "watermark",
        os.getenv("WATERMARK", ""),
    )

    data.setdefault(
        "claims_to_verify",
        [],
    )

    data["visual_style"] = "illustrated"

    validate_generated_script(
        data,
        minutes,
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
