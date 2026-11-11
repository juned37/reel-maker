import asyncio
import shutil
import subprocess
import time

from pathlib import Path


async def edge_tts_audio(text, voice, rate, output):

    import edge_tts

    communicator = edge_tts.Communicate(
        text,
        voice,
        rate=rate,
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

    return bounds


def synthesize(
    text,
    voice,
    rate,
    output_base,
    provider="edge"
):

    if provider == "edge":

        output = Path(
            str(output_base) + ".mp3"
        )

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

                if output.exists() and output.stat().st_size > 1000:
                    return output, bounds

            except Exception as exc:

                print(
                    f"Edge TTS attempt {attempt + 1} failed: {exc}"
                )

                time.sleep(2)

        if not shutil.which("espeak-ng"):

            raise RuntimeError(
                "Edge TTS failed; espeak-ng is not installed"
            )

        provider = "espeak"

    if provider == "espeak":

        output = Path(
            str(output_base) + ".wav"
        )

        subprocess.run(
            [
                "espeak-ng",
                "-v", "en-us",
                "-s", "145",
                "-w", str(output),
                text
            ],
            check=True
        )

        return output, None

    raise ValueError(
        "TTS provider must be edge or espeak"
    )
