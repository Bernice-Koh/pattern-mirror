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


class InvalidCredentialsError(PatternMirrorError):
    """Login credentials do not match an active user holding the expected role."""

    def __init__(self) -> None:
        super().__init__("Invalid credentials.")


class NotAuthenticatedError(PatternMirrorError):
    """The request carries no valid session token."""

    def __init__(self) -> None:
        super().__init__("Not authenticated.")


class NotAuthorizedError(PatternMirrorError):
    """The caller is authenticated but lacks the role required for this resource."""

    def __init__(self) -> None:
        super().__init__("Not authorized.")


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


class PendingAdditionNotFoundError(PatternMirrorError):
    """A requested pending dictionary addition does not exist."""

    def __init__(self, addition_id: object) -> None:
        super().__init__(f"Pending addition not found: {addition_id}")
        self.addition_id = addition_id


class ProposalNotFoundError(PatternMirrorError):
    """A requested dictionary-growth proposal does not exist."""

    def __init__(self, proposal_id: object) -> None:
        super().__init__(f"Proposal not found: {proposal_id}")
        self.proposal_id = proposal_id


class AdditionAlreadyDecidedError(PatternMirrorError):
    """A pending addition has already been approved or rejected and cannot be decided again."""

    def __init__(self, addition_id: object, status: object) -> None:
        super().__init__(f"Pending addition {addition_id} already decided: {status}")
        self.addition_id = addition_id
        self.status = status


class DictionaryEntryExistsError(PatternMirrorError):
    """An active dictionary entry already exists for this region, phrase, and category."""

    def __init__(self, lemma_key: object, category: object) -> None:
        super().__init__(f"Dictionary entry already exists: {lemma_key} ({category})")
        self.lemma_key = lemma_key
        self.category = category


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
