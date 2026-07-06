"""The behaviour seed records realistic, category-skewed accept/dismiss interactions, idempotently.

The outcome per flag is a deterministic draw against a per-cohort target share, so the assertions
are over cohorts (gender revised least, recent revised most, never 0% or 100%) rather than a single
flag's kind.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pattern_mirror.jobs.seed_demo_behaviour import seed_demo_behaviour
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

pytestmark = pytest.mark.db

_NOW = datetime(2026, 7, 1, tzinfo=UTC)


def _owner(session: Session) -> User:
    user = User(
        external_user_id=f"behaviour-{uuid.uuid4()}",
        legal_name="Behaviour Manager",
        email=f"{uuid.uuid4()}@example.test",
    )
    session.add(user)
    session.flush()
    return user


def _submitted_doc(session: Session, owner: User, *, days_ago: int) -> Document:
    document = Document(
        owner_id=owner.id,
        doc_type=DocType.feedback,
        status=DocumentStatus.submitted,
        content="text",
        submitted_content="text",
        submitted_at=_NOW - timedelta(days=days_ago),
    )
    session.add(document)
    session.flush()
    return document


def _run(session: Session, document: Document) -> AnalysisRun:
    run = AnalysisRun(
        document_id=document.id,
        trigger=AnalysisTrigger.submit,
        content_hash="0" * 64,
        status=AnalysisRunStatus.complete,
    )
    session.add(run)
    session.flush()
    return run


def _flags(
    session: Session,
    document: Document,
    category: BiasCategory,
    count: int,
    *,
    suppressed: bool = False,
) -> list[Flag]:
    """Add ``count`` distinct surfaced flags to the document's run, each a different concept."""
    run = _run(session, document)
    flags = [
        Flag(
            document_id=document.id,
            analysis_run_id=run.id,
            source_stage=FlagSourceStage.contextual,
            category=category,
            scope=FlagScope.general,
            raw_span=f"term{i}",
            normalised_span=f"term{i}",
            sentence_fingerprint=f"{i:064d}",
            rationale={},
            suppressed=suppressed,
        )
        for i in range(count)
    ]
    session.add_all(flags)
    session.flush()
    return flags


def _adopted_rate(session: Session, flags: list[Flag]) -> float:
    ids = [flag.id for flag in flags]
    accepted = session.scalar(
        select(func.count())
        .select_from(FlagInteraction)
        .where(
            FlagInteraction.flag_id.in_(ids),
            FlagInteraction.kind == FlagInteractionKind.accept,
        )
    )
    return (accepted or 0) / len(flags)


def test_gender_language_is_revised_less_than_other_categories(db_session: Session) -> None:
    owner = _owner(db_session)
    # Separate documents so each cohort is its document's latest run (one run per document).
    gender_doc = _submitted_doc(db_session, owner, days_ago=30)
    age_doc = _submitted_doc(db_session, owner, days_ago=30)
    gender = _flags(db_session, gender_doc, BiasCategory.gender, 40)
    age = _flags(db_session, age_doc, BiasCategory.age, 40)

    seed_demo_behaviour(db_session, now=_NOW)

    gender_rate = _adopted_rate(db_session, gender)
    age_rate = _adopted_rate(db_session, age)
    assert gender_rate < age_rate
    # Neither cohort collapses to a fake 0% or 100%.
    assert 0.0 < gender_rate < 1.0
    assert 0.0 < age_rate < 1.0


def test_recent_documents_are_revised_more_than_old_ones(db_session: Session) -> None:
    owner = _owner(db_session)
    recent = _submitted_doc(db_session, owner, days_ago=20)
    old = _submitted_doc(db_session, owner, days_ago=150)
    recent_flags = _flags(db_session, recent, BiasCategory.gender, 40)
    old_flags = _flags(db_session, old, BiasCategory.gender, 40)

    seed_demo_behaviour(db_session, now=_NOW)

    assert _adopted_rate(db_session, recent_flags) > _adopted_rate(db_session, old_flags)


def test_suppressed_flag_gets_no_interaction(db_session: Session) -> None:
    owner = _owner(db_session)
    doc = _submitted_doc(db_session, owner, days_ago=10)
    flags = _flags(db_session, doc, BiasCategory.gender, 1, suppressed=True)

    seed_demo_behaviour(db_session, now=_NOW)

    interactions = db_session.scalar(
        select(func.count())
        .select_from(FlagInteraction)
        .where(FlagInteraction.flag_id == flags[0].id)
    )
    assert interactions == 0


def test_is_idempotent(db_session: Session) -> None:
    owner = _owner(db_session)
    doc = _submitted_doc(db_session, owner, days_ago=10)
    _flags(db_session, doc, BiasCategory.gender, 5)

    first = seed_demo_behaviour(db_session, now=_NOW)
    db_session.flush()
    second = seed_demo_behaviour(db_session, now=_NOW)

    assert first == 5
    assert second == 0
    total = db_session.scalar(select(func.count()).select_from(FlagInteraction))
    assert total == 5
