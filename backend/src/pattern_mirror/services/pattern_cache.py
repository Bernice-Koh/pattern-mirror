"""Process-local cache for the Pattern Aggregator's dashboard output (#66, Tier 3 §5).

The aggregator scans a manager's whole history, so recomputing it on every dashboard load is
wasteful. Patterns only change when an analysis run, an interaction, or a submission is added —
all append-only — so a cheap count of those is a version stamp: equal stamp, reuse the cached
report; changed stamp, recompute. One process holds the dashboard in the MVP, so an in-process
dict suffices; a shared cache is post-MVP.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pattern_mirror.models.documents import AnalysisRun, Document
from pattern_mirror.models.engine import Flag, FlagInteraction
from pattern_mirror.services.pattern_aggregator import PatternReport, aggregate_patterns

# (run count, interaction count, submission count, threshold) — bumps when patterns could change.
_Version = tuple[int, int, int, float]

# owner -> (version stamp the report was computed at, the report). Module-global by design.
_CACHE: dict[uuid.UUID, tuple[_Version, PatternReport]] = {}


def _version(session: Session, owner_id: uuid.UUID, threshold: float) -> _Version:
    """A stamp that changes whenever the manager's patterns could (all three are append-only)."""
    runs = session.scalar(
        select(func.count())
        .select_from(AnalysisRun)
        .join(Document, AnalysisRun.document_id == Document.id)
        .where(Document.owner_id == owner_id)
    )
    interactions = session.scalar(
        select(func.count())
        .select_from(FlagInteraction)
        .join(Flag, FlagInteraction.flag_id == Flag.id)
        .join(Document, Flag.document_id == Document.id)
        .where(Document.owner_id == owner_id)
    )
    submissions = session.scalar(
        select(func.count()).where(
            Document.owner_id == owner_id, Document.submitted_content.is_not(None)
        )
    )
    return (runs or 0, interactions or 0, submissions or 0, threshold)


def cached_pattern_report(
    session: Session, *, owner_id: uuid.UUID, threshold: float
) -> PatternReport:
    """Return the manager's pattern report, recomputing only when their history has changed."""
    version = _version(session, owner_id, threshold)
    cached = _CACHE.get(owner_id)
    if cached is not None and cached[0] == version:
        return cached[1]
    report = aggregate_patterns(session, owner_id=owner_id, threshold=threshold)
    _CACHE[owner_id] = (version, report)
    return report


def clear_pattern_cache() -> None:
    """Drop every cached report. For tests and any explicit cache-busting path."""
    _CACHE.clear()
