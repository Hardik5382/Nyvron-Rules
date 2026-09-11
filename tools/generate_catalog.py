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

APPS_CONFIG = (
    # Social & Messaging
    {"id": "twitter", "title": "X (Twitter)", "url": "https://mobile.twitter.com", "category": "SOCIAL"},
    {"id": "reddit", "title": "Reddit", "url": "https://www.reddit.com", "category": "SOCIAL"},
    {"id": "threads", "title": "Threads", "url": "https://www.threads.net", "category": "SOCIAL"},
    {"id": "instagram", "title": "Instagram", "url": "https://www.instagram.com", "category": "SOCIAL"},
    {"id": "bluesky", "title": "Bluesky", "url": "https://bsky.app", "category": "SOCIAL"},
    {"id": "mastodon", "title": "Mastodon", "url": "https://mastodon.social", "category": "SOCIAL"},
    {"id": "linkedin", "title": "LinkedIn", "url": "https://www.linkedin.com", "category": "SOCIAL"},
    {"id": "pinterest", "title": "Pinterest", "url": "https://www.pinterest.com", "category": "SOCIAL"},
    {"id": "discord", "title": "Discord", "url": "https://discord.com/app", "category": "SOCIAL"},
    {"id": "telegram", "title": "Telegram Web", "url": "https://web.telegram.org", "category": "SOCIAL"},
    {"id": "whatsapp", "title": "WhatsApp Web", "url": "https://web.whatsapp.com", "category": "SOCIAL"},
    {"id": "facebook", "title": "Facebook", "url": "https://m.facebook.com", "category": "SOCIAL"},

    # Media & Entertainment
    {"id": "youtube", "title": "YouTube", "url": "https://m.youtube.com", "category": "MEDIA"},
    {"id": "twitch", "title": "Twitch", "url": "https://m.twitch.tv", "category": "MEDIA"},
    {"id": "spotify", "title": "Spotify", "url": "https://open.spotify.com", "category": "MEDIA"},
    {"id": "soundcloud", "title": "SoundCloud", "url": "https://m.soundcloud.com", "category": "MEDIA"},
    {"id": "netflix", "title": "Netflix", "url": "https://www.netflix.com", "category": "MEDIA"},
    {"id": "crunchyroll", "title": "Crunchyroll", "url": "https://www.crunchyroll.com", "category": "MEDIA"},
    {"id": "vimeo", "title": "Vimeo", "url": "https://vimeo.com", "category": "MEDIA"},

    # Productivity & Office
    {"id": "notion", "title": "Notion", "url": "https://www.notion.so", "category": "PRODUCTIVITY"},
    {"id": "trello", "title": "Trello", "url": "https://trello.com", "category": "PRODUCTIVITY"},
    {"id": "slack", "title": "Slack", "url": "https://app.slack.com", "category": "PRODUCTIVITY"},
    {"id": "asana", "title": "Asana", "url": "https://app.asana.com", "category": "PRODUCTIVITY"},
    {"id": "canva", "title": "Canva", "url": "https://www.canva.com", "category": "PRODUCTIVITY"},
    {"id": "figma", "title": "Figma", "url": "https://www.figma.com", "category": "PRODUCTIVITY"},
    {"id": "google_docs", "title": "Google Docs", "url": "https://docs.google.com", "category": "PRODUCTIVITY"},
    {"id": "google_drive", "title": "Google Drive", "url": "https://drive.google.com", "category": "PRODUCTIVITY"},
    {"id": "google_sheets", "title": "Google Sheets", "url": "https://sheets.google.com", "category": "PRODUCTIVITY"},

    # Tech, AI & Utilities
    {"id": "github", "title": "GitHub", "url": "https://github.com", "category": "UTILITIES"},
    {"id": "gitlab", "title": "GitLab", "url": "https://gitlab.com", "category": "UTILITIES"},
    {"id": "stackoverflow", "title": "Stack Overflow", "url": "https://stackoverflow.com", "category": "UTILITIES"},
    {"id": "chatgpt", "title": "ChatGPT", "url": "https://chatgpt.com", "category": "UTILITIES"},
    {"id": "claude", "title": "Claude", "url": "https://claude.ai", "category": "UTILITIES"},
    {"id": "duckduckgo", "title": "DuckDuckGo", "url": "https://duckduckgo.com", "category": "UTILITIES"},
    {"id": "wikipedia", "title": "Wikipedia", "url": "https://en.m.wikipedia.org", "category": "EDUCATION"},
    {"id": "archive_org", "title": "Internet Archive", "url": "https://archive.org", "category": "EDUCATION"},
    {"id": "speedtest", "title": "Speedtest", "url": "https://www.speedtest.net", "category": "UTILITIES"},

    # News & Reading
    {"id": "hackernews", "title": "Hacker News", "url": "https://news.ycombinator.com", "category": "NEWS"},
    {"id": "medium", "title": "Medium", "url": "https://medium.com", "category": "NEWS"},
    {"id": "substack", "title": "Substack", "url": "https://substack.com", "category": "NEWS"},
    {"id": "theverge", "title": "The Verge", "url": "https://www.theverge.com", "category": "NEWS"},
    {"id": "bbc", "title": "BBC News", "url": "https://www.bbc.com/news", "category": "NEWS"},
    {"id": "reuters", "title": "Reuters", "url": "https://www.reuters.com", "category": "NEWS"},

    # Shopping & Commerce
    {"id": "amazon", "title": "Amazon", "url": "https://www.amazon.com", "category": "SHOPPING"},
    {"id": "ebay", "title": "eBay", "url": "https://m.ebay.com", "category": "SHOPPING"},
    {"id": "aliexpress", "title": "AliExpress", "url": "https://m.aliexpress.com", "category": "SHOPPING"},
    {"id": "etsy", "title": "Etsy", "url": "https://www.etsy.com", "category": "SHOPPING"},

    # Finance & Crypto
    {"id": "tradingview", "title": "TradingView", "url": "https://www.tradingview.com", "category": "OTHER"},
    {"id": "coinmarketcap", "title": "CoinMarketCap", "url": "https://coinmarketcap.com", "category": "OTHER"},
    {"id": "yahoofinance", "title": "Yahoo Finance", "url": "https://finance.yahoo.com", "category": "OTHER"},
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
    domain_parts = domain.split(".")
    parent_domain = ".".join(domain_parts[-2:]) if len(domain_parts) > 2 else domain
    discovered = [url for _, url in candidates]
    discovered.extend(
        (
            f"{origin.scheme}://{origin.netloc}/apple-touch-icon.png",
            f"https://www.google.com/s2/favicons?domain={quote(domain)}&sz=256",
            f"https://www.google.com/s2/favicons?domain={quote(parent_domain)}&sz=256",
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
    best_image: bytes | None = None
    best_candidate = ""
    best_resolution = 0
    for candidate in icon_candidates(page_url):
        try:
            image_bytes, _ = fetch(candidate)
            with Image.open(io.BytesIO(image_bytes)) as image:
                image.load()
                resolution = min(image.width, image.height)
            if resolution > best_resolution:
                best_image = image_bytes
                best_candidate = candidate
                best_resolution = resolution
            if best_resolution >= 256:
                break
        except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
            failures.append(f"{candidate}: {exc}")
    if best_image is None:
        raise RuntimeError(f"No usable icon found for {title}: {'; '.join(failures)}")
    convert_to_webp(best_image, destination)
    print(f"  {title}: {best_candidate} ({best_resolution}px source)")


def main() -> None:
    ICONS_DIR.mkdir(parents=True, exist_ok=True)
    CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    catalog_apps = []
    expected_icon_files = {f"{app['id']}.webp" for app in APPS_CONFIG}
    for app in APPS_CONFIG:
        filename = app["id"]
        title = app["title"]
        url = app["url"]
        category = app["category"]
        build_icon(title, url, filename)
        catalog_apps.append(
            {
                "title": title,
                "url": url,
                "category": category,
                "iconUrl": f"{CDN_ROOT}/{filename}.webp",
            }
        )

    for existing_icon in ICONS_DIR.glob("*.webp"):
        if existing_icon.name not in expected_icon_files:
            existing_icon.unlink()

    CATALOG_PATH.write_text(
        json.dumps({"apps": catalog_apps}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(catalog_apps)} apps to {CATALOG_PATH}")


if __name__ == "__main__":
    main()
