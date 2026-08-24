import logging

from pymongo import AsyncMongoClient

from app.core.config import settings

logger = logging.getLogger(__name__)

client = AsyncMongoClient(settings.MONGO_URI)

db = client[settings.MONGO_DB]

candidates_collection = db["candidates"]
jobs_collection = db["jobs"]
applications_collection = db["applications"]
interviews_collection = db["interviews"]
agent_logs_collection = db["agent_logs"]


async def connect_mongodb():
    try:
        await client.admin.command("ping")
        logger.info("Connected to MongoDB")
        return True
    except Exception as e:
        logger.error("Error connecting to MongoDB: %s", e, exc_info=True)
        return False


async def close_mongodb():
    await client.close()
    logger.info("MongoDB connection closed")
