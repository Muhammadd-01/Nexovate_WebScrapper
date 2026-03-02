"""Module 4 – Website Health Analyzer.

Performs deep technical and SEO health checks on a website including:
- HTTPS, response time, status code
- Viewport, title, meta description, H1, favicon
- Broken links (basic), image alt tag presence
- CMS / tech stack detection
- eCommerce detection, blog presence, app store links
- Schema markup, mixed content, newsletter/contact form detection
- Social media link counting, video embed detection
- Open Graph / Twitter Card meta tags
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
    "Webflow": [
        "webflow.com", "webflow.io",
    ],
    "React": [
        "__next", "_next/static", "react-root", 'id="__next"', 'id="root"',
    ],
    "Angular": [
        "ng-version", "ng-app", "angular.js", "angular.min.js",
    ],
    "Vue.js": [
        "vue.js", "vue.min.js", "__vue__",
    ],
    "Bootstrap": [
        "bootstrap.min.css", "bootstrap.css", "bootstrap.min.js",
    ],
    "Tailwind": [
        "tailwindcss", "tailwind.min.css",
    ],
}

# eCommerce indicators
ECOMMERCE_PATTERNS = [
    "add-to-cart", "addtocart", "shopping-cart", "checkout", "product-detail",
    "woocommerce", "cart-icon", "shopify", "payment", "buy-now",
    "/cart", "/checkout", "/shop", "/products", "/product",
    "stripe.js", "paypal", "square.js", "klarna",
]

# Blog indicators
BLOG_PATTERNS = [
    "/blog", "/news", "/articles", "/post/", "/posts/",
    "category/", "tag/", "read-more", "blog-post",
    "article", "recent-posts", "latest-news",
]

# App Store link indicators
APP_STORE_PATTERNS = [
    "play.google.com", "apps.apple.com", "apple.com/app",
    "app-store", "google-play", "download-app",
    "appstore", "playstore",
]

# Newsletter / subscription indicators
NEWSLETTER_PATTERNS = [
    "mailchimp", "newsletter", "subscribe", "subscription",
    "email-signup", "sign-up", "klaviyo", "convertkit",
    "email_subscribe", "subscribe-form",
]

# Contact form indicators
CONTACT_FORM_PATTERNS = [
    "contact-form", "contact_form", "wpcf7", "contactform",
    'type="submit"', "send-message",
]

# Video embed indicators
VIDEO_PATTERNS = [
    "youtube.com/embed", "player.vimeo.com", "youtube.com/watch",
    "youtu.be", "video", "<video ", "videoId",
]

# Schema.org markup
SCHEMA_PATTERNS = [
    '"@type"', "application/ld+json", "itemtype=\"http://schema.org",
    "itemscope", "schema.org",
]


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
    html = ""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=12, allow_redirects=True)
        analysis.response_time = round(time.time() - start_time, 2)
        analysis.status_code = resp.status_code
        html = resp.text

        # Mixed content check: HTTP resources loaded on HTTPS page
        if analysis.https_enabled and "http://" in html:
            analysis.has_mixed_content = True
        else:
            analysis.has_mixed_content = False

    except requests.exceptions.SSLError:
        analysis.https_enabled = False
        try:
            http_url = url.replace("https://", "http://")
            resp = requests.get(http_url, headers=HEADERS, timeout=12, allow_redirects=True)
            analysis.response_time = round(time.time() - start_time, 2)
            analysis.status_code = resp.status_code
            html = resp.text
            analysis.has_mixed_content = False
        except Exception:
            analysis.response_time = round(time.time() - start_time, 2)
            return analysis
    except Exception:
        analysis.response_time = round(time.time() - start_time, 2)
        return analysis

    if resp.status_code != 200:
        return analysis

    soup = BeautifulSoup(html, "html.parser")
    html_lower = html.lower()

    # ── BASIC SEO ──────────────────────────────────────────────
    viewport = soup.find("meta", attrs={"name": "viewport"})
    analysis.has_viewport = viewport is not None

    title = soup.find("title")
    analysis.has_title = title is not None and bool(title.get_text(strip=True))

    meta_desc = soup.find("meta", attrs={"name": "description"})
    analysis.has_meta_description = meta_desc is not None and bool(
        meta_desc.get("content", "").strip()
    )

    h1 = soup.find("h1")
    analysis.has_h1 = h1 is not None and bool(h1.get_text(strip=True))

    favicon = soup.find("link", rel=lambda x: x and "icon" in " ".join(x).lower() if x else False)
    analysis.has_favicon = favicon is not None

    # ── IMAGES ────────────────────────────────────────────────
    images = soup.find_all("img")
    analysis.images_total = len(images)
    analysis.images_with_alt = sum(
        1 for img in images if img.get("alt", "").strip()
    )

    # ── LINKS ─────────────────────────────────────────────────
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

    for link in internal_links[:8]:
        try:
            r = requests.head(link, headers=HEADERS, timeout=3, allow_redirects=True)
            if r.status_code >= 400:
                broken_count += 1
        except Exception:
            broken_count += 1

    analysis.broken_links_count = broken_count
    analysis.internal_links_count = len(internal_links)

    # ── CMS / TECH STACK ──────────────────────────────────────
    detected_tech: list[str] = []
    for cms, signatures in CMS_SIGNATURES.items():
        for sig in signatures:
            if sig.lower() in html_lower:
                detected_tech.append(cms)
                break

    analysis.tech_stack = detected_tech
    if detected_tech:
        for tech in detected_tech:
            if tech in ("WordPress", "Shopify", "Wix", "Squarespace", "Webflow"):
                analysis.detected_cms = tech
                break
        if not analysis.detected_cms:
            analysis.detected_cms = detected_tech[0]

    # ── OPEN GRAPH / SOCIAL CARDS ─────────────────────────────
    og_title = soup.find("meta", attrs={"property": "og:title"})
    og_image = soup.find("meta", attrs={"property": "og:image"})
    analysis.has_open_graph = og_title is not None or og_image is not None

    twitter_card = soup.find("meta", attrs={"name": "twitter:card"})
    analysis.has_twitter_card = twitter_card is not None

    # ── SCHEMA MARKUP ─────────────────────────────────────────
    analysis.has_schema_markup = any(p in html for p in SCHEMA_PATTERNS)

    # ── eCOMMERCE DETECTION ───────────────────────────────────
    analysis.has_ecommerce = any(p in html_lower for p in ECOMMERCE_PATTERNS)

    # ── BLOG DETECTION ────────────────────────────────────────
    analysis.has_blog = any(p in html_lower for p in BLOG_PATTERNS)

    # ── APP STORE LINKS ───────────────────────────────────────
    analysis.has_app_links = any(p in html_lower for p in APP_STORE_PATTERNS)

    # ── NEWSLETTER / SUBSCRIPTION ─────────────────────────────
    analysis.has_newsletter = any(p in html_lower for p in NEWSLETTER_PATTERNS)

    # ── CONTACT FORM ──────────────────────────────────────────
    analysis.has_contact_form = any(p in html_lower for p in CONTACT_FORM_PATTERNS)

    # ── VIDEO EMBEDS ──────────────────────────────────────────
    analysis.has_video_embeds = any(p in html_lower for p in VIDEO_PATTERNS)

    # ── SOCIAL MEDIA LINKS COUNT ──────────────────────────────
    social_domains = ["instagram.com", "facebook.com", "twitter.com", "linkedin.com",
                      "youtube.com", "tiktok.com", "pinterest.com", "threads.net"]
    social_count = 0
    for a in soup.find_all("a", href=True):
        href = a["href"].lower()
        if any(domain in href for domain in social_domains):
            social_count += 1
    analysis.social_links_count = social_count

    # ── LIVE CHAT ─────────────────────────────────────────────
    chat_patterns = ["intercom", "tawkto", "zendesk", "crisp", "freshchat", "livechat",
                     "tidio", "drift.com", "chatbot", "live-chat"]
    analysis.has_live_chat = any(p in html_lower for p in chat_patterns)

    # ── GOOGLE ANALYTICS / TRACKING ───────────────────────────
    analytics_patterns = ["gtag(", "ga(", "googletagmanager.com", "fbq(", "pixel", "_ga"]
    analysis.has_analytics = any(p in html for p in analytics_patterns)

    # ── HEADING STRUCTURE ─────────────────────────────────────
    h2_tags = soup.find_all("h2")
    h3_tags = soup.find_all("h3")
    analysis.heading_count_h2 = len(h2_tags)
    analysis.heading_count_h3 = len(h3_tags)

    # ── WORD COUNT (approximate page content) ─────────────────
    body = soup.find("body")
    if body:
        text = body.get_text(separator=" ", strip=True)
        analysis.word_count = len(text.split())

    return analysis
