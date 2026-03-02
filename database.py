import logging
import requests
from motor.motor_asyncio import AsyncIOMotorClient
try:
    import certifi
    ca = certifi.where()
except ImportError:
    ca = None
from config import get_settings

logger = logging.getLogger(__name__)

_client: AsyncIOMotorClient | None = None


def get_public_ip():
    """Fetch public IP to help user with MongoDB whitelisting."""
    try:
        response = requests.get("https://api.ipify.org?format=json", timeout=5)
        return response.json().get("ip", "Unknown")
    except Exception:
        return "Unknown"


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        settings = get_settings()
        uri = settings.MONGODB_URI
        
        # Detect public IP for user guidance
        public_ip = get_public_ip()
        logger.info(f"*** DIAGNOSTIC: Your Public IP is {public_ip} ***")
        logger.info(f"*** Ensure {public_ip} is whitelisted in MongoDB Atlas Network Access (Search: 0.0.0.0/0 to allow all) ***")

        # Simplified but robust SSL handling
        # We try to use the URI as-is if it has parameters, or add the most compatible ones
        if "mongodb+srv" in uri and "tls=" not in uri and "ssl=" not in uri:
            separator = "&" if "?" in uri else "?"
            uri += f"{separator}tls=true&tlsAllowInvalidCertificates=true"
        
        client_kwargs = {
            "tlsCAFile": ca if ca else None,
            "serverSelectionTimeoutMS": 10000,
            "connectTimeoutMS": 10000,
            "retryWrites": True,
            "tlsAllowInvalidCertificates": True # Explicitly force this for Windows environment
        }
        
        # Filter out None values
        client_kwargs = {k: v for k, v in client_kwargs.items() if v is not None}
        
        _client = AsyncIOMotorClient(uri, **client_kwargs)
        logger.info(f"MongoDB Client initialized (certifi: {bool(ca)})")
    return _client


def get_database():
    settings = get_settings()
    return get_client()[settings.DATABASE_NAME]


async def create_indexes():
    """Create MongoDB indexes and VERIFY connection."""
    try:
        db = get_database()
        # Ping the database to verify connection
        await db.command("ping")
        logger.info("Successfully pinged MongoDB. Connection is alive.")
        
        collection = db.businesses
        await collection.create_index("opportunity_score", background=True)
        await collection.create_index("country", background=True)
        await collection.create_index("city", background=True)
        await collection.create_index("place_id", unique=True, background=True)
        logger.info("Indexes verified/created.")
    except Exception as e:
        logger.error(f"CRITICAL: MongoDB connection/index error: {e}")
        logger.error("DASHBOARD WILL LOAD BUT SHOW 0 RESULTS UNTIL IP IS WHITELISTED.")


async def close_connection():
    global _client
    if _client is not None:
        _client.close()
        _client = None
