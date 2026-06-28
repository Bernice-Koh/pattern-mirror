"""End-to-end POST /flags/{flag_id}/interactions: persisted event out, foreign flag 404.

The session and current-user dependencies are overridden onto the test's rolled-back
transaction, so the endpoint's writes and the test's assertions share one transaction.
"""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from pattern_mirror.api.deps import get_current_user
from pattern_mirror.db.session import get_session
from pattern_mirror.main import create_app
from pattern_mirror.models.engine import Flag, FlagDismissal, FlagInteraction
from pattern_mirror.models.enums import DocType
from pattern_mirror.models.identity import User
from pattern_mirror.services.analysis import analyze_document

pytestmark = pytest.mark.db


@pytest.fixture
def interaction_client(db_session: Session) -> Iterator[tuple[TestClient, User]]:
    user = User(
        external_user_id="api-interactions-manager",
        legal_name="API Interactions Manager",
        email="api.interactions@example.com",
    )
    db_session.add(user)
    db_session.flush()

    app = create_app()
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app) as client:
        yield client, user
    app.dependency_overrides.clear()


def _a_flag(db_session: Session, owner: User) -> Flag:
    result = analyze_document(
        db_session, owner_id=owner.id, doc_type=DocType.jd, content="We want a digital native."
    )
    return result.flags[0]


def test_dismiss_persists_an_event_and_a_dismissal(
    interaction_client: tuple[TestClient, User], db_session: Session
) -> None:
    client, user = interaction_client
    flag = _a_flag(db_session, user)

    response = client.post(f"/flags/{flag.id}/interactions", json={"kind": "dismiss"})

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "dismiss"
    assert body["dismissed"] is True
    assert db_session.scalars(
        select(FlagInteraction).where(FlagInteraction.flag_id == flag.id)
    ).one()
    assert db_session.scalars(
        select(FlagDismissal).where(FlagDismissal.document_id == flag.document_id)
    ).one()


def test_accept_carries_the_taken_alternative(
    interaction_client: tuple[TestClient, User], db_session: Session
) -> None:
    client, user = interaction_client
    flag = _a_flag(db_session, user)

    response = client.post(
        f"/flags/{flag.id}/interactions",
        json={"kind": "accept", "accepted_alternative": "recent graduate"},
    )

    assert response.status_code == 200
    assert response.json()["dismissed"] is False
    event = db_session.scalars(
        select(FlagInteraction).where(FlagInteraction.flag_id == flag.id)
    ).one()
    assert event.accepted_alternative == "recent graduate"


def test_unknown_flag_is_not_found(interaction_client: tuple[TestClient, User]) -> None:
    client, _ = interaction_client

    response = client.post(f"/flags/{uuid.uuid4()}/interactions", json={"kind": "accept"})

    assert response.status_code == 404


def test_unknown_kind_is_rejected(
    interaction_client: tuple[TestClient, User], db_session: Session
) -> None:
    client, user = interaction_client
    flag = _a_flag(db_session, user)

    response = client.post(f"/flags/{flag.id}/interactions", json={"kind": "snooze"})

    assert response.status_code == 422
