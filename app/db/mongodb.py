import logging

from pymongo import ASCENDING, AsyncMongoClient

from app.core.config import settings

logger = logging.getLogger(__name__)

client = AsyncMongoClient(settings.MONGO_URI)

db = client[settings.MONGO_DB]

candidates_collection = db["candidates"]
jobs_collection = db["jobs"]
applications_collection = db["applications"]
agent_logs_collection = db["agent_logs"]
interview_answers_collections = db["interview_answers"]
interview_sessions_collection = db["interview_sessions"]
users_collection = db["users"]
roles_collection = db["roles"]
notifications_collection = db["notifications"]
change_requests_collection = db["change_requests"]


async def ensure_indexes():
    """Create the indexes the queries and uniqueness rules rely on.

    The unique index on (session_id, question_id) is what actually prevents a
    second answer for the same question: the route's check-then-insert can
    interleave under concurrent uploads, and only the database can settle it.
    """
    try:
        await interview_answers_collections.create_index(
            [("session_id", ASCENDING), ("question_id", ASCENDING)],
            name="session_question_unique",
            unique=True,
        )

        await interview_sessions_collection.create_index(
            [("candidate_id", ASCENDING)], name="candidate_id"
        )

        # Sessions created before invite tokens existed have no token, so the
        # uniqueness rule only covers documents that actually carry one.
        await interview_sessions_collection.create_index(
            [("invite_token", ASCENDING)],
            name="invite_token_unique",
            unique=True,
            partialFilterExpression={"invite_token": {"$type": "string"}},
        )

        await candidates_collection.create_index(
            [("job_id", ASCENDING)], name="job_id"
        )

        await users_collection.create_index(
            [("email", ASCENDING)], name="email_unique", unique=True
        )

        await roles_collection.create_index(
            [("name", ASCENDING)], name="role_name_unique", unique=True
        )

        # A user's notifications, newest first.
        await notifications_collection.create_index(
            [("user_id", ASCENDING), ("created_at", ASCENDING)],
            name="user_created",
        )

        logger.info("MongoDB indexes ensured")

        return True

    except Exception as e:
        logger.error("Failed to create indexes: %s", e, exc_info=True)

        return False


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
