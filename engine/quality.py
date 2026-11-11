import re


def validate_script(data):

    if not isinstance(data, dict):
        raise ValueError("Script must be a JSON object")

    if not isinstance(data.get("title"), list) or not data["title"]:
        raise ValueError("title must be a non-empty list")

    scenes = data.get("scenes")

    if not isinstance(scenes, list) or not scenes:
        raise ValueError("scenes must be a non-empty list")

    if len(scenes) > 30:
        raise ValueError("Maximum 30 scenes")

    for i, scene in enumerate(scenes, 1):

        if (
            not isinstance(scene, dict)
            or not str(scene.get("narration", "")).strip()
        ):
            raise ValueError(f"Scene {i} has no narration")

        scene.setdefault("show", [])
        scene.setdefault("clear", True)
        scene.setdefault("camera", "slow_push")
        scene.setdefault("transition", "crossfade")

    words = sum(
        len(re.findall(r"\b[\w’'-]+\b", scene["narration"]))
        for scene in scenes
    )

    data["word_count"] = words
    data["estimated_minutes"] = round(words / 135, 2)

    return data
