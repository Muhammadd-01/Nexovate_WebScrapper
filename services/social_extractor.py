"""Module 3 – Social Media Link Extraction.

Parses <a> tags from a website to find social media profile URLs.
Only stores profile URLs found on the website; does NOT scrape social platforms.
"""

import asyncio
import logging
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from models import SocialLinks

logger = logging.getLogger(__name__)

SOCIAL_DOMAINS = {
    "instagram.com": "instagram",
    "www.instagram.com": "instagram",
    "facebook.com": "facebook",
    "www.facebook.com": "facebook",
    "m.facebook.com": "facebook",
    "linkedin.com": "linkedin",
    "www.linkedin.com": "linkedin",
    "twitter.com": "twitter",
    "www.twitter.com": "twitter",
    "x.com": "twitter",
    "www.x.com": "twitter",
    "tiktok.com": "tiktok",
    "www.tiktok.com": "tiktok",
    "youtube.com": "youtube",
    "www.youtube.com": "youtube",
    "pinterest.com": "pinterest",
    "www.pinterest.com": "pinterest",
    "threads.net": "threads",
    "www.threads.net": "threads",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}


async def extract_socials(website_url: str) -> SocialLinks:
    """Extract social media links from a website's homepage.

    Returns a SocialLinks model with found profile URLs.
    """
    socials = SocialLinks()
    if not website_url:
        return socials

    base_url = website_url.rstrip("/")
    if not base_url.startswith("http"):
        base_url = "https://" + base_url

    try:
        html = await asyncio.to_thread(_fetch_page, base_url)
        if html:
            socials = _parse_social_links(html)
    except Exception as e:
        logger.debug(f"Social extraction error for {base_url}: {e}")

    return socials


def _fetch_page(url: str) -> str | None:
    """Synchronous page fetch."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=5, allow_redirects=True)
        if resp.status_code == 200:
            return resp.text
    except Exception:
        pass
    return None


def _parse_social_links(html: str) -> SocialLinks:
    """Parse HTML for social media links in <a> tags."""
    soup = BeautifulSoup(html, "html.parser")
    result: dict[str, str] = {}
    others: list[str] = []

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].strip()
        if not href or href.startswith("#") or href.startswith("javascript:"):
            continue

        try:
            parsed = urlparse(href)
            domain = parsed.netloc.lower()
        except Exception:
            continue

        if not domain:
            continue

        # Match against known social domains
        platform = SOCIAL_DOMAINS.get(domain)
        if platform and platform not in result:
            # Clean up the URL
            clean_url = href.split("?")[0].rstrip("/")
            result[platform] = clean_url

    return SocialLinks(
        instagram=result.get("instagram", ""),
        facebook=result.get("facebook", ""),
        linkedin=result.get("linkedin", ""),
        twitter=result.get("twitter", ""),
        tiktok=result.get("tiktok", ""),
        youtube=result.get("youtube", ""),
        pinterest=result.get("pinterest", ""),
        threads=result.get("threads", ""),
        others=others,
    )
