"""Deterministic sentence fingerprints for document-scoped flag dismissals.

A dismissal suppresses a flag on future runs by signature, one component of which is
the fingerprint of the sentence the flag sits in: an edit elsewhere in the document
must not resurrect a dismissed flag, while editing the sentence itself should. The
Dictionary Service writes this when persisting flags; the dismissal logic later reads
it. Both must call this one function so their fingerprints agree.
"""

import hashlib

_SENTENCE_TERMINATORS = ".!?"


def compute_sentence_fingerprint(text: str, start: int, end: int) -> str:
    """Return a stable fingerprint of the sentence containing ``text[start:end]``.

    The sentence is the span between the nearest terminators (``.!?``) on either side
    of the offsets, normalised to be robust to casing and whitespace, then hashed. Equal
    sentences yield equal fingerprints regardless of where in the document they appear.

    Args:
        text: The full source document.
        start: Start offset of the flagged span.
        end: End offset (exclusive) of the flagged span.

    Returns:
        A 64-character hex SHA-256 digest of the normalised sentence.
    """
    left = max((text.rfind(term, 0, start) for term in _SENTENCE_TERMINATORS), default=-1)
    right_ends = [pos for term in _SENTENCE_TERMINATORS if (pos := text.find(term, end)) != -1]
    right = min(right_ends) + 1 if right_ends else len(text)
    sentence = " ".join(text[left + 1 : right].lower().split())
    return hashlib.sha256(sentence.encode("utf-8")).hexdigest()
