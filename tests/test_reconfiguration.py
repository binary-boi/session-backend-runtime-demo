from __future__ import annotations

import pytest

from session_backend import SessionService, SessionSettings


class FakeStorage:
    def __init__(self, label: str) -> None:
        self.label = label
        self.closed = False
        self.items: dict[str, dict] = {}

    def set(self, session_id: str, value: dict, ttl_seconds: int) -> None:
        self.items[session_id] = {**value, "_ttl": ttl_seconds}

    def get(self, session_id: str) -> dict | None:
        return self.items.get(session_id)

    def delete(self, session_id: str) -> None:
        self.items.pop(session_id, None)

    def close(self) -> None:
        self.closed = True


class RecordingFactory:
    def __init__(self) -> None:
        self.created: list[FakeStorage] = []
        self.calls: list[tuple[str, str | None]] = []

    def __call__(self, backend: str, url: str | None) -> FakeStorage:
        self.calls.append((backend, url))
        storage = FakeStorage(backend)
        self.created.append(storage)
        return storage


def test_backend_change_recreates_manager_and_preserves_settings() -> None:
    factory = RecordingFactory()
    initial = SessionSettings(
        backend="memory",
        max_sessions=250,
        timeout_seconds=900,
        cleanup_interval_seconds=60,
        storage_expiration_seconds=1200,
    )
    service = SessionService(initial, storage_factory=factory)
    old_manager = service.manager

    updated = SessionSettings(
        backend="redis",
        url="redis://cache.internal:6380/3",
        max_sessions=initial.max_sessions,
        timeout_seconds=initial.timeout_seconds,
        cleanup_interval_seconds=initial.cleanup_interval_seconds,
        storage_expiration_seconds=initial.storage_expiration_seconds,
    )
    assert service.reconfigure(updated) is True
    assert service.manager is not old_manager
    assert old_manager.storage.closed is True
    assert service.settings == updated
    assert service.generation == 2
    assert factory.calls[-1] == ("redis", "redis://cache.internal:6380/3")


def test_same_configuration_does_not_recreate_manager() -> None:
    factory = RecordingFactory()
    settings = SessionSettings()
    service = SessionService(settings, storage_factory=factory)
    original_manager = service.manager

    assert service.reconfigure(settings) is False
    assert service.manager is original_manager
    assert len(factory.created) == 1


def test_failed_replacement_keeps_previous_manager_active() -> None:
    factory = RecordingFactory()
    settings = SessionSettings()
    service = SessionService(settings, storage_factory=factory)
    old_manager = service.manager

    def failing_factory(backend: str, url: str | None):
        raise ConnectionError("backend unavailable")

    service._storage_factory = failing_factory
    target = SessionSettings(backend="redis", url="redis://localhost:6379/0")

    with pytest.raises(ConnectionError):
        service.reconfigure(target)

    assert service.manager is old_manager
    assert service.settings == settings
    assert old_manager.storage.closed is False


def test_session_operations_use_current_manager() -> None:
    factory = RecordingFactory()
    service = SessionService(SessionSettings(), storage_factory=factory)
    service.manager.save("abc", {"user": "demo"})
    assert service.manager.load("abc")["user"] == "demo"
    assert service.manager.load("abc")["_ttl"] == 3600


def test_sequential_redis_url_changes_use_latest_configuration() -> None:
    factory = RecordingFactory()
    service = SessionService(SessionSettings(backend="memory"), storage_factory=factory)

    first_redis = SessionSettings(backend="redis", url="redis://cache-a.internal:6379/0")
    second_redis = SessionSettings(backend="redis", url="redis://cache.internal:6380/3")

    assert service.reconfigure(first_redis) is True
    first_manager = service.manager
    assert service.reconfigure(second_redis) is True

    assert service.manager is not first_manager
    assert first_manager.storage.closed is True
    assert factory.calls[-1] == ("redis", "redis://cache.internal:6380/3")
    assert service.settings.url == "redis://cache.internal:6380/3"
    assert service.generation == 3
