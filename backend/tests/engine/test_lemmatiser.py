"""Behaviour of the deterministic lemmatiser: inflection collapse, stability, phrases."""

from pattern_mirror.engine.lemmatiser import lemma_key, lemmatise


def test_inflected_forms_collapse_to_one_key() -> None:
    keys = {lemma_key("young"), lemma_key("younger"), lemma_key("Youngest!")}
    assert keys == {"young"}


def test_case_and_punctuation_are_normalised() -> None:
    assert lemma_key("Aggressive!") == lemma_key("aggressive") == "aggressive"


def test_lemmatisation_is_stable_across_calls() -> None:
    assert lemma_key("digital natives") == lemma_key("digital natives")


def test_phrase_keys_join_lemmas_in_order() -> None:
    assert lemma_key("digital natives") == "digital native"


def test_text_without_content_tokens_yields_empty_key() -> None:
    assert lemma_key("!!!") == ""


def test_lemmatise_drops_punctuation() -> None:
    assert lemmatise("Aggressive!") == ["aggressive"]
