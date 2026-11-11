import html
import json
import re
import urllib.parse
import urllib.request

from pathlib import Path


API = "https://commons.wikimedia.org/w/api.php"

USER_AGENT = (
    "ReelMakerDocumentary/1.0 "
    "(educational documentary project)"
)


def search_images(query, limit=8):

    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": f"filetype:bitmap {query}",
        "gsrnamespace": 6,
        "gsrlimit": min(20, max(1, int(limit))),
        "prop": "imageinfo",
        "iiprop": "url|extmetadata",
        "iiurlwidth": 1800
    }

    url = API + "?" + urllib.parse.urlencode(params)

    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT}
    )

    with urllib.request.urlopen(request, timeout=35) as response:
        data = json.load(response)

    results = []

    for page in data.get("query", {}).get("pages", {}).values():

        info = (page.get("imageinfo") or [{}])[0]
        metadata = info.get("extmetadata") or {}

        def field(name):

            value = metadata.get(name, {}).get("value", "")

            return re.sub(
                r"<[^>]+>",
                "",
                html.unescape(str(value))
            ).strip()

        image_url = info.get("thumburl") or info.get("url")

        if image_url:

            results.append({
                "title": page.get("title", ""),
                "url": image_url,
                "source_url": info.get("descriptionurl", ""),
                "artist": field("Artist"),
                "license": field("LicenseShortName"),
                "license_url": field("LicenseUrl")
            })

    return results


def download_image(
    query,
    output_dir="assets/images",
    cache_name=None
):

    from PIL import Image

    folder = Path(output_dir)
    folder.mkdir(parents=True, exist_ok=True)

    slug = re.sub(
        r"[^a-z0-9]+",
        "-",
        (cache_name or query).lower()
    ).strip("-")[:70]

    if not slug:
        slug = "image"

    index_file = folder / "metadata.json"

    try:
        index = json.loads(
            index_file.read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        index = {}

    if slug in index:

        cached = Path(index[slug].get("path", ""))

        if cached.is_file():
            return index[slug]

    for item in search_images(query, 10):

        suffix = Path(
            urllib.parse.urlparse(item["url"]).path
        ).suffix.lower()

        if suffix not in (".jpg", ".jpeg", ".png", ".webp"):
            suffix = ".jpg"

        target = folder / (slug + suffix)

        try:

            request = urllib.request.Request(
                item["url"],
                headers={"User-Agent": USER_AGENT}
            )

            with urllib.request.urlopen(request, timeout=60) as response:
                payload = response.read()

            if len(payload) < 2048:
                continue

            target.write_bytes(payload)

            with Image.open(target) as image:
                image.verify()

            record = {
                **item,
                "query": query,
                "path": str(target)
            }

            index[slug] = record

            index_file.write_text(
                json.dumps(index, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )

            return record

        except Exception:
            target.unlink(missing_ok=True)

    return None


def write_credits(records, output):

    lines = [
        "# Wikimedia Commons asset credits",
        "",
        "Check each source page and license before publication.",
        ""
    ]

    for item in records:

        lines += [
            f"## {item.get('title', 'Untitled')}",
            f"- Creator: {item.get('artist') or 'Not stated'}",
            f"- License: {item.get('license') or 'Not stated'}",
            f"- License URL: {item.get('license_url') or 'Not supplied'}",
            f"- Source: {item.get('source_url') or 'Not supplied'}",
            ""
        ]

    Path(output).write_text(
        "\n".join(lines),
        encoding="utf-8"
    )
