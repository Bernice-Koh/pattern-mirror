"""SSE framing: each event type renders to its ``event:``/``data:`` frame.

Unit tests for ``format_sse`` shared by the streaming and re-check endpoints. The flag frame
is built from a real persisted flag so serialisation is exercised end to end.
"""

import uuid

import pytest
from sqlalchemy.orm import Session

from pattern_mirror.api.sse import format_sse
from pattern_mirror.models.documents import Document
from pattern_mirror.models.enums import AnalysisRunStatus, DocType
from pattern_mirror.models.identity import User
from pattern_mirror.services.analysis import analyze_document
from pattern_mirror.services.streaming_analysis import (
    FlagSurfaced,
    RunCompleted,
    StageCompleted,
)


def test_format_sse_renders_stage_and_done_frames() -> None:
    stage_frame = format_sse(StageCompleted(stage="judge")).decode()
    assert stage_frame == 'event: stage\ndata: {"stage":"judge"}\n\n'

    run_id = uuid.uuid4()
    done_frame = format_sse(
        RunCompleted(analysis_run_id=run_id, status=AnalysisRunStatus.complete, flag_count=2)
    ).decode()
    assert done_frame.startswith("event: done\ndata: ")
    assert f'"analysis_run_id":"{run_id}"' in done_frame
    assert '"status":"complete"' in done_frame
    assert '"flag_count":2' in done_frame


@pytest.mark.db
def test_format_sse_renders_a_flag_frame_from_a_persisted_flag(db_session: Session) -> None:
    user = User(
        external_user_id="flag-frame-manager",
        legal_name="Flag Frame Manager",
        email="flag.frame@example.com",
    )
    db_session.add(user)
    db_session.flush()
    document = Document(owner_id=user.id, doc_type=DocType.jd)
    db_session.add(document)
    db_session.flush()
    result = analyze_document(
        db_session,
        document_id=document.id,
        owner_id=user.id,
        content="We want a digital native.",
    )

    frame = format_sse(FlagSurfaced(flag=result.flags[0])).decode()

    assert frame.startswith("event: flag\ndata: ")
    assert '"raw_span":"digital native"' in frame
    assert '"citation":' in frame
    # A dictionary flag now carries its curated rewrites (#8 phase 1), so recommendations serialise.
    assert '"recommendations":{' in frame
    assert '"digitally fluent"' in frame


@pytest.mark.db
def test_format_sse_renders_recommendations_when_a_flag_has_them(db_session: Session) -> None:
    user = User(
        external_user_id="rec-frame-manager",
        legal_name="Rec Frame Manager",
        email="rec.frame@example.com",
    )
    db_session.add(user)
    db_session.flush()
    document = Document(owner_id=user.id, doc_type=DocType.jd)
    db_session.add(document)
    db_session.flush()
    result = analyze_document(
        db_session,
        document_id=document.id,
        owner_id=user.id,
        content="We want a digital native.",
    )
    flag = result.flags[0]
    flag.recommendations = {
        "rationale": "Coded age bias.",
        "alternatives": ["adaptable", "tech-savvy"],
    }
    db_session.flush()

    frame = format_sse(FlagSurfaced(flag=flag)).decode()

    assert '"rationale":"Coded age bias."' in frame
    assert '"adaptable"' in frame
