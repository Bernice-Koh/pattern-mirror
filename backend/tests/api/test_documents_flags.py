"""GET /documents/{id}/flags re-hydrates a document's surfaced flags on reopen.

Session and current-user dependencies are overridden onto the test's rolled-back transaction, so
the endpoint's reads and the test's writes share one transaction. The latest-run / suppression
semantics are asserted in the service test; this covers the wire shape and the ownership 404.
"""

import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from pattern_mirror.api.deps import get_current_user
from pattern_mirror.db.session import get_session
from pattern_mirror.main import create_app
from pattern_mirror.models.documents import AnalysisRun, Document
from pattern_mirror.models.engine import Flag
from pattern_mirror.models.enums import (
    AnalysisRunStatus,
    AnalysisTrigger,
    BiasCategory,
    CitationSourceType,
    DocType,
    FlagScope,
    FlagSourceStage,
)
from pattern_mirror.models.identity import User
from pattern_mirror.models.reference import Citation

pytestmark = pytest.mark.db


@pytest.fixture
def flags_client(db_session: Session) -> Iterator[tuple[TestClient, User]]:
    user = User(
        external_user_id="api-flags-manager",
        legal_name="API Flags Manager",
        email="api.flags@example.com",
    )
    db_session.add(user)
    db_session.flush()

    app = create_app()
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app) as client:
        yield client, user
    app.dependency_overrides.clear()


def _document_with_flag(db_session: Session, owner: User, *, suppressed: bool = False) -> Document:
    document = Document(owner_id=owner.id, doc_type=DocType.jd, content="We want a digital native.")
    db_session.add(document)
    db_session.flush()
    run = AnalysisRun(
        document_id=document.id,
        trigger=AnalysisTrigger.typing_pause,
        content_hash="0" * 64,
        status=AnalysisRunStatus.complete,
    )
    db_session.add(run)
    citation = Citation(
        source_type=CitationSourceType.tafep,
        title="TAFEP Guidelines on Fair Employment",
        reference="tafep-2021",
        publication_year=2021,
        finding="Age-coded language deters older applicants.",
    )
    db_session.add(citation)
    db_session.flush()
    rationale: dict[str, Any] = {"explanation": "'digital native' is age-coded."}
    db_session.add(
        Flag(
            document_id=document.id,
            analysis_run_id=run.id,
            source_stage=FlagSourceStage.dictionary,
            citation_id=citation.id,
            category=BiasCategory.age,
            scope=FlagScope.general,
            raw_span="digital native",
            normalised_span="digital native",
            sentence_fingerprint="f" * 64,
            start_offset=10,
            end_offset=24,
            rationale=rationale,
            suppressed=suppressed,
        )
    )
    db_session.flush()
    return document


def test_get_returns_the_documents_surfaced_flags(
    flags_client: tuple[TestClient, User], db_session: Session
) -> None:
    client, user = flags_client
    document = _document_with_flag(db_session, user)

    response = client.get(f"/documents/{document.id}/flags")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    flag = body[0]
    assert flag["raw_span"] == "digital native"
    assert flag["source_stage"] == "dictionary"
    assert flag["explanation"] == "'digital native' is age-coded."
    assert flag["citation"]["source_type"] == "tafep"


def test_get_excludes_suppressed_flags(
    flags_client: tuple[TestClient, User], db_session: Session
) -> None:
    client, user = flags_client
    document = _document_with_flag(db_session, user, suppressed=True)

    response = client.get(f"/documents/{document.id}/flags")

    assert response.status_code == 200
    assert response.json() == []


def test_get_on_a_document_with_no_flags_is_empty(
    flags_client: tuple[TestClient, User], db_session: Session
) -> None:
    client, user = flags_client
    document = Document(owner_id=user.id, doc_type=DocType.jd, content="Clean copy.")
    db_session.add(document)
    db_session.flush()

    response = client.get(f"/documents/{document.id}/flags")

    assert response.status_code == 200
    assert response.json() == []


def test_get_on_another_users_document_is_not_found(
    flags_client: tuple[TestClient, User], db_session: Session
) -> None:
    client, _ = flags_client
    other = User(
        external_user_id="api-flags-other",
        legal_name="Other Manager",
        email="api.flags.other@example.com",
    )
    db_session.add(other)
    db_session.flush()
    document = _document_with_flag(db_session, other)

    response = client.get(f"/documents/{document.id}/flags")

    assert response.status_code == 404


def test_get_on_a_missing_document_is_not_found(
    flags_client: tuple[TestClient, User],
) -> None:
    client, _ = flags_client

    response = client.get(f"/documents/{uuid.uuid4()}/flags")

    assert response.status_code == 404
