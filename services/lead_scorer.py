"""Module – Simple Lead Scorer.

Calculates a lead quality score (0–100) based on available contact
and web presence information.

Scoring:
  +30 if website exists
  +20 if email exists
  +20 if websiteActive is True
  +10 if phone exists
  +20 if social media links found
"""

from models import SocialLinks


def calculate_lead_score(biz: dict) -> int:
    """Calculate lead score (0–100) for a business."""
    score = 0

    # +30 if website exists
    if biz.get("website"):
        score += 30

    # +20 if email exists
    if biz.get("email"):
        score += 20

    # +20 if website is active (responds HTTP 200)
    if biz.get("websiteActive"):
        score += 20

    # +10 if phone exists
    if biz.get("phone"):
        score += 10

    # +20 if any social media link found
    socials = biz.get("socials", {})
    if isinstance(socials, dict):
        has_socials = any(
            socials.get(k)
            for k in ["instagram", "facebook", "linkedin", "twitter",
                       "tiktok", "youtube", "pinterest", "threads"]
        )
    elif isinstance(socials, SocialLinks):
        has_socials = any([
            socials.instagram, socials.facebook, socials.linkedin,
            socials.twitter, socials.tiktok, socials.youtube,
            socials.pinterest, socials.threads,
        ])
    else:
        has_socials = False

    if has_socials:
        score += 20

    return min(score, 100)
