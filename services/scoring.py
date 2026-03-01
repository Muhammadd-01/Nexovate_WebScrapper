"""Module 6 – Opportunity Scoring Engine.

Calculates an opportunity score for each business based on
their website quality, performance, SEO, and social presence.
Higher score = better pitch target for website/SEO services.
"""

from models import SocialLinks


def calculate_opportunity_score(business: dict) -> int:
    """Calculate opportunity score (0–100+).

    Logic:
    - No website → 100 (maximum opportunity)
    - Performance < 50 → +30
    - Load time > 4 sec → +20
    - No mobile viewport → +20
    - No meta description → +10
    - Accessibility < 50 → +10
    - No social links → +15
    """
    if not business.get("has_website"):
        return 100

    score = 0

    # Performance score check
    perf = business.get("performance_score", 0)
    if perf < 50:
        score += 30

    # Load time check
    health = business.get("health", {})
    if isinstance(health, dict):
        load_time = health.get("response_time", 0)
    else:
        load_time = getattr(health, "response_time", 0)
    if load_time > 4:
        score += 20

    # Mobile viewport check
    if isinstance(health, dict):
        has_viewport = health.get("has_viewport", False)
    else:
        has_viewport = getattr(health, "has_viewport", False)
    if not has_viewport:
        score += 20

    # Meta description check
    if isinstance(health, dict):
        has_meta = health.get("has_meta_description", False)
    else:
        has_meta = getattr(health, "has_meta_description", False)
    if not has_meta:
        score += 10

    # Accessibility check
    acc = business.get("accessibility_score", 0)
    if acc < 50:
        score += 10

    # Social links check
    socials = business.get("socials", {})
    if isinstance(socials, dict):
        has_socials = any(
            socials.get(k)
            for k in ["instagram", "facebook", "linkedin", "twitter", "tiktok", "youtube"]
        )
    elif isinstance(socials, SocialLinks):
        has_socials = any([
            socials.instagram, socials.facebook, socials.linkedin,
            socials.twitter, socials.tiktok, socials.youtube,
        ])
    else:
        has_socials = False

    if not has_socials:
        score += 15

    return min(score, 100)
