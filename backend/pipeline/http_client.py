"""Polite HTTP client for background scraping (§2 / Prompt B.2).

- honors robots.txt (cached per host)
- enforces a minimum interval between requests per host
- sends a clear User-Agent
- caches raw HTML on disk so re-runs don't re-hit the source
"""
from __future__ import annotations

import hashlib
import logging
import os
import time
from urllib.parse import urlparse
from urllib import robotparser

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_last_hit: dict[str, float] = {}
_robots: dict[str, robotparser.RobotFileParser | None] = {}


def _robots_allowed(url: str) -> bool:
    """Consult the site's robots.txt rules **as us** (our User-Agent).

    Important: `RobotFileParser.read()` fetches robots.txt with Python's own
    User-Agent, which bot-protected hosts (Cloudflare) answer with HTTP 403 —
    causing an over-block even when the site's real robots.txt says `Allow: /`.
    So we fetch it ourselves and parse the text.
    """
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    if origin not in _robots:
        _robots[origin] = _load_robots(origin)
    rp = _robots[origin]
    if rp == "disallow-all":
        return False
    if rp is None:
        return True  # no publishable rules; rely on rate limiting + clear UA
    return rp.can_fetch(settings.scrape_user_agent, url)


def _load_robots(origin: str):
    """Return a RobotFileParser, the sentinel "disallow-all", or None."""
    try:
        resp = httpx.get(
            f"{origin}/robots.txt",
            headers={"User-Agent": settings.scrape_user_agent},
            timeout=15,
            follow_redirects=True,
        )
    except httpx.HTTPError as exc:
        logger.warning("robots.txt unreachable for %s: %s", origin, exc)
        return None
    if resp.status_code in (401, 403):
        # RFC 9309: denial of the robots file means "assume fully disallowed".
        logger.info("robots.txt denied (%s) for %s — treating as disallowed",
                    resp.status_code, origin)
        return "disallow-all"
    if resp.status_code >= 400:
        return None
    rp = robotparser.RobotFileParser()
    rp.parse(resp.text.splitlines())
    return rp


def _throttle(url: str) -> None:
    host = urlparse(url).netloc
    elapsed = time.monotonic() - _last_hit.get(host, 0.0)
    wait = settings.scrape_min_interval_seconds - elapsed
    if wait > 0:
        time.sleep(wait)
    _last_hit[host] = time.monotonic()


def _cache_path(url: str) -> str:
    os.makedirs(settings.raw_html_cache_dir, exist_ok=True)
    digest = hashlib.sha1(url.encode()).hexdigest()
    return os.path.join(settings.raw_html_cache_dir, f"{digest}.html")


def fetch_html(url: str, max_age_seconds: int = 3600, force: bool = False) -> str | None:
    """Fetch URL (or return fresh cached copy). Returns None when disallowed."""
    path = _cache_path(url)
    if not force and os.path.exists(path):
        age = time.time() - os.path.getmtime(path)
        if age <= max_age_seconds:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                return fh.read()

    if not _robots_allowed(url):
        logger.warning("robots.txt disallows %s — skipping", url)
        return None

    _throttle(url)
    try:
        resp = httpx.get(
            url,
            headers={"User-Agent": settings.scrape_user_agent},
            timeout=20,
            follow_redirects=True,
        )
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("fetch failed for %s: %s", url, exc)
        return None

    with open(path, "w", encoding="utf-8") as fh:
        fh.write(resp.text)
    return resp.text
