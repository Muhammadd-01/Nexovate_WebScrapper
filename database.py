"""Async MongoDB connection via Motor."""

from motor.motor_asyncio import AsyncIOMotorClient
from config import get_settings

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        settings = get_settings()
        _client = AsyncIOMotorClient(settings.MONGODB_URI)
    return _client


def get_database():
    settings = get_settings()
    return get_client()[settings.DATABASE_NAME]


async def create_indexes():
    """Create MongoDB indexes for fast queries."""
    db = get_database()
    collection = db.businesses
    await collection.create_index("opportunity_score", background=True)
    await collection.create_index("country", background=True)
    await collection.create_index("city", background=True)
    await collection.create_index("place_id", unique=True, background=True)


async def close_connection():
    global _client
    if _client is not None:
        _client.close()
        _client = None
