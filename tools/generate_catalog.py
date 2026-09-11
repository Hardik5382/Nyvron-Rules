#!/usr/bin/env python3
"""Build the Nyvron web-app catalog and its locally hosted WebP icons."""

from __future__ import annotations

import io
import json
import re
import sys
from html import unescape
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urljoin, urlparse
from urllib.request import Request, urlopen

try:
    from PIL import Image
except ImportError as exc:
    raise SystemExit("Pillow is required. Install it with: python -m pip install Pillow") from exc


REPOSITORY = "Hardik5382/Nyvron-Rules"
CDN_ROOT = f"https://cdn.jsdelivr.net/gh/{REPOSITORY}@main/icons"
ROOT = Path(__file__).resolve().parents[1]
ICONS_DIR = ROOT / "icons"
CATALOG_PATH = ROOT / "catalog" / "webapps.json"
USER_AGENT = "Nyvron-Catalog-Generator/1.0"
MAX_DOWNLOAD_BYTES = 8 * 1024 * 1024

APPS = (
    ("X (Twitter)", "https://x.com", "SOCIAL", "x-twitter"),
    ("Reddit", "https://www.reddit.com", "SOCIAL", "reddit"),
    ("Instagram", "https://www.instagram.com", "SOCIAL", "instagram"),
    ("Discord", "https://discord.com/app", "SOCIAL", "discord"),
    ("Facebook", "https://m.facebook.com", "SOCIAL", "facebook"),
    ("LinkedIn", "https://www.linkedin.com", "SOCIAL", "linkedin"),
    ("YouTube", "https://m.youtube.com", "VIDEO", "youtube"),
    ("Twitch", "https://m.twitch.tv", "VIDEO", "twitch"),
    ("TikTok", "https://www.tiktok.com", "VIDEO", "tiktok"),
    ("DuckDuckGo", "https://duckduckgo.com", "SEARCH", "duckduckgo"),
    ("Google", "https://www.google.com", "SEARCH", "google"),
    ("GitHub", "https://github.com", "PRODUCTIVITY", "github"),
    ("Notion", "https://www.notion.so", "PRODUCTIVITY", "notion"),
    ("Wikipedia", "https://en.m.wikipedia.org", "REFERENCE", "wikipedia"),
    ("Hacker News", "https://news.ycombinator.com", "NEWS", "hacker-news"),
    ("BBC News", "https://www.bbc.com/news", "NEWS", "bbc-news"),
    ("Spotify", "https://open.spotify.com", "OTHER", "spotify"),
)

ICON_LINK_RE = re.compile(
    r"<link\b(?=[^>]*\brel\s*=\s*['\"][^'\"]*(?:apple-touch-icon|icon)[^'\"]*['\"])[^>]*>",
    re.IGNORECASE,
)
HREF_RE = re.compile(r"\bhref\s*=\s*(['\"])(.*?)\1", re.IGNORECASE)
SIZES_RE = re.compile(r"\bsizes\s*=\s*(['\"])(.*?)\1", re.IGNORECASE)


def fetch(url: str) -> tuple[bytes, str]:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,image/*,*/*;q=0.8"})
    with urlopen(request, timeout=20) as response:
        declared_length = response.headers.get("Content-Length")
        if declared_length and int(declared_length) > MAX_DOWNLOAD_BYTES:
            raise ValueError(f"response exceeds {MAX_DOWNLOAD_BYTES} bytes")
        data = response.read(MAX_DOWNLOAD_BYTES + 1)
        if len(data) > MAX_DOWNLOAD_BYTES:
            raise ValueError(f"response exceeds {MAX_DOWNLOAD_BYTES} bytes")
        return data, response.headers.get_content_type()


def icon_candidates(page_url: str) -> list[str]:
    candidates: list[tuple[int, str]] = []
    try:
        page_bytes, _ = fetch(page_url)
        html = page_bytes.decode("utf-8", errors="replace")
        for link in ICON_LINK_RE.findall(html):
            href_match = HREF_RE.search(link)
            if not href_match:
                continue
            href = unescape(href_match.group(2).strip())
            size_match = SIZES_RE.search(link)
            dimensions = [int(value) for value in re.findall(r"(\d+)x\d+", size_match.group(2) if size_match else "")]
            candidates.append((max(dimensions, default=0), urljoin(page_url, href)))
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        print(f"  page icon discovery failed: {exc}", file=sys.stderr)

    candidates.sort(key=lambda item: item[0], reverse=True)
    origin = urlparse(page_url)
    domain = origin.hostname or ""
    discovered = [url for _, url in candidates]
    discovered.extend(
        (
            f"{origin.scheme}://{origin.netloc}/apple-touch-icon.png",
            f"https://www.google.com/s2/favicons?domain={quote(domain)}&sz=256",
        )
    )
    return list(dict.fromkeys(discovered))


def convert_to_webp(source: bytes, destination: Path) -> None:
    with Image.open(io.BytesIO(source)) as image:
        image.load()
        image = image.convert("RGBA")
        image.thumbnail((256, 256), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
        canvas.alpha_composite(image, ((256 - image.width) // 2, (256 - image.height) // 2))
        canvas.save(destination, "WEBP", quality=92, method=6)


def build_icon(title: str, page_url: str, filename: str) -> None:
    destination = ICONS_DIR / f"{filename}.webp"
    failures: list[str] = []
    for candidate in icon_candidates(page_url):
        try:
            image_bytes, _ = fetch(candidate)
            convert_to_webp(image_bytes, destination)
            print(f"  {title}: {candidate}")
            return
        except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
            failures.append(f"{candidate}: {exc}")
    raise RuntimeError(f"No usable icon found for {title}: {'; '.join(failures)}")


def main() -> None:
    ICONS_DIR.mkdir(parents=True, exist_ok=True)
    CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    catalog_apps = []
    for title, url, category, filename in APPS:
        build_icon(title, url, filename)
        catalog_apps.append(
            {
                "title": title,
                "url": url,
                "category": category,
                "iconUrl": f"{CDN_ROOT}/{filename}.webp",
            }
        )

    CATALOG_PATH.write_text(
        json.dumps({"apps": catalog_apps}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(catalog_apps)} apps to {CATALOG_PATH}")


if __name__ == "__main__":
    main()
