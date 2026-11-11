
#!/usr/bin/env python3
"""Upgrade the existing Reel Maker renderer safely."""

from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
REEL = ROOT / "reel.py"
ART = ROOT / "art.py"
MARKER = "REEL_MAKER_CINEMATIC_IMAGE_LAYER"


ART_HELPERS = '''

# REEL_MAKER_CINEMATIC_IMAGE_LAYER

def load_scene_image(scene):
    """Load an optional image for a scene."""
    image_path = scene.get("image")

    if not image_path:
        return None

    path = Path(image_path)

    if not path.is_absolute():
        path = Path.cwd() / path

    try:
        with Image.open(path) as source:
            return source.convert("RGB")
    except (OSError, ValueError) as exc:
        print(f"Warning: cannot load image {path}: {exc}")
        return None


def draw_cinematic_image(frame, image, progress, scene=None):
    """Draw a slowly moving historical image."""
    if image is None:
        return

    scene = scene or {}

    box_w, box_h = 920, 610
    image_w, image_h = image.size

    if image_w <= 0 or image_h <= 0:
        return

    cover = max(
        box_w / image_w,
        box_h / image_h
    )

    progress = max(0.0, min(float(progress), 1.0))
    zoom = 1.035 + 0.065 * progress

    resized_w = max(box_w, int(image_w * cover * zoom))
    resized_h = max(box_h, int(image_h * cover * zoom))

    resized = image.resize(
        (resized_w, resized_h),
        Image.Resampling.LANCZOS
    )

    camera = str(
        scene.get("camera", "slow_push")
    ).lower()

    if "left" in camera:
        center_x = 0.38 + 0.08 * progress
    elif "right" in camera:
        center_x = 0.62 - 0.08 * progress
    else:
        center_x = 0.50

    left = int(max(0, resized_w - box_w) * center_x)
    top = int(max(0, resized_h - box_h) * 0.48)

    crop = resized.crop(
        (left, top, left + box_w, top + box_h)
    )

    shade = Image.new("RGB", crop.size, (24, 20, 16))
    crop = Image.blend(crop, shade, 0.08)

    fade = min(1.0, progress * 5.0)
    mask = Image.new(
        "L",
        (box_w, box_h),
        int(255 * fade)
    )

    x0, y0 = 80, 485
    frame.paste(crop, (x0, y0), mask)

    ImageDraw.Draw(frame).rounded_rectangle(
        (x0, y0, x0 + box_w, y0 + box_h),
        radius=24,
        outline=GOLD,
        width=3
    )
'''


def replace_once(source, old, new, description):
    if old not in source:
        raise RuntimeError(
            f"Could not locate {description} in the original file."
        )

    return source.replace(old, new, 1)


def main():

    if not REEL.is_file() or not ART.is_file():
        raise SystemExit(
            "Place apply_changes.py beside reel.py and art.py."
        )

    reel_source = REEL.read_text(encoding="utf-8")
    art_source = ART.read_text(encoding="utf-8")

    if MARKER in reel_source and MARKER in art_source:
        print("Cinematic upgrade is already installed.")
        return

    # Add image helpers without removing existing illustrations.
    if MARKER not in art_source:

        expected = (
            "from PIL import Image, ImageDraw, ImageFilter, ImageFont"
        )

        if expected not in art_source:
            raise RuntimeError("Unexpected art.py imports.")

        art_source = (
            art_source.rstrip()
            + "\n"
            + ART_HELPERS
            + "\n"
        )

    # Allow more scenes in the existing sanitizer.
    reel_source = replace_once(
        reel_source,
        '(s.get("scenes") or [])[:14]',
        '(s.get("scenes") or [])[:22]',
        "scene limit"
    )

    # Preserve documentary metadata through sanitization.
    old_append = (
        '        out.append({"narration": nar, '
        '"clear": clear, "show": fix + cen})'
    )

    new_append = '''        clean_scene = {
            "narration": nar,
            "clear": clear,
            "show": fix + cen
        }

        for key in (
            "image",
            "visual_query",
            "camera",
            "transition",
            "image_credit",
            "source_notes",
            "asset_status"
        ):
            if key in sc:
                clean_scene[key] = sc[key]

        out.append(clean_scene)'''

    reel_source = replace_once(
        reel_source,
        old_append,
        new_append,
        "scene metadata"
    )

    # Load images once before video rendering.
    setup = (
        'work = Path(tempfile.mkdtemp()); scenes = script["scenes"]; '
        'timeline = []; wavs = []'
    )

    reel_source = replace_once(
        reel_source,
        setup,
        setup
        + "\n    scene_images = [load_scene_image(sc) for sc in scenes]",
        "renderer setup"
    )

    # Do not overlay fallback drawings on downloaded photographs.
    visual_loop = '        for spec in sc.get("show", []):\n'

    reel_source = replace_once(
        reel_source,
        visual_loop,
        '        if sc.get("image"):\n'
        '            continue\n'
        + visual_loop,
        "visual loop"
    )

    # Animate the image belonging to the active scene.
    frame_line = "        t = k / FPS; fr = base.copy()\n"

    frame_code = '''        t = k / FPS; fr = base.copy()

        active_scene = 0

        while (
            active_scene < len(timeline) - 1
            and t >= timeline[active_scene]["t1"]
        ):
            active_scene += 1

        active_timeline = timeline[active_scene]

        duration = max(
            0.1,
            active_timeline["t1"] - active_timeline["t0"]
        )

        progress = min(
            1.0,
            max(
                0.0,
                (t - active_timeline["t0"]) / duration
            )
        )

        draw_cinematic_image(
            fr,
            scene_images[active_scene],
            progress,
            scenes[active_scene]
        )
'''

    reel_source = replace_once(
        reel_source,
        frame_line,
        frame_code,
        "video frame loop"
    )

    # Update the existing short-form prompt.
    reel_source = reel_source.replace(
        "35-60 second faint-minimal animated explainer video",
        "2-5 minute cinematic documentary"
    )

    reel_source = reel_source.replace(
        "6 to 9 scenes, about 90 to 130 spoken words in total.",
        "10 to 22 scenes, with narration matching the requested duration."
    )

    reel_source = replace_once(
        reel_source,
        "from art import *",
        "from art import *  # " + MARKER,
        "renderer marker"
    )

    # Verify syntax before changing the original files.
    compile(art_source, str(ART), "exec")
    compile(reel_source, str(REEL), "exec")

    # Create backups.
    art_backup = ROOT / "art.py.before-cinematic.bak"
    reel_backup = ROOT / "reel.py.before-cinematic.bak"

    if not art_backup.exists():
        shutil.copy2(ART, art_backup)

    if not reel_backup.exists():
        shutil.copy2(REEL, reel_backup)

    # Write updated files.
    ART.write_text(art_source, encoding="utf-8")
    REEL.write_text(reel_source, encoding="utf-8")

    print("Successfully updated reel.py and art.py.")
    print("Backups:")
    print(art_backup.name)
    print(reel_backup.name)


if __name__ == "__main__":
    main()
