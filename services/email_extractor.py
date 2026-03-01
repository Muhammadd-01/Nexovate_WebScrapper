"""Module 2 – Website Email Extraction.

Visits homepage and common contact pages to extract business emails
using regex. Filters out image files, duplicates, and noreply addresses.
"""

import asyncio
import logging
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp", ".ico"}
NOREPLY_PATTERNS = {"noreply", "no-reply", "donotreply", "do-not-reply"}

CONTACT_PATHS = [
    "/",
    "/contact",
    "/contact-us",
    "/about",
    "/about-us",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


async def extract_email(website_url: str) -> str:
    """Extract the first valid business email from a website.

    Visits homepage and common contact/about pages.
    Returns the first valid email found, or empty string.
    """
    if not website_url:
        return ""

    # Normalize URL
    base_url = website_url.rstrip("/")
    if not base_url.startswith("http"):
        base_url = "https://" + base_url

    found_emails: list[str] = []

    for path in CONTACT_PATHS:
        url = urljoin(base_url + "/", path.lstrip("/")) if path != "/" else base_url
        try:
            html = await asyncio.to_thread(_fetch_page, url)
            if html:
                emails = _extract_emails_from_html(html)
                found_emails.extend(emails)
        except Exception as e:
            logger.debug(f"Email extraction error for {url}: {e}")

        # Delay between page requests
        await asyncio.sleep(1.5)

        # If we already found a good email, stop early
        if found_emails:
            break

    # Deduplicate and return the best email
    seen = set()
    for email in found_emails:
        email_lower = email.lower()
        if email_lower not in seen and _is_valid_email(email_lower):
            return email_lower
        seen.add(email_lower)

    return ""


def _fetch_page(url: str) -> str | None:
    """Synchronous page fetch with timeout."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=5, allow_redirects=True)
        if resp.status_code == 200 and "text/html" in resp.headers.get("content-type", ""):
            return resp.text
    except Exception:
        pass
    return None


def _extract_emails_from_html(html: str) -> list[str]:
    """Extract emails from HTML content using regex and mailto links."""
    emails: list[str] = []

    # Parse mailto links first (higher confidence)
    soup = BeautifulSoup(html, "html.parser")
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if href.startswith("mailto:"):
            email = href.replace("mailto:", "").split("?")[0].strip()
            if email and EMAIL_REGEX.match(email):
                emails.append(email)

    # Regex scan on full text
    text = soup.get_text(separator=" ")
    regex_emails = EMAIL_REGEX.findall(text)
    emails.extend(regex_emails)

    # Also scan raw HTML for emails in attributes
    raw_emails = EMAIL_REGEX.findall(html)
    emails.extend(raw_emails)

    return emails


def _is_valid_email(email: str) -> bool:
    """Filter out fake/image/noreply emails."""
    # Check image extensions
    for ext in IMAGE_EXTENSIONS:
        if email.endswith(ext):
            return False

    # Check noreply patterns
    local_part = email.split("@")[0].lower()
    for pattern in NOREPLY_PATTERNS:
        if pattern in local_part:
            return False

    # Basic sanity checks
    if len(email) < 5 or len(email) > 254:
        return False

    # Filter common false positives
    if email.endswith(".wixpress.com") or email.endswith(".sentry.io"):
        return False

    return True
