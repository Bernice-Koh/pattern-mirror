"""The resume service returns a subject's stored file, or reports it missing."""

import uuid

import pytest
from sqlalchemy.orm import Session
from tests.conftest import InMemoryBlobStore

from pattern_mirror.core.errors import ResumeNotFoundError
from pattern_mirror.models.enums import SubjectType
from pattern_mirror.models.identity import Subject
from pattern_mirror.services.resumes import get_subject_resume

pytestmark = pytest.mark.db


def _subject(db_session: Session, *, name: str, resume_ref: str | None) -> Subject:
    subject = Subject(
        subject_type=SubjectType.candidate,
        legal_name=name,
        resume_blob_ref=resume_ref,
    )
    db_session.add(subject)
    db_session.flush()
    return subject


def test_returns_the_stored_file_with_a_download_name(
    db_session: Session, blob_store: InMemoryBlobStore
) -> None:
    subject = _subject(db_session, name="Ada Lovelace", resume_ref="resumes/x.pdf")
    blob_store.write("resumes/x.pdf", b"%PDF-bytes")

    resume = get_subject_resume(db_session, subject_id=subject.id, store=blob_store)

    assert resume.content == b"%PDF-bytes"
    assert resume.media_type == "application/pdf"
    assert resume.download_filename == "ada-lovelace-resume.pdf"


def test_unknown_subject_raises_resume_not_found(
    db_session: Session, blob_store: InMemoryBlobStore
) -> None:
    with pytest.raises(ResumeNotFoundError):
        get_subject_resume(db_session, subject_id=uuid.uuid4(), store=blob_store)


def test_subject_without_a_resume_raises_resume_not_found(
    db_session: Session, blob_store: InMemoryBlobStore
) -> None:
    subject = _subject(db_session, name="No Resume", resume_ref=None)

    with pytest.raises(ResumeNotFoundError):
        get_subject_resume(db_session, subject_id=subject.id, store=blob_store)


def test_missing_blob_raises_resume_not_found(
    db_session: Session, blob_store: InMemoryBlobStore
) -> None:
    subject = _subject(db_session, name="Dangling Ref", resume_ref="resumes/gone.pdf")

    with pytest.raises(ResumeNotFoundError):
        get_subject_resume(db_session, subject_id=subject.id, store=blob_store)
