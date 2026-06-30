"""The pattern cache reuses a report until the manager's history changes, then recomputes."""

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy.orm import Session

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
)
from pattern_mirror.models.identity import User
from pattern_mirror.services.pattern_cache import (
    cached_pattern_report,
    clear_pattern_cache,
)

pytestmark = pytest.mark.db

_THRESHOLD = 0.05


@pytest.fixture(autouse=True)
def _reset_cache() -> Iterator[None]:
    clear_pattern_cache()
    yield
    clear_pattern_cache()


def _manager(session: Session, suffix: str) -> User:
    user = User(
        external_user_id=f"cache-{suffix}",
        legal_name="Cache Manager",
        email=f"{suffix}@example.test",
    )
    session.add(user)
    session.flush()
    return user


def _submitted_flag(session: Session, owner: User, span: str) -> Flag:
    document = Document(
        owner_id=owner.id,
        doc_type=DocType.feedback,
        status=DocumentStatus.submitted,
        submitted_content=f"a notably {span} contributor",
    )
    session.add(document)
    session.flush()
    run = AnalysisRun(
        document_id=document.id,
        trigger=AnalysisTrigger.typing_pause,
        content_hash="0" * 64,
        status=AnalysisRunStatus.complete,
    )
    session.add(run)
    session.flush()
    flag = Flag(
        document_id=document.id,
        analysis_run_id=run.id,
        source_stage=FlagSourceStage.dictionary,
        category=BiasCategory.gender,
        scope=FlagScope.general,
        raw_span=span,
        normalised_span=span,
        sentence_fingerprint="f" * 64,
        rationale={},
    )
    session.add(flag)
    session.flush()
    return flag


def test_second_call_returns_the_cached_object(db_session: Session) -> None:
    owner = _manager(db_session, "hit")
    _submitted_flag(db_session, owner, "sharp")

    first = cached_pattern_report(db_session, owner_id=owner.id, threshold=_THRESHOLD)
    second = cached_pattern_report(db_session, owner_id=owner.id, threshold=_THRESHOLD)

    assert first is second


def test_a_new_interaction_invalidates_the_cache(db_session: Session) -> None:
    owner = _manager(db_session, "invalidate")
    flag = _submitted_flag(db_session, owner, "sharp")

    first = cached_pattern_report(db_session, owner_id=owner.id, threshold=_THRESHOLD)
    db_session.add(FlagInteraction(flag_id=flag.id, kind=FlagInteractionKind.dismiss))
    db_session.flush()
    second = cached_pattern_report(db_session, owner_id=owner.id, threshold=_THRESHOLD)

    assert first is not second


def test_clear_forces_a_recompute(db_session: Session) -> None:
    owner = _manager(db_session, "clear")
    _submitted_flag(db_session, owner, "sharp")

    first = cached_pattern_report(db_session, owner_id=owner.id, threshold=_THRESHOLD)
    clear_pattern_cache()
    second = cached_pattern_report(db_session, owner_id=owner.id, threshold=_THRESHOLD)

    assert first is not second


def test_a_different_threshold_recomputes(db_session: Session) -> None:
    owner = _manager(db_session, "threshold")
    _submitted_flag(db_session, owner, "sharp")

    first = cached_pattern_report(db_session, owner_id=owner.id, threshold=_THRESHOLD)
    second = cached_pattern_report(db_session, owner_id=owner.id, threshold=0.01)

    assert first is not second


def test_unknown_manager_reports_nothing(db_session: Session) -> None:
    report = cached_pattern_report(db_session, owner_id=uuid.uuid4(), threshold=_THRESHOLD)

    assert report.writing_patterns == ()
    assert report.decision_patterns == ()
