"""Blob storage for binary artefacts, behind a small swappable interface.

Resume/CV files are the only binaries the system holds (design spec §5): the engine never reads
them as text, so they stay out of Postgres, which keeps only the reference. Dev writes them to a
local folder; production swaps in an Azure Blob implementation of the same ``BlobStore`` protocol,
so the endpoint and call sites never change — the MVP-to-Azure move is data-only (#118).
"""

from pathlib import Path
from typing import Protocol

from pattern_mirror.core.config import get_settings
from pattern_mirror.core.errors import BlobNotFoundError


class BlobStore(Protocol):
    """Read and write opaque binary blobs keyed by a string reference."""

    def read(self, ref: str) -> bytes:
        """Return the bytes stored under ``ref``.

        Raises:
            BlobNotFoundError: if nothing is stored under ``ref``.
        """
        ...

    def write(self, ref: str, data: bytes) -> None:
        """Store ``data`` under ``ref``, replacing any existing blob."""
        ...


class LocalDiskBlobStore:
    """A ``BlobStore`` backed by a local directory; the dev/test stand-in for Azure Blob.

    A ``ref`` maps to a path under ``root``. Refs are treated as trusted internal keys (they are
    minted by seeding and by our own services, never from request input), so they are joined
    directly; the API never routes a client-supplied string here.
    """

    def __init__(self, root: Path) -> None:
        self._root = root

    def _path(self, ref: str) -> Path:
        return self._root / ref

    def read(self, ref: str) -> bytes:
        path = self._path(ref)
        try:
            return path.read_bytes()
        except FileNotFoundError as exc:
            raise BlobNotFoundError(ref) from exc

    def write(self, ref: str, data: bytes) -> None:
        path = self._path(ref)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def get_blob_store() -> BlobStore:
    """Return the configured blob store: the local-disk stand-in now, Azure Blob in production."""
    return LocalDiskBlobStore(Path(get_settings().blob_storage_path))
