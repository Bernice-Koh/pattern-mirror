"""Sentence fingerprints: a lemma bag, so casing, punctuation, inflection, and order wash out."""

from pattern_mirror.engine.fingerprint import compute_sentence_fingerprint


def _span(text: str, phrase: str) -> tuple[int, int]:
    start = text.index(phrase)
    return start, start + len(phrase)


def test_same_sentence_yields_same_fingerprint_regardless_of_position() -> None:
    a = "We want a digital native. Apply now."
    b = "Hello there. We want a digital native."

    assert compute_sentence_fingerprint(a, *_span(a, "digital native")) == (
        compute_sentence_fingerprint(b, *_span(b, "digital native"))
    )


def test_different_sentences_differ() -> None:
    text = "We want a digital native. We avoid bias."

    assert compute_sentence_fingerprint(text, *_span(text, "digital native")) != (
        compute_sentence_fingerprint(text, *_span(text, "bias"))
    )


def test_casing_and_whitespace_are_normalised() -> None:
    spaced = "A mature   candidate."
    cased = "a MATURE candidate."

    assert compute_sentence_fingerprint(spaced, *_span(spaced, "mature")) == (
        compute_sentence_fingerprint(cased, *_span(cased, "MATURE"))
    )


def test_internal_punctuation_is_immaterial() -> None:
    plain = "Strong culture fit."
    comma = "Strong culture, fit."

    assert compute_sentence_fingerprint(plain, *_span(plain, "culture")) == (
        compute_sentence_fingerprint(comma, *_span(comma, "culture"))
    )


def test_inflected_forms_share_a_fingerprint() -> None:
    singular = "We assess the candidate."
    plural = "We assess the candidates."

    assert compute_sentence_fingerprint(singular, *_span(singular, "candidate")) == (
        compute_sentence_fingerprint(plural, *_span(plural, "candidate"))
    )


def test_word_order_is_immaterial() -> None:
    a = "Dynamic aggressive leader."
    b = "Aggressive dynamic leader."

    assert compute_sentence_fingerprint(a, *_span(a, "leader")) == (
        compute_sentence_fingerprint(b, *_span(b, "leader"))
    )


def test_a_content_word_change_shifts_the_fingerprint() -> None:
    before = "Aggressive leader."
    after = "Aggressive manager."

    assert compute_sentence_fingerprint(before, *_span(before, "Aggressive")) != (
        compute_sentence_fingerprint(after, *_span(after, "Aggressive"))
    )


def test_returns_sha256_hex() -> None:
    text = "Hire a bachelor."
    fingerprint = compute_sentence_fingerprint(text, *_span(text, "bachelor"))

    assert len(fingerprint) == 64
    assert all(character in "0123456789abcdef" for character in fingerprint)
