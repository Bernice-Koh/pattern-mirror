"""Mock authentication: credential check and HMAC-signed session tokens.

No passwords are stored. ``authenticate`` matches a seeded user by email and confirms they
hold the role the login screen claimed. The token is a base64url payload plus an HMAC-SHA256
signature over it, so the role inside it cannot be edited without invalidating the signature —
enough for a mock, and replaceable wholesale when real auth lands.
"""

import base64
import hashlib
import hmac
import json
import uuid

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from pattern_mirror.core.config import get_settings
from pattern_mirror.core.errors import InvalidCredentialsError, NotAuthenticatedError
from pattern_mirror.models.enums import UserRole
from pattern_mirror.models.identity import User


class SessionPrincipal(BaseModel):
    """The identity carried inside a session token: who, and in which role."""

    user_id: uuid.UUID
    role: UserRole


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _sign(body: str) -> str:
    secret = get_settings().session_secret.encode()
    return _b64encode(hmac.new(secret, body.encode(), hashlib.sha256).digest())


def sign_token(principal: SessionPrincipal) -> str:
    """Serialise the principal into a ``<payload>.<signature>`` token."""
    body = _b64encode(
        json.dumps(
            {"user_id": str(principal.user_id), "role": principal.role.value},
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
    )
    return f"{body}.{_sign(body)}"


def verify_token(token: str) -> SessionPrincipal:
    """Verify a token's signature and return its principal.

    Raises:
        NotAuthenticatedError: if the token is malformed or its signature does not match.
    """
    body, _, signature = token.partition(".")
    if not signature or not hmac.compare_digest(signature, _sign(body)):
        raise NotAuthenticatedError
    try:
        data = json.loads(_b64decode(body))
        return SessionPrincipal(user_id=uuid.UUID(data["user_id"]), role=UserRole(data["role"]))
    except (ValueError, KeyError, TypeError) as exc:
        raise NotAuthenticatedError from exc


def authenticate(session: Session, *, email: str, expected_role: UserRole) -> User:
    """Return the active user with this email if they hold ``expected_role``.

    The password is not checked — this is mock auth. The role match is what makes the two
    login screens land on the correct portal.

    Raises:
        InvalidCredentialsError: if no active user has this email or they lack the role.
    """
    user = session.scalar(select(User).where(User.email == email, User.active.is_(True)))
    if user is None or expected_role not in {assignment.role for assignment in user.roles}:
        raise InvalidCredentialsError
    return user
