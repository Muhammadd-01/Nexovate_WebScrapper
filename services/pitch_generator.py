"""Module 9 – Auto Pitch Summary Generator.

Generates a human-readable sales pitch summary for each business
based on their analysis data, highlighting opportunity areas.
"""

from models import SocialLinks


def generate_pitch(business: dict) -> str:
    """Generate a pitch summary for a business.

    Builds a human-readable summary referencing scores,
    missing elements, and opportunity assessment.
    """
    lines: list[str] = []
    name = business.get("name", "This business")

    if not business.get("has_website"):
        lines.append(f"• No website detected")
        lines.append(f"• Opportunity score: 100/100")
        lines.append("")
        lines.append("HIGH PRIORITY: This business has no online presence.")
        lines.append("Excellent opportunity for a full website build, SEO setup, and social media strategy.")
        return "\n".join(lines)

    # Performance
    perf = business.get("performance_score", 0)
    lines.append(f"• Performance score: {perf}/100")

    # SEO
    seo = business.get("seo_score", 0)
    lines.append(f"• SEO score: {seo}/100")

    # Accessibility
    acc = business.get("accessibility_score", 0)
    lines.append(f"• Accessibility score: {acc}/100")

    # Health details
    health = business.get("health", {})
    if isinstance(health, dict):
        h = health
    else:
        h = health.dict() if hasattr(health, "dict") else {}

    if not h.get("has_viewport", False):
        lines.append("• No mobile optimization detected")

    if not h.get("has_meta_description", False):
        lines.append("• No meta description found")

    if not h.get("has_title", False):
        lines.append("• Missing title tag")

    if not h.get("has_h1", False):
        lines.append("• No H1 heading found")

    if not h.get("has_favicon", False):
        lines.append("• No favicon detected")

    if not h.get("https_enabled", False):
        lines.append("• Website not using HTTPS (security risk)")

    load_time = h.get("response_time", 0)
    if load_time > 4:
        lines.append(f"• Slow load time: {load_time}s")

    broken = h.get("broken_links_count", 0)
    if broken > 0:
        lines.append(f"• {broken} broken internal link(s) found")

    # Image alt tags
    total_imgs = h.get("images_total", 0)
    alt_imgs = h.get("images_with_alt", 0)
    if total_imgs > 0 and alt_imgs < total_imgs:
        pct = round(alt_imgs / total_imgs * 100)
        lines.append(f"• Only {pct}% of images have alt tags")

    # Social presence
    socials = business.get("socials", {})
    if isinstance(socials, SocialLinks):
        socials = socials.dict()

    missing_socials = []
    for platform in ["instagram", "facebook", "linkedin", "twitter", "youtube", "tiktok"]:
        if not socials.get(platform):
            missing_socials.append(platform.capitalize())

    if missing_socials:
        lines.append(f"• Missing social profiles: {', '.join(missing_socials)}")

    # Opportunity assessment
    opp_score = business.get("opportunity_score", 0)
    lines.append("")
    lines.append(f"Opportunity score: {opp_score}/100")

    if opp_score >= 70:
        lines.append("HIGH OPPORTUNITY for website redesign and digital marketing upgrade.")
    elif opp_score >= 40:
        lines.append("MODERATE OPPORTUNITY for performance optimization and SEO improvements.")
    else:
        lines.append("LOW OPPORTUNITY – website is reasonably optimized.")

    # CMS note
    cms = h.get("detected_cms", "") or business.get("detected_cms", "")
    if cms:
        lines.append(f"Currently using: {cms}")

    return "\n".join(lines)
