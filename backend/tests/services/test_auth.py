"""Token signing round-trips and tamper-rejects; authenticate matches email to an active role."""

import uuid

import pytest
from sqlalchemy.orm import Session

from pattern_mirror.core.errors import InvalidCredentialsError, NotAuthenticatedError
from pattern_mirror.models.enums import UserRole
from pattern_mirror.models.identity import User, UserRoleAssignment
from pattern_mirror.services.auth import (
    SessionPrincipal,
    authenticate,
    sign_token,
    verify_token,
)


def test_sign_then_verify_round_trips() -> None:
    principal = SessionPrincipal(user_id=uuid.uuid4(), role=UserRole.hr)

    assert verify_token(sign_token(principal)) == principal


def test_tampered_signature_is_rejected() -> None:
    token = sign_token(SessionPrincipal(user_id=uuid.uuid4(), role=UserRole.manager))
    body, _, signature = token.partition(".")
    forged = f"{body}.{signature[:-1]}{'A' if signature[-1] != 'A' else 'B'}"

    with pytest.raises(NotAuthenticatedError):
        verify_token(forged)


def test_malformed_token_is_rejected() -> None:
    with pytest.raises(NotAuthenticatedError):
        verify_token("not-a-token")


def _seed_user(session: Session, *, email: str, role: UserRole, active: bool = True) -> User:
    user = User(
        external_user_id=f"auth-test-{email}",
        legal_name="Auth Test",
        email=email,
        active=active,
    )
    session.add(user)
    session.flush()
    session.add(UserRoleAssignment(user_id=user.id, role=role))
    session.flush()
    return user


@pytest.mark.db
def test_authenticate_returns_user_when_role_matches(db_session: Session) -> None:
    user = _seed_user(db_session, email="manager@example.com", role=UserRole.manager)

    assert authenticate(db_session, email=user.email, expected_role=UserRole.manager) == user


@pytest.mark.db
def test_authenticate_rejects_wrong_role(db_session: Session) -> None:
    user = _seed_user(db_session, email="manager2@example.com", role=UserRole.manager)

    with pytest.raises(InvalidCredentialsError):
        authenticate(db_session, email=user.email, expected_role=UserRole.hr)


@pytest.mark.db
def test_authenticate_rejects_unknown_email(db_session: Session) -> None:
    with pytest.raises(InvalidCredentialsError):
        authenticate(db_session, email="nobody@example.com", expected_role=UserRole.manager)


@pytest.mark.db
def test_authenticate_rejects_inactive_user(db_session: Session) -> None:
    user = _seed_user(db_session, email="gone@example.com", role=UserRole.hr, active=False)

    with pytest.raises(InvalidCredentialsError):
        authenticate(db_session, email=user.email, expected_role=UserRole.hr)
