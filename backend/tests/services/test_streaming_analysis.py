"""The streaming pipeline service: per-stage events, persistence, supersede, failure.

The happy-path and supersede tests drive the real default graph over the migration-seeded
SG lexicon (so ``digital native`` resolves to a flag); the failure test substitutes a graph
that raises mid-stream. All are ``db``-marked because the run and its flags are persisted.
"""

import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from pattern_mirror.models.documents import AnalysisRun, Document
from pattern_mirror.models.engine import Flag
from pattern_mirror.models.enums import AnalysisRunStatus, DocType
from pattern_mirror.models.identity import User
from pattern_mirror.services import streaming_analysis
from pattern_mirror.services.run_registry import RunRegistry
from pattern_mirror.services.streaming_analysis import (
    FlagSurfaced,
    RunCompleted,
    StageCompleted,
    stream_analysis_events,
)

pytestmark = pytest.mark.db

_BIASED_TEXT = "We want a digital native for this role."


def _document(session: Session, *, content: str = _BIASED_TEXT) -> Document:
    user = User(
        external_user_id=f"stream-test-{uuid.uuid4()}",
        legal_name="Stream Manager",
        email=f"{uuid.uuid4()}@example.com",
    )
    session.add(user)
    session.flush()
    document = Document(owner_id=user.id, doc_type=DocType.jd, content=content)
    session.add(document)
    session.flush()
    return document


def test_stages_stream_then_a_verified_flag_then_a_terminal_done(db_session: Session) -> None:
    document = _document(db_session)

    events = list(
        stream_analysis_events(
            db_session,
            document_id=document.id,
            content=document.content,
            doc_type=document.doc_type,
            registry=RunRegistry(),
        )
    )

    assert any(isinstance(event, StageCompleted) for event in events)
    flags = [event for event in events if isinstance(event, FlagSurfaced)]
    assert [flag.flag.raw_span for flag in flags] == ["digital native"]

    terminal = events[-1]
    assert isinstance(terminal, RunCompleted)
    assert terminal.status is AnalysisRunStatus.complete
    assert terminal.flag_count == 1

    persisted = db_session.scalars(select(Flag).where(Flag.document_id == document.id)).all()
    assert [flag.raw_span for flag in persisted] == ["digital native"]


def test_clean_text_streams_no_flags_and_completes(db_session: Session) -> None:
    document = _document(db_session, content="We value clear communication.")

    events = list(
        stream_analysis_events(
            db_session,
            document_id=document.id,
            content=document.content,
            doc_type=document.doc_type,
            registry=RunRegistry(),
        )
    )

    assert not any(isinstance(event, FlagSurfaced) for event in events)
    terminal = events[-1]
    assert isinstance(terminal, RunCompleted)
    assert terminal.status is AnalysisRunStatus.complete
    assert terminal.flag_count == 0


def test_a_newer_run_supersedes_the_older_one_but_its_flags_persist(db_session: Session) -> None:
    document = _document(db_session)
    registry = RunRegistry()

    events: list[Any] = []
    stream = stream_analysis_events(
        db_session,
        document_id=document.id,
        content=document.content,
        doc_type=document.doc_type,
        registry=registry,
    )
    for event in stream:
        events.append(event)
        # A newer run starts once the older one clears contextual, i.e. the stage before the
        # adjudicator produces its flag — so the adjudicator persists but does not surface it.
        if isinstance(event, StageCompleted) and event.stage == "contextual":
            registry.register(document.id, uuid.uuid4())

    terminal = events[-1]
    assert isinstance(terminal, RunCompleted)
    assert terminal.status is AnalysisRunStatus.superseded

    # Suppress in UI: the superseded run surfaced no flags to the client.
    assert not any(isinstance(event, FlagSurfaced) for event in events)
    # Log everything: yet the flag the engine produced was committed to the database.
    persisted = db_session.scalars(select(Flag).where(Flag.document_id == document.id)).all()
    assert [flag.raw_span for flag in persisted] == ["digital native"]


class _RaisingGraph:
    """A compiled-graph stand-in: yields one stage, then fails as a later stage would."""

    def stream(self, state: Any, stream_mode: str) -> Iterator[dict[str, Any]]:
        yield {"dictionary": {"candidate_flags": []}}
        raise RuntimeError("contextual stage exploded")


def test_a_failed_stage_is_logged_and_the_stream_closes_cleanly(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    document = _document(db_session)
    monkeypatch.setattr(streaming_analysis, "build_default_graph", lambda session: _RaisingGraph())

    events = list(
        stream_analysis_events(
            db_session,
            document_id=document.id,
            content=document.content,
            doc_type=document.doc_type,
            registry=RunRegistry(),
        )
    )

    terminal = events[-1]
    assert isinstance(terminal, RunCompleted)
    assert terminal.status is AnalysisRunStatus.failed

    run = db_session.scalars(
        select(AnalysisRun).where(AnalysisRun.document_id == document.id)
    ).one()
    assert run.status is AnalysisRunStatus.failed
    assert run.completed_at is not None
