"""Derive the five behavioural states per flag (#66, design spec §13).

Pure functions over a flag's interaction history and the document's final submitted text — no
database, no engine — so the classification is deterministic in CI. The aggregator maps ORM
flags into ``FlagOutcome`` values; the decision-pattern stats then split flags by whether their
state counts as adoption (states 1–3) or rejection (states 4–5).
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum, auto

from pattern_mirror.models.enums import FlagInteractionKind


class BehaviouralState(StrEnum):
    """A flag's outcome, derived from the manager's decision and the final text (§13)."""

    explicit_accept = auto()
    edited_around = auto()
    dismissed_and_removed = auto()
    dismissed_and_kept = auto()
    ignored_and_kept = auto()


# States where the flagged language was removed or revised — the adoption numerator (§13).
ADOPTION_STATES = frozenset(
    {
        BehaviouralState.explicit_accept,
        BehaviouralState.edited_around,
        BehaviouralState.dismissed_and_removed,
    }
)


@dataclass(frozen=True)
class Decision:
    """A flag's net manager decision: accept is sticky, dismiss/undo toggle to the last action."""

    accepted: bool
    dismissed: bool


@dataclass(frozen=True)
class FlagOutcome:
    """One flag's inputs for classification: its verbatim span, interaction history, final text."""

    flagged_text: str
    interaction_kinds: tuple[FlagInteractionKind, ...]
    final_text: str


def net_decision(kinds: Iterable[FlagInteractionKind]) -> Decision:
    """Reduce a flag's interactions (chronological) to its net decision.

    ``accept`` sticks once seen; ``dismiss`` and ``undo`` toggle the dismissed state, so the
    last of them wins — mirroring the single dismissal row the interaction service maintains.
    """
    ordered = tuple(kinds)
    accepted = any(kind is FlagInteractionKind.accept for kind in ordered)
    dismissed = False
    for kind in ordered:
        if kind is FlagInteractionKind.dismiss:
            dismissed = True
        elif kind is FlagInteractionKind.undo:
            dismissed = False
    return Decision(accepted=accepted, dismissed=dismissed)


def span_present(flagged_text: str, final_text: str) -> bool:
    """Whether the flagged language still appears in the final text.

    Word-boundary and case-insensitive on the verbatim span — a content change to the flagged
    words reads as removed; ``raw_span`` is used (not the lemma form) so inflection still matches.
    """
    if not flagged_text:
        return False
    return re.search(rf"\b{re.escape(flagged_text)}\b", final_text, re.IGNORECASE) is not None


def derive_state(*, accepted: bool, dismissed: bool, present: bool) -> BehaviouralState:
    """Map the decision and final-text presence to one of the five states (§13)."""
    if accepted:
        return BehaviouralState.explicit_accept
    if dismissed:
        return (
            BehaviouralState.dismissed_and_kept
            if present
            else BehaviouralState.dismissed_and_removed
        )
    return BehaviouralState.ignored_and_kept if present else BehaviouralState.edited_around


def classify(outcome: FlagOutcome) -> BehaviouralState:
    """Classify a flag end to end from its span, interactions, and the final submitted text."""
    decision = net_decision(outcome.interaction_kinds)
    present = span_present(outcome.flagged_text, outcome.final_text)
    return derive_state(accepted=decision.accepted, dismissed=decision.dismissed, present=present)
