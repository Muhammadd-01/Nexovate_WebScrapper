"""Module – Website Liveness Checker.

Quick HEAD/GET check to determine if a website responds with HTTP 200.
Returns True/False for the websiteActive field.
"""

import asyncio
import logging
import requests

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}


async def check_website_active(url: str) -> bool:
    """Check if a website is active (responds with HTTP 200).

    Uses a quick HEAD request first; falls back to GET if HEAD fails.
    Timeout: 5 seconds.
    """
    if not url:
        return False

    # Ensure URL has a scheme
    if not url.startswith("http"):
        url = "https://" + url

    try:
        # Try HEAD first (fastest)
        resp = await asyncio.to_thread(
            requests.head, url, headers=HEADERS, timeout=5, allow_redirects=True
        )
        if resp.status_code == 200:
            return True

        # Some servers block HEAD – fall back to GET
        resp = await asyncio.to_thread(
            requests.get, url, headers=HEADERS, timeout=5, allow_redirects=True
        )
        return resp.status_code == 200

    except Exception as e:
        logger.debug(f"Website check failed for {url}: {e}")
        return False
