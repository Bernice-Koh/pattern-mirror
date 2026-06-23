"""Offset-aware tokenisation for Stage-1 matching.

Where ``lemmatiser`` collapses text to a canonical key, the dictionary matcher also
needs to point back at the exact source characters it matched. This module returns
each content token's lemma *with* its character span, reusing the one spaCy pipeline
via ``lemmatiser.get_nlp`` so there is a single model load and no risk of two
pipelines drifting apart.
"""

from dataclasses import dataclass

from pattern_mirror.engine.lemmatiser import get_nlp


@dataclass(frozen=True)
class LemmaToken:
    """A content token's lowercased lemma and its character span in the source text."""

    lemma: str
    start: int
    end: int


def lemmatise_with_offsets(text: str) -> list[LemmaToken]:
    """Return each content token's lemma with its character offsets into ``text``.

    Punctuation and whitespace tokens are dropped, exactly as ``lemmatiser.lemmatise``
    does, so the lemma sequence here agrees with the seeded ``lemma_key`` while also
    carrying offsets. ``token.idx`` is the start offset into the unmodified ``text``
    passed in, so a span sliced at these offsets maps back to the raw source verbatim.

    Args:
        text: The raw document text, used unmodified so the offsets stay valid.

    Returns:
        One ``LemmaToken`` per content token, in document order.
    """
    return [
        LemmaToken(lemma=token.lemma_.lower(), start=token.idx, end=token.idx + len(token.text))
        for token in get_nlp()(text)
        if not (token.is_punct or token.is_space)
    ]
