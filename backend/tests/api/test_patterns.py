"""GET /patterns returns the signed-in manager's gated patterns, and 401s without a token."""

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from pattern_mirror.api.deps import get_current_user
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
    SubjectType,
)
from pattern_mirror.models.identity import Subject, User
from pattern_mirror.services.pattern_cache import clear_pattern_cache

pytestmark = pytest.mark.db


@pytest.fixture(autouse=True)
def _reset_cache() -> Iterator[None]:
    clear_pattern_cache()
    yield
    clear_pattern_cache()


@pytest.fixture
def owner(db_session: Session) -> User:
    user = User(
        external_user_id="patterns-api-manager",
        legal_name="Patterns API Manager",
        email="patterns.api@example.com",
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def patterns_client(db_session: Session, owner: User) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: owner
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _feedback_about(db_session: Session, owner: User, *, gender: str, sharp: bool) -> None:
    subject = Subject(subject_type=SubjectType.candidate, legal_name="Candidate", gender=gender)
    db_session.add(subject)
    db_session.flush()
    document = Document(owner_id=owner.id, doc_type=DocType.feedback, subject_id=subject.id)
    db_session.add(document)
    db_session.flush()
    run = AnalysisRun(
        document_id=document.id,
        trigger=AnalysisTrigger.typing_pause,
        content_hash="0" * 64,
        status=AnalysisRunStatus.complete,
    )
    db_session.add(run)
    db_session.flush()
    if sharp:
        db_session.add(
            Flag(
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
        )
    db_session.flush()


def test_returns_a_significant_writing_pattern(
    patterns_client: TestClient, db_session: Session, owner: User
) -> None:
    for _ in range(5):
        _feedback_about(db_session, owner, gender="male", sharp=True)
    for _ in range(5):
        _feedback_about(db_session, owner, gender="female", sharp=False)

    response = patterns_client.get("/patterns")

    assert response.status_code == 200
    body = response.json()
    assert len(body["writing_patterns"]) == 1
    pattern = body["writing_patterns"][0]
    assert pattern["term"] == "sharp"
    assert pattern["category"] == "gender"
    assert pattern["mode"] == "across_time"
    assert pattern["supporting_count"] == 5
    assert pattern["p_value"] < 0.05
    assert len(pattern["document_ids"]) == 5
    assert body["decision_patterns"] == []


def _decided_flag(
    db_session: Session,
    owner: User,
    *,
    category: BiasCategory,
    span: str,
    kind: FlagInteractionKind,
    present_in_final: bool,
    submitted_at: datetime | None = None,
) -> None:
    final_text = f"a notably {span} contributor" if present_in_final else "a balanced contributor"
    document = Document(
        owner_id=owner.id,
        doc_type=DocType.feedback,
        status=DocumentStatus.submitted,
        submitted_content=final_text,
        submitted_at=submitted_at,
    )
    db_session.add(document)
    db_session.flush()
    run = AnalysisRun(
        document_id=document.id,
        trigger=AnalysisTrigger.typing_pause,
        content_hash="0" * 64,
        status=AnalysisRunStatus.complete,
    )
    db_session.add(run)
    db_session.flush()
    flag = Flag(
        document_id=document.id,
        analysis_run_id=run.id,
        source_stage=FlagSourceStage.dictionary,
        category=category,
        scope=FlagScope.general,
        raw_span=span,
        normalised_span=span,
        sentence_fingerprint="f" * 64,
        rationale={},
    )
    db_session.add(flag)
    db_session.flush()
    db_session.add(FlagInteraction(flag_id=flag.id, kind=kind))
    db_session.flush()


def test_returns_a_significant_decision_pattern(
    patterns_client: TestClient, db_session: Session, owner: User
) -> None:
    for index in range(6):
        _decided_flag(
            db_session,
            owner,
            category=BiasCategory.gender,
            span=f"aggressive{index}",
            kind=FlagInteractionKind.dismiss,
            present_in_final=True,
        )
    for index in range(6):
        _decided_flag(
            db_session,
            owner,
            category=BiasCategory.age,
            span=f"young{index}",
            kind=FlagInteractionKind.accept,
            present_in_final=False,
        )

    response = patterns_client.get("/patterns")

    assert response.status_code == 200
    decisions = {pattern["category"]: pattern for pattern in response.json()["decision_patterns"]}
    assert decisions["gender"]["adoption_rate"] == 0.0
    assert decisions["age"]["adoption_rate"] == 1.0
    assert len(decisions["gender"]["document_ids"]) == 6


def test_returns_the_adoption_trend(
    patterns_client: TestClient, db_session: Session, owner: User
) -> None:
    _decided_flag(
        db_session,
        owner,
        category=BiasCategory.gender,
        span="sharp",
        kind=FlagInteractionKind.accept,
        present_in_final=False,
        submitted_at=datetime(2026, 3, 1, tzinfo=UTC),
    )

    response = patterns_client.get("/patterns")

    assert response.status_code == 200
    assert response.json()["adoption_trend"] == [
        {"period": "2026-03", "adopted_count": 1, "total_count": 1, "adoption_rate": 1.0}
    ]


def test_returns_the_flag_volume_trend(
    patterns_client: TestClient, db_session: Session, owner: User
) -> None:
    _decided_flag(
        db_session,
        owner,
        category=BiasCategory.gender,
        span="sharp",
        kind=FlagInteractionKind.accept,
        present_in_final=False,
        submitted_at=datetime(2026, 3, 1, tzinfo=UTC),
    )

    response = patterns_client.get("/patterns")

    assert response.status_code == 200
    assert response.json()["flag_volume_trend"] == [
        {"period": "2026-03", "document_count": 1, "flag_count": 1, "flags_per_document": 1.0}
    ]


def test_returns_category_improvements(
    patterns_client: TestClient, db_session: Session, owner: User
) -> None:
    _decided_flag(
        db_session,
        owner,
        category=BiasCategory.gender,
        span="sharp",
        kind=FlagInteractionKind.accept,
        present_in_final=False,
        submitted_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    # A later month with no gender flag: gender falls to zero, age is a regression and is withheld.
    _decided_flag(
        db_session,
        owner,
        category=BiasCategory.age,
        span="young",
        kind=FlagInteractionKind.accept,
        present_in_final=False,
        submitted_at=datetime(2026, 6, 1, tzinfo=UTC),
    )

    response = patterns_client.get("/patterns")

    assert response.status_code == 200
    assert response.json()["category_improvements"] == [
        {
            "category": "gender",
            "first_period": "2026-01",
            "last_period": "2026-06",
            "first_rate": 1.0,
            "last_rate": 0.0,
            "reduction": 1.0,
        }
    ]


def test_empty_history_returns_empty_families(patterns_client: TestClient) -> None:
    response = patterns_client.get("/patterns")

    assert response.status_code == 200
    assert response.json() == {
        "writing_patterns": [],
        "decision_patterns": [],
        "adoption_trend": [],
        "flag_volume_trend": [],
        "category_improvements": [],
    }


def test_unauthenticated_request_is_rejected(db_session: Session) -> None:
    app = create_app()
    app.dependency_overrides[get_session] = lambda: db_session
    with TestClient(app) as client:
        response = client.get("/patterns")
    app.dependency_overrides.clear()

    assert response.status_code == 401
