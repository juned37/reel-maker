
"""Topic-independent hand-drawn illustration renderer."""

import math
from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1080, 1920

PALETTE = {
    "ink": (75, 62, 49),
    "gold": (176, 128, 36),
    "paper": (246, 237, 224),
    "pale": (238, 225, 204),
    "muted": (157, 132, 101),
    "blue": (112, 145, 160),
    "green": (126, 145, 105),
    "red": (170, 105, 83),
    "white": (255, 252, 245),
    "dark": (55, 48, 42),
}


def color(value, default=None):
    if default is None:
        default = PALETTE["ink"]

    if isinstance(value, str):
        return PALETTE.get(value.lower(), default)

    if (
        isinstance(value, (list, tuple))
        and len(value) == 3
        and all(isinstance(v, int) and 0 <= v <= 255 for v in value)
    ):
        return tuple(value)

    return default


def xy(value):
    return float(value) * WIDTH / 100


def point(value):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("Point must be [x, y].")

    return (xy(value[0]), xy(value[1]))


def get_font(size, bold=False):
    paths = (
        [
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
        ]
        if bold else [
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
        ]
    )

    for path in paths:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass

    return ImageFont.load_default()


def partial_line(draw, points, amount, fill, width):
    if len(points) < 2 or amount <= 0:
        return

    lengths = [
        math.dist(a, b)
        for a, b in zip(points, points[1:])
    ]

    total = sum(lengths)

    if total <= 0:
        return

    remaining = total * min(1.0, amount)
    output = [points[0]]

    for a, b, length in zip(points, points[1:], lengths):
        if remaining >= length:
            output.append(b)
            remaining -= length
        else:
            if length:
                ratio = remaining / length
                output.append((
                    a[0] + (b[0] - a[0]) * ratio,
                    a[1] + (b[1] - a[1]) * ratio,
                ))
            break

    if len(output) > 1:
        draw.line(output, fill=fill, width=width, joint="curve")


def draw_arrowhead(draw, start, end, fill, width):
    """Draw an arrowhead at the end of a line."""
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length = math.hypot(dx, dy)

    if length <= 0:
        return

    ux = dx / length
    uy = dy / length

    head_length = max(16, width * 4)
    head_width = max(10, width * 2.5)

    base_x = end[0] - ux * head_length
    base_y = end[1] - uy * head_length

    perpendicular_x = -uy
    perpendicular_y = ux

    left = (
        base_x + perpendicular_x * head_width,
        base_y + perpendicular_y * head_width,
    )

    right = (
        base_x - perpendicular_x * head_width,
        base_y - perpendicular_y * head_width,
    )

    draw.polygon([end, left, right], fill=fill)


def element_progress(element, progress):
    start = float(element.get("draw_at", 0))
    duration = max(0.01, float(element.get("draw_duration", 0.22)))

    return max(0, min(1, (progress - start) / duration))


def draw_element(draw, element, amount, progress):
    kind = str(element.get("type", "")).lower()
    stroke = color(element.get("color"))

    fill_value = element.get("fill")

    fill = (
        None
        if fill_value in (None, "none", "transparent")
        else color(fill_value, PALETTE["pale"])
    )

    width = max(1, min(18, int(element.get("width", 5))))

    move_x = float(element.get("move_x", 0)) * progress
    move_y = float(element.get("move_y", 0)) * progress

    def shifted(p):
        x, y = p

        return (
            x + xy(move_x),
            y + xy(move_y) * HEIGHT / WIDTH,
        )

    if kind in ("line", "path", "polyline", "polygon", "arrow"):
        points = [
            shifted(point(p))
            for p in element.get("points", [])
        ]

        if kind == "polygon":
            if len(points) < 3:
                return

            if amount >= 1:
                if fill:
                    draw.polygon(points, fill=fill)

                draw.line(
                    points + [points[0]],
                    fill=stroke,
                    width=width,
                )
            else:
                partial_line(
                    draw,
                    points + [points[0]],
                    amount,
                    stroke,
                    width,
                )

        elif kind == "arrow":
            partial_line(draw, points, amount, stroke, width)

            if amount >= 1 and len(points) >= 2:
                draw_arrowhead(
                    draw,
                    points[-2],
                    points[-1],
                    stroke,
                    width,
                )

        else:
            partial_line(draw, points, amount, stroke, width)

        return

    x = float(element.get("x", 50))
    y = float(element.get("y", 50))
    size = max(1, float(element.get("size", 10)))

    pulse = 1 + float(element.get("pulse", 0)) * math.sin(
        progress * math.tau
    )

    left = xy(x - size * pulse / 2) + xy(move_x)

    top = (
        xy(y - size * pulse / 2) * HEIGHT / WIDTH
        + xy(move_y) * HEIGHT / WIDTH
    )

    right = xy(x + size * pulse / 2) + xy(move_x)

    bottom = (
        xy(y + size * pulse / 2) * HEIGHT / WIDTH
        + xy(move_y) * HEIGHT / WIDTH
    )

    box = (left, top, right, bottom)

    if kind in ("circle", "ellipse"):
        if fill and amount >= 1:
            draw.ellipse(box, fill=fill)

        draw.arc(
            box,
            0,
            int(360 * amount),
            fill=stroke,
            width=width,
        )

    elif kind == "rect":
        if fill and amount >= 1:
            draw.rectangle(box, fill=fill)

        draw.rectangle(
            box,
            outline=stroke,
            width=width,
        )

    elif kind == "arc":
        draw.arc(
            box,
            0,
            int(360 * amount),
            fill=stroke,
            width=width,
        )

    elif kind == "text":
        text = str(
            element.get("text", element.get("label", ""))
        )[:100]

        if text:
            font = get_font(
                max(14, min(100, int(element.get("font_size", 34)))),
                bool(element.get("bold", False)),
            )

            visible = max(1, int(len(text) * amount))

            draw.text(
                (left, top),
                text[:visible],
                font=font,
                fill=stroke,
            )


def render_visual_plan(frame, visual_plan, progress):
    """Draw AI-planned elements, revealing them over scene time."""

    if not isinstance(visual_plan, dict):
        return frame

    elements = visual_plan.get("elements", [])

    if not isinstance(elements, list):
        return frame

    progress = max(0, min(1, float(progress)))

    overlay = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    for element in elements:
        if not isinstance(element, dict):
            continue

        amount = element_progress(element, progress)

        if amount > 0:
            draw_element(draw, element, amount, progress)

    return Image.alpha_composite(
        frame.convert("RGBA"),
        overlay,
    ).convert("RGB")


def validate_visual_plan(plan):
    if not isinstance(plan, dict):
        raise ValueError("visual_plan must be an object.")

    elements = plan.get("elements")

    if not isinstance(elements, list):
        raise ValueError("visual_plan.elements must be a list.")

    if len(elements) > 35:
        raise ValueError("A scene may contain at most 35 visual elements.")

    allowed = {
        "line",
        "path",
        "polyline",
        "polygon",
        "arrow",
        "circle",
        "ellipse",
        "rect",
        "text",
        "arc",
    }

    for index, element in enumerate(elements, 1):
        if not isinstance(element, dict):
            raise ValueError(
                f"Visual element {index} must be an object."
            )

        kind = str(element.get("type", "")).lower()

        if kind not in allowed:
            raise ValueError(
                f"Unsupported visual type: {kind!r}"
            )

        for key in ("draw_at", "draw_duration"):
            if key in element and not 0 <= float(element[key]) <= 1:
                raise ValueError(
                    f"{key} must be between 0 and 1."
                )

        if kind in ("line", "path", "polyline", "polygon", "arrow"):
            points = element.get("points")

            minimum = 3 if kind == "polygon" else 2

            if not isinstance(points, list) or len(points) < minimum:
                raise ValueError(
                    f"{kind} requires at least {minimum} points."
                )

            for p in points:
                if (
                    not isinstance(p, (list, tuple))
                    or len(p) != 2
                    or not all(
                        isinstance(v, (int, float)) and 0 <= v <= 100
                        for v in p
                    )
                ):
                    raise ValueError(
                        "Points must be [x, y] in the 0-100 range."
                    )

        if kind in ("circle", "ellipse", "rect", "arc"):
            for key, default in (
                ("x", 50),
                ("y", 50),
                ("size", 10),
            ):
                value = float(element.get(key, default))

                if not 0 <= value <= 100:
                    raise ValueError(
                        f"{key} must be between 0 and 100."
                    )

        if kind == "text":
            value = element.get(
                "text",
                element.get("label", ""),
            )

            if not isinstance(value, str) or len(value) > 100:
                raise ValueError(
                    "Text element must be a string of at most 100 characters."
                )

    return plan
