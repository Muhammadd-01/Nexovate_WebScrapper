"""FastAPI entry point – Global Business Lead Intelligence System."""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from database import create_indexes, close_connection
from routers import search, businesses, dashboard

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup & shutdown events."""
    logging.info("Starting up – attempting to create MongoDB indexes...")
    try:
        await create_indexes()
        logging.info("MongoDB indexes created.")
    except Exception as e:
        logging.warning(f"MongoDB connection failed on startup (indexes not created): {e}")
        logging.warning("The dashboard will still load. Please update your MONGODB_URI in .env")
    yield
    logging.info("Shutting down – closing MongoDB connection...")
    await close_connection()


app = FastAPI(
    title="Global Business Lead Intelligence System",
    description="Fetch, analyze, and score businesses for website upgrade opportunities.",
    version="1.0.0",
    lifespan=lifespan,
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include routers
app.include_router(dashboard.router)
app.include_router(search.router)
app.include_router(businesses.router)
