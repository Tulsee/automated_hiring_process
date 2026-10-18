"""Set the superadmin's credentials to whatever is in .env, right now.

Startup only *creates* a superadmin when none exists; it never changes one.
So after editing SUPERADMIN_EMAIL / SUPERADMIN_PASSWORD you run this once to
apply them:

    uv run python scripts/set_superadmin.py

It updates the existing superadmin's email, password and name in place (so the
account, its history and anything pointing at it are kept). If there is no
superadmin yet, it creates one. Idempotent: safe to run repeatedly.
"""

import asyncio
import sys

from app.core.config import settings
from app.core.security import hash_password
from app.db.mongodb import users_collection
from app.models.user import KIND_ADMINISTRATION, create_user_document


async def main() -> int:
    email = settings.SUPERADMIN_EMAIL.strip().lower()
    password = settings.SUPERADMIN_PASSWORD
    name = settings.SUPERADMIN_NAME

    if not password:
        print("SUPERADMIN_PASSWORD is empty in .env; set it and run again.")
        return 1

    existing = [u async for u in users_collection.find({"is_superadmin": True})]

    if len(existing) > 1:
        print(
            f"Warning: {len(existing)} superadmin accounts exist "
            f"({', '.join(u['email'] for u in existing)}). "
            "Updating the first and leaving the rest; delete the extras by hand."
        )

    # Guard the unique-email index: the target email must not belong to a
    # different (non-superadmin) account.
    clash = await users_collection.find_one(
        {"email": email, "is_superadmin": {"$ne": True}}
    )
    if clash:
        print(
            f"Another account already uses {email}. "
            "Choose a different SUPERADMIN_EMAIL or remove that user first."
        )
        return 1

    if existing:
        target = existing[0]
        old_email = target["email"]

        from datetime import datetime

        await users_collection.update_one(
            {"_id": target["_id"]},
            {
                "$set": {
                    "email": email,
                    "password_hash": hash_password(password),
                    "name": name,
                    "active": True,
                    "updated_at": datetime.utcnow(),
                }
            },
        )

        if old_email == email:
            print(f"Superadmin {email}: password and name updated.")
        else:
            print(f"Superadmin migrated: {old_email} -> {email} (password updated).")
    else:
        await users_collection.insert_one(
            create_user_document(
                email=email,
                password_hash=hash_password(password),
                name=name,
                kind=KIND_ADMINISTRATION,
                role=None,
                is_superadmin=True,
            )
        )
        print(f"Superadmin created: {email}.")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
