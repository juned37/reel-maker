
"""Generate documentary scripts with Gemini/Groq and cinematic storyboards."""

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

Return one valid JSON object only. No Markdown fences.

JSON structure:
{
  "title": ["Documentary title"],
  "watermark": "",
  "voice": "en-US-GuyNeural",
  "rate": "-3%",
  "claims_to_verify": [],
  "visual_style": "cinematic",
  "scenes": [
    {
      "onscreen_title": "Scene heading",
      "narration": "Spoken narration",
      "clear": true,
      "visual_brief": "Detailed cinematic scene description.",
      "show": ["book@left"],
      "visual_plan": {
        "elements": [
          {
            "type": "arrow",
            "points": [[20, 70], [50, 40], [80, 30]],
            "color": "gold",
            "width": 5,
            "draw_at": 0.2,
            "draw_duration": 0.5
          }
        ]
      },
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
- Open with a strong hook and end with a meaningful conclusion.
- Use natural spoken language.
- Avoid repetition and unsupported claims.

CINEMATIC VISUALS:
- Every scene must have its own detailed visual_brief.
- Describe the actual subject of that scene, not a generic symbol.
- Describe foreground, middle ground and background.
- Describe architecture, environment, objects, materials and lighting.
- Use historically appropriate periods and geographical settings.
- Make each visual_brief specific enough for image generation.
- Maintain a consistent cinematic, hand-painted documentary style.
- Use dramatic but believable lighting and atmospheric depth.
- Do not use web photographs.
- Do not request text, captions, letters or logos inside images.
- Do not repeat the same composition across scenes.
- Do not invent identifiable portraits of historical people.
- Use landscapes, architecture, objects, manuscripts and environments
  when depicting historical events.

HYBRID VECTOR VISUALS:
- visual_plan is optional.
- Use it for maps, timelines, routes, diagrams, processes and comparisons.
- Do not create vector plans merely for decoration.
- Use 3 to 12 elements for a useful diagram.
- Supported types: line, path, polyline, polygon, arrow, circle,
  ellipse, rect, text, arc.
- Coordinates must be between 0 and 100.
- Supported colors: ink, gold, paper, pale, muted, blue, green,
  red, white, dark.
- draw_at and draw_duration must be between 0 and 1.
- Keep labels short.
- Vector graphics must complement the artwork, not replace it.

FALLBACK ILLUSTRATIONS:
- show must be a list of 0 to 2 supported art.py specifications.
- Use these only when generated artwork is unavailable.
- Use @left, @center or @right for positions.
- Avoid repeating the same object without a narrative reason.

AVAILABLE ILLUSTRATIONS:
crescent, sun, book, mosque, kaaba, calendar, question,
hourglass, heart, lantern, globe, prayer_mat, beads, coins,
water_vessel, dates, minaret, dome, caravan, tent, scroll,
ship, palace, city_gate, map, compass, mountain, river,
atom, microscope, telescope, lightbulb, gears, computer,
ledger, marketplace, inkwell, arches, scale, figures.

ISLAMIC CONTENT AND HISTORICAL SAFEGUARDS:
- Never depict Prophet Muhammad ﷺ in any form, including face,
  body, silhouette, shadow or symbolic human representation.
- Never depict any named prophet.
- Do not invent portraits or appearances of historical people.
- Do not present imagined reconstructions as historical evidence.
- Avoid anachronistic clothing, objects and buildings.
- Distinguish established evidence, tradition and disputed reports.
- Do not invent quotations, dates or religious rulings.
- Put important uncertain claims in claims_to_verify.
- When a sacred figure is relevant, show the setting, architecture,
  landscape or objects without depicting the person.

FIELDS:
- clear must be true.
- camera must be slow_push, pan_left, pan_right, pan_up or pan_down.
- transition must be crossfade or cut.
- source_notes should identify evidence limitations when relevant.

Return valid JSON only. No comments or trailing commas.
"""


def build_prompt(topic, minutes):
    target_words = round(minutes * 135)

    return (
        PROMPT
        .replace("{topic}", topic)
        .replace("{minutes}", str(minutes))
        .replace("{words}", str(target_words))
        .replace("{minimum_words}", str(round(target_words * 0.80)))
        .replace("{maximum_words}", str(round(target_words * 1.20)))
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
        raise ValueError("AI response does not contain a complete JSON object.")

    return json.loads(text[start:end + 1])


def read_http_error(exc):
    try:
        detail = exc.read().decode("utf-8", "replace")
    except Exception:
        detail = str(exc)

    return detail[:1500]


def retry_delay(exc, default=12):
    headers = getattr(exc, "headers", None)

    if headers:
        value = headers.get("Retry-After")

        if value:
            try:
                return min(max(float(value), 2), 90)
            except (TypeError, ValueError):
                pass

    match = re.search(
        r"try again in ([0-9.]+)s",
        read_http_error(exc),
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
                    "cinematic storyboard artist. Return valid JSON only."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 10000,
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

    choice = choices[0]

    if choice.get("finish_reason") == "length":
        raise RuntimeError("Groq output was truncated by the token limit.")

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
            {"parts": [{"text": prompt}]}
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.3,
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
        raise RuntimeError("Gemini output was truncated by the token limit.")

    parts = candidate.get("content", {}).get("parts", [])
    content = "".join(part.get("text", "") for part in parts).strip()

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
    from art import parse_spec

    if not isinstance(candidate, dict):
        raise ValueError("Generated script must be a JSON object.")

    scenes = candidate.get("scenes")

    if not isinstance(scenes, list):
        raise ValueError("Generated script must contain a scenes list.")

    # Keep visual_plan: the renderer validates and draws it.
    for index, scene in enumerate(scenes, 1):
        if not isinstance(scene, dict):
            raise ValueError(f"Scene {index} must be an object.")

        scene.setdefault("show", [])

        if not isinstance(scene["show"], list):
            raise ValueError(f"Scene {index}: show must be a list.")

        if len(scene["show"]) > 2:
            raise ValueError(f"Scene {index}: use no more than 2 fallback illustrations.")

        for spec in scene["show"]:
            if not isinstance(spec, str):
                raise ValueError(
                    f"Scene {index}: illustration specifications must be strings."
                )
            parse_spec(spec)

        brief = scene.get("visual_brief", "")

        if not isinstance(brief, str):
            raise ValueError(
                f"Scene {index}: visual_brief must be a string."
            )

        if not brief.strip():
            scene["visual_brief"] = (
                f"Cinematic scene illustrating: {scene.get('onscreen_title', '')}. "
                f"{scene.get('narration', '')}"
            )

    validate_script(candidate, target_minutes=minutes)
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
            validate_generated_script(candidate, minutes)

            return candidate

        except urllib.error.HTTPError as exc:
            errors.append(f"HTTP {exc.code}: {read_http_error(exc)}")

            if exc.code == 429 and attempt < 2:
                delay = retry_delay(exc)
                print(f"{provider['name']} rate limited. Waiting {delay:.1f}s.")
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
                    + "\n\nCORRECTION: Return complete valid JSON. "
                    "Meet the requested word count. Every scene needs "
                    "a detailed visual_brief. Keep visual_plan valid "
                    "and optional. Do not remove visual_plan. "
                    "Do not use Markdown."
                )
                time.sleep(2)

    raise RuntimeError(
        f"{provider['name']} ({provider['model']}) failed:\n"
        + "\n".join(errors)
    )


def generate_documentary(topic, output, minutes=3):
    topic = str(topic).strip()

    if not topic:
        raise ValueError("Please provide a documentary topic.")

    minutes = float(minutes)

    if not 2 <= minutes <= 5:
        raise ValueError("Documentary duration must be between 2 and 5 minutes.")

    providers = provider_configuration()

    if not providers:
        raise RuntimeError(
            "No AI provider key found. Add GEMINI_API_KEY or GROQ_API_KEY."
        )

    prompt = build_prompt(topic, minutes)
    errors = []
    data = None

    for provider in providers:
        try:
            data = generate_with_provider(provider, prompt, minutes)
            print(
                f"Documentary generated using "
                f"{provider['name']} ({provider['model']})."
            )
            break

        except RuntimeError as exc:
            errors.append(str(exc))
            print(f"{provider['name']} failed. Trying next provider.")

    if data is None:
        raise RuntimeError(
            "All configured AI providers failed:\n" + "\n".join(errors)
        )

    data.setdefault("voice", os.getenv("VOICE", "en-US-GuyNeural"))
    data.setdefault("rate", "-3%")
    data.setdefault("watermark", os.getenv("WATERMARK", ""))
    data.setdefault("claims_to_verify", [])
    data["visual_style"] = "cinematic"

    validate_generated_script(data, minutes)

    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(
        f"Script saved: {path}\n"
        f"Words: {data['word_count']}\n"
        f"Estimated narration: {data['estimated_minutes']} minutes"
    )

    return data
