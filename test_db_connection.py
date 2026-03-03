import asyncio
import logging
import sys
from database import get_database, close_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_connection():
    try:
        logger.info("Attempting to connect to MongoDB...")
        db = get_database()
        # Ping the database
        await db.command("ping")
        logger.info("SUCCESS: Successfully pinged MongoDB!")
        
        # Try to count documents in businesses collection
        count = await db.businesses.count_documents({})
        logger.info(f"Successfully connected! Found {count} businesses in the database.")
        
    except Exception as e:
        logger.error(f"FAILED: Connection error: {e}")
        logger.info("\n*** TROUBLESHOOTING TIPS ***")
        logger.info("1. Ensure your IP address is whitelisted in MongoDB Atlas.")
        logger.info("2. Check if your MongoDB URI in .env is correct.")
        logger.info("3. Ensure you have an active internet connection.")
        sys.exit(1)
    finally:
        await close_connection()

if __name__ == "__main__":
    asyncio.run(test_connection())
