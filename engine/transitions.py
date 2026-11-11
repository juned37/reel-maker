from PIL import Image


def crossfade(previous, current, progress):

    if previous is None:
        return current

    progress = max(
        0.0,
        min(1.0, float(progress))
    )

    return Image.blend(
        previous,
        current,
        progress
    )


def transition_name(scene):

    value = str(
        scene.get("transition", "crossfade")
    ).lower()

    if value in {"crossfade", "cut"}:
        return value

    return "crossfade"
