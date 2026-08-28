import logging
import uuid

from qdrant_client.models import Distance, VectorParams, PointStruct

from app.core.config import settings
from app.db.qdrant import qdrant

logger = logging.getLogger(__name__)


async def create_collection():
    exists = await qdrant.collection_exists(settings.QDRANT_COLLECTION)

    if exists:
        logger.info("Collection '%s' already exists.", settings.QDRANT_COLLECTION)
        return

    await qdrant.create_collection(
        collection_name=settings.QDRANT_COLLECTION,
        vectors_config=VectorParams(size=768, distance=Distance.COSINE),
    )

    logger.info("Collection '%s' created successfully.", settings.QDRANT_COLLECTION)


def build_point_id(candidate_id: str) -> str:
    """
    Qdrant point IDs must be an unsigned integer or a UUID, so a Mongo ObjectId
    cannot be used directly. Derive a deterministic UUID from it instead, so
    re-processing the same candidate upserts the same point.
    """
    return str(uuid.uuid5(uuid.NAMESPACE_OID, candidate_id))


async def store_candidate_embedding(
    candidate_id: str, embedding: list[float], payload: dict
):

    await qdrant.upsert(
        collection_name=settings.QDRANT_COLLECTION,
        points=[
            PointStruct(
                id=build_point_id(candidate_id), vector=embedding, payload=payload
            )
        ],
    )

    logger.info(
        "Stored embedding for candidate '%s' in collection '%s'.",
        candidate_id,
        settings.QDRANT_COLLECTION,
    )
