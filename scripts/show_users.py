"""List every account, so you can see what each one actually is.

Run it when a login behaves unexpectedly - e.g. an account you think is the
superadmin is showing only the candidate screens:

    uv run python scripts/show_users.py

It prints each user's email, kind, superadmin flag, role and active state. It
reads nothing secret (never the password hash) and changes nothing.
"""

import asyncio
import sys

from app.db.mongodb import users_collection


async def main() -> int:
    users = [u async for u in users_collection.find()]

    if not users:
        print("No users exist yet. Start the API once (it bootstraps the")
        print("superadmin from .env), or run scripts/set_superadmin.py.")
        return 0

    # Widest email, so the columns line up.
    width = max(len(u.get("email", "")) for u in users)

    print(f"{'EMAIL':<{width}}  {'KIND':<14}  SUPER  ROLE          ACTIVE")
    print("-" * (width + 46))

    superadmins = 0

    for user in sorted(users, key=lambda u: (not u.get("is_superadmin"), u.get("email", ""))):
        is_super = bool(user.get("is_superadmin"))
        superadmins += is_super
        print(
            f"{user.get('email', ''):<{width}}  "
            f"{user.get('kind', '?'):<14}  "
            f"{'yes' if is_super else '-':<5}  "
            f"{(user.get('role') or '-'):<13}  "
            f"{'yes' if user.get('active', True) else 'no'}"
        )

    print("-" * (width + 46))
    print(f"{len(users)} user(s), {superadmins} superadmin(s).")

    if superadmins == 0:
        print(
            "\nNo superadmin exists. Run:  uv run python scripts/set_superadmin.py"
        )

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
