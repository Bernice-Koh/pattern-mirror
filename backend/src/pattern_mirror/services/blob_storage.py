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


# backend/src/pattern_mirror/services/blob_storage.py -> repo root, so a relative BLOB_STORAGE_PATH
# lands in the same place no matter which directory the server or the seed job is launched from.
_REPO_ROOT = Path(__file__).resolve().parents[4]


def _resolve_root(path_str: str) -> Path:
    """Anchor a relative blob path to the repo root; pass absolute paths through unchanged.

    The default (``./deploy/blob-data``) is repo-root-relative — anchoring on CWD would let the
    seed job write to one folder and the API server read from another, surfacing as a 404 download.
    Production sets an absolute path, which is used as-is.
    """
    path = Path(path_str)
    return path if path.is_absolute() else _REPO_ROOT / path


def get_blob_store() -> BlobStore:
    """Return the configured blob store: the local-disk stand-in now, Azure Blob in production."""
    return LocalDiskBlobStore(_resolve_root(get_settings().blob_storage_path))
