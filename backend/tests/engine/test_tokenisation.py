"""Offset-aware tokenisation: lemmas agree with the lemmatiser, offsets map to source."""

from pattern_mirror.engine.lemmatiser import lemmatise
from pattern_mirror.engine.tokenisation import lemmatise_with_offsets


def test_offsets_slice_back_to_the_surface_token() -> None:
    text = "We seek a digital native."
    for token in lemmatise_with_offsets(text):
        assert text[token.start : token.end] != ""
        assert token.lemma == lemmatise(text[token.start : token.end])[0]


def test_lemmas_match_the_lemmatiser_in_order() -> None:
    text = "Aggressive natives!"
    lemmas = [token.lemma for token in lemmatise_with_offsets(text)]
    assert lemmas == lemmatise(text)


def test_punctuation_and_whitespace_are_dropped() -> None:
    tokens = lemmatise_with_offsets("Aggressive!  Young.")
    assert [token.lemma for token in tokens] == ["aggressive", "young"]


def test_clean_text_offsets_are_strictly_ordered() -> None:
    tokens = lemmatise_with_offsets("a mature seasoned bachelor")
    starts = [token.start for token in tokens]
    assert starts == sorted(starts)


def test_empty_text_yields_no_tokens() -> None:
    assert lemmatise_with_offsets("") == []
