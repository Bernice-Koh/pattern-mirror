"""The five behavioural states: each decision-and-text combination maps to the right §13 state."""

from pattern_mirror.models.enums import FlagInteractionKind
from pattern_mirror.services.behavioural_states import (
    ADOPTION_STATES,
    BehaviouralState,
    Decision,
    FlagOutcome,
    classify,
    derive_state,
    net_decision,
    span_present,
)

ACCEPT = FlagInteractionKind.accept
DISMISS = FlagInteractionKind.dismiss
UNDO = FlagInteractionKind.undo


def test_no_interactions_is_neither_accepted_nor_dismissed() -> None:
    assert net_decision([]) == Decision(accepted=False, dismissed=False)


def test_accept_is_sticky() -> None:
    assert net_decision([ACCEPT]).accepted


def test_dismiss_then_undo_clears_the_dismissal() -> None:
    assert not net_decision([DISMISS, UNDO]).dismissed


def test_last_dismiss_action_wins() -> None:
    assert net_decision([DISMISS, UNDO, DISMISS]).dismissed


def test_span_present_matches_whole_words_case_insensitively() -> None:
    assert span_present("Sharp", "a sharp candidate")


def test_span_present_ignores_subword_matches() -> None:
    assert not span_present("man", "management material")


def test_span_present_matches_multi_word_phrases() -> None:
    assert span_present("cultural fit", "great cultural fit here")


def test_span_present_is_false_for_an_empty_span() -> None:
    assert not span_present("", "any text")


def test_span_present_is_false_when_the_language_is_gone() -> None:
    assert not span_present("sharp", "an incisive candidate")


def test_derive_state_accept_is_explicit_accept() -> None:
    state = derive_state(accepted=True, dismissed=False, present=True)
    assert state is BehaviouralState.explicit_accept


def test_derive_state_dismissed_and_kept() -> None:
    state = derive_state(accepted=False, dismissed=True, present=True)
    assert state is BehaviouralState.dismissed_and_kept


def test_derive_state_dismissed_and_removed() -> None:
    state = derive_state(accepted=False, dismissed=True, present=False)
    assert state is BehaviouralState.dismissed_and_removed


def test_derive_state_ignored_and_kept() -> None:
    state = derive_state(accepted=False, dismissed=False, present=True)
    assert state is BehaviouralState.ignored_and_kept


def test_derive_state_edited_around() -> None:
    state = derive_state(accepted=False, dismissed=False, present=False)
    assert state is BehaviouralState.edited_around


def test_classify_treats_accept_as_adoption_even_if_text_lingers() -> None:
    outcome = FlagOutcome(
        flagged_text="sharp",
        interaction_kinds=(ACCEPT,),
        final_text="still a sharp pick",
    )
    state = classify(outcome)
    assert state is BehaviouralState.explicit_accept
    assert state in ADOPTION_STATES


def test_classify_dismissed_and_kept_is_a_rejection() -> None:
    outcome = FlagOutcome(
        flagged_text="aggressive",
        interaction_kinds=(DISMISS,),
        final_text="an aggressive operator",
    )
    state = classify(outcome)
    assert state is BehaviouralState.dismissed_and_kept
    assert state not in ADOPTION_STATES


def test_classify_edited_around_with_no_interaction() -> None:
    outcome = FlagOutcome(
        flagged_text="rockstar",
        interaction_kinds=(),
        final_text="a standout engineer",
    )
    assert classify(outcome) is BehaviouralState.edited_around
