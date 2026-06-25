"""The /analyze endpoint: submit a document, run Stage 1, return persisted cited flags.

A thin boundary over ``services.analysis``: it validates the request (an unknown
``doc_type`` is rejected here by the enum), attributes the document to the current user,
and serialises the persisted result into typed models so no ORM object crosses the API.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from pattern_mirror.api.deps import get_current_user
from pattern_mirror.api.schemas import FlagResponse, serialise_flag
from pattern_mirror.db.session import get_session
from pattern_mirror.models.enums import DocType
from pattern_mirror.models.identity import User
from pattern_mirror.services.analysis import AnalysisResult, analyze_document

router = APIRouter(tags=["analyze"])


class AnalyzeRequest(BaseModel):
    """A document submitted for analysis."""

    doc_type: DocType
    content: str


class AnalyzeResponse(BaseModel):
    """The persisted document, its run, and the flags returned to the client."""

    document_id: uuid.UUID
    analysis_run_id: uuid.UUID
    content_hash: str
    flags: list[FlagResponse]


def _serialise(result: AnalysisResult) -> AnalyzeResponse:
    """Map the persisted ORM result into response models (no ORM leaks out)."""
    return AnalyzeResponse(
        document_id=result.document.id,
        analysis_run_id=result.run.id,
        content_hash=result.run.content_hash,
        flags=[serialise_flag(flag) for flag in result.flags],
    )


@router.post("/analyze", response_model=AnalyzeResponse, summary="Analyze a document for bias")
def analyze(
    request: AnalyzeRequest,
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> AnalyzeResponse:
    """Persist the document, run Stage 1, and return its persisted cited flags."""
    result = analyze_document(
        session,
        owner_id=current_user.id,
        doc_type=request.doc_type,
        content=request.content,
    )
    return _serialise(result)
