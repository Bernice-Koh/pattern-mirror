"""Batch entrypoint for the dictionary-growth loop: trigger, then review each candidate (#88→#89).

Runs the recurring-phrase trigger (``services.growth_trigger``) and feeds every candidate through
the four-agent review (``services.dictionary_growth``), committing the batch once. Run on demand
(``python -m pattern_mirror.jobs.growth``); it makes real Anthropic calls, so it is never part of
CI. Monthly HR approval (#90) turns the queued advances into live dictionary rows.
"""

import structlog
from sqlalchemy.orm import Session

from pattern_mirror.core.config import Settings, get_settings
from pattern_mirror.db.session import get_sessionmaker
from pattern_mirror.engine.llm_agent import StructuredCompletionClient, build_instructor_client
from pattern_mirror.services.dictionary_growth import GrowthReviewOutcome, review_candidate
from pattern_mirror.services.growth_trigger import find_growth_candidates

_log = structlog.get_logger("pattern_mirror.jobs.growth")


def run_growth_review(
    session: Session,
    *,
    client: StructuredCompletionClient,
    settings: Settings,
) -> list[GrowthReviewOutcome]:
    """Review every triggered candidate and commit the batch.

    Args:
        session: An open database session; this function owns the transaction and commits it.
        client: An Instructor-wrapped Anthropic client (or a test fake) shared by the four agents.
        settings: Source of the recurrence thresholds and per-agent model choices.

    Returns:
        One outcome per reviewed candidate, in the trigger's deterministic order.
    """
    candidates = find_growth_candidates(session, settings)
    outcomes = [
        review_candidate(session, client=client, candidate=candidate, settings=settings)
        for candidate in candidates
    ]
    session.commit()
    _log.info(
        "growth.batch_reviewed",
        reviewed=len(outcomes),
        advanced=sum(outcome.advanced for outcome in outcomes),
    )
    return outcomes


def main() -> None:  # pragma: no cover
    """Run the growth batch against the configured database and live API."""
    settings = get_settings()
    client = build_instructor_client(settings)
    if client is None:
        raise SystemExit("ANTHROPIC_API_KEY is required to run the dictionary-growth review")

    session = get_sessionmaker()()
    try:
        run_growth_review(session, client=client, settings=settings)
    finally:
        session.rollback()
        session.close()


if __name__ == "__main__":  # pragma: no cover
    main()
