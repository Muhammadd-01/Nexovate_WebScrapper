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

                if biz.get("has_website") and biz.get("website"):
                    async with WEBSITE_SEMAPHORE:
                        try:
                            biz = await _analyze_business(biz, settings.GOOGLE_API_KEY)
                        except Exception as e:
                            logger.error(f"Error analyzing {biz['name']}: {e}")
                
                # Calculate opportunity score
                biz["opportunity_score"] = calculate_opportunity_score(biz)

                # Generate pitch summary
                biz["pitch_summary"] = generate_pitch(biz)

                # Set timestamp
                biz["created_at"] = datetime.utcnow()

                # Convert nested models to dicts for MongoDB
                if isinstance(biz.get("socials"), SocialLinks):
                    biz["socials"] = biz["socials"].model_dump()
                if isinstance(biz.get("health"), HealthAnalysis):
                    biz["health"] = biz["health"].model_dump()

                # Upsert into MongoDB
                try:
                    await collection.update_one(
                        {"place_id": biz["place_id"]},
                        {"$set": biz},
                        upsert=True,
                    )
                    total_saved += 1
                except Exception as e:
                    logger.error(f"MongoDB upsert error for {biz['name']}: {e}")

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

            yield _sse({
                "type": "complete",
                "message": f"Analysis complete! Found {total} businesses, saved {total_saved}.",
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


async def _analyze_business(biz: dict, api_key: str = "") -> dict:
    """Run full analysis on a single business with a website."""
    website = biz["website"]

    # Run email, socials, and health analysis concurrently
    email_task = extract_email(website)
    social_task = extract_socials(website)
    health_task = analyze_health(website)

    email, socials, health = await asyncio.gather(
        email_task, social_task, health_task,
        return_exceptions=True,
    )

    # Handle results (may be exceptions)
    if isinstance(email, str):
        biz["email"] = email
    else:
        biz["email"] = ""
        logger.warning(f"Email extraction failed for {website}: {email}")

    if isinstance(socials, SocialLinks):
        biz["socials"] = socials
    else:
        biz["socials"] = SocialLinks()
        logger.warning(f"Social extraction failed for {website}: {socials}")

    if isinstance(health, HealthAnalysis):
        biz["health"] = health
        biz["load_time"] = health.response_time
        biz["detected_cms"] = health.detected_cms
    else:
        biz["health"] = HealthAnalysis()
        logger.warning(f"Health analysis failed for {website}: {health}")

    # PageSpeed (separate call, may be slow)
    try:
        pagespeed = await fetch_pagespeed(website, api_key)
        biz["performance_score"] = pagespeed["performance"]
        biz["seo_score"] = pagespeed["seo"]
        biz["accessibility_score"] = pagespeed["accessibility"]
        biz["best_practices_score"] = pagespeed["best_practices"]
    except Exception as e:
        logger.warning(f"PageSpeed failed for {website}: {e}")

    return biz


def _sse(data: dict) -> str:
    """Format a dict as an SSE data line."""
    return f"data: {json.dumps(data)}\n\n"
