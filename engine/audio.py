import asyncio
import shutil
import subprocess
import time
from pathlib import Path


def normalize_rate(rate):
    """
    Convert friendly speed names or numeric values into
    Edge TTS percentage rates.

    Examples:
        medium -> +0%
        slow   -> -10%
        fast   -> +10%
        -3     -> -3%
        -3%    -> -3%
    """
    if rate is None:
        return "+0%"

    value = str(rate).strip().lower()

    presets = {
        "very slow": "-20%",
        "slow": "-10%",
        "medium": "+0%",
        "normal": "+0%",
        "default": "+0%",
        "fast": "+10%",
        "very fast": "+20%",
    }

    if value in presets:
        return presets[value]

    if not value.endswith("%"):
        value = f"{value}%"

    try:
        number = int(value[:-1])
    except ValueError as exc:
        raise ValueError(
            f"Invalid TTS rate: {rate!r}. "
            "Use slow, medium, fast, or a percentage such as -3%."
        ) from exc

    if not -50 <= number <= 100:
        raise ValueError(
            "TTS rate must be between -50% and +100%."
        )

    return f"{number:+d}%"


async def edge_tts_audio(text, voice, rate, output):
    import edge_tts

    communicator = edge_tts.Communicate(
        text=text,
        voice=voice,
        rate=normalize_rate(rate),
        boundary="WordBoundary"
    )

    bounds = []

    with open(output, "wb") as target:
        async for chunk in communicator.stream():

            if chunk["type"] == "audio":
                target.write(chunk["data"])

            elif chunk["type"] == "WordBoundary":
                start = chunk["offset"] / 10_000_000
                end = (
                    start
                    + chunk["duration"] / 10_000_000
                )
                bounds.append((start, end))

    if not output.exists() or output.stat().st_size < 1000:
        raise RuntimeError("Edge TTS returned an empty audio file.")

    return bounds


def run_espeak(text, output):
    executable = shutil.which("espeak-ng")

    if not executable:
        raise RuntimeError(
            "espeak-ng is not installed. "
            "Install it or fix the Edge TTS connection."
        )

    subprocess.run(
        [
            executable,
            "-v", "en-us",
            "-s", "145",
            "-w", str(output),
            text
        ],
        check=True
    )

    if not output.exists() or output.stat().st_size < 1000:
        raise RuntimeError("espeak-ng returned an empty audio file.")

    return output, None


def synthesize(
    text,
    voice,
    rate,
    output_base,
    provider="edge"
):
    if not str(text).strip():
        raise ValueError("Cannot synthesize empty narration.")

    output_base = Path(output_base)
    output_base.parent.mkdir(parents=True, exist_ok=True)

    if provider == "espeak":
        output = Path(str(output_base) + ".wav")
        return run_espeak(text, output)

    if provider != "edge":
        raise ValueError("TTS provider must be edge or espeak.")

    output = Path(str(output_base) + ".mp3")
    output.unlink(missing_ok=True)

    errors = []

    for attempt in range(3):
        try:
            bounds = asyncio.run(
                edge_tts_audio(
                    text,
                    voice,
                    rate,
                    output
                )
            )

            return output, bounds

        except Exception as exc:
            errors.append(str(exc))
            output.unlink(missing_ok=True)

            print(
                f"Edge TTS attempt {attempt + 1}/3 failed: {exc}"
            )

            if attempt < 2:
                time.sleep(2)

    print(
        "Edge TTS failed after 3 attempts. "
        "Trying espeak-ng fallback."
    )

    try:
        return run_espeak(
            text,
            Path(str(output_base) + ".wav")
        )
    except Exception as exc:
        raise RuntimeError(
            "Both Edge TTS and espeak-ng failed.\n"
            + "\n".join(errors)
            + f"\nespeak-ng error: {exc}"
        ) from exc
