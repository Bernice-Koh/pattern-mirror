"""seed_demo_analysis primes submitted documents with persisted analysis, idempotently.

``db``-marked and client-free: it drives the real dictionary-only path over the migration-seeded
SG lexicon (so ``digital native`` resolves to a flag), which is deterministic and needs no LLM.
The full-pipeline behaviour is covered by ``test_streaming_analysis``; this covers the job's
selection and idempotency.
"""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from pattern_mirror.jobs.seed_demo_analysis import seed_demo_analysis
from pattern_mirror.models.documents import AnalysisRun, Document
from pattern_mirror.models.engine import Flag
from pattern_mirror.models.enums import DocType, DocumentStatus
from pattern_mirror.models.identity import User
from pattern_mirror.services.documents import list_flags

pytestmark = pytest.mark.db


def _manager(db_session: Session) -> User:
    user = User(
        external_user_id="demo-analysis-manager",
        legal_name="Demo Manager",
        email="demo.analysis@example.test",
    )
    db_session.add(user)
    db_session.flush()
    return user


def _submitted(db_session: Session, owner: User, content: str) -> Document:
    document = Document(
        owner_id=owner.id,
        doc_type=DocType.jd,
        content=content,
        submitted_content=content,
        status=DocumentStatus.submitted,
    )
    db_session.add(document)
    db_session.flush()
    return document


def test_analyses_a_submitted_document_and_persists_its_flags(db_session: Session) -> None:
    owner = _manager(db_session)
    document = _submitted(db_session, owner, "We want a digital native.")

    count = seed_demo_analysis(db_session)

    assert count == 1
    persisted = db_session.scalars(select(Flag).where(Flag.document_id == document.id)).all()
    assert [flag.raw_span for flag in persisted] == ["digital native"]
    # The flag re-hydrates through the same read the reopened surface uses.
    rehydrated = list_flags(db_session, document_id=document.id, owner_id=owner.id)
    assert [flag.raw_span for flag in rehydrated] == ["digital native"]


def test_is_idempotent_across_runs(db_session: Session) -> None:
    owner = _manager(db_session)
    document = _submitted(db_session, owner, "We want a digital native.")

    assert seed_demo_analysis(db_session) == 1
    # The document now has a run, so a second pass skips it and analyses nothing new.
    assert seed_demo_analysis(db_session) == 0

    runs = db_session.scalars(
        select(AnalysisRun).where(AnalysisRun.document_id == document.id)
    ).all()
    assert len(runs) == 1


def test_skips_drafts(db_session: Session) -> None:
    owner = _manager(db_session)
    draft = Document(
        owner_id=owner.id,
        doc_type=DocType.jd,
        content="We want a digital native.",
        status=DocumentStatus.draft,
    )
    db_session.add(draft)
    db_session.flush()

    assert seed_demo_analysis(db_session) == 0
    assert (
        db_session.scalars(select(AnalysisRun).where(AnalysisRun.document_id == draft.id)).first()
        is None
    )
