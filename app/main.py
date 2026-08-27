import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.logging_config import setup_logging
from app.db.mongodb import close_mongodb, connect_mongodb
from app.db.qdrant import close_qdrant, connect_qdrant
from app.routes.applications import router as applications_router
from app.routes.jobs import router as jobs_router

setup_logging()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting AI Hiring Agent...")

    mongo_ok = await connect_mongodb()
    qdrant_ok = await connect_qdrant()

    logger.info("Database connection status")
    logger.info("MongoDB : %s", "CONNECTED" if mongo_ok else "FAILED")
    logger.info("Qdrant  : %s", "CONNECTED" if qdrant_ok else "FAILED")

    if not (mongo_ok and qdrant_ok):
        logger.warning("Starting with one or more database connections unavailable")

    yield

    logger.info("Shutting down...")

    await close_mongodb()
    await close_qdrant()


app = FastAPI(title="Automated Hiring Process", lifespan=lifespan)

app.include_router(jobs_router)
app.include_router(applications_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
