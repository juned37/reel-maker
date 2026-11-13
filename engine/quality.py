
"""Documentary script validation and duration estimation."""

import re

WORDS_PER_MINUTE = 135
MIN_DOCUMENTARY_MINUTES = 2
MAX_DOCUMENTARY_MINUTES = 5
DURATION_TOLERANCE = 0.20

SUPPORTED_CAMERAS = {
    "slow_push", "pan_left", "pan_right", "pan_up", "pan_down",
}
SUPPORTED_TRANSITIONS = {"crossfade", "cut"}


def count_words(text):
    return len(re.findall(r"\b[\w’'-]+\b", str(text)))


def _normalise_title(title):
    if isinstance(title, str):
        title = [title.strip()] if title.strip() else []
    if isinstance(title, list):
        return [
            item.strip()
            for item in title
            if isinstance(item, str) and item.strip()
        ]
    return []


def _validate_visual_plan(plan, scene_number):
    from .illustrations import validate_visual_plan

    try:
        validate_visual_plan(plan)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Scene {scene_number}: {exc}") from exc


def validate_script(data, target_minutes=None):
    if not isinstance(data, dict):
        raise ValueError("Script must be a JSON object.")

    title = _normalise_title(data.get("title"))
    if not title:
        raise ValueError("title must be a non-empty string or list.")
    data["title"] = title

    scenes = data.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise ValueError("scenes must be a non-empty list.")
    if not 1 <= len(scenes) <= 30:
        raise ValueError("A script must contain between 1 and 30 scenes.")

    for index, scene in enumerate(scenes, 1):
        if not isinstance(scene, dict):
            raise ValueError(f"Scene {index} must be an object.")

        narration = scene.get("narration")
        if not isinstance(narration, str) or not narration.strip():
            raise ValueError(f"Scene {index} must contain narration.")
        scene["narration"] = narration.strip()

        heading = scene.get("onscreen_title") or scene.get("label")
        if not isinstance(heading, str) or not heading.strip():
            words = re.findall(r"[\w’'-]+", scene["narration"])
            heading = " ".join(words[:6]).strip(" .,:;!?-")
        scene["onscreen_title"] = heading.strip()

        scene.setdefault("show", [])
        scene.setdefault("clear", True)
        scene.setdefault("camera", "slow_push")
        scene.setdefault("transition", "crossfade")

        if not isinstance(scene["show"], list) or not all(
            isinstance(item, str) for item in scene["show"]
        ):
            raise ValueError(f"Scene {index}: show must be a list of strings.")

        if not isinstance(scene.get("visual_query", ""), str):
            raise ValueError(f"Scene {index}: visual_query must be a string.")

        camera = str(scene["camera"]).lower()
        if camera not in SUPPORTED_CAMERAS:
            raise ValueError(f"Scene {index}: unsupported camera {camera!r}.")
        scene["camera"] = camera

        transition = str(scene["transition"]).lower()
        if transition not in SUPPORTED_TRANSITIONS:
            raise ValueError(
                f"Scene {index}: unsupported transition {transition!r}."
            )
        scene["transition"] = transition

        if scene.get("image") is not None and not isinstance(scene["image"], str):
            raise ValueError(f"Scene {index}: image must be a path or null.")

        if "visual_plan" in scene:
            _validate_visual_plan(scene["visual_plan"], index)

    claims = data.setdefault("claims_to_verify", [])
    if not isinstance(claims, list) or not all(
        isinstance(item, str) for item in claims
    ):
        raise ValueError("claims_to_verify must be a list of strings.")

    words = sum(count_words(scene["narration"]) for scene in scenes)
    estimated_minutes = words / WORDS_PER_MINUTE
    data["word_count"] = words
    data["estimated_minutes"] = round(estimated_minutes, 2)

    if target_minutes is not None:
        target_minutes = float(target_minutes)
        if not MIN_DOCUMENTARY_MINUTES <= target_minutes <= MAX_DOCUMENTARY_MINUTES:
            raise ValueError("Target duration must be between 2 and 5 minutes.")

        minimum = target_minutes * WORDS_PER_MINUTE * (1 - DURATION_TOLERANCE)
        maximum = target_minutes * WORDS_PER_MINUTE * (1 + DURATION_TOLERANCE)

        if not minimum <= words <= maximum:
            raise ValueError(
                f"Script has {words} words; expected {round(minimum)}–"
                f"{round(maximum)} for {target_minutes:g} minutes. "
                f"Estimated duration: {estimated_minutes:.2f} minutes."
            )

    return data
