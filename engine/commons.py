
import html
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from pathlib import Path


API = "https://commons.wikimedia.org/w/api.php"

# Set WIKIMEDIA_CONTACT as a GitHub Actions variable if you
# want to include a project contact address in the User-Agent.
CONTACT = os.getenv("WIKIMEDIA_CONTACT", "").strip()

USER_AGENT = (
    "ReelMakerDocumentary/1.1 "
    "(educational documentary asset downloader)"
    + (f" ({CONTACT})" if CONTACT else "")
)

RATE_LIMITED_UNTIL = 0


def _request(url, timeout=35, attempts=3):

    global RATE_LIMITED_UNTIL

    if time.time() < RATE_LIMITED_UNTIL:
        return None

    for attempt in range(attempts):

        request = urllib.request.Request(
            url,
            headers={"User-Agent": USER_AGENT}
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=timeout
            ) as response:
                return response.read()

        except urllib.error.HTTPError as exc:

            if exc.code == 429:

                retry_after = exc.headers.get("Retry-After", "")

                try:
                    wait = min(60, max(5, int(retry_after)))
                except (TypeError, ValueError):
                    wait = min(60, 10 * (2 ** attempt))

                print(
                    f"Wikimedia rate limit reached. "
                    f"Retrying in {wait} seconds..."
                )

                if attempt == attempts - 1:
                    RATE_LIMITED_UNTIL = time.time() + 120
                    print(
                        "Wikimedia is temporarily unavailable. "
                        "Using illustration fallbacks."
                    )
                    return None

                time.sleep(wait)

            elif exc.code in (500, 502, 503, 504):

                if attempt == attempts - 1:
                    print(
                        f"Wikimedia server error: HTTP {exc.code}"
                    )
                    return None

                time.sleep(2 ** attempt)

            else:
                print(f"Wikimedia request failed: HTTP {exc.code}")
                return None

        except (urllib.error.URLError, TimeoutError, OSError) as exc:

            if attempt == attempts - 1:
                print(f"Wikimedia connection failed: {exc}")
                return None

            time.sleep(2 ** attempt)

    return None


def search_images(query, limit=8):

    if time.time() < RATE_LIMITED_UNTIL:
        return []

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

    payload = _request(url)

    if not payload:
        return []

    try:
        data = json.loads(payload)
    except (ValueError, UnicodeDecodeError):
        print("Wikimedia returned an invalid JSON response.")
        return []

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

    # Reuse previously downloaded images.
    if slug in index:

        cached = Path(index[slug].get("path", ""))

        if cached.is_file():
            return index[slug]

    if time.time() < RATE_LIMITED_UNTIL:
        return None

    for item in search_images(query, 10):

        if time.time() < RATE_LIMITED_UNTIL:
            break

        suffix = Path(
            urllib.parse.urlparse(item["url"]).path
        ).suffix.lower()

        if suffix not in (".jpg", ".jpeg", ".png", ".webp"):
            suffix = ".jpg"

        target = folder / (slug + suffix)

        try:

            payload = _request(
                item["url"],
                timeout=60
            )

            if not payload:
                continue

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

        except Exception as exc:

            print(
                f"Could not download Wikimedia image "
                f"for '{query}': {exc}"
            )

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
