
import re


def validate_script(data):

    if not isinstance(data, dict):
        raise ValueError("Script must be a JSON object")

    # Accept both a string title and a list of title lines.
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
        raise ValueError("title must be a non-empty string or list")

    # Keep title in list format for compatibility with reel.py.
    data["title"] = title

    scenes = data.get("scenes")

    if not isinstance(scenes, list) or not scenes:
        raise ValueError("scenes must be a non-empty list")

    if len(scenes) > 30:
        raise ValueError("Maximum 30 scenes")

    for i, scene in enumerate(scenes, 1):

        if not isinstance(scene, dict):
            raise ValueError(f"Scene {i} must be a JSON object")

        if not str(scene.get("narration", "")).strip():
            raise ValueError(f"Scene {i} has no narration")

        scene.setdefault("show", [])
        scene.setdefault("clear", True)
        scene.setdefault("camera", "slow_push")
        scene.setdefault("transition", "crossfade")

        if not isinstance(scene["show"], list):
            scene["show"] = []

    words = sum(
        len(re.findall(r"\b[\w’'-]+\b", scene["narration"]))
        for scene in scenes
    )

    data["word_count"] = words
    data["estimated_minutes"] = round(words / 135, 2)

    return data
