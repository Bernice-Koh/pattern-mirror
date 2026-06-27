"""Load citation evidence text for the engine's Agent prompts.

The Recommendations Agent grounds each rationale in the flag's cited source (design spec §7);
this resolves citation ids to a short evidence string so the engine can pass evidence by value
into the prompt — the model anchors on a real source rather than inventing one.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from pattern_mirror.models.reference import Citation


def load_citation_evidence(
    session: Session, citation_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, str]:
    """Map each citation id to a short evidence string: its finding, else title + reference.

    Args:
        session: An open database session.
        citation_ids: The citation ids to resolve; duplicates and unknown ids are tolerated.

    Returns:
        One evidence string per distinct citation found; an id with no row is omitted.
    """
    if not citation_ids:
        return {}
    citations = session.scalars(select(Citation).where(Citation.id.in_(set(citation_ids)))).all()
    return {c.id: (c.finding or f"{c.title} ({c.reference})") for c in citations}
