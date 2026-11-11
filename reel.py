#!/usr/bin/env python3
"""Reel Maker: cinematic documentary renderer.

Commands:
  python reel.py generate "topic" scripts/generated.json --minutes 3
  python -m engine.prepare_assets scripts/generated.json
  python reel.py render scripts/generated.json out/video.mp4 --tts edge
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

from art import (
    W, H, INK, GOLD, make_base, make_element,
    parse_spec, FIXED, font
)

from engine.audio import synthesize
from engine.motion import render_motion
from engine.quality import validate_script
from engine.story import generate_documentary


FPS = 30
LEAD = 0.5
SCENE_GAP = 0.25
END_GAP = 0.8


def probe(path):
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path)
        ],
        capture_output=True,
        text=True,
        check=True
    )

    return float(result.stdout.strip())


def word_bounds(words, bounds, duration):

    if bounds and len(bounds) == len(words):
        return bounds

    weights = [max(1, len(word)) for word in words]
    total = sum(weights) or 1

    cursor = 0
    result = []

    usable = max(0.1, duration - 0.08)

    for weight in weights:
        start = usable * cursor / total
        cursor += weight
        end = usable * cursor / total

        result.append((start, end))

    return result


def build_audio(scenes, voice, rate, provider, work):

    tracks = []
    timeline = []
    now = LEAD

    lead = work / "lead.wav"

    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi",
            "-i", "anullsrc=r=44100:cl=mono",
            "-t", str(LEAD),
            "-ar", "44100",
            "-ac", "1",
            str(lead)
        ],
        check=True
    )

    tracks.append(lead)

    for index, scene in enumerate(scenes):

        text = scene["narration"]
        words = text.split()

        audio_path, bounds = synthesize(
            text,
            voice,
            rate,
            work / f"voice-{index:03d}",
            provider
        )

        duration = probe(audio_path)

        gap = (
            END_GAP
            if index == len(scenes) - 1
            else SCENE_GAP
        )

        segment_duration = duration + gap

        normalized = work / f"segment-{index:03d}.wav"

        subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error",
                "-i", str(audio_path),
                "-af", "apad",
                "-t", f"{segment_duration:.3f}",
                "-ar", "44100",
                "-ac", "1",
                str(normalized)
            ],
            check=True
        )

        tracks.append(normalized)

        timed = [
            (word, now + start, now + end)
            for word, (start, end) in zip(
                words,
                word_bounds(words, bounds, duration)
            )
        ]

        timeline.append({
            "start": now,
            "end": now + segment_duration,
            "words": timed
        })

        now += segment_duration

    concat = work / "audio-list.txt"

    concat.write_text(
        "".join(
            f"file '{track.resolve()}'\n"
            for track in tracks
        ),
        encoding="utf-8"
    )

    combined = work / "combined.wav"

    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat),
            "-c", "copy",
            str(combined)
        ],
        check=True
    )

    return combined, timeline, now


def build_art_elements(scenes, timeline):

    elements = []
    active = []

    for scene, timing in zip(scenes, timeline):

        if scene.get("clear"):

            for item in active:
                item["hide"] = timing["start"]

            active = []

        if scene.get("image"):
            continue

        for spec in scene.get("show", []):

            image, (x, y) = make_element(spec)

            item = {
                "image": image.convert("RGB"),
                "mask": image.getchannel("A"),
                "x": x,
                "y": y,
                "floating": parse_spec(spec)[0] not in FIXED,
                "show": timing["start"] + 0.1,
                "hide": None
            }

            elements.append(item)
            active.append(item)

    return elements


def draw_caption(frame, word_entries, current_time):

    visible = [
        word for word in word_entries
        if word[1] <= current_time < word[2]
    ]

    if not visible:
        return

    active = visible[-1]

    candidates = [
        word for word in word_entries
        if active[1] - 2.4 <= word[1] <= active[1]
    ][-7:]

    phrase = " ".join(item[0] for item in candidates)

    draw = ImageDraw.Draw(frame)

    caption_font = font(54, True)

    while (
        draw.textlength(phrase, font=caption_font) > 900
        and caption_font.size > 34
    ):
        caption_font = font(caption_font.size - 2, True)

    draw.rounded_rectangle(
        (55, 1250, 1025, 1450),
        radius=22,
        fill=(250, 245, 235)
    )

    draw.text(
        (W // 2, 1350),
        phrase,
        font=caption_font,
        fill=GOLD,
        anchor="mm",
        align="center"
    )


def render(script_path, output_path, provider="edge"):

    script_path = Path(script_path)

    data = json.loads(
        script_path.read_text(encoding="utf-8")
    )

    validate_script(data)

    scenes = data["scenes"]

    work = Path(
        tempfile.mkdtemp(prefix="reel-maker-")
    )

    audio, timeline, duration = build_audio(
        scenes,
        data.get("voice", "en-US-GuyNeural"),
        data.get("rate", "-3%"),
        provider,
        work
    )

    base = make_base(data)

    art_elements = build_art_elements(
        scenes,
        timeline
    )

    images = []

    for scene in scenes:

        try:
            with Image.open(scene["image"]) as source:
                images.append(source.convert("RGB"))

        except (KeyError, OSError, TypeError):
            images.append(None)

    words = [
        word
        for entry in timeline
        for word in entry["words"]
    ]

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    command = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo",
        "-pix_fmt", "rgb24",
        "-s", f"{W}x{H}",
        "-r", str(FPS),
        "-i", "-",
        "-i", str(audio),
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "160k",
        "-shortest",
        "-movflags", "+faststart",
        str(output_path)
    ]

    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE
    )

    total_frames = math.ceil(duration * FPS)
    scene_index = 0

    try:

        for frame_no in range(total_frames):

            now = frame_no / FPS
            frame = base.copy()

            while (
                scene_index < len(timeline) - 1
                and now >= timeline[scene_index]["end"]
            ):
                scene_index += 1

            timing = timeline[scene_index]
            scene = scenes[scene_index]

            span = max(
                0.1,
                timing["end"] - timing["start"]
            )

            progress = min(
                1.0,
                max(
                    0.0,
                    (now - timing["start"]) / span
                )
            )

            if images[scene_index] is not None:

                render_motion(
                    frame,
                    images[scene_index],
                    progress,
                    scene
                )

            for item in art_elements:

                if now < item["show"]:
                    continue

                alpha = min(
                    1.0,
                    (now - item["show"]) / 0.8
                )

                if item["hide"] is not None:

                    alpha *= max(
                        0.0,
                        1.0 - (now - item["hide"]) / 0.5
                    )

                if alpha <= 0:
                    continue

                dy = (
                    int(
                        5 * math.sin(
                            (now - item["show"]) * 1.5
                        )
                    )
                    if item["floating"]
                    else 0
                )

                mask = item["mask"]

                if alpha < 0.999:

                    mask = mask.point(
                        lambda value, a=alpha:
                        int(value * a)
                    )

                frame.paste(
                    item["image"],
                    (
                        int(item["x"]),
                        int(item["y"]) + dy
                    ),
                    mask
                )

            draw_caption(frame, words, now)

            process.stdin.write(frame.tobytes())

            if frame_no and frame_no % (FPS * 15) == 0:
                print(
                    f"Rendered {frame_no}/{total_frames} frames"
                )

    except BrokenPipeError as exc:

        raise RuntimeError(
            "FFmpeg stopped while receiving video frames."
        ) from exc

    finally:

        if process.stdin and not process.stdin.closed:
            process.stdin.close()

    if process.wait() != 0:
        raise RuntimeError("FFmpeg rendering failed.")

    notes = [
        f"# {' '.join(data.get('title', []))}",
        "",
        "## Claims to verify before publishing",
        ""
    ]

    notes.extend(
        f"- {claim}"
        for claim in data.get("claims_to_verify", [])
    )

    notes.extend([
        "",
        f"Rendered duration: {duration / 60:.2f} minutes",
        f"Spoken words: {sum(len(s['narration'].split()) for s in scenes)}"
    ])

    (output_path.parent / "render-notes.md").write_text(
        "\n".join(notes) + "\n",
        encoding="utf-8"
    )

    print(f"Video created: {output_path}")


def main():

    parser = argparse.ArgumentParser(
        description=__doc__
    )

    commands = parser.add_subparsers(
        dest="command",
        required=True
    )

    gen = commands.add_parser("generate")
    gen.add_argument("topic")
    gen.add_argument("output")
    gen.add_argument("--minutes", type=float, default=3.0)

    ren = commands.add_parser("render")
    ren.add_argument("script")
    ren.add_argument("output")
    ren.add_argument(
        "--tts",
        choices=("edge", "espeak"),
        default="edge"
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
            args.tts
        )


if __name__ == "__main__":
    main()
