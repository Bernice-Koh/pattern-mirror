"""Project exception hierarchy.

Every error raised by pattern-mirror subclasses :class:`PatternMirrorError`, so
callers can catch the whole family at a boundary (an API handler, the engine
orchestrator) and map it to a response, while still raising the most specific
type at the point of failure.
"""


class PatternMirrorError(Exception):
    """Base class for all pattern-mirror domain errors."""
