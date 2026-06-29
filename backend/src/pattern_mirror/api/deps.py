"""Shared FastAPI dependencies.

``get_current_user`` resolves the signed-in user from the request's bearer token. It is the one
seam every authenticated endpoint depends on; tests override it directly to inject a known user.
"""

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from pattern_mirror.core.errors import NotAuthenticatedError
from pattern_mirror.db.session import get_session
from pattern_mirror.models.identity import User
from pattern_mirror.services.auth import verify_token

# auto_error=False so a missing header yields None and raises our typed 401 rather than
# Starlette's bare 403.
_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    session: Annotated[Session, Depends(get_session)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    """Return the user named by the request's session token.

    Raises:
        NotAuthenticatedError: if the token is absent, invalid, or names an inactive/unknown user.
    """
    if credentials is None:
        raise NotAuthenticatedError
    principal = verify_token(credentials.credentials)
    user = session.get(User, principal.user_id)
    if user is None or not user.active:
        raise NotAuthenticatedError
    return user
