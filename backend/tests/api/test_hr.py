"""The /hr endpoints serve aggregates to HR, reject non-HR, and never leak individual content."""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from pattern_mirror.api.deps import get_current_principal
from pattern_mirror.db.session import get_session
from pattern_mirror.main import create_app
from pattern_mirror.models.documents import AnalysisRun, Document
from pattern_mirror.models.engine import Flag, FlagInteraction
from pattern_mirror.models.enums import (
    AnalysisRunStatus,
    AnalysisTrigger,
    BiasCategory,
    DocType,
    DocumentStatus,
    FlagInteractionKind,
    FlagScope,
    FlagSourceStage,
    UserRole,
)
from pattern_mirror.models.identity import User
from pattern_mirror.services.auth import SessionPrincipal

pytestmark = pytest.mark.db

_HR_ENDPOINTS = ("/hr/effectiveness", "/hr/calibration", "/hr/dictionary-health")
# Distinctive text seeded into a manager's submitted document; it must never reach an HR response.
_SENTINEL = "CONFIDENTIAL-MANAGER-PROSE-9f3a"


def _principal(role: UserRole) -> SessionPrincipal:
    return SessionPrincipal(user_id=uuid.uuid4(), role=role)


def _hr_client(db_session: Session, role: UserRole) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_current_principal] = lambda: _principal(role)
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def hr_client(db_session: Session) -> Iterator[TestClient]:
    yield from _hr_client(db_session, UserRole.hr)


@pytest.fixture
def manager_client(db_session: Session) -> Iterator[TestClient]:
    yield from _hr_client(db_session, UserRole.manager)


def _seed_manager_with_flag(db_session: Session, index: int) -> uuid.UUID:
    """A manager who submitted a document carrying the sentinel content, with one dismissed flag."""
    user = User(
        external_user_id=f"hr-api-manager-{index}",
        legal_name=f"HR API Manager {index}",
        email=f"hr.api.{index}@example.com",
    )
    db_session.add(user)
    db_session.flush()
    document = Document(
        owner_id=user.id,
        doc_type=DocType.feedback,
        status=DocumentStatus.submitted,
        submitted_content=f"{_SENTINEL} describes a sharp candidate",
        submitted_at=datetime(2026, 3, 1, tzinfo=UTC),
    )
    db_session.add(document)
    db_session.flush()
    run = AnalysisRun(
        document_id=document.id,
        trigger=AnalysisTrigger.submit,
        content_hash="0" * 64,
        status=AnalysisRunStatus.complete,
    )
    db_session.add(run)
    db_session.flush()
    flag = Flag(
        document_id=document.id,
        analysis_run_id=run.id,
        source_stage=FlagSourceStage.dictionary,
        category=BiasCategory.gender,
        scope=FlagScope.general,
        raw_span="sharp",
        normalised_span="sharp",
        sentence_fingerprint="f" * 64,
        rationale={},
    )
    db_session.add(flag)
    db_session.flush()
    db_session.add(FlagInteraction(flag_id=flag.id, kind=FlagInteractionKind.dismiss))
    db_session.flush()
    return document.id


def test_hr_user_can_read_each_dimension(hr_client: TestClient) -> None:
    for endpoint in _HR_ENDPOINTS:
        response = hr_client.get(endpoint)

        assert response.status_code == 200


def test_effectiveness_returns_aggregated_adoption(
    hr_client: TestClient, db_session: Session
) -> None:
    for index in range(3):
        _seed_manager_with_flag(db_session, index)

    body = hr_client.get("/hr/effectiveness").json()

    by_category = {cell["category"]: cell for cell in body["adoption_by_category"]}
    assert by_category["gender"]["total_count"] == 3


def test_manager_session_is_forbidden(manager_client: TestClient) -> None:
    for endpoint in _HR_ENDPOINTS:
        response = manager_client.get(endpoint)

        assert response.status_code == 403


def test_unauthenticated_request_is_rejected(db_session: Session) -> None:
    app = create_app()
    app.dependency_overrides[get_session] = lambda: db_session
    with TestClient(app) as client:
        response = client.get("/hr/effectiveness")
    app.dependency_overrides.clear()

    assert response.status_code == 401


def test_no_hr_endpoint_leaks_individual_content(
    hr_client: TestClient, db_session: Session
) -> None:
    document_ids = [str(_seed_manager_with_flag(db_session, index)) for index in range(3)]

    for endpoint in _HR_ENDPOINTS:
        response = hr_client.get(endpoint)

        assert response.status_code == 200
        assert _SENTINEL not in response.text
        assert all(document_id not in response.text for document_id in document_ids)
        assert "document_id" not in response.text
