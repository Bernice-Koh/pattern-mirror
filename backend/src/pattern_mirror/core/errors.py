"""Project exception hierarchy.

Every error raised by pattern-mirror subclasses :class:`PatternMirrorError`, so
callers can catch the whole family at a boundary (an API handler, the engine
orchestrator) and map it to a response, while still raising the most specific
type at the point of failure.
"""


class PatternMirrorError(Exception):
    """Base class for all pattern-mirror domain errors."""


class SeedDataMissingError(PatternMirrorError):
    """Required seed data (e.g. the demo manager) is absent from the database."""


class DocumentNotFoundError(PatternMirrorError):
    """A requested document does not exist or is not owned by the current user."""

    def __init__(self, document_id: object) -> None:
        super().__init__(f"Document not found: {document_id}")
        self.document_id = document_id


class FlagNotFoundError(PatternMirrorError):
    """A requested flag does not exist or belongs to another user's document."""

    def __init__(self, flag_id: object) -> None:
        super().__init__(f"Flag not found: {flag_id}")
        self.flag_id = flag_id


class JudgeVerdictCountError(PatternMirrorError):
    """The Judge returned a different number of verdicts than the flags it was asked to score."""

    def __init__(self, expected: int, received: int) -> None:
        super().__init__(f"Judge returned {received} verdicts for {expected} flags")
        self.expected = expected
        self.received = received


class RecommendationCountError(PatternMirrorError):
    """The Recommendations Agent returned a different number of sets than the flags given."""

    def __init__(self, expected: int, received: int) -> None:
        super().__init__(f"Recommendations returned {received} sets for {expected} flags")
        self.expected = expected
        self.received = received
