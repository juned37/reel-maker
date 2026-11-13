
"""Documentary script validation and duration estimation."""

import re


WORDS_PER_MINUTE = 135
MIN_DOCUMENTARY_MINUTES = 2
MAX_DOCUMENTARY_MINUTES = 5
DURATION_TOLERANCE = 0.20

SUPPORTED_CAMERAS = {
    "slow_push",
    "pan_left",
    "pan_right",
    "pan_up",
    "pan_down",
}

SUPPORTED_TRANSITIONS = {
    "crossfade",
    "cut",
}


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
    if not isinstance(plan, dict):
        raise ValueError(
            f"Scene {scene_number}: visual_plan must be an object."
        )

    elements = plan.get("elements")

    if not isinstance(elements, list):
        raise ValueError(
            f"Scene {scene_number}: visual_plan.elements must be a list."
        )

    if len(elements) > 35:
        raise ValueError(
            f"Scene {scene_number}: maximum 35 visual elements allowed."
        )

    allowed = {
        "line", "path", "polyline", "polygon",
        "circle", "ellipse", "rect", "text", "arc",
    }

    for element_number, element in enumerate(elements, 1):
        if not isinstance(element, dict):
            raise ValueError(
                f"Scene {scene_number}, element {element_number}: "
                "must be an object."
            )

        kind = str(element.get("type", "")).lower()

        if kind not in allowed:
            raise ValueError(
                f"Scene {scene_number}, element {element_number}: "
                f"unsupported drawing type {kind!r}."
            )

        for key in ("draw_at", "draw_duration"):
            if key in element:
                try:
                    value = float(element[key])
                except (TypeError, ValueError):
                    raise ValueError(
                        f"Scene {scene_number}: {key} must be numeric."
                    )

                if not 0 <= value <= 1:
                    raise ValueError(
                        f"Scene {scene_number}: {key} must be between 0 and 1."
                    )

        if kind in ("line", "path", "polyline", "polygon"):
            points = element.get("points")
            minimum = 3 if kind == "polygon" else 2

            if not isinstance(points, list) or len(points) < minimum:
                raise ValueError(
                    f"Scene {scene_number}: {kind} needs at least "
                    f"{minimum} points."
                )

            for point in points:
                if (
                    not isinstance(point, (list, tuple))
                    or len(point) != 2
                    or not all(
                        isinstance(v, (int, float)) and 0 <= v <= 100
                        for v in point
                    )
                ):
                    raise ValueError(
                        f"Scene {scene_number}: drawing points must be "
                        "numeric [x, y] pairs between 0 and 100."
                    )

        if kind in ("circle", "ellipse", "rect", "arc"):
            for key, default in (
                ("x", 50),
                ("y", 50),
                ("size", 10),
            ):
                try:
                    value = float(element.get(key, default))
                except (TypeError, ValueError):
                    raise ValueError(
                        f"Scene {scene_number}: {key} must be numeric."
                    )

                if not 0 <= value <= 100:
                    raise ValueError(
                        f"Scene {scene_number}: {key} must be between 0 and 100."
                    )

        if kind == "text":
            label = element.get("text", element.get("label", ""))

            if not isinstance(label, str):
                raise ValueError(
                    f"Scene {scene_number}: text element needs a string."
                )

            if len(label) > 100:
                raise ValueError(
                    f"Scene {scene_number}: text elements are limited to 100 characters."
                )


def validate_script(data, target_minutes=None):
    if not isinstance(data, dict):
        raise ValueError("Script must be a JSON object.")

    title = _normalise_title(data.get("title"))

    if not title:
        raise ValueError(
            "title must be a non-empty string or a list of strings."
        )

    data["title"] = title

    scenes = data.get("scenes")

    if not isinstance(scenes, list) or not scenes:
        raise ValueError("scenes must be a non-empty list.")

    if not 1 <= len(scenes) <= 30:
        raise ValueError("A script must contain between 1 and 30 scenes.")

    for index, scene in enumerate(scenes, start=1):
        if not isinstance(scene, dict):
            raise ValueError(f"Scene {index} must be a JSON object.")

        narration = scene.get("narration")

        if not isinstance(narration, str) or not narration.strip():
            raise ValueError(
                f"Scene {index} must contain non-empty narration."
            )

        scene["narration"] = narration.strip()

        onscreen_title = scene.get("onscreen_title") or scene.get("label")

        if not isinstance(onscreen_title, str) or not onscreen_title.strip():
            words_for_title = re.findall(
                r"[\w’'-]+",
                scene["narration"]
            )
            onscreen_title = " ".join(words_for_title[:6]).strip(
                " .,:;!?-"
            )

        scene["onscreen_title"] = onscreen_title.strip()

        scene.setdefault("show", [])
        scene.setdefault("clear", True)
        scene.setdefault("camera", "slow_push")
        scene.setdefault("transition", "crossfade")

        if not isinstance(scene["show"], list):
            raise ValueError(f"Scene {index}: show must be a list.")

        if not all(isinstance(item, str) for item in scene["show"]):
            raise ValueError(
                f"Scene {index}: every show item must be a string."
            )

        if not isinstance(scene.get("visual_query", ""), str):
            raise ValueError(
                f"Scene {index}: visual_query must be a string."
            )

        camera = str(scene["camera"]).lower()

        if camera not in SUPPORTED_CAMERAS:
            raise ValueError(
                f"Scene {index}: unsupported camera movement {camera!r}."
            )

        scene["camera"] = camera

        transition = str(scene["transition"]).lower()

        if transition not in SUPPORTED_TRANSITIONS:
            raise ValueError(
                f"Scene {index}: unsupported transition {transition!r}."
            )

        scene["transition"] = transition

        if scene.get("image") is not None and not isinstance(
            scene["image"], str
        ):
            raise ValueError(
                f"Scene {index}: image must be a path string or null."
            )

        # Older scripts remain valid. New scripts should include visual_plan.
        if "visual_plan" in scene:
            _validate_visual_plan(scene["visual_plan"], index)

    claims = data.setdefault("claims_to_verify", [])

    if not isinstance(claims, list):
        raise ValueError("claims_to_verify must be a list.")

    if not all(isinstance(item, str) for item in claims):
        raise ValueError(
            "Every claims_to_verify entry must be a string."
        )

    words = sum(
        count_words(scene["narration"])
        for scene in scenes
    )

    estimated_minutes = words / WORDS_PER_MINUTE

    data["word_count"] = words
    data["estimated_minutes"] = round(estimated_minutes, 2)

    if target_minutes is not None:
        target_minutes = float(target_minutes)

        if not (
            MIN_DOCUMENTARY_MINUTES
            <= target_minutes
            <= MAX_DOCUMENTARY_MINUTES
        ):
            raise ValueError(
                "Target duration must be between 2 and 5 minutes."
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
                f"Script has {words} words, which is outside the expected "
                f"range of {round(minimum_words)}–{round(maximum_words)} "
                f"words for a {target_minutes:g}-minute documentary. "
                f"Estimated narration time: {estimated_minutes:.2f} minutes."
            )

    return data
