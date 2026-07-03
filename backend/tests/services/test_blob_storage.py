"""The local-disk blob store round-trips bytes and reports a missing ref distinctly."""

from pathlib import Path

import pytest

from pattern_mirror.core.config import get_settings
from pattern_mirror.core.errors import BlobNotFoundError
from pattern_mirror.services.blob_storage import LocalDiskBlobStore, get_blob_store


def test_write_then_read_round_trips(tmp_path: Path) -> None:
    store = LocalDiskBlobStore(tmp_path)
    store.write("resumes/a.pdf", b"%PDF-fake")

    assert store.read("resumes/a.pdf") == b"%PDF-fake"


def test_write_creates_nested_directories(tmp_path: Path) -> None:
    store = LocalDiskBlobStore(tmp_path)
    store.write("deep/nested/ref.bin", b"data")

    assert (tmp_path / "deep" / "nested" / "ref.bin").read_bytes() == b"data"


def test_write_replaces_an_existing_blob(tmp_path: Path) -> None:
    store = LocalDiskBlobStore(tmp_path)
    store.write("ref", b"first")
    store.write("ref", b"second")

    assert store.read("ref") == b"second"


def test_read_missing_ref_raises_blob_not_found(tmp_path: Path) -> None:
    store = LocalDiskBlobStore(tmp_path)

    with pytest.raises(BlobNotFoundError):
        store.read("absent")


def test_get_blob_store_roots_at_the_configured_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BLOB_STORAGE_PATH", str(tmp_path))
    get_settings.cache_clear()
    try:
        store = get_blob_store()
        store.write("ref", b"x")
        assert (tmp_path / "ref").read_bytes() == b"x"
    finally:
        get_settings.cache_clear()
