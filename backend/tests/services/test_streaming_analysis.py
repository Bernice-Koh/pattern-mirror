"""The streaming pipeline service: per-stage events, persistence, supersede, failure.

The happy-path and supersede tests drive the real default graph over the migration-seeded
SG lexicon (so ``digital native`` resolves to a flag); the failure test substitutes a graph
that raises mid-stream. All are ``db``-marked because the run and its flags are persisted.
"""

import uuid
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from pattern_mirror.engine.contextual_pass import ContextualFlag, ContextualPassResult
from pattern_mirror.models.audit import AgentRun
from pattern_mirror.models.documents import AnalysisRun, Document
from pattern_mirror.models.engine import Flag
from pattern_mirror.models.enums import (
    AgentName,
    AnalysisRunStatus,
    BiasCategory,
    DocType,
    FlagScope,
    FlagSourceStage,
)
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


class _FakeContextualClient:
    """Deterministic stand-in for the Instructor client: fixed flags, recorded usage."""

    def __init__(self, result: ContextualPassResult) -> None:
        self._result = result
        self._completion = SimpleNamespace(usage=SimpleNamespace(input_tokens=90, output_tokens=30))

    def create_with_completion(self, **kwargs: Any) -> tuple[Any, Any]:
        return self._result, self._completion


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
    monkeypatch.setattr(
        streaming_analysis, "build_default_graph", lambda *args, **kwargs: _RaisingGraph()
    )

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


def test_contextual_flags_are_verified_persisted_and_logged(db_session: Session) -> None:
    # The fake flags a phrase present verbatim, so the Adjudicator keeps it and resolves
    # its offsets; the dictionary may also flag, so assertions filter to contextual.
    document = _document(db_session, content="We value a strong culture fit.")
    fake = _FakeContextualClient(
        ContextualPassResult(
            flags=[
                ContextualFlag(
                    raw_span="culture fit",
                    category=BiasCategory.race,
                    scope=FlagScope.role_specific,
                    explanation="Vague 'fit' invites in-group bias.",
                )
            ]
        )
    )

    events = list(
        stream_analysis_events(
            db_session,
            document_id=document.id,
            content=document.content,
            doc_type=document.doc_type,
            registry=RunRegistry(),
            contextual_client=fake,
        )
    )

    contextual = [
        event.flag
        for event in events
        if isinstance(event, FlagSurfaced) and event.flag.source_stage is FlagSourceStage.contextual
    ]
    assert [flag.raw_span for flag in contextual] == ["culture fit"]
    flag = contextual[0]
    assert flag.scope is FlagScope.role_specific
    assert flag.citation_id is not None  # the category-level TAFEP floor citation (ADR 0006)
    assert flag.normalised_span == "culture fit"  # derived from raw_span via the lemmatiser
    assert flag.start_offset is not None  # the Adjudicator resolved the span

    agent_run = db_session.scalars(
        select(AgentRun).where(AgentRun.document_id == document.id)
    ).one()
    assert agent_run.agent_name is AgentName.contextual_pass
    assert agent_run.prompt_tokens == 90
    assert agent_run.analysis_run_id is not None
