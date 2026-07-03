"""GET /subjects/{id}/resume streams the file to a manager and refuses everyone else."""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from tests.conftest import InMemoryBlobStore

from pattern_mirror.api.deps import get_current_principal
from pattern_mirror.db.session import get_session
from pattern_mirror.main import create_app
from pattern_mirror.models.enums import SubjectType, UserRole
from pattern_mirror.models.identity import Subject
from pattern_mirror.services.auth import SessionPrincipal
from pattern_mirror.services.blob_storage import get_blob_store

pytestmark = pytest.mark.db


def _principal(role: UserRole) -> SessionPrincipal:
    return SessionPrincipal(user_id=uuid.uuid4(), role=role)


def _client(
    db_session: Session, store: InMemoryBlobStore, role: UserRole | None
) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_blob_store] = lambda: store
    if role is not None:
        app.dependency_overrides[get_current_principal] = lambda: _principal(role)
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def manager_client(db_session: Session, blob_store: InMemoryBlobStore) -> Iterator[TestClient]:
    yield from _client(db_session, blob_store, UserRole.manager)


def _seed_subject_with_resume(
    db_session: Session, store: InMemoryBlobStore, *, name: str
) -> Subject:
    subject = Subject(
        subject_type=SubjectType.candidate,
        legal_name=name,
        resume_blob_ref="resumes/seed.pdf",
    )
    db_session.add(subject)
    db_session.flush()
    store.write("resumes/seed.pdf", b"%PDF-resume-bytes")
    return subject


def test_manager_downloads_the_resume_bytes(
    manager_client: TestClient, db_session: Session, blob_store: InMemoryBlobStore
) -> None:
    subject = _seed_subject_with_resume(db_session, blob_store, name="Ada Lovelace")

    response = manager_client.get(f"/subjects/{subject.id}/resume")

    assert response.status_code == 200
    assert response.content == b"%PDF-resume-bytes"
    assert response.headers["content-type"] == "application/pdf"
    assert (
        response.headers["content-disposition"] == 'attachment; filename="ada-lovelace-resume.pdf"'
    )


def test_unknown_subject_returns_404(manager_client: TestClient) -> None:
    response = manager_client.get(f"/subjects/{uuid.uuid4()}/resume")

    assert response.status_code == 404


def test_hr_session_is_forbidden(db_session: Session, blob_store: InMemoryBlobStore) -> None:
    subject = _seed_subject_with_resume(db_session, blob_store, name="Ada Lovelace")
    client_gen = _client(db_session, blob_store, UserRole.hr)
    client = next(client_gen)
    try:
        response = client.get(f"/subjects/{subject.id}/resume")
        assert response.status_code == 403
    finally:
        client_gen.close()


def test_unauthenticated_request_is_rejected(
    db_session: Session, blob_store: InMemoryBlobStore
) -> None:
    subject = _seed_subject_with_resume(db_session, blob_store, name="Ada Lovelace")
    client_gen = _client(db_session, blob_store, role=None)
    client = next(client_gen)
    try:
        response = client.get(f"/subjects/{subject.id}/resume")
        assert response.status_code == 401
    finally:
        client_gen.close()
