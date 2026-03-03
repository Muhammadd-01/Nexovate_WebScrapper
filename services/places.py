"""Module 1 – OpenStreetMap + Overpass API Integration.

Fetches businesses using the free Overpass API (OpenStreetMap data).
No API key or billing required. Supports global search by keyword, city, country.
Uses multiple mirror servers with automatic fallback for reliability.
"""

import asyncio
import logging
import requests
from typing import Any

logger = logging.getLogger(__name__)

# Multiple Overpass API mirrors for reliability
OVERPASS_SERVERS = [
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

HEADERS = {
    "User-Agent": "LeadIntel/1.0 (Business Lead Intelligence System)",
    "Accept": "application/json",
}

# Map common business keywords to OSM tags
KEYWORD_TAG_MAP = {
    "restaurant": ["amenity=restaurant"],
    "restaurants": ["amenity=restaurant"],
    "cafe": ["amenity=cafe"],
    "coffee": ["amenity=cafe"],
    "hotel": ["tourism=hotel"],
    "hotels": ["tourism=hotel"],
    "motel": ["tourism=motel"],
    "hospital": ["amenity=hospital"],
    "clinic": ["amenity=clinic"],
    "doctor": ["amenity=doctors"],
    "dentist": ["amenity=dentist"],
    "pharmacy": ["amenity=pharmacy"],
    "school": ["amenity=school"],
    "university": ["amenity=university"],
    "bank": ["amenity=bank"],
    "gym": ["leisure=fitness_centre"],
    "fitness": ["leisure=fitness_centre"],
    "salon": ["shop=hairdresser", "shop=beauty"],
    "barber": ["shop=hairdresser"],
    "beauty": ["shop=beauty"],
    "supermarket": ["shop=supermarket"],
    "grocery": ["shop=supermarket", "shop=convenience"],
    "bakery": ["shop=bakery"],
    "car repair": ["shop=car_repair"],
    "mechanic": ["shop=car_repair"],
    "garage": ["shop=car_repair"],
    "plumber": ["craft=plumber"],
    "electrician": ["craft=electrician"],
    "lawyer": ["office=lawyer"],
    "accountant": ["office=accountant"],
    "insurance": ["office=insurance"],
    "real estate": ["office=estate_agent"],
    "shop": ["shop=yes"],
    "store": ["shop=yes"],
    "bar": ["amenity=bar"],
    "pub": ["amenity=pub"],
    "fast food": ["amenity=fast_food"],
    "pizza": ["amenity=restaurant", "amenity=fast_food"],
    "gas station": ["amenity=fuel"],
    "petrol": ["amenity=fuel"],
    "fuel": ["amenity=fuel"],
    "parking": ["amenity=parking"],
    "veterinary": ["amenity=veterinary"],
    "pet": ["shop=pet"],
    "florist": ["shop=florist"],
    "jewelry": ["shop=jewelry"],
    "clothing": ["shop=clothes"],
    "clothes": ["shop=clothes"],
    "electronics": ["shop=electronics"],
    "furniture": ["shop=furniture"],
    "bookstore": ["shop=books"],
    "books": ["shop=books"],
    "office": ["office=yes"],
    "company": ["office=company"],
    "construction": ["office=company", "craft=builder"],
    "cleaning": ["office=company", "shop=cleaning"],
    "photography": ["craft=photographer"],
    "spa": ["leisure=spa", "shop=beauty"],
    "laundry": ["shop=laundry"],
    "travel": ["shop=travel_agency"],
    "car dealer": ["shop=car"],
    "car wash": ["amenity=car_wash"],
    "mosque": ["amenity=place_of_worship"],
    "church": ["amenity=place_of_worship"],
    "temple": ["amenity=place_of_worship"],
}


async def fetch_businesses(
    keyword: str,
    city: str,
    country: str,
    limit: int,
    progress_callback=None,
) -> list[dict[str, Any]]:
    """Fetch businesses from OpenStreetMap via Overpass API.

    1. Geocode city+country via Nominatim to get bounding box.
    2. Query Overpass API with keyword-based tags.
    3. Parse results and return structured business data.
    """
    if progress_callback:
        await progress_callback(f"Geocoding {city}, {country}...")

    # Step 1: Get bounding box via Nominatim
    bbox = await _geocode_bbox(city, country)
    if not bbox:
        logger.error(f"Failed to geocode {city}, {country}")
        return []

    if progress_callback:
        await progress_callback(f"Building query for '{keyword}' businesses...")

    # Step 2: Build and execute Overpass query
    query = _build_query(keyword, bbox, limit)
    logger.info(f"Overpass query built, fetching data...")

    # Polite delay between Nominatim and Overpass to prevent rate limiting
    await asyncio.sleep(0.7)

    if progress_callback:
        await progress_callback(f"Querying OpenStreetMap for '{keyword}' in {city}...")

    data = await _execute_overpass_query(query)
    if data is None:
        return []

    # Step 3: Parse results
    elements = data.get("elements", [])
    businesses: list[dict[str, Any]] = []

    for elem in elements:
        if len(businesses) >= limit:
            break

        tags = elem.get("tags", {})
        name = tags.get("name", "").strip()
        if not name:
            continue

        biz = _parse_element(elem, tags, city, country)
        businesses.append(biz)

        if progress_callback and len(businesses) % 25 == 0:
            await progress_callback(
                f"Parsed {len(businesses)} businesses so far..."
            )

    logger.info(f"Fetched {len(businesses)} businesses for '{keyword}' in {city}, {country}")
    return businesses


async def _execute_overpass_query(query: str) -> dict | None:
    """Try multiple Overpass servers with fallback."""
    for i, server_url in enumerate(OVERPASS_SERVERS):
        try:
            logger.info(f"Trying Overpass server {i+1}/{len(OVERPASS_SERVERS)}: {server_url}")
            resp = await asyncio.to_thread(
                requests.post,
                server_url,
                data={"data": query},
                headers=HEADERS,
                timeout=90,
            )
            resp.raise_for_status()
            data = resp.json()
            logger.info(f"Overpass server {i+1} responded with {len(data.get('elements', []))} elements")
            return data
        except Exception as e:
            logger.warning(f"Overpass server {i+1} failed: {e}")
            if i < len(OVERPASS_SERVERS) - 1:
                logger.info("Falling back to next mirror...")
                await asyncio.sleep(1)
            continue

    logger.error("All Overpass mirrors failed!")
    return None


async def _geocode_bbox(city: str, country: str) -> tuple | None:
    """Get bounding box for a city using Nominatim."""
    params = {
        "q": f"{city}, {country}",
        "format": "json",
        "limit": 1,
        "addressdetails": 0,
    }
    try:
        resp = await asyncio.to_thread(
            requests.get, NOMINATIM_URL, params=params, headers=HEADERS, timeout=15
        )
        resp.raise_for_status()
        results = resp.json()
        if results:
            bbox = results[0].get("boundingbox", [])
            if len(bbox) == 4:
                # Nominatim returns [south, north, west, east]
                south, north, west, east = [float(x) for x in bbox]
                logger.info(f"Geocoded {city}, {country} → bbox: {south},{west},{north},{east}")
                return (south, west, north, east)
            # Fallback: use lat/lon with a ~5km radius
            lat = float(results[0].get("lat", 0))
            lon = float(results[0].get("lon", 0))
            if lat and lon:
                delta = 0.05  # ~5km
                return (lat - delta, lon - delta, lat + delta, lon + delta)
    except Exception as e:
        logger.error(f"Nominatim geocode error: {e}")
    return None


def _get_osm_filters(keyword: str) -> list[str]:
    """Map a keyword to OSM tag=value pairs."""
    keyword_lower = keyword.lower().strip()
    filters = []

    # Direct match
    if keyword_lower in KEYWORD_TAG_MAP:
        filters.extend(KEYWORD_TAG_MAP[keyword_lower])
        return filters

    # Partial match
    for key, tags in KEYWORD_TAG_MAP.items():
        if key in keyword_lower or keyword_lower in key:
            filters.extend(tags)

    # Deduplicate
    return list(dict.fromkeys(filters))


def _build_query(keyword: str, bbox: tuple, limit: int) -> str:
    """Build an Overpass QL query using bounding box.

    Uses a simple, fast query format to avoid timeouts.
    """
    south, west, north, east = bbox
    bbox_str = f"{south},{west},{north},{east}"
    filters = _get_osm_filters(keyword)
    keyword_escaped = keyword.replace("\\", "\\\\").replace('"', '\\"')

    # Fetch extra to allow for unnamed entries being filtered out
    fetch_limit = min(limit + 100, 700)

    # Build union of tag-based and name-based queries
    parts = []

    # Tag-based queries (most efficient)
    for tag_filter in filters:
        key, value = tag_filter.split("=", 1)
        if value == "yes":
            parts.append(f'  nwr["{key}"]["name"]({bbox_str});')
        else:
            parts.append(f'  nwr["{key}"="{value}"]["name"]({bbox_str});')

    # Name-based regex fallback (catches businesses not matching mapped tags)
    parts.append(f'  nwr["name"~"{keyword_escaped}",i]["name"]({bbox_str});')

    union_body = "\n".join(parts)

    query = f"""[out:json][timeout:45];
(
{union_body}
);
out center {fetch_limit};"""

    return query


def _parse_element(
    elem: dict, tags: dict, city: str, country: str
) -> dict[str, Any]:
    """Parse a single Overpass element into our business format."""
    # Get coordinates
    lat = elem.get("lat", 0.0)
    lon = elem.get("lon", 0.0)
    if "center" in elem:
        lat = elem["center"].get("lat", lat)
        lon = elem["center"].get("lon", lon)

    # Build address from available tags
    address_parts = []
    house = tags.get("addr:housenumber", "")
    street = tags.get("addr:street", "")
    if house and street:
        address_parts.append(f"{house} {street}")
    elif street:
        address_parts.append(street)

    for key in ["addr:suburb", "addr:city", "addr:state", "addr:postcode"]:
        val = tags.get(key, "").strip()
        if val:
            address_parts.append(val)

    address = ", ".join(address_parts) if address_parts else f"{city}, {country}"

    # Phone number
    phone = (
        tags.get("phone", "")
        or tags.get("contact:phone", "")
        or tags.get("telephone", "")
    )

    # Website
    website = (
        tags.get("website", "")
        or tags.get("contact:website", "")
        or tags.get("url", "")
    )
    # Clean up website URL
    if website and not website.startswith("http"):
        website = "https://" + website

    # Generate stable place_id
    osm_type = elem.get("type", "node")
    osm_id = elem.get("id", 0)
    place_id = f"osm_{osm_type}_{osm_id}"

    return {
        "place_id": place_id,
        "name": tags.get("name", ""),
        "address": address,
        "phone": phone,
        "website": website,
        "has_website": bool(website),
        "rating": 0.0,
        "user_ratings_total": 0,
        "latitude": lat,
        "longitude": lon,
        "email": tags.get("email", "") or tags.get("contact:email", ""),
        # Niche: extract from OSM tags (amenity, shop, office, leisure, craft, tourism)
        "niche": (
            tags.get("amenity", "")
            or tags.get("shop", "")
            or tags.get("office", "")
            or tags.get("leisure", "")
            or tags.get("craft", "")
            or tags.get("tourism", "")
        ),
        # Default scores to prevent 'undefined' in UI
        "performance_score": 0,
        "seo_score": 0,
        "accessibility_score": 0,
        "best_practices_score": 0,
        "opportunity_score": 0,
        "pitch_summary": "",
    }
