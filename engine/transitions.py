"""Scene transition helpers."""

from PIL import Image


SUPPORTED_TRANSITIONS = {"crossfade", "cut"}


def transition_name(scene):
    value = str(
        (scene or {}).get("transition", "crossfade")
    ).strip().lower()

    return value if value in SUPPORTED_TRANSITIONS else "crossfade"


def crossfade(previous, current, progress):
    if previous is None:
        return current

    if previous.size != current.size:
        current = current.resize(
            previous.size,
            Image.Resampling.LANCZOS
        )

    progress = max(0.0, min(1.0, float(progress)))

    return Image.blend(previous, current, progress)


def apply_transition(previous, current, transition, progress):
    if transition == "cut" or previous is None:
        return current

    return crossfade(previous, current, progress)
