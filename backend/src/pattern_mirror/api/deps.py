"""Shared FastAPI dependencies.

``get_current_user`` resolves the signed-in user from the request's bearer token; it is the seam
every authenticated endpoint depends on, and tests override it to inject a known user.
``get_current_principal`` exposes the token's active role, and ``require_hr`` gates the HR Portal
on it — the structural boundary behind the aggregate-only HR queries (#70).
"""

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from pattern_mirror.core.errors import NotAuthenticatedError, NotAuthorizedError
from pattern_mirror.db.session import get_session
from pattern_mirror.models.enums import UserRole
from pattern_mirror.models.identity import User
from pattern_mirror.services.auth import SessionPrincipal, verify_token

# auto_error=False so a missing header yields None and raises our typed 401 rather than
# Starlette's bare 403.
_bearer = HTTPBearer(auto_error=False)


def _authenticate(
    session: Session, credentials: HTTPAuthorizationCredentials | None
) -> tuple[SessionPrincipal, User]:
    """Verify the token and confirm it names an active user, returning both principal and user.

    Raises:
        NotAuthenticatedError: if the token is absent, invalid, or names an inactive/unknown user.
    """
    if credentials is None:
        raise NotAuthenticatedError
    principal = verify_token(credentials.credentials)
    user = session.get(User, principal.user_id)
    if user is None or not user.active:
        raise NotAuthenticatedError
    return principal, user


def get_current_user(
    session: Annotated[Session, Depends(get_session)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    """Return the user named by the request's session token.

    Raises:
        NotAuthenticatedError: if the token is absent, invalid, or names an inactive/unknown user.
    """
    _, user = _authenticate(session, credentials)
    return user


def get_current_principal(
    session: Annotated[Session, Depends(get_session)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> SessionPrincipal:
    """Return the principal (user and active role) carried by the request's session token.

    Raises:
        NotAuthenticatedError: if the token is absent, invalid, or names an inactive/unknown user.
    """
    principal, _ = _authenticate(session, credentials)
    return principal


def require_hr(
    principal: Annotated[SessionPrincipal, Depends(get_current_principal)],
) -> SessionPrincipal:
    """Authorize an HR-only endpoint: the active session role must be HR.

    Gating on the token's active role (not merely a granted role) means a manager-portal session
    cannot reach the HR aggregates even for a user who also holds HR.

    Raises:
        NotAuthorizedError: if the signed-in session is not acting as HR.
    """
    if principal.role is not UserRole.hr:
        raise NotAuthorizedError
    return principal


def require_manager(
    principal: Annotated[SessionPrincipal, Depends(get_current_principal)],
) -> SessionPrincipal:
    """Authorize a manager-only endpoint: the active session role must be manager.

    Resume downloads are individual candidate/employee content, which HR never sees (design spec
    §5: HR reads aggregates only). Gating on the active role keeps an HR-portal session out even
    for a user who also holds the manager role.

    Raises:
        NotAuthorizedError: if the signed-in session is not acting as a manager.
    """
    if principal.role is not UserRole.manager:
        raise NotAuthorizedError
    return principal
