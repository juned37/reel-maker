#!/usr/bin/env python3
"""Vertical documentary video generator for Reels and YouTube Shorts."""

from __future__ import annotations

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


WIDTH = 1080
HEIGHT = 1920
FPS = 30

LEAD_SECONDS = 1.2
SCENE_GAP_SECONDS = 0.18
END_SECONDS = 1.0

CAPTION_Y = 1390
CAPTION_WIDTH = 900
CAPTION_MAX_WORDS = 7


def run_checked(command: list[str], **kwargs):
    """Run a command and raise a useful error if it fails."""
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


def probe_duration(path: Path) -> float:
    result = run_checked([
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path)
    ])

    return float(result.stdout.strip())


def word_bounds(words, bounds, duration):
    """Use speech timing when available; otherwise estimate by word length."""
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


def build_audio(scenes, voice, rate, provider, work: Path):
    """Create one narration track and a matching scene/word timeline."""
    tracks = []
    timeline = []
    current_time = LEAD_SECONDS

    lead = work / "lead.wav"

    run_checked([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "lavfi",
        "-i", "anullsrc=r=44100:cl=mono",
        "-t", str(LEAD_SECONDS),
        "-ar", "44100",
        "-ac", "1",
        str(lead)
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

        gap = (
            END_SECONDS
            if index == len(scenes) - 1
            else SCENE_GAP_SECONDS
        )

        segment_duration = speech_duration + gap
        normalized = work / f"segment-{index:03d}.wav"

        run_checked([
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", str(audio_path),
            "-af", "apad",
            "-t", f"{segment_duration:.3f}",
            "-ar", "44100",
            "-ac", "1",
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
        "-f", "concat",
        "-safe", "0",
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


def build_art_elements(scenes, timeline):
    """Prepare optional illustrations for scenes without photographs."""
    elements = []

    for scene, timing in zip(scenes, timeline):
        if scene.get("image"):
            continue

        for spec in scene.get("show", []):
            # Scene headings and timed subtitles replace oversized legacy text art.
            if str(spec).strip().startswith("text:"):
                continue
            try:
                image, (x, y) = make_element(spec)
                elements.append({
                    "image": image.convert("RGBA"),
                    "x": int(x),
                    "y": int(y),
                    "show": timing["start"] + 0.15,
                    "hide": timing["end"],
                    "floating": parse_spec(spec)[0] not in FIXED
                })
            except Exception as exc:
                print(f"WARNING: Could not create illustration {spec!r}: {exc}")

    return elements


def make_fallback_background():
    """Warm parchment background used by the editorial illustration style."""
    return make_background().resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)


def draw_scene_heading(frame, scene, scene_number):
    """Small gold section marker and restrained serif scene heading."""
    label = scene.get("onscreen_title") or scene.get("label")
    if not label:
        return
    draw = ImageDraw.Draw(frame)
    kicker = font(25, True)
    heading = font(54, True)
    while draw.textlength(str(label), font=heading) > 920 and heading.size > 34:
        heading = font(heading.size - 2, True)
    draw.text((WIDTH // 2, 205), f"{scene_number:02d}  •  THE STORY", font=kicker,
              fill=(154, 119, 65), anchor="mm")
    draw.text((WIDTH // 2, 285), str(label), font=heading, fill=INK, anchor="mm")
    draw.line((WIDTH//2-110, 340, WIDTH//2-10, 340), fill=GOLD, width=3)
    draw.polygon([(WIDTH//2,332),(WIDTH//2+8,340),(WIDTH//2,348),(WIDTH//2-8,340)], fill=GOLD)
    draw.line((WIDTH//2+10,340,WIDTH//2+110,340), fill=GOLD, width=3)


def draw_caption(frame, word_entries, current_time):
    """Editorial serif subtitles: no dark pill, with the spoken word in gold."""
    active_index = next((i for i, item in enumerate(word_entries)
                         if item[1] <= current_time < item[2]), None)
    if active_index is None:
        return
    start = max(0, active_index - CAPTION_MAX_WORDS + 1)
    selected = word_entries[start:active_index + 1]
    draw = ImageDraw.Draw(frame)
    f = font(48, True)
    words = [item[0] for item in selected]
    # Center each line, keeping the caption airy and readable.
    lines, line = [], []
    for word in words:
        candidate = " ".join(line + [word])
        if line and draw.textlength(candidate, font=f) > CAPTION_WIDTH:
            lines.append(line); line = [word]
        else:
            line.append(word)
    if line: lines.append(line)
    line_height = 64
    y0 = CAPTION_Y - (len(lines) - 1) * line_height // 2
    for row, line_words in enumerate(lines):
        widths = [draw.textlength(w + (" " if i < len(line_words)-1 else ""), font=f)
                  for i, w in enumerate(line_words)]
        x = (WIDTH - sum(widths)) / 2
        y = y0 + row * line_height
        for word, width in zip(line_words, widths):
            # Only the currently spoken word receives the gold accent.
            is_active = word == selected[-1][0] and row == len(lines)-1
            draw.text((x, y), word, font=f, fill=GOLD if is_active else INK)
            x += width


def apply_art_elements(frame, elements, current_time):
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

        dy = 0
        if item["floating"]:
            dy = int(math.sin(current_time * 1.4) * 4)

        frame.paste(
            image,
            (item["x"], item["y"] + dy),
            image
        )


def create_title_card(data):
    """Use the repository's existing artwork as a separate opening card."""
    card = make_base(data).convert("RGB")
    return card.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)


def render_frame(
    scene_index,
    now,
    scenes,
    images,
    timeline,
    art_elements,
    previous_scene_frame,
    title_card
):
    scene = scenes[scene_index]
    timing = timeline[scene_index]

    if now < LEAD_SECONDS:
        frame = title_card.copy()
        return frame

    if images[scene_index] is not None:
        span = max(0.1, timing["speech_end"] - timing["start"])
        progress = min(
            1.0,
            max(0.0, (now - timing["start"]) / span)
        )

        frame = make_fallback_background()
        render_motion(
            frame,
            images[scene_index],
            progress,
            scene
        )
    else:
        frame = make_fallback_background()
        apply_art_elements(frame, art_elements, now)

    draw_scene_heading(frame, scene, scene_index + 1)

    all_words = [
        word
        for item in timeline
        for word in item["words"]
    ]
    draw_caption(frame, all_words, now)

    return frame


def render(script_path, output_path, provider="edge", style=None):
    script_path = Path(script_path)
    output_path = Path(output_path)

    if not script_path.is_file():
        raise FileNotFoundError(f"Script not found: {script_path}")

    data = json.loads(script_path.read_text(encoding="utf-8"))
    validate_script(data)

    scenes = data["scenes"]
    style = (style or data.get("visual_style", "editorial")).lower()
    if style not in {"editorial", "photographic"}:
        raise ValueError("visual_style must be 'editorial' or 'photographic'.")
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

        # Editorial is the default: intentionally ignore downloaded photos so
        # the parchment + hand-drawn visual identity stays consistent.
        images = load_scene_images(scenes) if style == "photographic" else [None] * len(scenes)
        art_elements = build_art_elements(scenes, timeline)
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
                    transition_from = previous_frame.copy() if previous_frame is not None else title_card.copy()
                    transition_started = LEAD_SECONDS if scene_index == 0 else now
                    last_scene_index = scene_index

                if now < LEAD_SECONDS:
                    frame = title_card.copy()
                else:
                    timing = timeline[scene_index]
                    scene = scenes[scene_index]
                    span = max(
                        0.1,
                        timing["speech_end"] - timing["start"]
                    )
                    progress = min(
                        1.0,
                        max(0.0, (now - timing["start"]) / span)
                    )

                    if images[scene_index] is not None:
                        frame = make_fallback_background()
                        render_motion(
                            frame,
                            images[scene_index],
                            progress,
                            scene
                        )
                    else:
                        frame = make_fallback_background()
                        apply_art_elements(frame, art_elements, now)

                    draw_scene_heading(frame, scene, scene_index + 1)
                    draw_caption(frame, words_by_scene[scene_index], now)

                    transition = transition_name(scene)
                    if transition == "crossfade" and now - transition_started < 0.35:
                        blend_progress = min(1.0, max(0.0, (now - transition_started) / 0.35))
                        frame = crossfade(transition_from, frame, blend_progress)

                if frame.size != (WIDTH, HEIGHT):
                    frame = frame.resize(
                        (WIDTH, HEIGHT),
                        Image.Resampling.LANCZOS
                    )

                process.stdin.write(frame.convert("RGB").tobytes())
                previous_frame = frame

                if frame_number and frame_number % (FPS * 15) == 0:
                    print(f"Rendered {frame_number}/{total_frames} frames")

        except (BrokenPipeError, OSError) as exc:
            raise RuntimeError(
                "FFmpeg stopped while receiving video frames."
            ) from exc
        finally:
            if process.stdin and not process.stdin.closed:
                process.stdin.close()

        stderr = process.stderr.read().decode(
            "utf-8",
            errors="replace"
        ) if process.stderr else ""

        return_code = process.wait()

        if return_code != 0:
            raise RuntimeError(f"FFmpeg rendering failed:\n{stderr}")

        if not output_path.is_file() or output_path.stat().st_size == 0:
            raise RuntimeError("FFmpeg did not create a valid output file.")

        actual_duration = probe_duration(output_path)

        notes = [
            f"# {' '.join(data.get('title', []))}",
            "",
            "## Production details",
            f"- Format: vertical 9:16 ({WIDTH}x{HEIGHT})",
            f"- Frame rate: {FPS} FPS",
            "- Video: H.264",
            "- Audio: AAC narration",
            f"- Duration: {actual_duration:.2f} seconds",
            "",
            "## Claims to verify before publication",
            ""
        ]

        notes.extend(
            f"- {claim}"
            for claim in data.get("claims_to_verify", [])
        )

        notes.extend([
            "",
            "## Historical and visual notes",
            ""
        ])

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
    commands = parser.add_subparsers(dest="command", required=True)

    generate_parser = commands.add_parser("generate")
    generate_parser.add_argument("topic")
    generate_parser.add_argument("output")
    generate_parser.add_argument("--minutes", type=float, default=3.0)

    render_parser = commands.add_parser("render")
    render_parser.add_argument("script")
    render_parser.add_argument("output")
    render_parser.add_argument(
        "--tts",
        choices=("edge", "espeak"),
        default="edge"
    )
    render_parser.add_argument(
        "--style", choices=("editorial", "photographic"),
        default=None, help="Visual style (default: script visual_style or editorial)."
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
