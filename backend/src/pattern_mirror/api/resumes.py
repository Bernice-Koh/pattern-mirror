"""Resume download endpoint (design spec §5, #118).

A single manager-gated ``GET /subjects/{id}/resume`` streams a subject's stored resume as a file
download. Resumes are individual candidate/employee content, so HR (aggregates only) is kept out
by ``require_manager``. Download-only: there is no upload UI in the MVP — files are seeded — and
the endpoint contract stays stable so the post-MVP Azure Blob swap is data-only.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from pattern_mirror.api.deps import require_manager
from pattern_mirror.db.session import get_session
from pattern_mirror.services.auth import SessionPrincipal
from pattern_mirror.services.blob_storage import BlobStore, get_blob_store
from pattern_mirror.services.resumes import get_subject_resume

router = APIRouter(tags=["resumes"])


@router.get(
    "/subjects/{subject_id}/resume",
    summary="Download a subject's resume",
    response_class=Response,
)
def download_subject_resume(
    subject_id: uuid.UUID,
    session: Annotated[Session, Depends(get_session)],
    store: Annotated[BlobStore, Depends(get_blob_store)],
    _principal: Annotated[SessionPrincipal, Depends(require_manager)],
) -> Response:
    """Return the subject's resume as a file download for the manager reviewing them.

    Raises:
        ResumeNotFoundError: if the subject is unknown or has no stored resume (mapped to 404).
    """
    resume = get_subject_resume(session, subject_id=subject_id, store=store)
    return Response(
        content=resume.content,
        media_type=resume.media_type,
        headers={"Content-Disposition": f'attachment; filename="{resume.download_filename}"'},
    )
