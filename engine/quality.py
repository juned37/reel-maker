
import re


WORDS_PER_MINUTE = 135

MIN_DOCUMENTARY_MINUTES = 2
MAX_DOCUMENTARY_MINUTES = 5

# Allow generated narration to be within 20% of the target.
DURATION_TOLERANCE = 0.20


def count_words(text):
    return len(
        re.findall(r"\b[\w’'-]+\b", str(text))
    )


def validate_script(data, target_minutes=None):

    if not isinstance(data, dict):
        raise ValueError("Script must be a JSON object.")

    title = data.get("title")

    if isinstance(title, str):
        title = [title.strip()] if title.strip() else []

    elif isinstance(title, list):
        title = [
            item.strip()
            for item in title
            if isinstance(item, str) and item.strip()
        ]

    else:
        title = []

    if not title:
        raise ValueError(
            "title must be a non-empty string or list."
        )

    data["title"] = title

    scenes = data.get("scenes")

    if not isinstance(scenes, list) or not scenes:
        raise ValueError(
            "scenes must be a non-empty list."
        )

    if not 1 <= len(scenes) <= 30:
        raise ValueError(
            "A script must contain between 1 and 30 scenes."
        )

    for index, scene in enumerate(scenes, 1):

        if not isinstance(scene, dict):
            raise ValueError(
                f"Scene {index} must be a JSON object."
            )

        narration = scene.get("narration")

        if not isinstance(narration, str) or not narration.strip():
            raise ValueError(
                f"Scene {index} has no valid narration."
            )

        scene.setdefault("show", [])
        scene.setdefault("clear", True)
        scene.setdefault("camera", "slow_push")
        scene.setdefault("transition", "crossfade")

        if not isinstance(scene["show"], list):
            raise ValueError(
                f"Scene {index}: show must be a list."
            )

        if not isinstance(scene.get("visual_query", ""), str):
            raise ValueError(
                f"Scene {index}: visual_query must be a string."
            )

        if scene["camera"] not in (
            "slow_push",
            "pan_left",
            "pan_right"
        ):
            raise ValueError(
                f"Scene {index}: unsupported camera movement."
            )

        if scene["transition"] not in (
            "crossfade",
            "cut"
        ):
            raise ValueError(
                f"Scene {index}: unsupported transition."
            )

    words = sum(
        count_words(scene["narration"])
        for scene in scenes
    )

    estimated_minutes = words / WORDS_PER_MINUTE

    data["word_count"] = words
    data["estimated_minutes"] = round(
        estimated_minutes, 2
    )

    if target_minutes is not None:

        target_minutes = float(target_minutes)

        if not (
            MIN_DOCUMENTARY_MINUTES
            <= target_minutes
            <= MAX_DOCUMENTARY_MINUTES
        ):
            raise ValueError(
                "Documentary duration must be between "
                "2 and 5 minutes."
            )

        minimum_words = (
            target_minutes
            * WORDS_PER_MINUTE
            * (1 - DURATION_TOLERANCE)
        )

        maximum_words = (
            target_minutes
            * WORDS_PER_MINUTE
            * (1 + DURATION_TOLERANCE)
        )

        if not minimum_words <= words <= maximum_words:
            raise ValueError(
                f"Narration is too short or too long for "
                f"{target_minutes:g} minutes. "
                f"Found {words} words; expected approximately "
                f"{round(minimum_words)}–{round(maximum_words)} "
                f"words at {WORDS_PER_MINUTE} words per minute. "
                f"Estimated duration: {estimated_minutes:.2f} minutes."
            )

    return data
