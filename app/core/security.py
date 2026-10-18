"""Password hashing and JWT handling.

Kept dependency-light and in one place: bcrypt for passwords, PyJWT for tokens.
Nothing here reaches the database or FastAPI, so it is trivial to test and
reuse.
"""

import logging
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import settings

logger = logging.getLogger(__name__)

# bcrypt hashes at most 72 bytes of input and silently ignores the rest, which
# would make a very long password weaker than it looks. Rejecting over-long
# input is clearer than truncating it.
MAX_PASSWORD_BYTES = 72

ALGORITHM = "HS256"


class PasswordTooLong(ValueError):
    """The password exceeds what bcrypt can hash."""


def hash_password(password: str) -> str:
    encoded = password.encode("utf-8")

    if len(encoded) > MAX_PASSWORD_BYTES:
        raise PasswordTooLong(
            f"Password must be at most {MAX_PASSWORD_BYTES} bytes"
        )

    return bcrypt.hashpw(encoded, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Constant-time check; False rather than raising on a malformed hash."""
    try:
        return bcrypt.checkpw(
            password.encode("utf-8")[:MAX_PASSWORD_BYTES],
            hashed.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


def create_access_token(
    subject: str,
    claims: dict,
    expires_delta: timedelta | None = None,
) -> str:
    """A signed token for `subject` (the user id), carrying `claims`.

    `claims` holds what the guards read without a database round trip - the
    user's kind and whether they are the superadmin - so a request can be
    rejected before any query. Anything that can change and must be current
    (a role's permissions) is looked up fresh instead.
    """
    now = datetime.now(timezone.utc)

    expire = now + (
        expires_delta
        or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    payload = {
        **claims,
        "sub": subject,
        "iat": now,
        "exp": expire,
    }

    return jwt.encode(payload, settings.JWT_SECRET, algorithm=ALGORITHM)


class TokenError(ValueError):
    """The token is missing, malformed, expired or badly signed."""


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError as error:
        raise TokenError("The session has expired; sign in again") from error
    except jwt.InvalidTokenError as error:
        raise TokenError("Invalid authentication token") from error
