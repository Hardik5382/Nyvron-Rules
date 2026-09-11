#!/usr/bin/env python3
"""Build the Nyvron web-app catalog and its locally hosted WebP icons."""

from __future__ import annotations

import io
import json
import re
import sys
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
DASHBOARD_ICONS_ROOT = "https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/png"

# Catalog IDs stay stable for Nyvron. Values here follow Dashboard Icons slugs.
DASHBOARD_ICON_ALIASES = {
    "twitter": ("x", "twitter"),
    "google_docs": ("google-docs",),
    "google_drive": ("google-drive",),
    "google_sheets": ("google-sheets",),
    "stackoverflow": ("stack-overflow",),
    "chatgpt": ("chatgpt", "openai"),
    "archive_org": ("internet-archive",),
    "hackernews": ("hacker-news",),
    "theverge": ("the-verge",),
    "yahoofinance": ("yahoo-finance",),
}

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

LINK_RE = re.compile(r"<link\b[^>]*>", re.IGNORECASE)
HREF_RE = re.compile(r"\bhref\s*=\s*(['\"])(.*?)\1", re.IGNORECASE)
REL_RE = re.compile(r"\brel\s*=\s*(['\"])(.*?)\1", re.IGNORECASE)


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


def dashboard_icon_urls(app_id: str) -> list[str]:
    slugs = DASHBOARD_ICON_ALIASES.get(app_id, (app_id.replace("_", "-"),))
    return [f"{DASHBOARD_ICONS_ROOT}/{slug}.png" for slug in dict.fromkeys(slugs)]


def manifest_urls(page_url: str) -> list[str]:
    discovered: list[str] = []
    try:
        page_bytes, _ = fetch(page_url)
        html = page_bytes.decode("utf-8", errors="replace")
        for link in LINK_RE.findall(html):
            rel_match = REL_RE.search(link)
            href_match = HREF_RE.search(link)
            if not href_match or not rel_match or "manifest" not in rel_match.group(2).lower().split():
                continue
            discovered.append(urljoin(page_url, href_match.group(2).strip()))
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        print(f"  manifest discovery failed: {exc}", file=sys.stderr)
    origin = urlparse(page_url)
    discovered.extend((
        f"{origin.scheme}://{origin.netloc}/manifest.json",
        f"{origin.scheme}://{origin.netloc}/site.webmanifest",
    ))
    return list(dict.fromkeys(discovered))


def manifest_icon_urls(page_url: str) -> list[str]:
    candidates: list[tuple[int, str]] = []
    for manifest_url in manifest_urls(page_url):
        try:
            manifest_bytes, _ = fetch(manifest_url)
            manifest = json.loads(manifest_bytes.decode("utf-8-sig"))
            for icon in manifest.get("icons", []):
                src = icon.get("src")
                if not isinstance(src, str) or not src.strip():
                    continue
                declared_sizes = [
                    min(int(width), int(height))
                    for width, height in re.findall(r"(\d+)x(\d+)", str(icon.get("sizes", "")))
                ]
                largest_size = max(declared_sizes, default=0)
                if largest_size >= 192 or str(icon.get("sizes", "")).lower() == "any":
                    candidates.append((largest_size, urljoin(manifest_url, src.strip())))
        except (HTTPError, URLError, TimeoutError, ValueError, TypeError, json.JSONDecodeError) as exc:
            print(f"  unusable manifest {manifest_url}: {exc}", file=sys.stderr)
    candidates.sort(key=lambda item: item[0], reverse=True)
    return list(dict.fromkeys(url for _, url in candidates))


def google_icon_urls(page_url: str) -> list[str]:
    domain = urlparse(page_url).hostname or ""
    domain_parts = domain.split(".")
    parent_domain = ".".join(domain_parts[-2:]) if len(domain_parts) > 2 else domain
    return list(dict.fromkeys((
        f"https://www.google.com/s2/favicons?domain={quote(domain)}&sz=256",
        f"https://www.google.com/s2/favicons?domain={quote(parent_domain)}&sz=256",
    )))


def image_resolution(source: bytes) -> int:
    with Image.open(io.BytesIO(source)) as image:
        image.load()
        return min(image.width, image.height)


def convert_to_webp(source: bytes, destination: Path) -> None:
    with Image.open(io.BytesIO(source)) as image:
        image.load()
        image = image.convert("RGBA")
        image = image.resize((256, 256), Image.Resampling.LANCZOS)
        image.save(destination, "WEBP", quality=95, method=6)


def download_and_convert_webp(app_id: str, title: str, page_url: str, destination: Path) -> None:
    failures: list[str] = []
    source_tiers = (
        ("dashboard-icons", lambda: dashboard_icon_urls(app_id)),
        ("web-manifest", lambda: manifest_icon_urls(page_url)),
        ("google-favicon", lambda: google_icon_urls(page_url)),
    )
    for source_name, load_candidates in source_tiers:
        for candidate in load_candidates():
            try:
                image_bytes, _ = fetch(candidate)
                resolution = image_resolution(image_bytes)
                convert_to_webp(image_bytes, destination)
                print(f"  {title}: {source_name} {candidate} ({resolution}px source)")
                return
            except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
                failures.append(f"{candidate}: {exc}")
    raise RuntimeError(f"No usable icon found for {title}: {'; '.join(failures)}")


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
        download_and_convert_webp(filename, title, url, ICONS_DIR / f"{filename}.webp")
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
