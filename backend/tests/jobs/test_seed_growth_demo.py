"""The growth-queue demo seed inserts full audit chains and is safe to re-run."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pattern_mirror.jobs.seed_growth_demo import CANDIDATES, seed_growth_queue
from pattern_mirror.models.audit import AgentRun
from pattern_mirror.models.enums import DictionaryAdditionStatus
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

    second_run = seed_growth_queue(db_session)

    assert second_run == 0
    total = db_session.scalar(select(func.count()).select_from(PendingDictionaryAddition))
    assert total == len(CANDIDATES)
