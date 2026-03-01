"""Businesses router – query, filter, and export business data.

GET /api/businesses – filtered JSON results
GET /api/businesses/csv – CSV download
GET /api/businesses/{id} – single business detail
"""

import csv
import io
import logging
from datetime import datetime
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from bson import ObjectId
from database import get_database
from fpdf import FPDF

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["businesses"])


@router.get("/businesses")
async def list_businesses(
    city: str = Query(default="", description="Filter by city"),
    country: str = Query(default="", description="Filter by country"),
    keyword: str = Query(default="", description="Filter by keyword"),
    has_website: str = Query(default="", description="true/false"),
    has_email: str = Query(default="", description="true/false"),
    min_opportunity: int = Query(default=0, description="Min opportunity score"),
    max_performance: int = Query(default=100, description="Max performance score"),
    sort_by: str = Query(default="opportunity_score", description="Sort field"),
    sort_order: str = Query(default="desc", description="asc or desc"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
):
    """List businesses with optional filters."""
    try:
        db = get_database()
        collection = db.businesses

        query = _build_query(city, country, keyword, has_website, has_email, min_opportunity, max_performance)
        sort_dir = -1 if sort_order == "desc" else 1

        cursor = (
            collection.find(query, {"_id": 0})
            .sort(sort_by, sort_dir)
            .skip(skip)
            .limit(limit)
        )

        businesses = await cursor.to_list(length=limit)

        # Get total count for pagination
        total = await collection.count_documents(query)
        logger.info(f"Fetched {len(businesses)}/{total} businesses from DB (Query: {query})")

        return {"businesses": businesses, "total": total}
    except Exception as e:
        logger.warning(f"Failed to fetch businesses (MongoDB may not be configured): {e}")
        return {"businesses": [], "total": 0}


@router.get("/businesses/csv")
async def export_csv(
    city: str = Query(default=""),
    country: str = Query(default=""),
    keyword: str = Query(default=""),
    has_website: str = Query(default=""),
    has_email: str = Query(default=""),
    min_opportunity: int = Query(default=0),
    max_performance: int = Query(default=100),
    export_format: str = Query(default="all", alias="format", description="all, email, whatsapp, instagram, health"),
):
    """Export businesses as CSV in various specialized formats."""
    db = get_database()
    collection = db.businesses

    query = _build_query(city, country, keyword, has_website, has_email, min_opportunity, max_performance)
    cursor = collection.find(query, {"_id": 0}).sort("opportunity_score", -1)
    businesses = await cursor.to_list(length=1000)

    # Build CSV based on format
    output = io.StringIO()
    
    if export_format == "email":
        fieldnames = ["business_name", "email"]
        filename = "email_leads.csv"
    elif export_format == "whatsapp":
        fieldnames = ["business_name", "whatsapp_number"]
        filename = "whatsapp_leads.csv"
    elif export_format == "instagram":
        fieldnames = ["business_name", "instagram_link"]
        filename = "instagram_leads.csv"
    elif export_format == "health":
        fieldnames = [
            "business_name", "has_website", "website", "detected_cms", 
            "opportunity_score", "performance_score", "seo_score", 
            "accessibility_score", "best_practices_score", "load_time",
            "https_enabled", "has_viewport", "has_title", "has_meta_description",
            "has_h1", "has_favicon", "broken_links_count", "images_total", "images_with_alt"
        ]
        filename = "website_health_report.csv"
    else:
        fieldnames = [
            "name", "address", "phone", "website", "email",
            "instagram", "facebook", "linkedin", "twitter", "youtube", "tiktok",
            "has_website", "performance_score", "seo_score",
            "accessibility_score", "best_practices_score",
            "load_time", "detected_cms", "opportunity_score",
            "rating", "user_ratings_total",
            "https_enabled", "has_viewport", "has_meta_description",
            "pitch_summary", "city", "country", "keyword",
        ]
        filename = "businesses_export_full.csv"

    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()

    for biz in businesses:
        row = {**biz}
        row["business_name"] = biz.get("name", "")
        
        # Flatten socials
        socials = biz.get("socials", {})
        if isinstance(socials, dict):
            row["instagram"] = socials.get("instagram", "")
            row["instagram_link"] = socials.get("instagram", "")
            row["facebook"] = socials.get("facebook", "")
            row["linkedin"] = socials.get("linkedin", "")
            row["twitter"] = socials.get("twitter", "")
            row["youtube"] = socials.get("youtube", "")
            row["tiktok"] = socials.get("tiktok", "")

        # Flatten health
        health = biz.get("health", {})
        if isinstance(health, dict):
            row["https_enabled"] = health.get("https_enabled", "")
            row["has_viewport"] = health.get("has_viewport", "")
            row["has_title"] = health.get("has_title", "")
            row["has_meta_description"] = health.get("has_meta_description", "")
            row["has_h1"] = health.get("has_h1", "")
            row["has_favicon"] = health.get("has_favicon", "")
            row["broken_links_count"] = health.get("broken_links_count", 0)
            row["images_total"] = health.get("images_total", 0)
            row["images_with_alt"] = health.get("images_with_alt", 0)
        
        # WhatsApp mapping (from phone)
        row["whatsapp_number"] = biz.get("phone", "")

        # Filter out rows that are missing the target lead field for lead lists
        if export_format == "email" and not row.get("email"): continue
        if export_format == "whatsapp" and not row.get("whatsapp_number"): continue
        if export_format == "instagram" and not row.get("instagram_link"): continue

        writer.writerow(row)

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )

@router.get("/businesses/pdf")
async def export_pdf(
    city: str = Query(default=""),
    country: str = Query(default=""),
    keyword: str = Query(default=""),
):
    """Generate a professional PDF Website Health Report for filtered businesses."""
    db = get_database()
    collection = db.businesses
    
    query = {}
    if city: query["city"] = {"$regex": city, "$options": "i"}
    if country: query["country"] = {"$regex": country, "$options": "i"}
    if keyword: query["keyword"] = {"$regex": keyword, "$options": "i"}
    
    cursor = collection.find(query).sort("opportunity_score", -1)
    businesses = await cursor.to_list(length=100) # Limit PDF to top 100 for performance
    
    if not businesses:
        raise HTTPException(status_code=404, detail="No businesses found for this report.")

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    for biz in businesses:
        pdf.add_page()
        
        # Header
        pdf.set_font("Helvetica", "B", 20)
        pdf.set_text_color(63, 81, 181) # Indigo
        pdf.cell(0, 15, biz.get("name", "Business Report"), ln=True, align="C")
        
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 5, f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True, align="C")
        pdf.ln(10)
        
        # Stats Overview
        pdf.set_fill_color(240, 240, 240)
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 10, "  Opportunity Overview", ln=True, fill=True)
        pdf.ln(2)
        
        pdf.set_font("Helvetica", "", 11)
        pdf.cell(90, 8, f"Opportunity Score: {biz.get('opportunity_score', 0)}/100")
        pdf.cell(90, 8, f"Website: {'Available' if biz.get('has_website') else 'Not Found'}", ln=True)
        
        if biz.get('has_website'):
            pdf.cell(90, 8, f"Performance Score: {biz.get('performance_score', 0)}/100")
            pdf.cell(90, 8, f"Detected CMS: {biz.get('detected_cms', 'Custom/Unknown')}", ln=True)
        pdf.ln(5)
        
        # Technical Audit
        if biz.get('has_website'):
            pdf.set_font("Helvetica", "B", 12)
            pdf.cell(0, 10, "  Technical Audit", ln=True, fill=True)
            pdf.ln(2)
            pdf.set_font("Helvetica", "", 10)
            
            h = biz.get("health", {})
            audit_items = [
                ("HTTPS Enabled", h.get("https_enabled")),
                ("Mobile Viewport", h.get("has_viewport")),
                ("Title Tag", h.get("has_title")),
                ("Meta Description", h.get("has_meta_description")),
                ("H1 Heading", h.get("has_h1")),
                ("Favicon", h.get("has_favicon")),
            ]
            
            for label, status in audit_items:
                pdf.cell(60, 7, f"- {label}:")
                pdf.set_text_color(0, 150, 0) if status else pdf.set_text_color(200, 0, 0)
                pdf.cell(30, 7, "PASSED" if status else "FAILED", ln=True)
                pdf.set_text_color(0, 0, 0)
            
            pdf.ln(5)

        # Sales Pitch
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 10, "  Strategic Pitch Summary", ln=True, fill=True)
        pdf.ln(2)
        pdf.set_font("Helvetica", "", 10)
        
        pitch = biz.get("pitch_summary", "No pitch summary available.")
        pdf.multi_cell(0, 6, pitch)
        
        # Footer
        pdf.set_y(-25)
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(150, 150, 150)
        pdf.cell(0, 10, f"LeadIntel Global Lead Intelligence - Page {pdf.page_no()}", align="C")

    # Output to stream
    pdf_bytes = pdf.output()
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=Health_Report_{datetime.now().strftime('%Y%m%d')}.pdf"},
    )


@router.get("/businesses/{place_id}")
async def get_business(place_id: str):
    """Get a single business by place_id."""
    db = get_database()
    collection = db.businesses
    biz = await collection.find_one({"place_id": place_id}, {"_id": 0})
    if not biz:
        return JSONResponse(status_code=404, content={"error": "Business not found"})
    return biz


@router.delete("/businesses")
async def clear_businesses():
    """Clear all businesses from the database."""
    db = get_database()
    result = await db.businesses.delete_many({})
    return {"deleted": result.deleted_count}


def _build_query(
    city: str, country: str, keyword: str,
    has_website: str, has_email: str,
    min_opportunity: int, max_performance: int,
) -> dict:
    """Build MongoDB filter query from parameters."""
    query: dict = {}

    if city:
        query["city"] = {"$regex": city, "$options": "i"}
    if country:
        query["country"] = {"$regex": country, "$options": "i"}
    if keyword:
        query["keyword"] = {"$regex": keyword, "$options": "i"}

    if has_website == "true":
        query["has_website"] = True
    elif has_website == "false":
        query["has_website"] = False

    if has_email == "true":
        query["email"] = {"$ne": ""}
    elif has_email == "false":
        query["email"] = ""

    if min_opportunity > 0:
        query["opportunity_score"] = {"$gte": min_opportunity}

    if max_performance < 100:
        query["performance_score"] = {"$lte": max_performance}

    return query
