"""Session manager lifecycle and safe runtime reconfiguration."""

from __future__ import annotations

from collections.abc import Callable

from .config import SessionSettings
from .storage import SessionStorage, create_storage


class SessionManager:
    def __init__(self, settings: SessionSettings, storage: SessionStorage) -> None:
        self.settings = settings
        self.storage = storage

    def save(self, session_id: str, data: dict) -> None:
        self.storage.set(
            session_id,
            data,
            ttl_seconds=self.settings.storage_expiration_seconds,
        )

    def load(self, session_id: str) -> dict | None:
        return self.storage.get(session_id)

    def delete(self, session_id: str) -> None:
        self.storage.delete(session_id)

    def close(self) -> None:
        self.storage.close()


StorageFactory = Callable[[str, str | None], SessionStorage]


class SessionService:
    """Owns the active manager and replaces it when effective config changes."""

    def __init__(
        self,
        settings: SessionSettings,
        storage_factory: StorageFactory = create_storage,
    ) -> None:
        self._storage_factory = storage_factory
        self._settings = settings
        self._manager = self._build_manager(settings)
        self._generation = 1

    def _build_manager(self, settings: SessionSettings) -> SessionManager:
        storage = self._storage_factory(settings.backend, settings.url)
        return SessionManager(settings=settings, storage=storage)

    @property
    def manager(self) -> SessionManager:
        return self._manager

    @property
    def settings(self) -> SessionSettings:
        return self._settings

    @property
    def generation(self) -> int:
        return self._generation

    def reconfigure(self, new_settings: SessionSettings) -> bool:
        """Build first, then swap; leave the old manager active if construction fails."""
        if new_settings == self._settings:
            return False

        replacement = self._build_manager(new_settings)
        previous = self._manager
        self._manager = replacement
        self._settings = new_settings
        self._generation += 1
        previous.close()
        return True

    def close(self) -> None:
        self._manager.close()
