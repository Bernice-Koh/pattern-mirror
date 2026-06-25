"""The supersede registry: newer runs win, and a finishing run never clobbers a newer one."""

import uuid

from pattern_mirror.services.run_registry import RunRegistry, get_run_registry


def test_a_registered_run_is_the_latest() -> None:
    registry = RunRegistry()
    document_id, run_id = uuid.uuid4(), uuid.uuid4()

    registry.register(document_id, run_id)

    assert registry.is_latest(document_id, run_id)


def test_a_newer_run_supersedes_an_older_one() -> None:
    registry = RunRegistry()
    document_id = uuid.uuid4()
    older, newer = uuid.uuid4(), uuid.uuid4()

    registry.register(document_id, older)
    registry.register(document_id, newer)

    assert not registry.is_latest(document_id, older)
    assert registry.is_latest(document_id, newer)


def test_release_clears_only_when_still_latest() -> None:
    registry = RunRegistry()
    document_id = uuid.uuid4()
    older, newer = uuid.uuid4(), uuid.uuid4()

    registry.register(document_id, older)
    registry.register(document_id, newer)
    # The older run finishing must not drop the newer run's entry.
    registry.release(document_id, older)

    assert registry.is_latest(document_id, newer)


def test_an_unknown_run_is_not_latest() -> None:
    registry = RunRegistry()

    assert not registry.is_latest(uuid.uuid4(), uuid.uuid4())


def test_get_run_registry_returns_one_shared_instance() -> None:
    assert get_run_registry() is get_run_registry()
