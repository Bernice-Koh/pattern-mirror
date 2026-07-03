"""Read a subject's stored resume for the manager-facing download link (#118).

Resolves the subject's blob reference and pulls the bytes from the configured ``BlobStore``,
returning them with a display filename and media type for the download response. The engine never
touches these files; this is a straight fetch behind the manager-role gate the endpoint applies.
"""

import re
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from pattern_mirror.core.errors import BlobNotFoundError, ResumeNotFoundError
from pattern_mirror.models.identity import Subject
from pattern_mirror.services.blob_storage import BlobStore

# Blob refs end in the source file's extension; map the ones we seed to a media type so the
# browser opens the download correctly. Anything else downloads as a generic binary.
_MEDIA_TYPES: dict[str, str] = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
}
_DEFAULT_MEDIA_TYPE = "application/octet-stream"


@dataclass(frozen=True)
class ResumeFile:
    """A fetched resume: its bytes plus what the download response needs to label them."""

    content: bytes
    media_type: str
    download_filename: str


def _download_filename(subject_name: str, ref: str) -> str:
    """Build a human-friendly download name from the subject's name and the ref's extension."""
    slug = re.sub(r"[^a-z0-9]+", "-", subject_name.lower()).strip("-") or "subject"
    suffix = ref[ref.rfind(".") :] if "." in ref else ""
    return f"{slug}-resume{suffix}"


def get_subject_resume(session: Session, *, subject_id: uuid.UUID, store: BlobStore) -> ResumeFile:
    """Return a subject's stored resume file.

    Args:
        session: An open session.
        subject_id: The subject whose resume is requested.
        store: The blob store to read the bytes from.

    Returns:
        The resume bytes with a display filename and media type.

    Raises:
        ResumeNotFoundError: if the subject is unknown, has no stored resume, or its blob is gone.
    """
    subject = session.get(Subject, subject_id)
    if subject is None or subject.resume_blob_ref is None:
        raise ResumeNotFoundError(subject_id)
    try:
        content = store.read(subject.resume_blob_ref)
    except BlobNotFoundError as exc:
        raise ResumeNotFoundError(subject_id) from exc
    media_type = _MEDIA_TYPES.get(_suffix(subject.resume_blob_ref), _DEFAULT_MEDIA_TYPE)
    return ResumeFile(
        content=content,
        media_type=media_type,
        download_filename=_download_filename(subject.legal_name, subject.resume_blob_ref),
    )


def _suffix(ref: str) -> str:
    return ref[ref.rfind(".") :].lower() if "." in ref else ""
