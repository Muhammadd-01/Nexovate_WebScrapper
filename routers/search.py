"""Search router – orchestrates the full business analysis pipeline.

POST /api/search accepts keyword+city+country+limit,
runs OpenStreetMap/Overpass API → website analysis → scoring → MongoDB storage,
and streams progress via Server-Sent Events.
"""

import asyncio
import json
import logging
from datetime import datetime
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from config import get_settings
from database import get_database
from models import SearchRequest, SocialLinks, HealthAnalysis
from services.places import fetch_businesses
from services.email_extractor import extract_email
from services.social_extractor import extract_socials
from services.health_analyzer import analyze_health
from services.pagespeed import fetch_pagespeed
from services.scoring import calculate_opportunity_score
from services.pitch_generator import generate_pitch
from services.service_detector import detect_services
from services.website_checker import check_website_active
from services.lead_scorer import calculate_lead_score

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["search"])

# Semaphore to limit concurrent website requests
WEBSITE_SEMAPHORE = asyncio.Semaphore(3)


@router.post("/search")
async def search_businesses(req: SearchRequest):
    """Start a business search and analysis pipeline. Returns SSE stream."""

    async def event_stream():
        settings = get_settings()
        db = get_database()
        collection = db.businesses

        # Sanitize inputs
        keyword_clean = req.keyword.strip()
        city_clean = req.city.strip()
        country_clean = req.country.strip()

        total_processed = 0
        total_saved = 0
        total_skipped = 0
        total_duplicates = 0

        try:
            # Step 1: Fetch businesses from OpenStreetMap
            yield _sse({"type": "status", "message": "Fetching businesses from OpenStreetMap..."})

            progress_messages = []

            async def places_progress(msg):
                progress_messages.append(msg)

            businesses = await fetch_businesses(
                keyword=keyword_clean,
                city=city_clean,
                country=country_clean,
                limit=req.limit,
                progress_callback=places_progress,
            )

            total = len(businesses)
            yield _sse({
                "type": "status",
                "message": f"Found {total} businesses. Starting analysis...",
                "total": total,
            })

            if total == 0:
                yield _sse({
                    "type": "complete",
                    "message": "No businesses found for this search.",
                    "count": 0,
                })
                return

            # Step 2: Analyze each business
            for i, biz in enumerate(businesses, 1):
                biz["keyword"] = keyword_clean
                biz["city"] = city_clean
                biz["country"] = country_clean

                # ── Enhancement 2: Skip leads with no email AND no website ──
                if not biz.get("email") and not biz.get("website"):
                    total_skipped += 1
                    yield _sse({
                        "type": "progress",
                        "message": f"Skipping {i}/{total}: {biz['name']} (no email/website)",
                        "current": i,
                        "total": total,
                    })
                    continue

                # ── Enhancement 2: Duplicate check (email OR website already in DB) ──
                dup_query = []
                if biz.get("email"):
                    dup_query.append({"email": biz["email"]})
                if biz.get("website"):
                    dup_query.append({"website": biz["website"]})

                if dup_query:
                    existing = await collection.find_one(
                        {"$or": dup_query, "place_id": {"$ne": biz.get("place_id", "")}}
                    )
                    if existing:
                        total_duplicates += 1
                        yield _sse({
                            "type": "progress",
                            "message": f"Duplicate {i}/{total}: {biz['name']} (already exists)",
                            "current": i,
                            "total": total,
                        })
                        continue

                # ── Enhancement 4: Website liveness check ──
                if biz.get("has_website") and biz.get("website"):
                    async with WEBSITE_SEMAPHORE:
                        try:
                            # Check if website is active
                            biz["websiteActive"] = await check_website_active(biz["website"])

                            # Full analysis (email, socials, health, pagespeed)
                            analysis_results = await _analyze_business(biz["website"], settings.GOOGLE_API_KEY)
                            biz.update(analysis_results)
                        except Exception as e:
                            logger.error(f"Error analyzing {biz['name']}: {e}")
                            biz["websiteActive"] = False
                else:
                    biz["websiteActive"] = False

                # Calculate opportunity score
                biz["opportunity_score"] = calculate_opportunity_score(biz)

                # Generate pitch summary
                biz["pitch_summary"] = generate_pitch(biz)

                # Detect recommended services
                try:
                    service_data = detect_services(biz)
                    biz.update(service_data)
                except Exception as e:
                    logger.error(f"Service detection error for {biz['name']}: {e}")
                    biz.setdefault("recommended_services", [])
                    biz.setdefault("primary_pitch", "")
                    biz.setdefault("service_pitch_summary", "")

                # ── Enhancement 5: Lead scoring ──
                biz["leadScore"] = calculate_lead_score(biz)

                # Set timestamp
                biz["created_at"] = datetime.utcnow()

                # Convert nested models to dicts for MongoDB
                if isinstance(biz.get("socials"), SocialLinks):
                    biz["socials"] = biz["socials"].model_dump()
                if isinstance(biz.get("health"), HealthAnalysis):
                    biz["health"] = biz["health"].model_dump()

                # Upsert into MongoDB
                try:
                    res = await collection.update_one(
                        {"place_id": biz["place_id"]},
                        {"$set": biz},
                        upsert=True,
                    )
                    if res.acknowledged:
                        total_saved += 1
                        logger.info(f"Successfully saved {biz['name']} to DB.")
                    else:
                        logger.error(f"Failed to save {biz['name']}: Not acknowledged")
                except Exception as e:
                    logger.error(f"MongoDB upsert error for {biz['name']}: {e}", exc_info=True)

                # Send progress ONLY after saving to DB so UI can see it
                status_msg = f"Analyzing {i}/{total}: {biz['name']}"
                if not biz.get("has_website"):
                    status_msg += " (no website)"

                yield _sse({
                    "type": "progress",
                    "message": status_msg,
                    "current": i,
                    "total": total,
                })

                total_processed += 1

                # ── Enhancement 1: Polite delay between analyses to prevent rate limiting ──
                await asyncio.sleep(0.5)

            yield _sse({
                "type": "complete",
                "message": (
                    f"Analysis complete! Found {total} businesses, "
                    f"saved {total_saved}, skipped {total_skipped}, "
                    f"duplicates {total_duplicates}."
                ),
                "count": total_saved,
            })

        except Exception as e:
            logger.error(f"Search pipeline error: {e}")
            yield _sse({
                "type": "error",
                "message": f"Pipeline error: {str(e)}",
            })

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _analyze_business(website: str, api_key: str = "") -> dict:
    """Run full analysis on a single business with a website and return results dict."""
    results = {}
    
    # Run email, socials, and health analysis concurrently
    email_task = extract_email(website)
    social_task = extract_socials(website)
    health_task = analyze_health(website)

    email, socials, health = await asyncio.gather(
        email_task, social_task, health_task,
        return_exceptions=True,
    )

    # Handle results (may be exceptions)
    results["email"] = email if isinstance(email, str) else ""
    results["socials"] = socials if isinstance(socials, SocialLinks) else SocialLinks()
    
    if isinstance(health, HealthAnalysis):
        results["health"] = health
        results["load_time"] = health.response_time
        results["detected_cms"] = health.detected_cms
    else:
        results["health"] = HealthAnalysis()
        results["load_time"] = 0
        results["detected_cms"] = "Unknown"

    # PageSpeed (separate call, may be slow)
    try:
        pagespeed = await fetch_pagespeed(website, api_key)
        results["performance_score"] = pagespeed["performance"]
        results["seo_score"] = pagespeed["seo"]
        results["accessibility_score"] = pagespeed["accessibility"]
        results["best_practices_score"] = pagespeed["best_practices"]
    except Exception as e:
        logger.warning(f"PageSpeed failed for {website}: {e}")
        results["performance_score"] = 0
        results["seo_score"] = 0
        results["accessibility_score"] = 0
        results["best_practices_score"] = 0

    return results


def _sse(data: dict) -> str:
    """Format a dict as an SSE data line."""
    return f"data: {json.dumps(data)}\n\n"

