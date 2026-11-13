#!/usr/bin/env python3
"""Vertical documentary video generator for Reels and YouTube Shorts."""

from __future__ import annotations
from engine.image_generator import generate_scene_images

import argparse
import json
import math
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

from art import (
    W, H, INK, GOLD, make_base, make_element,
    parse_spec, FIXED, font, make_background
)
from engine.audio import synthesize
from engine.motion import render_motion
from engine.transitions import transition_name, crossfade
from engine.quality import validate_script
from engine.story import generate_documentary
from engine.illustrations import render_visual_plan


WIDTH = 1080
HEIGHT = 1920
FPS = 30

LEAD_SECONDS = 1.2
SCENE_GAP_SECONDS = 0.18
END_SECONDS = 1.0

CAPTION_Y = 1390
CAPTION_WIDTH = 900
CAPTION_MAX_WORDS = 8


def run_checked(command, **kwargs):
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        **kwargs
    )
    if result.returncode != 0:
        raise RuntimeError(
            "Command failed:\n"
            + " ".join(map(str, command))
            + "\n\n"
            + (result.stderr or result.stdout or "No error output")
        )
    return result


def probe_duration(path):
    result = run_checked([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path)
    ])
    return float(result.stdout.strip())


def word_bounds(words, bounds, duration):
    if bounds and len(bounds) == len(words):
        return bounds

    weights = [max(1, len(word)) for word in words]
    total = sum(weights) or 1
    cursor = 0
    output = []
    usable = max(0.1, duration - 0.05)

    for weight in weights:
        start = usable * cursor / total
        cursor += weight
        end = usable * cursor / total
        output.append((start, end))

    return output


def build_audio(scenes, voice, rate, provider, work):
    tracks = []
    timeline = []
    current_time = LEAD_SECONDS

    lead = work / "lead.wav"
    run_checked([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
        "-t", str(LEAD_SECONDS),
        "-ar", "44100", "-ac", "1", str(lead)
    ])
    tracks.append(lead)

    for index, scene in enumerate(scenes):
        narration = scene["narration"].strip()
        words = narration.split()

        audio_path, speech_bounds = synthesize(
            narration,
            voice,
            rate,
            work / f"voice-{index:03d}",
            provider
        )

        speech_duration = probe_duration(Path(audio_path))
        gap = END_SECONDS if index == len(scenes) - 1 else SCENE_GAP_SECONDS
        segment_duration = speech_duration + gap
        normalized = work / f"segment-{index:03d}.wav"

        run_checked([
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", str(audio_path),
            "-af", "apad",
            "-t", f"{segment_duration:.3f}",
            "-ar", "44100", "-ac", "1",
            str(normalized)
        ])
        tracks.append(normalized)

        timed_words = [
            (word, current_time + start, current_time + end)
            for word, (start, end) in zip(
                words,
                word_bounds(words, speech_bounds, speech_duration)
            )
        ]

        timeline.append({
            "start": current_time,
            "speech_end": current_time + speech_duration,
            "end": current_time + segment_duration,
            "words": timed_words
        })
        current_time += segment_duration

    concat_file = work / "audio-list.txt"
    concat_file.write_text(
        "".join(
            f"file '{track.resolve().as_posix()}'\n"
            for track in tracks
        ),
        encoding="utf-8"
    )

    combined = work / "combined.wav"
    run_checked([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_file),
        "-c:a", "pcm_s16le",
        str(combined)
    ])

    return combined, timeline, current_time


def load_scene_images(scenes):
    images = []

    for scene in scenes:
        image_path = scene.get("image")

        if not image_path:
            images.append(None)
            continue

        try:
            with Image.open(image_path) as source:
                images.append(source.convert("RGB").copy())
        except (OSError, TypeError, ValueError):
            print(f"WARNING: Could not open scene image: {image_path}")
            images.append(None)

    return images


def build_legacy_art_elements(scenes, timeline):
    """
    Build illustrations separately for each scene.

    Returning a list per scene prevents illustrations from one scene
    appearing in later scenes. Text illustrations are supported too.
    """
    if len(scenes) != len(timeline):
        raise ValueError(
            "The number of scenes and timeline entries must match."
        )

    scene_elements = []

    for scene_index, (scene, timing) in enumerate(zip(scenes, timeline), 1):
        elements = []

        for spec in scene.get("show", []):
            try:
                name, _, _ = parse_spec(spec)
                image, (x, y) = make_element(spec)

                elements.append({
                    "image": image.convert("RGBA"),
                    "x": int(x),
                    "y": int(y),
                    "show": timing["start"] + 0.15,
                    "hide": timing["end"],
                    "floating": name not in FIXED
                })

            except (TypeError, ValueError, KeyError) as exc:
                raise ValueError(
                    f"Scene {scene_index}: could not build "
                    f"illustration {spec!r}: {exc}"
                ) from exc

        scene_elements.append(elements)

    return scene_elements


def make_fallback_background():
    return make_background().resize(
        (WIDTH, HEIGHT),
        Image.Resampling.LANCZOS
    )


def draw_scene_heading(frame, scene, scene_number):
    label = scene.get("onscreen_title") or scene.get("label")

    if not label:
        return

    draw = ImageDraw.Draw(frame)
    kicker = font(25, True)
    heading = font(54, True)

    while draw.textlength(str(label), font=heading) > 920 and heading.size > 34:
        heading = font(heading.size - 2, True)

    draw.text(
        (WIDTH // 2, 205),
        f"{scene_number:02d}  •  THE STORY",
        font=kicker,
        fill=(154, 119, 65),
        anchor="mm"
    )
    draw.text(
        (WIDTH // 2, 285),
        str(label),
        font=heading,
        fill=INK,
        anchor="mm"
    )
    draw.line(
        (WIDTH // 2 - 110, 340, WIDTH // 2 - 10, 340),
        fill=GOLD,
        width=3
    )
    draw.polygon([
        (WIDTH // 2, 332),
        (WIDTH // 2 + 8, 340),
        (WIDTH // 2, 348),
        (WIDTH // 2 - 8, 340)
    ], fill=GOLD)
    draw.line(
        (WIDTH // 2 + 10, 340, WIDTH // 2 + 110, 340),
        fill=GOLD,
        width=3
    )


def group_caption_phrases(word_entries):
    phrases = []
    current = []

    for item in word_entries:
        current.append(item)
        word = item[0].rstrip("\"'”’)]}")

        sentence_end = word.endswith((".", "?", "!", ";", ":"))

        if sentence_end or len(current) >= CAPTION_MAX_WORDS:
            phrases.append(current)
            current = []

    if current:
        phrases.append(current)

    return phrases


def draw_caption(frame, word_entries, current_time):
    """Display a fixed phrase until the next phrase begins."""
    phrases = group_caption_phrases(word_entries)
    active = None

    for phrase in phrases:
        start = phrase[0][1]
        end = phrase[-1][2]

        if start <= current_time < end:
            active = phrase
            break

    if active is None:
        return

    draw = ImageDraw.Draw(frame)
    caption_font = font(46, True)
    words = [item[0] for item in active]

    lines = []
    current_line = ""

    for word in words:
        candidate = f"{current_line} {word}".strip()

        if (
            current_line
            and draw.textlength(candidate, font=caption_font) > CAPTION_WIDTH
        ):
            lines.append(current_line)
            current_line = word
        else:
            current_line = candidate

    if current_line:
        lines.append(current_line)

    lines = lines[:2]
    line_height = 62
    first_y = CAPTION_Y - (len(lines) - 1) * line_height / 2

    for index, line in enumerate(lines):
        draw.text(
            (WIDTH // 2, first_y + index * line_height),
            line,
            font=caption_font,
            fill=INK,
            anchor="mm",
            align="center"
        )


def apply_legacy_art(frame, elements, current_time):
    for item in elements:
        if current_time < item["show"] or current_time >= item["hide"]:
            continue

        image = item["image"]
        alpha = min(1.0, (current_time - item["show"]) / 0.5)

        if alpha <= 0:
            continue

        if alpha < 0.999:
            image = image.copy()
            channel = image.getchannel("A")
            channel = channel.point(
                lambda value, factor=alpha: int(value * factor)
            )
            image.putalpha(channel)

        dy = (
            int(math.sin(current_time * 1.4) * 4)
            if item["floating"] else 0
        )

        frame.paste(
            image,
            (item["x"], item["y"] + dy),
            image
        )


def create_title_card(data):
    return make_base(data).convert("RGB").resize(
        (WIDTH, HEIGHT),
        Image.Resampling.LANCZOS
    )


def render_scene_frame(
    scene_index,
    now,
    scenes,
    images,
    timeline,
    art_elements,
    words_by_scene,
    style
):
    scene = scenes[scene_index]
    timing = timeline[scene_index]

    span = max(0.1, timing["speech_end"] - timing["start"])
    progress = min(
        1.0,
        max(0.0, (now - timing["start"]) / span)
    )

    frame = make_fallback_background()

    if style == "photographic" and images[scene_index] is not None:
        render_motion(frame, images[scene_index], progress, scene)

    else:
        plan = scene.get("visual_plan")

        if plan:
            frame = render_visual_plan(frame, plan, progress)
        else:
            # Only the current scene's illustrations are rendered.
            apply_legacy_art(
                frame,
                art_elements[scene_index],
                now
            )

    draw_scene_heading(frame, scene, scene_index + 1)
    draw_caption(frame, words_by_scene[scene_index], now)

    return frame


def render(script_path, output_path, provider="edge", style=None):
    script_path = Path(script_path)
    output_path = Path(output_path)

    if not script_path.is_file():
        raise FileNotFoundError(f"Script not found: {script_path}")

    data = json.loads(script_path.read_text(encoding="utf-8"))
    validate_script(data)

    scenes = data["scenes"]
    style = (style or data.get("visual_style", "illustrated")).lower()

    if style not in {"illustrated", "editorial", "photographic"}:
        raise ValueError(
            "Visual style must be illustrated, editorial or photographic."
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="reel-maker-"))

    try:
        audio, timeline, total_duration = build_audio(
            scenes,
            data.get("voice", "en-US-GuyNeural"),
            data.get("rate", "-3%"),
            provider,
            work
        )

        # Illustrated mode deliberately ignores downloaded web photographs.
        images = (
            load_scene_images(scenes)
            if style == "photographic"
            else [None] * len(scenes)
        )

        art_elements = build_legacy_art_elements(scenes, timeline)
        title_card = create_title_card(data)
        words_by_scene = [item["words"] for item in timeline]

        command = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "rawvideo",
            "-pix_fmt", "rgb24",
            "-s:v", f"{WIDTH}x{HEIGHT}",
            "-r", str(FPS),
            "-i", "-",
            "-i", str(audio),
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "19",
            "-pix_fmt", "yuv420p",
            "-r", str(FPS),
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", "44100",
            "-shortest",
            "-movflags", "+faststart",
            str(output_path)
        ]

        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        total_frames = math.ceil(total_duration * FPS)
        previous_frame = None
        transition_from = title_card.copy()
        transition_started = 0.0
        last_scene_index = -1
        scene_index = 0

        try:
            for frame_number in range(total_frames):
                now = frame_number / FPS

                while (
                    scene_index < len(timeline) - 1
                    and now >= timeline[scene_index]["end"]
                ):
                    scene_index += 1

                if scene_index != last_scene_index:
                    transition_from = (
                        previous_frame.copy()
                        if previous_frame is not None
                        else title_card.copy()
                    )

                    transition_started = (
                        LEAD_SECONDS if scene_index == 0 else now
                    )
                    last_scene_index = scene_index

                if now < LEAD_SECONDS:
                    frame = title_card.copy()

                else:
                    frame = render_scene_frame(
                        scene_index,
                        now,
                        scenes,
                        images,
                        timeline,
                        art_elements,
                        words_by_scene,
                        style
                    )

                    scene = scenes[scene_index]

                    if (
                        transition_name(scene) == "crossfade"
                        and now - transition_started < 0.35
                    ):
                        blend_progress = min(
                            1.0,
                            max(
                                0.0,
                                (now - transition_started) / 0.35
                            )
                        )

                        frame = crossfade(
                            transition_from,
                            frame,
                            blend_progress
                        )

                if frame.size != (WIDTH, HEIGHT):
                    frame = frame.resize(
                        (WIDTH, HEIGHT),
                        Image.Resampling.LANCZOS
                    )

                process.stdin.write(frame.convert("RGB").tobytes())
                previous_frame = frame

                if frame_number and frame_number % (FPS * 15) == 0:
                    print(
                        f"Rendered {frame_number}/{total_frames} frames"
                    )

        except (BrokenPipeError, OSError) as exc:
            raise RuntimeError(
                "FFmpeg stopped while receiving video frames."
            ) from exc

        finally:
            if process.stdin and not process.stdin.closed:
                process.stdin.close()

        stderr = (
            process.stderr.read().decode("utf-8", errors="replace")
            if process.stderr else ""
        )
        return_code = process.wait()

        if return_code != 0:
            raise RuntimeError(f"FFmpeg rendering failed:\n{stderr}")

        if not output_path.is_file() or output_path.stat().st_size == 0:
            raise RuntimeError(
                "FFmpeg did not create a valid output file."
            )

        actual_duration = probe_duration(output_path)

        notes = [
            f"# {' '.join(data.get('title', []))}",
            "",
            "## Production details",
            f"- Format: vertical 9:16 ({WIDTH}x{HEIGHT})",
            f"- Frame rate: {FPS} FPS",
            "- Video: H.264",
            "- Audio: AAC narration",
            f"- Visual style: {style}",
            f"- Duration: {actual_duration:.2f} seconds",
            "",
            "## Claims to verify before publication",
            "",
        ]

        notes.extend(
            f"- {claim}"
            for claim in data.get("claims_to_verify", [])
        )
        notes.extend(["", "## Scene notes", ""])

        for index, scene in enumerate(scenes, 1):
            if scene.get("source_notes"):
                notes.append(
                    f"- Scene {index}: {scene['source_notes']}"
                )

        (output_path.parent / "render-notes.md").write_text(
            "\n".join(notes) + "\n",
            encoding="utf-8"
        )

        print(f"Video created: {output_path}")
        print(f"Duration: {actual_duration:.2f} seconds")

    finally:
        shutil.rmtree(work, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(
        dest="command",
        required=True
    )

    generate_parser = commands.add_parser("generate")
    generate_parser.add_argument("topic")
    generate_parser.add_argument("output")
    generate_parser.add_argument(
        "--minutes",
        type=float,
        default=3.0
    )

    render_parser = commands.add_parser("render")
    render_parser.add_argument("script")
    render_parser.add_argument("output")
    render_parser.add_argument(
        "--tts",
        choices=("edge", "espeak"),
        default="edge"
    )
    render_parser.add_argument(
        "--style",
        choices=("illustrated", "editorial", "photographic"),
        default=None,
        help="Visual style (default: illustrated)."
    )

    args = parser.parse_args()

    if args.command == "generate":
        generate_documentary(
            args.topic,
            args.output,
            args.minutes
        )
    else:
        render(
            args.script,
            args.output,
            args.tts,
            args.style
        )


if __name__ == "__main__":
    main()
