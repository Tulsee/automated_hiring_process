"""One-time setup run on startup: the superadmin and the default roles.

Both are idempotent, so they run safely on every boot. The default roles are
created only when there are none, so edits or deletions a recruiter makes are
never undone by a restart.
"""

import logging

from app.core.config import settings
from app.db.mongodb import roles_collection
from app.models.role import create_role_document
from app.services.auth_service import ensure_superadmin
from app.services.permissions import DEFAULT_ROLES

logger = logging.getLogger(__name__)


async def bootstrap_auth() -> None:
    await ensure_superadmin(
        email=settings.SUPERADMIN_EMAIL,
        password=settings.SUPERADMIN_PASSWORD,
        name=settings.SUPERADMIN_NAME,
    )

    if await roles_collection.count_documents({}) == 0:
        for name, spec in DEFAULT_ROLES.items():
            await roles_collection.insert_one(
                create_role_document(
                    name=name,
                    permissions=spec["permissions"],
                    description=spec["description"],
                    created_by="system",
                )
            )

        logger.info("Seeded %d default roles", len(DEFAULT_ROLES))
