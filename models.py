"""Pydantic models for request/response and MongoDB documents."""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class SearchRequest(BaseModel):
    keyword: str
    city: str
    country: str
    limit: int = Field(default=100, ge=1, le=200)


class SocialLinks(BaseModel):
    instagram: str = ""
    facebook: str = ""
    linkedin: str = ""
    twitter: str = ""
    tiktok: str = ""
    youtube: str = ""
    pinterest: str = ""
    threads: str = ""
    others: list[str] = []


class HealthAnalysis(BaseModel):
    https_enabled: bool = False
    response_time: float = 0.0
    status_code: int = 0
    has_viewport: bool = False
    has_title: bool = False
    has_meta_description: bool = False
    has_h1: bool = False
    has_favicon: bool = False
    broken_links_count: int = 0
    images_total: int = 0
    images_with_alt: int = 0
    detected_cms: str = ""
    tech_stack: list[str] = []


class BusinessDocument(BaseModel):
    place_id: str = ""
    name: str = ""
    address: str = ""
    phone: str = ""
    website: str = ""
    email: str = ""
    socials: SocialLinks = SocialLinks()
    has_website: bool = False
    rating: float = 0.0
    user_ratings_total: int = 0
    latitude: float = 0.0
    longitude: float = 0.0
    health: HealthAnalysis = HealthAnalysis()
    performance_score: int = 0
    seo_score: int = 0
    accessibility_score: int = 0
    best_practices_score: int = 0
    load_time: float = 0.0
    detected_cms: str = ""
    opportunity_score: int = 0
    pitch_summary: str = ""
    keyword: str = ""
    city: str = ""
    country: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SearchResponse(BaseModel):
    status: str
    message: str
    count: int = 0
