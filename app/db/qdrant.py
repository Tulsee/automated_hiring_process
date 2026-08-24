import logging

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams

from app.core.config import settings

logger = logging.getLogger(__name__)

qdrant = AsyncQdrantClient(url=settings.QDRANT_URL)


async def connect_qdrant():
    try:
        await qdrant.get_collections()
        logger.info("Connected to Qdrant")
        return True
    except Exception as e:
        logger.error("Error connecting to Qdrant: %s", e, exc_info=True)
        return False


async def close_qdrant():
    await qdrant.close()
    logger.info("Qdrant connection closed")


async def init_qdrant():

    collections = await qdrant.get_collections()

    exists = any(
        collection.name == settings.QDRANT_COLLECTION
        for collection in collections.collections
    )

    if not exists:
        await qdrant.create_collection(
            collection_name=settings.QDRANT_COLLECTION,
            vectors_config=VectorParams(
                size=settings.EMBEDDING_DIMENSION, distance=Distance.COSINE
            ),
        )
