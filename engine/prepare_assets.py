import json
import sys

from pathlib import Path

from .commons import download_image, write_credits


def prepare(
    script_path,
    output_dir="assets/images"
):

    path = Path(script_path)

    data = json.loads(
        path.read_text(encoding="utf-8")
    )

    credits = []

    for number, scene in enumerate(
        data.get("scenes", []),
        1
    ):

        query = str(
            scene.get("visual_query", "")
        ).strip()

        if not query:
            continue

        asset = download_image(
            query,
            output_dir,
            f"scene-{number}-{query}"
        )

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

            credits.append(asset)

        else:

            scene["asset_status"] = (
                "not_found_use_art_fallback"
            )

    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    write_credits(
        credits,
        path.parent / "asset-credits.md"
    )

    return data


if __name__ == "__main__":

    if len(sys.argv) < 2:
        raise SystemExit(
            "Usage: python -m engine.prepare_assets scripts/file.json"
        )

    prepare(sys.argv[1])
