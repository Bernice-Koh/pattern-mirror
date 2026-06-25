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
