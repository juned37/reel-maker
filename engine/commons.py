from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://commons.wikimedia.org/w/api.php"
UA = "ReelMakerDocumentary/1.0 (educational video project)"


def _api(params):
    req = urllib.request.Request(
        API + "?" + urllib.parse.urlencode(params),
        headers={"User-Agent": UA}
    )

    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def search_images(query, limit=8):
    data = _api({
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": f"filetype:bitmap {query}",
        "gsrnamespace": 6,
        "gsrlimit": min(max(int(limit), 1), 20),
        "prop": "imageinfo",
        "iiprop": "url|extmetadata",
        "iiurlwidth": 1800
    })

    found = []

    for page in data.get("query", {}).get("pages", {}).values():
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}

        def field(key):
            value = meta.get(key, {}).get("value", "")
            return re.sub(r"<[^>]*>", " ", str(value)).strip()

        url = info.get("thumburl") or info.get("url")

        if url:
            found.append({
                "title": str(page.get("title", "")),
                "url": str(url),
                "source_url": str(info.get("descriptionurl", "")),
                "artist": field("Artist"),
                "license": field("LicenseShortName") or "License not stated",
                "license_url": field("LicenseUrl"),
                "credit": field("Credit")
            })

    return found


def download_image(
    query,
    output_dir="assets/images",
    cache_name=None
):
    from PIL import Image

    folder = Path(output_dir)
    folder.mkdir(parents=True, exist_ok=True)

    safe = re.sub(
        r"[^a-z0-9]+",
        "-",
        (cache_name or query).lower()
    ).strip("-")[:72]

    index_path = folder / "metadata.json"

    try:
        index = (
            json.loads(index_path.read_text(encoding="utf-8"))
            if index_path.exists()
            else {}
        )
    except (OSError, ValueError):
        index = {}

    cached = index.get(safe)

    if cached and Path(cached.get("path", "")).is_file():
        return cached

    for item in search_images(query):

        suffix = Path(
            urllib.parse.urlparse(item["url"]).path
        ).suffix.lower()

        if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
            suffix = ".jpg"

        target = folder / f"{safe}{suffix}"

        try:
            req = urllib.request.Request(
                item["url"],
                headers={"User-Agent": UA}
            )

            with urllib.request.urlopen(req, timeout=45) as response:
                target.write_bytes(response.read())

            with Image.open(target) as image:
                image.verify()

            record = {
                **item,
                "path": str(target),
                "query": query
            }

            index[safe] = record

            index_path.write_text(
                json.dumps(index, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )

            return record

        except Exception:
            target.unlink(missing_ok=True)

    return None


def write_credits(records, path):

    lines = [
        "# Visual asset credits",
        "",
        "Review each source page and license before publishing.",
        ""
    ]

    for record in records:

        lines += [
            f"## {record.get('title') or 'Untitled Commons asset'}",
            f"- Creator: {record.get('artist') or 'Not stated'}",
            f"- License: {record.get('license') or 'Not stated'}",
            f"- License URL: {record.get('license_url') or 'Not supplied'}",
            f"- Source: {record.get('source_url') or 'Not supplied'}",
            ""
        ]

    Path(path).write_text(
        "\n".join(lines),
        encoding="utf-8"
    )
