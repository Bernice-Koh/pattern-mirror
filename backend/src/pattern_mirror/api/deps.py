"""Shared FastAPI dependencies.

``get_current_user`` is a pre-auth placeholder: until the login flow exists, the
analyze endpoint attributes every document to the seeded demo manager. When real
authentication lands, only this function changes — the endpoint contract does not.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from pattern_mirror.core.errors import SeedDataMissingError
from pattern_mirror.db.session import get_session
from pattern_mirror.jobs.seed_demo import DEMO_MANAGER_EXTERNAL_ID
from pattern_mirror.models.identity import User


def get_current_user(session: Annotated[Session, Depends(get_session)]) -> User:
    """Return the authenticated user; currently the seeded demo manager.

    Raises:
        SeedDataMissingError: if the demo manager has not been seeded.
    """
    user = session.scalar(select(User).where(User.external_user_id == DEMO_MANAGER_EXTERNAL_ID))
    if user is None:
        raise SeedDataMissingError(
            "Demo manager not seeded; run 'python -m pattern_mirror.jobs.seed_demo'."
        )
    return user
