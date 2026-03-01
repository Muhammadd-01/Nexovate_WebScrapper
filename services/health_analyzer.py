"""Module 4 – Website Health Analyzer.

Performs technical and SEO health checks on a website including:
- HTTPS, response time, status code
- Viewport, title, meta description, H1, favicon
- Broken links (basic), image alt tag presence
- CMS / tech stack detection
"""

import asyncio
import logging
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from models import HealthAnalysis

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}

# CMS / tech detection patterns
CMS_SIGNATURES = {
    "WordPress": [
        "wp-content", "wp-includes", "wp-json",
        'name="generator" content="WordPress',
    ],
    "Shopify": [
        "cdn.shopify.com", "shopify.com", "Shopify.theme",
    ],
    "Wix": [
        "wix.com", "wixpress.com", "wix-code",
    ],
    "Squarespace": [
        "squarespace.com", "squarespace-cdn.com",
        'name="generator" content="Squarespace',
    ],
    "React": [
        "__next", "_next/static", "react-root", 'id="__next"', 'id="root"',
    ],
    "Angular": [
        "ng-version", "ng-app", "angular.js", "angular.min.js",
    ],
    "Bootstrap": [
        "bootstrap.min.css", "bootstrap.css", "bootstrap.min.js",
    ],
}


async def analyze_health(website_url: str) -> HealthAnalysis:
    """Run health analysis on a website."""
    analysis = HealthAnalysis()
    if not website_url:
        return analysis

    base_url = website_url.rstrip("/")
    if not base_url.startswith("http"):
        base_url = "https://" + base_url

    try:
        result = await asyncio.to_thread(_perform_health_check, base_url)
        return result
    except Exception as e:
        logger.error(f"Health analysis error for {base_url}: {e}")
        return analysis


def _perform_health_check(url: str) -> HealthAnalysis:
    """Synchronous health check."""
    analysis = HealthAnalysis()

    # Check HTTPS
    analysis.https_enabled = url.startswith("https://")

    # Fetch with timing
    start_time = time.time()
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10, allow_redirects=True)
        analysis.response_time = round(time.time() - start_time, 2)
        analysis.status_code = resp.status_code
    except requests.exceptions.SSLError:
        analysis.https_enabled = False
        try:
            http_url = url.replace("https://", "http://")
            resp = requests.get(http_url, headers=HEADERS, timeout=10, allow_redirects=True)
            analysis.response_time = round(time.time() - start_time, 2)
            analysis.status_code = resp.status_code
        except Exception:
            return analysis
    except Exception:
        analysis.response_time = round(time.time() - start_time, 2)
        return analysis

    if resp.status_code != 200:
        return analysis

    html = resp.text
    soup = BeautifulSoup(html, "html.parser")

    # Viewport meta tag
    viewport = soup.find("meta", attrs={"name": "viewport"})
    analysis.has_viewport = viewport is not None

    # Title tag
    title = soup.find("title")
    analysis.has_title = title is not None and bool(title.get_text(strip=True))

    # Meta description
    meta_desc = soup.find("meta", attrs={"name": "description"})
    analysis.has_meta_description = meta_desc is not None and bool(
        meta_desc.get("content", "").strip()
    )

    # H1 tag
    h1 = soup.find("h1")
    analysis.has_h1 = h1 is not None and bool(h1.get_text(strip=True))

    # Favicon
    favicon = soup.find("link", rel=lambda x: x and "icon" in " ".join(x).lower() if x else False)
    analysis.has_favicon = favicon is not None

    # Image alt tags
    images = soup.find_all("img")
    analysis.images_total = len(images)
    analysis.images_with_alt = sum(
        1 for img in images if img.get("alt", "").strip()
    )

    # Broken internal links (basic – check first 10)
    broken_count = 0
    internal_links = []
    parsed_base = urlparse(url)
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:"):
            continue
        full_url = urljoin(url, href)
        parsed_link = urlparse(full_url)
        if parsed_link.netloc == parsed_base.netloc:
            internal_links.append(full_url)

    # Check up to 10 internal links
    for link in internal_links[:10]:
        try:
            r = requests.head(link, headers=HEADERS, timeout=3, allow_redirects=True)
            if r.status_code >= 400:
                broken_count += 1
        except Exception:
            broken_count += 1

    analysis.broken_links_count = broken_count

    # CMS / Tech stack detection
    detected_tech: list[str] = []
    html_lower = html.lower()
    for cms, signatures in CMS_SIGNATURES.items():
        for sig in signatures:
            if sig.lower() in html_lower:
                detected_tech.append(cms)
                break

    analysis.tech_stack = detected_tech
    if detected_tech:
        # Primary CMS is the first non-framework detection
        for tech in detected_tech:
            if tech in ("WordPress", "Shopify", "Wix", "Squarespace"):
                analysis.detected_cms = tech
                break
        if not analysis.detected_cms:
            analysis.detected_cms = detected_tech[0]

    return analysis
