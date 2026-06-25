"""In-process registry of the latest analysis run per document, for supersede semantics.

The two-trigger model fires a fresh LLM run on every typing pause, so an older run can
still be streaming when a newer one starts for the same document. The newer run wins: the
older one keeps persisting (log-everything) but stops surfacing results to the client. The
registry is the single place that decides which run is current.

Single-instance only. Access is from the asyncio event loop and the threadpool worker that
drives one stream; reads and writes are individually atomic and a document's entry is only
ever advanced, never contended for correctness, so no lock is needed at this scale. Cross-
instance supersede (multiple replicas) would need a shared store such as Redis pub/sub —
out of scope for the MVP.
"""

import uuid


class RunRegistry:
    """Tracks the most recently started analysis run for each document."""

    def __init__(self) -> None:
        self._latest_by_document: dict[uuid.UUID, uuid.UUID] = {}

    def register(self, document_id: uuid.UUID, run_id: uuid.UUID) -> None:
        """Mark ``run_id`` as the current run for ``document_id``, superseding any prior."""
        self._latest_by_document[document_id] = run_id

    def is_latest(self, document_id: uuid.UUID, run_id: uuid.UUID) -> bool:
        """Return whether ``run_id`` is still the current run for ``document_id``."""
        return self._latest_by_document.get(document_id) == run_id

    def release(self, document_id: uuid.UUID, run_id: uuid.UUID) -> None:
        """Drop ``document_id``'s entry, but only if ``run_id`` is still the current run.

        Guards against a finishing run clearing the entry of a newer run that has already
        superseded it.
        """
        if self._latest_by_document.get(document_id) == run_id:
            del self._latest_by_document[document_id]


_registry = RunRegistry()


def get_run_registry() -> RunRegistry:
    """Return the process-wide run registry."""
    return _registry
