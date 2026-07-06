"""The growth-queue demo seed inserts full audit chains and is safe to re-run."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pattern_mirror.jobs.seed_growth_demo import CANDIDATES, seed_growth_queue
from pattern_mirror.models.audit import AgentRun
from pattern_mirror.models.documents import Document
from pattern_mirror.models.engine import Flag
from pattern_mirror.models.enums import DictionaryAdditionStatus, FlagScope, FlagSourceStage
from pattern_mirror.models.growth import PendingDictionaryAddition

pytestmark = pytest.mark.db


def test_seed_queues_each_candidate_with_its_full_chain(db_session: Session) -> None:
    created = seed_growth_queue(db_session)

    assert created == len(CANDIDATES)
    additions = db_session.scalars(select(PendingDictionaryAddition)).all()
    assert len(additions) == len(CANDIDATES)
    for addition in additions:
        assert addition.proposal.citation is not None
        run_count = db_session.scalar(
            select(func.count())
            .select_from(AgentRun)
            .where(AgentRun.proposal_id == addition.proposal_id)
        )
        assert run_count == 4


def test_seed_backs_each_candidate_with_its_flag_count(db_session: Session) -> None:
    seed_growth_queue(db_session)

    for candidate in CANDIDATES:
        surfaced = db_session.scalar(
            select(func.count())
            .select_from(Flag)
            .where(
                Flag.normalised_span == candidate.phrase.lower().strip(),
                Flag.source_stage == FlagSourceStage.contextual,
                Flag.scope == FlagScope.general,
            )
        )
        assert surfaced == candidate.flag_count


def test_backing_flags_sit_on_unsubmitted_drafts(db_session: Session) -> None:
    # The word-cloud weight must not leak into the HR / Pattern Dashboard aggregates, which read
    # submitted documents only.
    seed_growth_queue(db_session)

    submitted_flags = db_session.scalar(
        select(func.count())
        .select_from(Flag)
        .join(Document, Document.id == Flag.document_id)
        .where(Document.submitted_content.is_not(None))
    )
    assert submitted_flags == 0


def test_seed_marks_the_deferred_candidate(db_session: Session) -> None:
    seed_growth_queue(db_session)

    deferred = db_session.scalars(
        select(PendingDictionaryAddition).where(
            PendingDictionaryAddition.status == DictionaryAdditionStatus.deferred
        )
    ).all()

    assert len(deferred) == sum(candidate.deferred for candidate in CANDIDATES)


def test_seed_is_idempotent(db_session: Session) -> None:
    seed_growth_queue(db_session)
    flags_after_first = db_session.scalar(select(func.count()).select_from(Flag))

    second_run = seed_growth_queue(db_session)

    assert second_run == 0
    total = db_session.scalar(select(func.count()).select_from(PendingDictionaryAddition))
    assert total == len(CANDIDATES)
    # A re-run adds no additions, so it adds no backing flags either.
    assert db_session.scalar(select(func.count()).select_from(Flag)) == flags_after_first
