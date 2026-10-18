"""The permission catalogue, and how a user's permissions are resolved.

A permission is a `resource:action` string. Routes require one; roles grant a
set of them. This is the whole vocabulary of what an administration user can be
allowed to do, so it lives in one list rather than being scattered across the
routes that check it.

Three kinds of principal:

* the **superadmin** holds every permission implicitly and can never be locked
  out - permission checks are skipped for them entirely;
* an **administration** user holds exactly the permissions of the role assigned
  to them;
* a **candidate** holds no administration permissions at all. The candidate
  surface (browsing open roles, applying, interviewing by invite link) is
  public and guarded by other means, not by these permissions.
"""

# resource:action -> what it lets an administration user do.
PERMISSIONS: dict[str, str] = {
    "jobs:read": "View roles, including drafts and closed ones",
    "jobs:write": "Create and edit roles, set deadlines, publish and close",
    "candidates:read": "View candidates and their screening detail",
    "candidates:screen": "Run the screening decision for a candidate",
    "interviews:read": "View interview sessions, transcripts and scorecards",
    "interviews:manage": "Create interview invites and run transcription",
    "interviews:score": "Score an interview against the rubric",
    "roles:manage": "Create roles and assign their permissions",
    "users:manage": "Create administration users and assign them a role",
}

ALL_PERMISSIONS: frozenset[str] = frozenset(PERMISSIONS)

# Roles the superadmin gets on a fresh system, so the dashboard is usable
# before anyone hand-builds a single role. They are ordinary roles and can be
# edited or deleted afterwards.
DEFAULT_ROLES: dict[str, dict] = {
    "recruiter": {
        "description": "Day-to-day hiring: screen, invite, interview, decide",
        "permissions": [
            "jobs:read",
            "jobs:write",
            "candidates:read",
            "candidates:screen",
            "interviews:read",
            "interviews:manage",
            "interviews:score",
        ],
    },
    "hiring_manager": {
        "description": "Review and decide, without editing roles",
        "permissions": [
            "jobs:read",
            "candidates:read",
            "interviews:read",
            "interviews:score",
        ],
    },
    "viewer": {
        "description": "Read-only visibility into the pipeline",
        "permissions": [
            "jobs:read",
            "candidates:read",
            "interviews:read",
        ],
    },
}


class UnknownPermission(ValueError):
    """A permission string that is not in the catalogue."""


def validate_permissions(permissions: list[str]) -> list[str]:
    """Normalise and check a permission list, rejecting anything unknown.

    A typo in a role's permissions would otherwise grant nothing silently and
    be very hard to spot, so an unknown permission is an error, not a no-op.
    """
    cleaned = []
    seen = set()

    for permission in permissions:
        name = permission.strip()

        if not name or name in seen:
            continue

        if name not in ALL_PERMISSIONS:
            raise UnknownPermission(
                f"Unknown permission '{name}'. "
                f"Valid permissions: {sorted(ALL_PERMISSIONS)}"
            )

        seen.add(name)
        cleaned.append(name)

    return cleaned
