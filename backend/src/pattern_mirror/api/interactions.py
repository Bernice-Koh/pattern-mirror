"""The flag-interactions endpoint: record a manager's accept/dismiss/undo on a flag.

A thin boundary over ``services.interactions``: it validates the request, attributes it to
the current user (a foreign flag is rejected as not found), and serialises the persisted
event so no ORM object crosses the API. The dismiss/undo suppression side effect lives in
the service.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from pattern_mirror.api.deps import get_current_user
from pattern_mirror.db.session import get_session
from pattern_mirror.models.enums import FlagInteractionKind
from pattern_mirror.models.identity import User
from pattern_mirror.services.interactions import record_interaction

router = APIRouter(tags=["interactions"])


class InteractionRequest(BaseModel):
    """A manager's response to a flag."""

    kind: FlagInteractionKind
    accepted_alternative: str | None = None


class InteractionResponse(BaseModel):
    """The persisted interaction event and whether it left an active dismissal."""

    id: uuid.UUID
    flag_id: uuid.UUID
    kind: FlagInteractionKind
    dismissed: bool


@router.post(
    "/flags/{flag_id}/interactions",
    response_model=InteractionResponse,
    summary="Record a manager's accept/dismiss/undo on a flag",
)
def create_interaction(
    flag_id: uuid.UUID,
    request: InteractionRequest,
    session: Annotated[Session, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> InteractionResponse:
    """Persist the interaction and apply its suppression side effect."""
    result = record_interaction(
        session,
        flag_id=flag_id,
        owner_id=current_user.id,
        kind=request.kind,
        accepted_alternative=request.accepted_alternative,
    )
    return InteractionResponse(
        id=result.interaction.id,
        flag_id=flag_id,
        kind=request.kind,
        dismissed=result.dismissal is not None and result.dismissal.active,
    )
