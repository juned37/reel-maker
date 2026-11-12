import json
import sys
import time

from pathlib import Path

from .commons import download_image, write_credits


def prepare(script_path):

    path = Path(script_path)

    data = json.loads(
        path.read_text(encoding="utf-8")
    )

    credits = []
    scenes = data.get("scenes", [])

    for number, scene in enumerate(scenes, 1):

        query = str(
            scene.get("visual_query", "")
        ).strip()

        if not query:
            scene["asset_status"] = "no_query_art_fallback"
            continue

        print(
            f"Preparing asset {number}/{len(scenes)}: {query}"
        )

        try:

            asset = download_image(
                query,
                cache_name=f"scene-{number}-{query}"
            )

        except Exception as exc:

            print(
                f"Asset preparation failed for scene "
                f"{number}: {exc}"
            )

            asset = None

        if asset:

            scene["image"] = asset["path"]

            scene["image_credit"] = {
                key: asset.get(key, "")
                for key in (
                    "title",
                    "artist",
                    "license",
                    "license_url",
                    "source_url"
                )
            }

            scene["asset_status"] = "downloaded"
            credits.append(asset)

        else:

            scene.pop("image", None)
            scene["asset_status"] = "not_found_art_fallback"

            print(
                f"No image available for scene {number}. "
                "The renderer will use its illustration fallback."
            )

        # Avoid sending requests too quickly.
        time.sleep(1.5)

    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    write_credits(
        credits,
        path.parent / "asset-credits.md"
    )

    print(
        f"Asset preparation complete: "
        f"{len(credits)} images downloaded, "
        f"{len(scenes) - len(credits)} scenes using fallback."
    )

    return data


if __name__ == "__main__":

    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: python -m engine.prepare_assets scripts/file.json"
        )

    prepare(sys.argv[1])
