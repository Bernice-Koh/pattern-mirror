"""Deterministic text-to-lemma normalisation, shared by the dictionary seed and matcher.

One place turns text into lemmas so a seeded ``lemma_key`` and a key computed from a
document agree on inflected and cased forms. No DB, no LLM.
"""

import spacy

# Loaded once at import: spacy.load reads the model off disk and builds the
# pipeline, which is expensive to repeat per call. parser/ner are unused here;
# the tagger stays because the rule-based lemmatiser needs POS tags.
_NLP = spacy.load("en_core_web_sm", disable=["parser", "ner"])


def lemmatise(text: str) -> list[str]:
    """Return the lowercased lemma of each word token in ``text``, in order.

    Punctuation and whitespace tokens are dropped, so ``"Aggressive!"`` and
    ``"aggressive"`` yield the same single lemma.

    Args:
        text: A word or phrase, e.g. a dictionary term or a document span.

    Returns:
        One lemma per content token, lowercased.
    """
    return [token.lemma_.lower() for token in _NLP(text) if not (token.is_punct or token.is_space)]


def lemma_key(text: str) -> str:
    """Collapse ``text`` to a single canonical key for storage and matching.

    The key is the space-joined lemmas, so inflected or cased variants of the
    same term map to one string. This is what is stored in
    ``dictionaries.lemma_key`` and what the matcher compares document spans against.

    Args:
        text: A word or phrase to normalise.

    Returns:
        The canonical lemma key (``""`` for text with no content tokens).
    """
    return " ".join(lemmatise(text))
