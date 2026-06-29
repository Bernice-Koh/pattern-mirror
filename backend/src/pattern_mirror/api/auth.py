"""Mock login: exchange a seeded email and a role for a signed session token.

The password is cosmetic (any non-empty value); the email identifies the user and
``expected_role`` is the portal the screen is for. A mismatch — or an unknown email — is rejected
as invalid credentials. The response carries the display identity the frontend caches, so no
separate ``/auth/me`` round trip is needed.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from pattern_mirror.db.session import get_session
from pattern_mirror.models.enums import UserRole
from pattern_mirror.services.auth import SessionPrincipal, authenticate, sign_token

router = APIRouter(tags=["auth"])


class LoginRequest(BaseModel):
    """A login attempt from one of the two portal screens."""

    email: str
    password: str = Field(min_length=1)
    expected_role: UserRole


class LoginUser(BaseModel):
    """The signed-in user's display identity, cached by the frontend."""

    id: uuid.UUID
    legal_name: str
    initials: str
    email: str
    role: UserRole


class LoginResponse(BaseModel):
    """A successful login: the session token and the user to show in the chrome."""

    token: str
    user: LoginUser


def _initials(legal_name: str) -> str:
    """Two-letter avatar initials from a name ("Alex Tan" -> "AT")."""
    parts = legal_name.split()
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


@router.post("/auth/login", summary="Mock login for a manager or HR user")
def login(
    request: LoginRequest,
    session: Annotated[Session, Depends(get_session)],
) -> LoginResponse:
    """Validate the email and role, then return a signed token and the user's identity.

    Raises:
        InvalidCredentialsError: if no active user has this email with the expected role.
    """
    user = authenticate(session, email=request.email, expected_role=request.expected_role)
    token = sign_token(SessionPrincipal(user_id=user.id, role=request.expected_role))
    return LoginResponse(
        token=token,
        user=LoginUser(
            id=user.id,
            legal_name=user.legal_name,
            initials=_initials(user.legal_name),
            email=user.email,
            role=request.expected_role,
        ),
    )
