"""Deterministic sentence fingerprints for document-scoped flag dismissals.

One component of a dismissal's signature (design spec §12). Flag persistence and the
dismissal lookup must call this one function so their fingerprints agree.
"""

import hashlib

from pattern_mirror.engine.lemmatiser import lemmatise

_SENTENCE_TERMINATORS = ".!?"


def compute_sentence_fingerprint(text: str, start: int, end: int) -> str:
    """Return the lemma-bag fingerprint of the sentence containing ``text[start:end]``.

    The sentence is the span between the nearest terminators (``.!?``) around the offsets,
    reduced to its sorted content lemmas before hashing. Casing, punctuation, inflection, and
    word order are immaterial; a content-word change shifts the hash (design spec §12).

    Args:
        text: The full source document.
        start: Start offset of the flagged span.
        end: End offset (exclusive) of the flagged span.

    Returns:
        A 64-character hex SHA-256 digest of the sentence's sorted lemma bag.
    """
    left = max((text.rfind(term, 0, start) for term in _SENTENCE_TERMINATORS), default=-1)
    right_ends = [pos for term in _SENTENCE_TERMINATORS if (pos := text.find(term, end)) != -1]
    right = min(right_ends) + 1 if right_ends else len(text)
    lemma_bag = " ".join(sorted(lemmatise(text[left + 1 : right])))
    return hashlib.sha256(lemma_bag.encode("utf-8")).hexdigest()
