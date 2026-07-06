"""Seed flag interactions on the primed demo, lighting up the dashboard's behavioural layer.

Run on demand after ``seed_demo_analysis`` (``python -m pattern_mirror.jobs.seed_demo_behaviour``).
Priming persists the flags a manager was shown, but not what they *did* with them — and the
decision-pattern layer (§13, Layer 2) and the adoption trend both read those interactions. This job
records one accept/dismiss per surfaced flag with a deliberate, category-skewed story:

- The manager dismisses **gender-coded** flags on their older documents but accepts them on recent
  ones — a manager who has been *learning* to revise gendered language. That gives gender a low but
  **rising** adoption rate (a decision pattern, and an upward adoption trend).
- They accept the other categories (age, family status, nationality, …), so those sit at a high
  adoption rate — the categorical asymmetry the decision patterns are meant to surface.

Deterministic (the skew is a pure function of category + submission age), idempotent (a flag that
already has an interaction is skipped), and never part of CI — like the other demo jobs it seeds
sample data, not reference data.
"""

import hashlib
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from pattern_mirror.db.session import get_sessionmaker
from pattern_mirror.models.documents import AnalysisRun, Document
from pattern_mirror.models.engine import Flag, FlagInteraction
from pattern_mirror.models.enums import BiasCategory, DocumentStatus, FlagInteractionKind

_log = structlog.get_logger("pattern_mirror.jobs.seed_demo_behaviour")

# The midpoint of the seed's ~6-month spread: documents older than this read as written before the
# manager improved, so their adoption swings down; more recent ones swing up (the rising trend).
_LEARNING_CUTOFF_DAYS = 75

# Base share of flags revised, by category. Gender-coded language is revised least — the categorical
# asymmetry the decision patterns surface. Both are well under 1.0 so no month reads a fake 100%.
_GENDER_ADOPTION = 0.33
_OTHER_ADOPTION = 0.60
# A gentle recency lift (the "improving" story is mostly carried by the falling flag volume), kept
# small so front-loaded old flags don't drag the firm rate to an implausible floor.
_RECENCY_SWING = 0.05


def _adopt_probability(category: BiasCategory, days_ago: int) -> float:
    """The share of this flag's cohort the manager revised: low for gender, higher when recent."""
    base = _GENDER_ADOPTION if category is BiasCategory.gender else _OTHER_ADOPTION
    swing = _RECENCY_SWING if days_ago < _LEARNING_CUTOFF_DAYS else -_RECENCY_SWING
    return base + swing


def _decision(flag: Flag, days_ago: int) -> FlagInteractionKind:
    """Accept or dismiss this flag, hitting the cohort's target adoption share deterministically.

    The draw is a stable hash of the flag's identity, so a re-run reproduces the same mix (and the
    firm-wide rate never collapses to 0% or 100%): gender-coded flags are revised least, recent
    documents most, with realistic spread within each cohort.
    """
    seed = f"{flag.document_id}:{flag.normalised_span}:{flag.sentence_fingerprint}"
    draw = (int(hashlib.sha256(seed.encode()).hexdigest(), 16) % 1000) / 1000
    if draw < _adopt_probability(flag.category, days_ago):
        return FlagInteractionKind.accept
    return FlagInteractionKind.dismiss


def _surfaced_latest_run_flags(session: Session, document_id: object) -> list[Flag]:
    """A document's un-suppressed flags from its most recent run — the ones the manager saw."""
    latest_run_id = session.scalars(
        select(Flag.analysis_run_id)
        .join(AnalysisRun, AnalysisRun.id == Flag.analysis_run_id)
        .where(Flag.document_id == document_id)
        .order_by(AnalysisRun.started_at.desc())
        .limit(1)
    ).first()
    if latest_run_id is None:
        return []
    return list(
        session.scalars(
            select(Flag).where(Flag.analysis_run_id == latest_run_id, Flag.suppressed.is_(False))
        ).all()
    )


def seed_demo_behaviour(session: Session, *, now: datetime | None = None) -> int:
    """Record one accept/dismiss per surfaced flag on the submitted demo documents.

    Returns the number of interactions inserted. A flag that already has any interaction is left
    untouched, so a re-run — or a document a manager decided on live — is a no-op.
    """
    now = now or datetime.now(UTC)
    documents = session.scalars(
        select(Document).where(
            Document.status == DocumentStatus.submitted,
            Document.submitted_content.is_not(None),
        )
    ).all()
    added = 0
    for document in documents:
        days_ago = (now - document.submitted_at).days if document.submitted_at is not None else 0
        for flag in _surfaced_latest_run_flags(session, document.id):
            already = session.scalars(
                select(FlagInteraction.id).where(FlagInteraction.flag_id == flag.id).limit(1)
            ).first()
            if already is not None:
                continue
            session.add(FlagInteraction(flag_id=flag.id, kind=_decision(flag, days_ago)))
            added += 1
    return added


def main() -> None:
    with get_sessionmaker()() as session:
        added = seed_demo_behaviour(session)
        session.commit()
    _log.info("demo.behaviour_seeded", interactions=added)


if __name__ == "__main__":  # pragma: no cover
    main()
