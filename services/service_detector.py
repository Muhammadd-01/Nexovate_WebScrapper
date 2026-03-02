"""Module 10 – Service Opportunity Detection Engine.

Analyzes each scraped business and determines which of Nexovate's
11 services are the best fit to pitch, with a confidence score (0–100)
and a human-readable reason for each recommendation.

Output fields added to the business document:
  - recommended_services: list of {service, confidence_score, reason}
  - primary_pitch: the top-scoring service name
  - service_pitch_summary: auto-generated short pitch sentence
"""

# ============================================================
# SERVICE CATALOGUE (reference list)
# ============================================================
ALL_SERVICES = [
    "Full-Stack Web Development",
    "Software Development",
    "Mobile App Development",
    "Graphic & Vector Design",
    "UI/UX Design",
    "Photo Editing",
    "Video Editing",
    "SEO Services",
    "Digital Marketing",
    "Website Maintenance & Support",
    "Shopify Store Development",
]

# Keywords that indicate specific business types
ECOMMERCE_KEYWORDS = ["shop", "store", "ecommerce", "retail", "boutique", "fashion", "clothing", "jewel",
                       "furniture", "electronics", "market", "supermarket", "wholesale", "dealership"]

FOOD_KEYWORDS = ["restaurant", "cafe", "coffee", "bakery", "pizza", "sushi", "grill", "diner",
                  "bistro", "bar", "pub", "brewery", "catering", "food", "kitchen"]

MOBILE_LIKELY_KEYWORDS = ["restaurant", "gym", "fitness", "clinic", "pharmacy", "hospital",
                           "delivery", "school", "university", "hotel", "travel", "salon", "spa",
                           "laundry", "cleaning", "grocery"]

VISUAL_KEYWORDS = ["salon", "spa", "photography", "studio", "fashion", "boutique", "jewel",
                    "restaurant", "cafe", "bakery", "home decor", "architecture", "interior", "art"]

VIDEO_LIKELY_KEYWORDS = ["gym", "fitness", "restaurant", "travel", "hotel", "resort", "school",
                          "real estate", "ecommerce", "retail", "fashion"]

DIGITAL_SERVICE_KEYWORDS = ["saas", "software", "agency", "logistics", "manufacturing", "automation",
                              "consulting", "finance", "legal", "accounting", "insurance", "healthcare",
                              "medical", "clinic", "hospital"]


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def _get_health(biz: dict) -> dict:
    """Safely extract health dict from a business document."""
    h = biz.get("health", {})
    if hasattr(h, "model_dump"):
        return h.model_dump()
    if hasattr(h, "dict"):
        return h.dict()
    return h if isinstance(h, dict) else {}


def _get_socials(biz: dict) -> dict:
    """Safely extract socials dict."""
    s = biz.get("socials", {})
    if hasattr(s, "model_dump"):
        return s.model_dump()
    if hasattr(s, "dict"):
        return s.dict()
    return s if isinstance(s, dict) else {}


def _social_count(socials: dict) -> int:
    """Count how many social platforms are linked."""
    platforms = ["instagram", "facebook", "linkedin", "twitter", "tiktok", "youtube", "pinterest", "threads"]
    return sum(1 for p in platforms if socials.get(p, ""))


def _keyword_matches(keyword: str, word_list: list) -> bool:
    """Check if the business keyword contains any word from the list."""
    kw = keyword.lower()
    return any(w.lower() in kw for w in word_list)


def _cap(score: int) -> int:
    """Cap score between 0 and 100."""
    return max(0, min(100, score))


# ============================================================
# INDIVIDUAL SERVICE DETECTORS
# ============================================================

def _detect_fullstack_web(biz: dict, h: dict) -> tuple[int, str]:
    """Full-Stack Web Development opportunity."""
    reasons = []
    score = 0

    if not biz.get("has_website"):
        return 95, "No website exists — immediately needs a full web presence."

    if not h.get("has_viewport"):
        score += 30
        reasons.append("no mobile responsive design")
    if not h.get("https_enabled"):
        score += 15
        reasons.append("no HTTPS")
    cms = h.get("detected_cms", "") or biz.get("detected_cms", "")
    tech = h.get("tech_stack", [])
    modern = any(t in tech for t in ["React", "Angular", "Next.js", "Vue"])
    if not modern and cms not in ("React", "Angular"):
        score += 20
        reasons.append("no modern JS framework detected")
    if not h.get("has_h1"):
        score += 10
        reasons.append("poor HTML structure")
    if biz.get("performance_score", 0) < 50:
        score += 15
        reasons.append(f"very low performance score ({biz.get('performance_score', 0)}/100)")

    reason = "Website issues: " + ", ".join(reasons) if reasons else "Outdated web presence detected."
    return _cap(score), reason


def _detect_software_dev(biz: dict, h: dict) -> tuple[int, str]:
    """Software Development opportunity."""
    score = 0
    reasons = []
    keyword = biz.get("keyword", "")

    if _keyword_matches(keyword, DIGITAL_SERVICE_KEYWORDS):
        score += 50
        reasons.append(f"business type ({keyword}) typically needs custom software")
    if not biz.get("has_website"):
        score += 20
        reasons.append("no online presence or automated workflows")
    elif not h.get("tech_stack"):
        score += 20
        reasons.append("no detectable software infra")

    if score < 30:
        return 0, ""
    return _cap(score), "Potential for custom software: " + ", ".join(reasons) + "."


def _detect_mobile_app(biz: dict, h: dict) -> tuple[int, str]:
    """Mobile App Development opportunity."""
    score = 0
    reasons = []
    keyword = biz.get("keyword", "")

    if _keyword_matches(keyword, MOBILE_LIKELY_KEYWORDS):
        score += 45
        reasons.append(f"'{keyword}' businesses typically benefit from a mobile app")

    # Check if website has app store links (basic detection)
    # We don't scrape full HTML here, so we infer from lack of data
    if biz.get("has_website") and biz.get("performance_score", 0) > 0:
        # If site exists but no modern framework, probably no app
        tech = h.get("tech_stack", [])
        if not any(t in tech for t in ["React", "Angular"]):
            score += 25
            reasons.append("no app-like tech stack detected")
    elif not biz.get("has_website"):
        score += 30
        reasons.append("no digital presence at all")

    if score < 30:
        return 0, ""
    return _cap(score), "Mobile app opportunity: " + ", ".join(reasons) + "."


def _detect_shopify(biz: dict, h: dict) -> tuple[int, str]:
    """Shopify Store Development opportunity."""
    score = 0
    reasons = []
    keyword = biz.get("keyword", "")
    cms = h.get("detected_cms", "") or biz.get("detected_cms", "")

    if _keyword_matches(keyword, ECOMMERCE_KEYWORDS):
        score += 50
        reasons.append(f"eCommerce / retail business ({keyword})")
        if cms and cms != "Shopify":
            score += 30
            reasons.append(f"currently on {cms}, not Shopify")
        elif not cms:
            score += 20
            reasons.append("no recognizable eCommerce platform detected")
    
    if not biz.get("has_website") and _keyword_matches(keyword, ECOMMERCE_KEYWORDS):
        return 90, "No online store exists for this retail/eCommerce business."

    if score < 40:
        return 0, ""
    return _cap(score), "Shopify opportunity: " + ", ".join(reasons) + "."


def _detect_seo(biz: dict, h: dict) -> tuple[int, str]:
    """SEO Services opportunity."""
    score = 0
    reasons = []

    if not biz.get("has_website"):
        return 80, "No website — needs SEO setup from scratch."

    if not h.get("has_meta_description"):
        score += 25
        reasons.append("no meta description")
    if not h.get("has_h1"):
        score += 20
        reasons.append("no H1 tag")
    perf = biz.get("performance_score", 0)
    if perf < 60 and perf > 0:
        score += 20
        reasons.append(f"performance score {perf}/100")
    if not h.get("has_title"):
        score += 15
        reasons.append("no title tag")
    seo = biz.get("seo_score", 0)
    if seo < 60 and seo > 0:
        score += 15
        reasons.append(f"SEO score only {seo}/100")

    if score < 20:
        return 0, ""
    return _cap(score), "SEO gaps found: " + ", ".join(reasons) + "."


def _detect_digital_marketing(biz: dict, h: dict) -> tuple[int, str]:
    """Digital Marketing opportunity."""
    score = 0
    reasons = []
    socials = _get_socials(biz)
    count = _social_count(socials)

    if count == 0:
        score += 55
        reasons.append("zero social media presence")
    elif count <= 2:
        score += 30
        reasons.append(f"only {count} social platform(s) active")
    
    if not biz.get("has_website"):
        score += 25
        reasons.append("no website or marketing funnel")
    elif biz.get("performance_score", 0) < 50:
        score += 15
        reasons.append("weak online performance")

    if score < 20:
        return 0, ""
    return _cap(score), "Digital marketing opportunity: " + ", ".join(reasons) + "."


def _detect_uiux(biz: dict, h: dict) -> tuple[int, str]:
    """UI/UX Design opportunity."""
    score = 0
    reasons = []

    if not biz.get("has_website"):
        return 70, "No website — needs full UI/UX design from ground up."

    if not h.get("has_viewport"):
        score += 35
        reasons.append("no responsive/mobile design")
    if biz.get("accessibility_score", 0) < 60 and biz.get("accessibility_score", 0) > 0:
        score += 25
        reasons.append(f"accessibility score {biz.get('accessibility_score', 0)}/100")
    if not h.get("has_h1"):
        score += 20
        reasons.append("poor heading structure")
    tech = h.get("tech_stack", [])
    if not any(t in tech for t in ["React", "Angular", "Bootstrap"]):
        score += 15
        reasons.append("no design framework detected")

    if score < 30:
        return 0, ""
    return _cap(score), "UI/UX improvement needed: " + ", ".join(reasons) + "."


def _detect_graphic_design(biz: dict, h: dict) -> tuple[int, str]:
    """Graphic & Vector Design opportunity."""
    score = 0
    reasons = []

    if not h.get("has_favicon"):
        score += 35
        reasons.append("no favicon / brand identity")

    total_imgs = h.get("images_total", 0)
    alt_imgs = h.get("images_with_alt", 0)
    if total_imgs > 0 and alt_imgs < total_imgs * 0.5:
        score += 25
        reasons.append(f"low image quality / alt coverage ({alt_imgs}/{total_imgs} images optimized)")
    
    keyword = biz.get("keyword", "")
    if _keyword_matches(keyword, VISUAL_KEYWORDS):
        score += 30
        reasons.append(f"visual business type ({keyword}) needs strong branding")

    if score < 25:
        return 0, ""
    return _cap(score), "Branding/design gaps: " + ", ".join(reasons) + "."


def _detect_photo_editing(biz: dict, h: dict) -> tuple[int, str]:
    """Photo Editing opportunity."""
    score = 0
    reasons = []
    keyword = biz.get("keyword", "")

    if _keyword_matches(keyword, FOOD_KEYWORDS + VISUAL_KEYWORDS):
        score += 50
        reasons.append(f"'{keyword}' type business relies heavily on visual content")

    total_imgs = h.get("images_total", 0)
    alt_imgs = h.get("images_with_alt", 0)
    if total_imgs > 0:
        if alt_imgs < total_imgs * 0.4:
            score += 25
            reasons.append("poor image optimization detected")
    elif biz.get("has_website"):
        score += 15
        reasons.append("very few images on website")

    if score < 40:
        return 0, ""
    return _cap(score), "Photo editing opportunity: " + ", ".join(reasons) + "."


def _detect_video_editing(biz: dict, h: dict) -> tuple[int, str]:
    """Video Editing opportunity."""
    score = 0
    reasons = []
    keyword = biz.get("keyword", "")
    socials = _get_socials(biz)

    if _keyword_matches(keyword, VIDEO_LIKELY_KEYWORDS):
        score += 40
        reasons.append(f"'{keyword}' businesses thrive with video content")

    # If they have social presence but likely no video (no youtube)
    if _social_count(socials) > 0 and not socials.get("youtube"):
        score += 30
        reasons.append("active on socials but no YouTube channel")

    if _social_count(socials) == 0:
        score += 20
        reasons.append("no social video presence whatsoever")

    if score < 35:
        return 0, ""
    return _cap(score), "Video content opportunity: " + ", ".join(reasons) + "."


def _detect_maintenance(biz: dict, h: dict) -> tuple[int, str]:
    """Website Maintenance & Support opportunity."""
    score = 0
    reasons = []

    if not biz.get("has_website"):
        return 0, ""

    if not h.get("https_enabled"):
        score += 35
        reasons.append("no SSL / HTTPS")
    if h.get("broken_links_count", 0) > 0:
        score += 25
        reasons.append(f"{h.get('broken_links_count', 0)} broken internal link(s)")
    load_time = h.get("response_time", 0)
    if load_time > 4:
        score += 20
        reasons.append(f"slow load time ({load_time}s)")
    cms = h.get("detected_cms", "") or biz.get("detected_cms", "")
    if cms in ("WordPress", "Wix", "Squarespace"):
        score += 15
        reasons.append(f"CMS ({cms}) needs active maintenance")
    if biz.get("performance_score", 0) < 40 and biz.get("performance_score", 0) > 0:
        score += 20
        reasons.append(f"critically low performance ({biz.get('performance_score', 0)}/100)")

    if score < 25:
        return 0, ""
    return _cap(score), "Maintenance needed: " + ", ".join(reasons) + "."


# ============================================================
# DETECTOR REGISTRY
# ============================================================
DETECTORS = {
    "Full-Stack Web Development": _detect_fullstack_web,
    "Software Development": _detect_software_dev,
    "Mobile App Development": _detect_mobile_app,
    "Shopify Store Development": _detect_shopify,
    "SEO Services": _detect_seo,
    "Digital Marketing": _detect_digital_marketing,
    "UI/UX Design": _detect_uiux,
    "Graphic & Vector Design": _detect_graphic_design,
    "Photo Editing": _detect_photo_editing,
    "Video Editing": _detect_video_editing,
    "Website Maintenance & Support": _detect_maintenance,
}


# ============================================================
# MAIN DETECTION FUNCTION
# ============================================================
def detect_services(biz: dict) -> dict:
    """Run all service detectors and return ranked recommendations.

    Args:
        biz: The full business dict after scraping and analysis.

    Returns:
        dict with keys:
            - recommended_services: list of {service, confidence_score, reason}
            - primary_pitch: str (top service name)
            - service_pitch_summary: str (auto-generated pitch)
    """
    h = _get_health(biz)

    recommendations = []
    for service_name, detector in DETECTORS.items():
        try:
            score, reason = detector(biz, h)
            if score > 0:
                recommendations.append({
                    "service": service_name,
                    "confidence_score": score,
                    "reason": reason,
                })
        except Exception:
            pass  # Never let a bad detector break the pipeline

    # Sort by confidence descending
    recommendations.sort(key=lambda x: x["confidence_score"], reverse=True)

    primary = recommendations[0]["service"] if recommendations else ""
    summary = _generate_service_pitch(biz, recommendations)

    return {
        "recommended_services": recommendations,
        "primary_pitch": primary,
        "service_pitch_summary": summary,
    }


def _generate_service_pitch(biz: dict, recommendations: list) -> str:
    """Generate a concise, compelling pitch sentence for this business."""
    name = biz.get("name", "This business")
    has_website = biz.get("has_website", False)

    if not recommendations:
        return f"{name} appears to be well-optimized with no immediate service gaps detected."

    top = recommendations[0]
    top2 = recommendations[1]["service"] if len(recommendations) > 1 else None

    if not has_website:
        return (
            f"{name} has no online presence whatsoever — an immediate opportunity for "
            f"{top['service']} and full digital setup. Confidence: {top['confidence_score']}/100."
        )

    perf = biz.get("performance_score", 0)
    seo = biz.get("seo_score", 0)

    parts = [f"{name} shows strong signals for {top['service']}"]
    parts.append(f"({top['reason']})")
    if top2:
        parts.append(f"along with opportunities in {top2}")
    if perf > 0:
        parts.append(f"Performance: {perf}/100, SEO: {seo}/100")

    return ". ".join(parts) + "."
