"""analyze_document persists the document, run, and flags with full provenance."""

import hashlib

import pytest
from sqlalchemy.orm import Session

from pattern_mirror.models.documents import AnalysisRun, Document
from pattern_mirror.models.enums import AnalysisRunStatus, DocType, FlagScope, FlagSourceStage
from pattern_mirror.models.identity import User
from pattern_mirror.services.analysis import analyze_document

pytestmark = pytest.mark.db


def _manager(db_session: Session) -> User:
    user = User(
        external_user_id="test-manager",
        legal_name="Test Manager",
        email="test.manager@example.com",
    )
    db_session.add(user)
    db_session.flush()
    return user


def test_persists_document_run_and_cited_flag(db_session: Session) -> None:
    owner = _manager(db_session)

    result = analyze_document(
        db_session, owner_id=owner.id, doc_type=DocType.jd, content="We want a digital native."
    )

    assert db_session.get(Document, result.document.id) is not None
    run = db_session.get(AnalysisRun, result.run.id)
    assert run is not None
    assert run.status is AnalysisRunStatus.complete
    assert run.completed_at is not None

    assert len(result.flags) == 1
    flag = result.flags[0]
    assert flag.source_stage is FlagSourceStage.dictionary
    assert flag.scope is FlagScope.general
    assert flag.dictionary_entry_id is not None
    assert flag.citation_id is not None
    assert flag.normalised_span == "digital native"
    assert flag.sentence_fingerprint
    assert flag.raw_span == "digital native"
    assert flag.rationale["explanation"]


def test_clean_document_persists_with_no_flags(db_session: Session) -> None:
    owner = _manager(db_session)

    result = analyze_document(
        db_session, owner_id=owner.id, doc_type=DocType.jd, content="We value teamwork and clarity."
    )

    assert db_session.get(Document, result.document.id) is not None
    assert result.flags == []


def test_content_hash_is_the_sha256_of_the_content(db_session: Session) -> None:
    owner = _manager(db_session)
    content = "We want a digital native."

    result = analyze_document(db_session, owner_id=owner.id, doc_type=DocType.jd, content=content)

    assert result.run.content_hash == hashlib.sha256(content.encode("utf-8")).hexdigest()
