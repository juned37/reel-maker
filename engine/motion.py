"""Full-screen vertical image motion for documentary scenes."""

from PIL import Image, ImageDraw


CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1920


def cover_resize(image, width, height, zoom=1.0):
    image = image.convert("RGB")

    source_width, source_height = image.size
    if source_width <= 0 or source_height <= 0:
        raise ValueError("Image has invalid dimensions.")

    scale = max(width / source_width, height / source_height)
    scale *= zoom

    resized_width = max(width, round(source_width * scale))
    resized_height = max(height, round(source_height * scale))

    return image.resize(
        (resized_width, resized_height),
        Image.Resampling.LANCZOS
    )


def camera_position(camera, progress):
    progress = max(0.0, min(1.0, float(progress)))

    positions = {
        "pan_left": (0.65 - 0.30 * progress, 0.50),
        "pan_right": (0.35 + 0.30 * progress, 0.50),
        "pan_up": (0.50, 0.60 - 0.20 * progress),
        "pan_down": (0.50, 0.40 + 0.20 * progress),
    }

    return positions.get(camera, (0.50, 0.50))


def add_overlay(image):
    """Add subtle contrast in caption and title-safe regions."""
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    draw.rectangle(
        (0, 0, CANVAS_WIDTH, 260),
        fill=(0, 0, 0, 35)
    )

    for y in range(1120, CANVAS_HEIGHT):
        progress = (y - 1120) / (CANVAS_HEIGHT - 1120)
        alpha = int(8 + progress * 72)
        draw.line(
            (0, y, CANVAS_WIDTH, y),
            fill=(0, 0, 0, alpha)
        )

    return Image.alpha_composite(
        image.convert("RGBA"),
        overlay
    ).convert("RGB")


def render_motion(frame, image, progress, scene=None):
    """Paste a gently moving full-screen image into a 1080x1920 frame."""
    if image is None:
        return frame

    if frame.size != (CANVAS_WIDTH, CANVAS_HEIGHT):
        raise ValueError("Expected a 1080x1920 frame.")

    scene = scene or {}
    progress = max(0.0, min(1.0, float(progress)))
    camera = str(scene.get("camera", "slow_push")).lower()

    zoom = (
        1.015 + 0.055 * progress
        if camera == "slow_push"
        else 1.025 + 0.025 * progress
    )

    resized = cover_resize(
        image,
        CANVAS_WIDTH,
        CANVAS_HEIGHT,
        zoom
    )

    center_x, center_y = camera_position(camera, progress)

    extra_x = max(0, resized.width - CANVAS_WIDTH)
    extra_y = max(0, resized.height - CANVAS_HEIGHT)

    left = int(extra_x * center_x)
    top = int(extra_y * center_y)

    crop = resized.crop((
        left,
        top,
        left + CANVAS_WIDTH,
        top + CANVAS_HEIGHT
    ))

    fade = min(1.0, progress / 0.15)
    if fade < 1.0:
        crop = Image.blend(
            Image.new("RGB", crop.size, (8, 10, 14)),
            crop,
            fade
        )

    frame.paste(add_overlay(crop), (0, 0))
    return frame
