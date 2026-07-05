"""list_flags reads back a document's latest-run, surfaced bias flags for re-hydration on reopen.

``db``-marked: flags and the runs they belong to are persisted against the migration-built schema.
The write side (persisting flags) is covered in ``test_analysis``/``test_streaming_analysis``; this
covers only the read path the reopen feature adds.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy.orm import Session

from pattern_mirror.core.errors import DocumentNotFoundError
from pattern_mirror.models.documents import AnalysisRun, Document
from pattern_mirror.models.engine import Flag
from pattern_mirror.models.enums import (
    AnalysisRunStatus,
    AnalysisTrigger,
    BiasCategory,
    DocType,
    FlagScope,
    FlagSourceStage,
)
from pattern_mirror.models.identity import User
from pattern_mirror.services.documents import list_flags

pytestmark = pytest.mark.db


def _owner_and_document(db_session: Session, suffix: str) -> tuple[User, Document]:
    user = User(
        external_user_id=f"list-flags-{suffix}",
        legal_name="Flags Manager",
        email=f"{suffix}@example.test",
    )
    db_session.add(user)
    db_session.flush()
    document = Document(owner_id=user.id, doc_type=DocType.jd, content="Doc under analysis.")
    db_session.add(document)
    db_session.flush()
    return user, document


def _run(
    db_session: Session, document: Document, *, started_at: datetime | None = None
) -> AnalysisRun:
    run = AnalysisRun(
        document_id=document.id,
        trigger=AnalysisTrigger.typing_pause,
        content_hash="0" * 64,
        status=AnalysisRunStatus.complete,
    )
    if started_at is not None:
        # now() is constant within a test transaction, so distinguish run recency explicitly.
        run.started_at = started_at
    db_session.add(run)
    db_session.flush()
    return run


def _flag(
    db_session: Session,
    document: Document,
    run: AnalysisRun,
    *,
    raw_span: str,
    start_offset: int,
    suppressed: bool = False,
) -> Flag:
    rationale: dict[str, Any] = {"explanation": f"{raw_span} is bias-coded."}
    flag = Flag(
        document_id=document.id,
        analysis_run_id=run.id,
        source_stage=FlagSourceStage.contextual,
        category=BiasCategory.age,
        scope=FlagScope.general,
        raw_span=raw_span,
        normalised_span=raw_span,
        sentence_fingerprint="f" * 64,
        start_offset=start_offset,
        end_offset=start_offset + len(raw_span),
        rationale=rationale,
        suppressed=suppressed,
    )
    db_session.add(flag)
    db_session.flush()
    return flag


def test_list_returns_the_latest_runs_flags(db_session: Session) -> None:
    owner, document = _owner_and_document(db_session, "latest")
    first_run = _run(db_session, document, started_at=datetime(2026, 7, 1, tzinfo=UTC))
    _flag(db_session, document, first_run, raw_span="old flag", start_offset=0)
    second_run = _run(db_session, document, started_at=datetime(2026, 7, 2, tzinfo=UTC))
    _flag(db_session, document, second_run, raw_span="new flag", start_offset=0)

    flags = list_flags(db_session, document_id=document.id, owner_id=owner.id)

    assert [f.raw_span for f in flags] == ["new flag"]


def test_list_excludes_suppressed_flags(db_session: Session) -> None:
    owner, document = _owner_and_document(db_session, "suppressed")
    run = _run(db_session, document)
    _flag(db_session, document, run, raw_span="kept", start_offset=0)
    _flag(db_session, document, run, raw_span="dismissed", start_offset=10, suppressed=True)

    flags = list_flags(db_session, document_id=document.id, owner_id=owner.id)

    assert [f.raw_span for f in flags] == ["kept"]


def test_list_orders_by_document_position(db_session: Session) -> None:
    owner, document = _owner_and_document(db_session, "order")
    run = _run(db_session, document)
    # Insert out of document order; the read orders by start_offset so the panel matches the text.
    _flag(db_session, document, run, raw_span="second", start_offset=20)
    _flag(db_session, document, run, raw_span="first", start_offset=0)

    flags = list_flags(db_session, document_id=document.id, owner_id=owner.id)

    assert [f.raw_span for f in flags] == ["first", "second"]


def test_list_is_empty_when_a_document_has_no_flags(db_session: Session) -> None:
    owner, document = _owner_and_document(db_session, "empty")

    assert list_flags(db_session, document_id=document.id, owner_id=owner.id) == []


def test_list_on_another_users_document_is_not_found(db_session: Session) -> None:
    _, document = _owner_and_document(db_session, "owner")
    intruder = User(
        external_user_id="list-flags-intruder",
        legal_name="Intruder",
        email="intruder@example.test",
    )
    db_session.add(intruder)
    db_session.flush()

    with pytest.raises(DocumentNotFoundError):
        list_flags(db_session, document_id=document.id, owner_id=intruder.id)


def test_list_on_a_missing_document_is_not_found(db_session: Session) -> None:
    owner, _ = _owner_and_document(db_session, "missing")

    with pytest.raises(DocumentNotFoundError):
        list_flags(db_session, document_id=uuid.uuid4(), owner_id=owner.id)
