"""The /auth/login endpoint and the token-based get_current_user seam.

Login is exercised over the real credential path against seeded users; the token it returns is
then used to reach a protected route, confirming get_current_user resolves the bearer token.
"""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from pattern_mirror.api.auth import _initials
from pattern_mirror.core.errors import RecommendationCountError
from pattern_mirror.db.session import get_session
from pattern_mirror.main import create_app
from pattern_mirror.models.enums import UserRole
from pattern_mirror.models.identity import User, UserRoleAssignment
from pattern_mirror.services.auth import SessionPrincipal, sign_token

pytestmark = pytest.mark.db

_MANAGER_EMAIL = "alex.tan@example.com"
_HR_EMAIL = "jordan.lee@example.com"


@pytest.fixture
def seeded_users(db_session: Session) -> None:
    for email, role, name in (
        (_MANAGER_EMAIL, UserRole.manager, "Alex Tan"),
        (_HR_EMAIL, UserRole.hr, "Jordan Lee"),
    ):
        user = User(external_user_id=f"auth-{role.value}", legal_name=name, email=email)
        db_session.add(user)
        db_session.flush()
        db_session.add(UserRoleAssignment(user_id=user.id, role=role))
    db_session.flush()


@pytest.fixture
def client(db_session: Session, seeded_users: None) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_session] = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _login(client: TestClient, *, email: str, role: str) -> object:
    return client.post(
        "/auth/login",
        json={"email": email, "password": "anything", "expected_role": role},
    )


def test_manager_login_returns_a_token_and_identity(client: TestClient) -> None:
    response = _login(client, email=_MANAGER_EMAIL, role="manager")

    assert response.status_code == 200
    body = response.json()
    assert body["token"]
    assert body["user"]["role"] == "manager"
    assert body["user"]["initials"] == "AT"
    assert body["user"]["email"] == _MANAGER_EMAIL


def test_hr_login_lands_on_the_hr_role(client: TestClient) -> None:
    response = _login(client, email=_HR_EMAIL, role="hr")

    assert response.status_code == 200
    assert response.json()["user"]["role"] == "hr"


def test_manager_on_the_hr_screen_is_rejected(client: TestClient) -> None:
    response = _login(client, email=_MANAGER_EMAIL, role="hr")

    assert response.status_code == 401
    assert response.json()["error"] == "InvalidCredentialsError"


def test_unknown_email_is_rejected(client: TestClient) -> None:
    response = _login(client, email="nobody@example.com", role="manager")

    assert response.status_code == 401


def test_empty_password_is_unprocessable(client: TestClient) -> None:
    response = client.post(
        "/auth/login",
        json={"email": _MANAGER_EMAIL, "password": "", "expected_role": "manager"},
    )

    assert response.status_code == 422


def test_token_reaches_a_protected_route(client: TestClient) -> None:
    token = _login(client, email=_MANAGER_EMAIL, role="manager").json()["token"]

    created = client.post(
        "/documents",
        json={"doc_type": "jd"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert created.status_code == 200


def test_protected_route_without_a_token_is_unauthorized(client: TestClient) -> None:
    response = client.post("/documents", json={"doc_type": "jd"})

    assert response.status_code == 401
    assert response.json()["error"] == "NotAuthenticatedError"


def test_protected_route_with_a_bad_token_is_unauthorized(client: TestClient) -> None:
    response = client.post(
        "/documents",
        json={"doc_type": "jd"},
        headers={"Authorization": "Bearer not-a-real-token"},
    )

    assert response.status_code == 401


def test_token_for_an_unknown_user_is_unauthorized(client: TestClient) -> None:
    token = sign_token(SessionPrincipal(user_id=uuid.uuid4(), role=UserRole.manager))

    response = client.post(
        "/documents",
        json={"doc_type": "jd"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert response.json()["error"] == "NotAuthenticatedError"


@pytest.mark.parametrize(
    ("legal_name", "expected"),
    [("", "?"), ("Cher", "CH"), ("Alex Tan", "AT"), ("Maria de la Cruz", "MC")],
)
def test_initials(legal_name: str, expected: str) -> None:
    assert _initials(legal_name) == expected


def test_unexpected_domain_error_maps_to_500() -> None:
    app = create_app()

    @app.get("/_raise_domain")
    def _raise() -> None:
        raise RecommendationCountError(expected=1, received=2)

    with TestClient(app, raise_server_exceptions=False) as test_client:
        response = test_client.get("/_raise_domain")

    assert response.status_code == 500
    assert response.json()["error"] == "RecommendationCountError"
