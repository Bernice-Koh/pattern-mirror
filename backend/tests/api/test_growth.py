"""The /growth endpoints let HR list and decide additions, and reject non-HR callers."""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from pattern_mirror.api.deps import get_current_principal
from pattern_mirror.db.session import get_session
from pattern_mirror.main import create_app
from pattern_mirror.models.dictionary import Dictionary
from pattern_mirror.models.enums import (
    BiasCategory,
    CitationSourceType,
    DictionaryAdditionStatus,
    UserRole,
)
from pattern_mirror.models.growth import DictionaryProposal, PendingDictionaryAddition
from pattern_mirror.models.identity import User
from pattern_mirror.models.reference import Citation
from pattern_mirror.services.auth import SessionPrincipal

pytestmark = pytest.mark.db


@pytest.fixture
def actor(db_session: Session) -> User:
    user = User(
        external_user_id=f"growth-api-hr-{uuid.uuid4()}",
        legal_name="Growth API HR",
        email=f"growth.api.{uuid.uuid4()}@example.com",
    )
    db_session.add(user)
    db_session.flush()
    return user


def _client(db_session: Session, principal: SessionPrincipal | None) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_session] = lambda: db_session
    if principal is not None:
        app.dependency_overrides[get_current_principal] = lambda: principal
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def hr_client(db_session: Session, actor: User) -> Iterator[TestClient]:
    yield from _client(db_session, SessionPrincipal(user_id=actor.id, role=UserRole.hr))


@pytest.fixture
def manager_client(db_session: Session, actor: User) -> Iterator[TestClient]:
    yield from _client(db_session, SessionPrincipal(user_id=actor.id, role=UserRole.manager))


@pytest.fixture
def anon_client(db_session: Session) -> Iterator[TestClient]:
    yield from _client(db_session, None)


def _seed_pending(db_session: Session, *, lemma_key: str) -> PendingDictionaryAddition:
    citation = Citation(
        source_type=CitationSourceType.regulatory,
        title="Fair hiring guideline",
        reference="TAFEP-2021-3",
        publication_year=2021,
        finding="The phrasing discourages protected applicants.",
    )
    db_session.add(citation)
    db_session.flush()
    proposal = DictionaryProposal(phrase=lemma_key, lemma_key=lemma_key, citation_id=citation.id)
    db_session.add(proposal)
    db_session.flush()
    addition = PendingDictionaryAddition(
        proposal_id=proposal.id,
        phrase=lemma_key,
        lemma_key=lemma_key,
        proposed_category=BiasCategory.age,
        explanation="Youth-coded phrasing that deters older candidates.",
    )
    db_session.add(addition)
    db_session.flush()
    return addition


def test_list_returns_pending_additions_with_their_citation(
    hr_client: TestClient, db_session: Session
) -> None:
    _seed_pending(db_session, lemma_key="growth phrase one")

    response = hr_client.get("/growth/pending-additions")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["phrase"] == "growth phrase one"
    assert body[0]["status"] == DictionaryAdditionStatus.pending.value
    assert body[0]["citation"]["reference"] == "TAFEP-2021-3"


def test_approve_creates_entry_and_marks_addition_approved(
    hr_client: TestClient, db_session: Session
) -> None:
    addition = _seed_pending(db_session, lemma_key="growth phrase two")

    response = hr_client.post(f"/growth/pending-additions/{addition.id}/approve")

    assert response.status_code == 200
    assert response.json()["lemma_key"] == "growth phrase two"
    stored = db_session.get(PendingDictionaryAddition, addition.id)
    assert stored is not None
    assert stored.status is DictionaryAdditionStatus.approved
    assert db_session.scalars(
        select(Dictionary).where(Dictionary.lemma_key == "growth phrase two")
    ).one()


def test_reject_marks_addition_and_adds_no_entry(
    hr_client: TestClient, db_session: Session
) -> None:
    addition = _seed_pending(db_session, lemma_key="growth phrase three")

    response = hr_client.post(f"/growth/pending-additions/{addition.id}/reject")

    assert response.status_code == 200
    assert response.json()["status"] == DictionaryAdditionStatus.rejected.value
    assert response.json()["decided_at"] is not None
    assert db_session.scalars(
        select(Dictionary).where(Dictionary.lemma_key == "growth phrase three")
    ).all() == []


def test_defer_marks_addition_deferred(hr_client: TestClient, db_session: Session) -> None:
    addition = _seed_pending(db_session, lemma_key="growth phrase four")

    response = hr_client.post(f"/growth/pending-additions/{addition.id}/defer")

    assert response.status_code == 200
    assert response.json()["status"] == DictionaryAdditionStatus.deferred.value


def test_deciding_twice_conflicts(hr_client: TestClient, db_session: Session) -> None:
    addition = _seed_pending(db_session, lemma_key="growth phrase five")
    hr_client.post(f"/growth/pending-additions/{addition.id}/approve")

    conflict = hr_client.post(f"/growth/pending-additions/{addition.id}/reject")

    assert conflict.status_code == 409


def test_unknown_addition_is_not_found(hr_client: TestClient) -> None:
    response = hr_client.post(f"/growth/pending-additions/{uuid.uuid4()}/approve")
    assert response.status_code == 404


def test_manager_role_is_forbidden(manager_client: TestClient, db_session: Session) -> None:
    addition = _seed_pending(db_session, lemma_key="growth phrase six")

    assert manager_client.get("/growth/pending-additions").status_code == 403
    assert (
        manager_client.post(f"/growth/pending-additions/{addition.id}/approve").status_code == 403
    )


def test_unauthenticated_is_rejected(anon_client: TestClient) -> None:
    assert anon_client.get("/growth/pending-additions").status_code == 401
