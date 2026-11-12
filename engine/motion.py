from PIL import Image, ImageDraw


CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1920


def _cover_resize(image, width, height, zoom=1.0):
    """Resize an image to cover the complete target canvas."""
    image = image.convert("RGB")

    source_width, source_height = image.size

    if source_width <= 0 or source_height <= 0:
        raise ValueError("Cannot render an image with invalid dimensions.")

    scale = max(
        width / source_width,
        height / source_height
    )

    scale *= zoom

    resized_width = max(width, round(source_width * scale))
    resized_height = max(height, round(source_height * scale))

    return image.resize(
        (resized_width, resized_height),
        Image.Resampling.LANCZOS
    )


def _camera_position(camera, progress):
    """Return a normalized crop position for the camera movement."""
    progress = max(0.0, min(1.0, float(progress)))

    if camera == "pan_left":
        return 0.65 - (0.30 * progress), 0.50

    if camera == "pan_right":
        return 0.35 + (0.30 * progress), 0.50

    if camera == "pan_up":
        return 0.50, 0.60 - (0.20 * progress)

    if camera == "pan_down":
        return 0.50, 0.40 + (0.20 * progress)

    return 0.50, 0.50


def _apply_readability_overlay(frame):
    """
    Apply a subtle vertical darkening gradient.

    This preserves the photograph while improving contrast
    for captions and other on-screen text.
    """
    overlay = Image.new(
        "RGBA",
        frame.size,
        (0, 0, 0, 0)
    )

    draw = ImageDraw.Draw(overlay)

    height = frame.height
    width = frame.width

    # Light darkening at the top for platform-safe title text.
    draw.rectangle(
        (0, 0, width, 300),
        fill=(0, 0, 0, 28)
    )

    # Stronger darkening in the lower caption area.
    for y in range(1050, height):
        progress = (y - 1050) / max(1, height - 1050)
        alpha = int(12 + (progress * 65))

        draw.line(
            (0, y, width, y),
            fill=(0, 0, 0, alpha)
        )

    return Image.alpha_composite(
        frame.convert("RGBA"),
        overlay
    ).convert("RGB")


def render_motion(frame, image, progress, scene=None):
    """
    Render a full-bleed 9:16 historical image.

    The caller supplies the 1080x1920 frame. The image fills
    the complete canvas without a border or inset panel.
    """
    if image is None:
        return frame

    scene = scene or {}

    if frame.size != (CANVAS_WIDTH, CANVAS_HEIGHT):
        raise ValueError(
            "The video frame must be 1080x1920 for vertical output."
        )

    progress = max(
        0.0,
        min(float(progress), 1.0)
    )

    camera = str(
        scene.get("camera", "slow_push")
    ).strip().lower()

    # Gentle zoom prevents the image from looking static.
    if camera == "slow_push":
        zoom = 1.02 + (0.055 * progress)
    else:
        zoom = 1.035 + (0.025 * progress)

    resized = _cover_resize(
        image,
        CANVAS_WIDTH,
        CANVAS_HEIGHT,
        zoom=zoom
    )

    center_x, center_y = _camera_position(
        camera,
        progress
    )

    available_x = max(
        0,
        resized.width - CANVAS_WIDTH
    )

    available_y = max(
        0,
        resized.height - CANVAS_HEIGHT
    )

    left = int(available_x * center_x)
    top = int(available_y * center_y)

    left = max(
        0,
        min(left, available_x)
    )

    top = max(
        0,
        min(top, available_y)
    )

    crop = resized.crop(
        (
            left,
            top,
            left + CANVAS_WIDTH,
            top + CANVAS_HEIGHT
        )
    )

    # Fade the image in at the beginning of each scene.
    fade = min(
        1.0,
        progress / 0.12
    )

    if fade < 1.0:
        black = Image.new(
            "RGB",
            crop.size,
            (12, 12, 14)
        )

        crop = Image.blend(
            black,
            crop,
            fade
        )

    crop = _apply_readability_overlay(crop)

    frame.paste(crop, (0, 0))

    return frame
