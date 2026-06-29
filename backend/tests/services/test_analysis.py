"""analyze_document persists the document, run, and flags with full provenance."""

import hashlib
import uuid

import pytest
from sqlalchemy.orm import Session

from pattern_mirror.core.errors import DocumentNotFoundError
from pattern_mirror.engine.candidate_flag import CandidateFlag
from pattern_mirror.models.documents import AnalysisRun, Document
from pattern_mirror.models.enums import (
    AnalysisRunStatus,
    BiasCategory,
    DocType,
    FlagScope,
    FlagSourceStage,
)
from pattern_mirror.models.identity import User
from pattern_mirror.services.analysis import analyze_document, build_flag

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


def _draft(db_session: Session, owner: User) -> Document:
    document = Document(owner_id=owner.id, doc_type=DocType.jd)
    db_session.add(document)
    db_session.flush()
    return document


def test_persists_run_and_cited_flag_for_the_document(db_session: Session) -> None:
    owner = _manager(db_session)
    document = _draft(db_session, owner)

    result = analyze_document(
        db_session,
        document_id=document.id,
        owner_id=owner.id,
        content="We want a digital native.",
    )

    assert result.document.id == document.id
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
    document = _draft(db_session, owner)

    result = analyze_document(
        db_session,
        document_id=document.id,
        owner_id=owner.id,
        content="We value teamwork and clarity.",
    )

    assert result.flags == []


def test_content_hash_is_the_sha256_of_the_content(db_session: Session) -> None:
    owner = _manager(db_session)
    document = _draft(db_session, owner)
    content = "We want a digital native."

    result = analyze_document(
        db_session, document_id=document.id, owner_id=owner.id, content=content
    )

    assert result.run.content_hash == hashlib.sha256(content.encode("utf-8")).hexdigest()


def test_analysing_a_foreign_document_is_rejected(db_session: Session) -> None:
    owner = _manager(db_session)
    document = _draft(db_session, owner)
    other = User(
        external_user_id="other-manager",
        legal_name="Other Manager",
        email="other.manager@example.com",
    )
    db_session.add(other)
    db_session.flush()

    with pytest.raises(DocumentNotFoundError):
        analyze_document(
            db_session, document_id=document.id, owner_id=other.id, content="anything"
        )


def test_build_flag_derives_normalised_span_for_a_contextual_candidate() -> None:
    # A contextual candidate has no lemma key; build_flag derives the normalised span from
    # the raw span via the lemmatiser, and carries its scope.
    content = "We value a culture fit."
    start = content.index("culture fit")
    citation_id = uuid.uuid4()
    candidate = CandidateFlag(
        source_stage=FlagSourceStage.contextual,
        category=BiasCategory.race,
        raw_span="culture fit",
        scope=FlagScope.role_specific,
        citation_id=citation_id,
        start_offset=start,
        end_offset=start + len("culture fit"),
        explanation="Vague 'fit' invites in-group bias.",
    )

    flag = build_flag(
        document_id=uuid.uuid4(),
        analysis_run_id=uuid.uuid4(),
        candidate=candidate,
        content=content,
    )

    assert flag.source_stage is FlagSourceStage.contextual
    assert flag.scope is FlagScope.role_specific
    assert flag.dictionary_entry_id is None
    assert flag.citation_id == citation_id  # the floor citation carries through unchanged
    assert flag.normalised_span == "culture fit"
    assert flag.sentence_fingerprint
