from PIL import Image, ImageDraw


def render_motion(frame, image, progress, scene=None):

    if image is None:
        return frame

    scene = scene or {}

    progress = max(
        0.0,
        min(float(progress), 1.0)
    )

    box_w = 920
    box_h = 650

    image_w, image_h = image.size

    scale = max(
        box_w / image_w,
        box_h / image_h
    )

    zoom = 1.03 + 0.07 * progress

    resized_w = max(
        box_w,
        int(image_w * scale * zoom)
    )

    resized_h = max(
        box_h,
        int(image_h * scale * zoom)
    )

    resized = image.resize(
        (resized_w, resized_h),
        Image.Resampling.LANCZOS
    )

    camera = str(scene.get("camera", "slow_push"))

    center_x = 0.5

    if camera == "pan_left":
        center_x = 0.65 - 0.25 * progress

    elif camera == "pan_right":
        center_x = 0.35 + 0.25 * progress

    left = int(max(0, resized_w - box_w) * center_x)
    top = int(max(0, resized_h - box_h) * 0.5)

    crop = resized.crop((
        left,
        top,
        left + box_w,
        top + box_h
    ))

    x, y = 80, 420

    fade = min(1.0, progress * 5.0)

    mask = Image.new(
        "L",
        crop.size,
        int(255 * fade)
    )

    frame.paste(crop, (x, y), mask)

    ImageDraw.Draw(frame).rounded_rectangle(
        (x, y, x + box_w, y + box_h),
        radius=24,
        outline=(176, 128, 36),
        width=3
    )

    return frame
