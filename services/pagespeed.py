"""Module 5 – PageSpeed Insights API Integration.

Fetches Lighthouse scores (performance, SEO, accessibility, best practices)
for a given URL using the Google PageSpeed Insights API v5.

Works WITHOUT an API key (rate-limited to ~25 req/day).
With an API key, the rate limit is much higher.
"""

import asyncio
import logging
import requests

logger = logging.getLogger(__name__)

PAGESPEED_API_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"


async def fetch_pagespeed(website_url: str, api_key: str = "") -> dict[str, int]:
    """Fetch PageSpeed Insights scores for a URL.

    Returns dict with keys: performance, seo, accessibility, best_practices.
    All values are integers 0–100.

    Works without API key (free, rate-limited).
    """
    scores = {
        "performance": 0,
        "seo": 0,
        "accessibility": 0,
        "best_practices": 0,
    }

    if not website_url:
        return scores

    url = website_url.rstrip("/")
    if not url.startswith("http"):
        url = "https://" + url

    params = {
        "url": url,
        "category": ["performance", "seo", "accessibility", "best-practices"],
        "strategy": "mobile",
    }

    # API key is optional – works without it (just rate-limited)
    if api_key:
        params["key"] = api_key

    try:
        resp = await asyncio.to_thread(
            requests.get, PAGESPEED_API_URL, params=params, timeout=60
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning(f"PageSpeed API error for {url}: {e}")
        return scores

    try:
        categories = data.get("lighthouseResult", {}).get("categories", {})
        scores["performance"] = int(
            categories.get("performance", {}).get("score", 0) * 100
        )
        scores["seo"] = int(
            categories.get("seo", {}).get("score", 0) * 100
        )
        scores["accessibility"] = int(
            categories.get("accessibility", {}).get("score", 0) * 100
        )
        scores["best_practices"] = int(
            categories.get("best-practices", {}).get("score", 0) * 100
        )
    except Exception as e:
        logger.warning(f"PageSpeed parsing error for {url}: {e}")

    return scores
