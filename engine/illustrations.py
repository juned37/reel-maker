
"""Generic hand-drawn scene renderer.

Visual-plan coordinates use a 0-100 coordinate system:
(0, 0) is top-left and (100, 100) is bottom-right.
The AI generates the elements for each scene; this module draws them.
"""

import math
from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1080, 1920

INK = (75, 62, 49)
GOLD = (176, 128, 36)
PAPER = (246, 237, 224)
PALE = (238, 225, 204)
MUTED = (157, 132, 101)
BLUE = (112, 145, 160)
GREEN = (126, 145, 105)
RED = (170, 105, 83)

PALETTE = {
    "ink": INK,
    "gold": GOLD,
    "paper": PAPER,
    "pale": PALE,
    "muted": MUTED,
    "blue": BLUE,
    "green": GREEN,
    "red": RED,
    "white": (255, 252, 245),
    "dark": (55, 48, 42),
}


def _xy(value):
    """Convert normalised 0-100 coordinates to pixels."""
    return float(value) * WIDTH / 100


def _point(value):
    """Convert a normalised [x, y] point to canvas coordinates."""
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("A drawing point must be [x, y].")
    return (_xy(value[0]), _xy(value[1]))


def _color(value, default=INK):
    if isinstance(value, str):
        return PALETTE.get(value.lower(), default)
    if (
        isinstance(value, (list, tuple))
        and len(value) == 3
        and all(isinstance(v, int) and 0 <= v <= 255 for v in value)
    ):
        return tuple(value)
    return default


def _font(size=30, bold=False):
    candidates = (
        [
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
        ]
        if bold else [
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
        ]
    )

    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass

    return ImageFont.load_default()


def _progress_for_element(element, scene_progress):
    start = float(element.get("draw_at", 0.0))
    duration = max(0.01, float(element.get("draw_duration", 0.25)))
    return max(0.0, min(1.0, (scene_progress - start) / duration))


def _draw_partial_line(draw, points, amount, fill, width):
    if len(points) < 2 or amount <= 0:
        return

    lengths = []
    total = 0.0

    for a, b in zip(points, points[1:]):
        length = math.dist(a, b)
        lengths.append(length)
        total += length

    if total <= 0:
        return

    remaining = total * min(1.0, amount)
    output = [points[0]]

    for a, b, length in zip(points, points[1:], lengths):
        if remaining >= length:
            output.append(b)
            remaining -= length
        else:
            if length > 0:
                ratio = remaining / length
                output.append((
                    a[0] + (b[0] - a[0]) * ratio,
                    a[1] + (b[1] - a[1]) * ratio,
                ))
            break

    if len(output) >= 2:
        draw.line(output, fill=fill, width=width, joint="curve")


def _draw_element(draw, element, amount, scene_progress):
    kind = str(element.get("type", "")).lower()
    color = _color(element.get("color"))
    fill_value = element.get("fill")
    fill = None if fill_value in (None, "none", "transparent") else _color(
        fill_value, PALE
    )
    width = max(1, min(18, int(element.get("width", 5))))
    points = element.get("points", [])

    # Optional simple motion. Values are percentages of canvas width/height.
    move_x = float(element.get("move_x", 0)) * scene_progress
    move_y = float(element.get("move_y", 0)) * scene_progress
    pulse = 1.0 + float(element.get("pulse", 0)) * math.sin(
        scene_progress * math.pi * 2
    )

    def moved(point):
        x, y = point
        return (
            x + _xy(move_x),
            y + _xy(move_y) * HEIGHT / WIDTH,
        )

    if kind in ("line", "path", "polyline"):
        converted = [moved(_point(p)) for p in points]
        _draw_partial_line(draw, converted, amount, color, width)
        return

    if kind == "polygon":
        converted = [moved(_point(p)) for p in points]
        if len(converted) < 3:
            return
        if amount >= 1:
            if fill:
                draw.polygon(converted, fill=fill)
            draw.line(converted + [converted[0]], fill=color, width=width)
        else:
            _draw_partial_line(
                draw, converted + [converted[0]], amount, color, width
            )
        return

    x = float(element.get("x", 50))
    y = float(element.get("y", 50))
    size = max(1.0, float(element.get("size", 10))) * pulse
    x1 = _xy(x - size / 2) + _xy(move_x)
    y1 = _xy(y - size / 2) * HEIGHT / WIDTH + _xy(move_y) * HEIGHT / WIDTH
    x2 = _xy(x + size / 2) + _xy(move_x)
    y2 = _xy(y + size / 2) * HEIGHT / WIDTH + _xy(move_y) * HEIGHT / WIDTH
    box = (x1, y1, x2, y2)

    if kind in ("circle", "ellipse"):
        if amount >= 1 and fill:
            draw.ellipse(box, fill=fill)
        draw.arc(box, 0, int(360 * amount), fill=color, width=width)
        return

    if kind == "rect":
        if amount >= 1 and fill:
            draw.rectangle(box, fill=fill)
        draw.rectangle(box, outline=color, width=width)
        return

    if kind == "text":
        label = str(element.get("text", element.get("label", "")))[:100]
        if not label:
            return
        font_size = max(14, min(100, int(element.get("font_size", 34))))
        font = _font(font_size, bool(element.get("bold", False)))
        visible_chars = max(1, int(len(label) * amount))
        draw.text(
            (x1, y1),
            label[:visible_chars],
            font=font,
            fill=color,
        )
        return

    if kind == "arc":
        draw.arc(box, 0, int(360 * amount), fill=color, width=width)
        return

    # Unknown element types are skipped instead of crashing a render.


def render_visual_plan(frame, visual_plan, progress):
    """Draw one scene's generated visual plan onto a frame."""
    if not isinstance(visual_plan, dict):
        return frame

    progress = max(0.0, min(1.0, float(progress)))
    elements = visual_plan.get("elements", [])

    if not isinstance(elements, list):
        return frame

    # Draw elements in the order supplied by the story model.
    overlay = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    for element in elements:
        if not isinstance(element, dict):
            continue

        amount = _progress_for_element(element, progress)
        if amount <= 0:
            continue

        _draw_element(draw, element, amount, progress)

    frame_rgba = frame.convert("RGBA")
    result = Image.alpha_composite(frame_rgba, overlay)
    return result.convert("RGB")


def validate_visual_plan(plan):
    """Raise ValueError for malformed visual plans."""
    if not isinstance(plan, dict):
        raise ValueError("visual_plan must be an object.")

    elements = plan.get("elements")

    if not isinstance(elements, list):
        raise ValueError("visual_plan.elements must be a list.")

    if len(elements) > 35:
        raise ValueError("A scene may contain at most 35 drawing elements.")

    allowed = {
        "line", "path", "polyline", "polygon",
        "circle", "ellipse", "rect", "text", "arc",
    }

    for index, element in enumerate(elements, 1):
        if not isinstance(element, dict):
            raise ValueError(f"Visual element {index} must be an object.")

        kind = str(element.get("type", "")).lower()

        if kind not in allowed:
            raise ValueError(
                f"Visual element {index}: unsupported type {kind!r}."
            )

        for key in ("draw_at", "draw_duration"):
            if key in element:
                value = float(element[key])
                if not 0 <= value <= 1:
                    raise ValueError(
                        f"Visual element {index}: {key} must be between 0 and 1."
                    )

        if kind in ("line", "path", "polyline", "polygon"):
            points = element.get("points")
            minimum = 3 if kind == "polygon" else 2

            if not isinstance(points, list) or len(points) < minimum:
                raise ValueError(
                    f"Visual element {index}: invalid points list."
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
                        f"Visual element {index}: points must use 0-100 coordinates."
                    )

        elif kind in ("circle", "ellipse", "rect", "arc"):
            for key in ("x", "y", "size"):
                value = float(element.get(key, 50 if key != "size" else 10))
                if not 0 <= value <= 100:
                    raise ValueError(
                        f"Visual element {index}: {key} must be between 0 and 100."
                    )

        elif kind == "text":
            if not isinstance(element.get("text", element.get("label", "")), str):
                raise ValueError(
                    f"Visual element {index}: text must be a string."
                )

    return plan
