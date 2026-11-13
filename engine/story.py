
"""Generate documentary scripts using the reusable art.py library."""

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
      "show": ["book@left", "crescent@right"],
      "visual_query": "",
      "camera": "slow_push",
      "transition": "crossfade",
      "source_notes": ""
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
- The video uses the existing hand-drawn art.py illustration library.
- Do not use web photographs.
- Do not create visual_plan objects.
- Select 1 or 2 objects from the supported asset catalogue per scene.
- Use the object that best communicates the narration.
- Use @left, @center or @right to position an object.
- Do not use the same object in every scene unless narratively necessary.
- Do not add decorative objects without a narrative reason.
- Use figures only for generic crowds or groups.
- Never use figures to represent a named historical or religious person.
- Use text:TITLE|SUBTITLE sparingly, only when a short label
  genuinely improves understanding.
- Avoid using two objects in the same position.

AVAILABLE ILLUSTRATIONS:
crescent, sun, book, mosque, kaaba, calendar, question,
hourglass, heart, lantern, globe, prayer_mat, beads, coins,
water_vessel, dates, minaret, dome, caravan, tent, scroll,
ship, palace, city_gate, map, compass, mountain, river,
atom, microscope, telescope, lightbulb, gears, computer,
ledger, marketplace, inkwell, arches, scale, figures.

TOPIC ADAPTATION:
- Religion: use relevant objects, architecture, places and practices.
- History: use maps, manuscripts, buildings, ships and period objects.
- Science: use scientific instruments, diagrams and equipment.
- Geography: use maps, mountains, rivers, globes and navigation tools.
- Economics: use coins, ledgers, scales and marketplaces.
- Technology: use computers, gears and relevant equipment.
- Other topics: choose the closest accurate visual metaphor.

ISLAMIC CONTENT AND HISTORICAL SAFEGUARDS:
- Never depict Prophet Muhammad ﷺ in any form, including silhouette,
  shadow or symbolic human representation.
- Never use figures to represent Prophet Muhammad ﷺ or any named prophet.
- Do not invent portraits or appearances of historical people.
- Do not present imagined reconstructions as historical evidence.
- Avoid anachronistic clothing, objects and buildings.
- Distinguish established evidence, tradition and disputed reports.
- Do not invent quotations, dates or religious rulings.
- Put important uncertain claims in claims_to_verify.

FIELDS:
- clear must be true.
- show must be a list of supported art.py object specifications.
- Use no more than 2 illustrations per scene.
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

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

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
    """Read Retry-After or wait time from a provider error."""
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
            "Groq output was truncated. Increase the output token "
            "limit or simplify the requested storyboard."
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

    if candidate.get("finishReason") == "MAX_TOKENS":
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
    from art import ELEMENTS, FIXED, parse_spec

    if not isinstance(candidate, dict):
        raise ValueError("Generated script must be a JSON object.")

    scenes = candidate.get("scenes")

    if not isinstance(scenes, list):
        raise ValueError("Generated script must contain a scenes list.")

    # Remove legacy visual plans. The illustrated renderer uses art.py.
    for scene in scenes:
        if isinstance(scene, dict):
            scene.pop("visual_plan", None)

    validate_script(
        candidate,
        target_minutes=minutes,
    )

    for index, scene in enumerate(candidate["scenes"], 1):
        show = scene.get("show", [])

        if not isinstance(show, list):
            raise ValueError(
                f"Scene {index}: show must be a list."
            )

        if len(show) > 2:
            raise ValueError(
                f"Scene {index}: use no more than 2 illustrations."
            )

        used_positions = set()
        used_names = set()

        for spec in show:
            if not isinstance(spec, str):
                raise ValueError(
                    f"Scene {index}: illustration specs must be strings."
                )

            name, arg, position = parse_spec(spec)

            if name not in ELEMENTS:
                raise ValueError(
                    f"Scene {index}: unsupported illustration '{name}'."
                )

            if position in used_positions:
                raise ValueError(
                    f"Scene {index}: two illustrations use the same "
                    f"position '{position}'."
                )

            if name in used_names:
                raise ValueError(
                    f"Scene {index}: duplicate illustration '{name}'."
                )

            used_positions.add(position)
            used_names.add(name)

            if name in FIXED and len(show) > 1:
                raise ValueError(
                    f"Scene {index}: '{name}' is a fixed-position "
                    "illustration and must be used alone."
                )

            if name == "figures":
                try:
                    count = int(arg or 3)
                except ValueError as exc:
                    raise ValueError(
                        f"Scene {index}: figures count must be an integer."
                    ) from exc

                if not 1 <= count <= 6:
                    raise ValueError(
                        f"Scene {index}: figures count must be from 1 to 6."
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

            if exc.code == 429 and attempt < 2:
                delay = retry_delay(exc)

                print(
                    f"{provider['name']} rate limited. "
                    f"Waiting {delay:.1f} seconds."
                )

                time.sleep(delay)
                continue

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
                attempt_prompt = (
                    prompt
                    + "\n\nIMPORTANT CORRECTION:\n"
                    "Your previous response did not pass validation. "
                    "Return a complete valid JSON object. "
                    "Do not shorten the narration. "
                    "Meet the requested total word count within the "
                    "specified acceptable range. "
                    "Every scene must contain a show list using only "
                    "supported art.py illustration names. "
                    "Use no more than 2 illustrations per scene. "
                    "Do not include visual_plan. "
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

    data.setdefault("rate", "-3%")
    data.setdefault("watermark", os.getenv("WATERMARK", ""))
    data.setdefault("claims_to_verify", [])

    data["visual_style"] = "illustrated"

    validate_generated_script(
        data,
        minutes,
    )

    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)

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
