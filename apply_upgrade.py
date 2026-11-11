"""Install a cinematic still-image stage into the existing reel.py."""

from pathlib import Path
import shutil


path = Path("reel.py")

if not path.exists():
    raise SystemExit(
        "Run this script from the reel-maker root; reel.py was not found."
    )

source = path.read_text(encoding="utf-8")

if "CINEMATIC_IMAGE_LAYER" in source:
    print("Cinematic image layer already installed.")
    raise SystemExit(0)

backup = Path("reel.py.before-cinematic-upgrade.bak")

if not backup.exists():
    shutil.copy2(path, backup)


source = source.replace(
    "from PIL import Image, ImageDraw",
    "from PIL import Image, ImageDraw\n\n# CINEMATIC_IMAGE_LAYER"
)


anchor = "def render(script_path, out_path, provider):"


helpers = """
def _load_scene_images(scenes):

    loaded = []

    for scene in scenes:

        image_path = scene.get("image")

        try:

            loaded.append(
                Image.open(image_path).convert("RGB")
                if image_path and Path(image_path).is_file()
                else None
            )

        except Exception as exc:

            print(
                f"  warning: could not load image {image_path}: {exc}",
                file=sys.stderr
            )

            loaded.append(None)

    return loaded


def _cinematic_stage(frame, image, progress, scene):

    if image is None:
        return

    box_w, box_h = 920, 640

    iw, ih = image.size

    cover = max(
        box_w / iw,
        box_h / ih
    )

    zoom = 1.04 + 0.075 * min(
        max(progress, 0.0),
        1.0
    )

    rw = max(
        box_w,
        int(iw * cover * zoom)
    )

    rh = max(
        box_h,
        int(ih * cover * zoom)
    )

    resized = image.resize(
        (rw, rh),
        Image.Resampling.LANCZOS
    )

    camera = str(
        scene.get("camera", "slow_push")
    ).lower()

    cx = (
        0.35 if "left" in camera
        else 0.65 if "right" in camera
        else 0.50
    )

    cy = 0.48 + 0.04 * min(
        max(progress, 0.0),
        1.0
    )

    max_x = rw - box_w
    max_y = rh - box_h

    x = int(
        max_x * min(
            max(cx + (progress - 0.5) * 0.10, 0.0),
            1.0
        )
    )

    y = int(
        max_y * min(
            max(cy, 0.0),
            1.0
        )
    )

    crop = resized.crop(
        (x, y, x + box_w, y + box_h)
    )

    crop = Image.blend(
        crop,
        Image.new(
            "RGB",
            crop.size,
            (22, 18, 15)
        ),
        0.10
    )

    mask = Image.new(
        "L",
        (box_w, box_h),
        0
    )

    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, box_w - 1, box_h - 1),
        radius=28,
        fill=255
    )

    fade = min(
        1.0,
        max(0.0, progress * 5.0)
    )

    if fade < 0.999:
        mask = mask.point(
            lambda value: int(value * fade)
        )

    frame.paste(
        crop,
        (80, 470),
        mask
    )

    ImageDraw.Draw(frame).rounded_rectangle(
        (80, 470, 1000, 1110),
        radius=28,
        outline=(176, 128, 36),
        width=3
    )


"""


if anchor not in source:
    raise SystemExit(
        "Could not locate render() function."
    )

source = source.replace(
    anchor,
    helpers + anchor,
    1
)


old = (
    'work = Path(tempfile.mkdtemp()); '
    'scenes = script["scenes"]; timeline = []; wavs = []'
)

new = (
    old +
    '\n    scene_images = _load_scene_images(scenes)'
)

if old not in source:
    raise SystemExit(
        "Could not locate scene initialization."
    )

source = source.replace(
    old,
    new,
    1
)


old_loop = "t = k / FPS; fr = base.copy()"


new_loop = old_loop + """
        # CINEMATIC_IMAGE_LAYER
        active_scene = 0

        while (
            active_scene < len(timeline) - 1
            and t >= timeline[active_scene]["t1"]
        ):
            active_scene += 1

        active_tl = timeline[active_scene]
        active_data = scenes[active_scene]

        span = max(
            0.1,
            active_tl["t1"] - active_tl["t0"]
        )

        progress = min(
            1.0,
            max(
                0.0,
                (t - active_tl["t0"]) / span
            )
        )

        _cinematic_stage(
            fr,
            scene_images[active_scene],
            progress,
            active_data
        )
"""


if old_loop not in source:
    raise SystemExit(
        "Could not locate frame loop."
    )

source = source.replace(
    old_loop,
    new_loop,
    1
)


path.write_text(
    source,
    encoding="utf-8"
)

print(
    "Installed. Original backup:",
    backup
)
