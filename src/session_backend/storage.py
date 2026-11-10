"""Storage adapters. Each adapter exposes the same small interface."""

from __future__ import annotations

import json
from typing import Protocol
from urllib.parse import urlparse

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


class SessionStorage(Protocol):
    def set(self, session_id: str, value: dict, ttl_seconds: int) -> None: ...
    def get(self, session_id: str) -> dict | None: ...
    def delete(self, session_id: str) -> None: ...
    def close(self) -> None: ...


class MemorySessionStorage:
    def __init__(self) -> None:
        self._items: dict[str, dict] = {}

    def set(self, session_id: str, value: dict, ttl_seconds: int) -> None:
        # TTL is accepted to keep the adapter interface consistent. This demo's
        # in-memory adapter does not run a background expiration worker.
        self._items[session_id] = value

    def get(self, session_id: str) -> dict | None:
        return self._items.get(session_id)

    def delete(self, session_id: str) -> None:
        self._items.pop(session_id, None)

    def close(self) -> None:
        self._items.clear()


class RedisSessionStorage:
    def __init__(self, url: str) -> None:
        import redis

        self._client = redis.Redis.from_url(url, decode_responses=True)
        self._client.ping()

    def set(self, session_id: str, value: dict, ttl_seconds: int) -> None:
        self._client.set(session_id, json.dumps(value), ex=ttl_seconds)

    def get(self, session_id: str) -> dict | None:
        raw = self._client.get(session_id)
        return json.loads(raw) if raw is not None else None

    def delete(self, session_id: str) -> None:
        self._client.delete(session_id)

    def close(self) -> None:
        self._client.close()


class MemcachedSessionStorage:
    def __init__(self, url: str) -> None:
        from pymemcache.client.base import Client

        parsed = urlparse(url)
        port = parsed.port or 11211
        self._client = Client((parsed.hostname, port), connect_timeout=2, timeout=2)
        self._client.version()  # Fail fast if the configured service is unreachable.

    def set(self, session_id: str, value: dict, ttl_seconds: int) -> None:
        self._client.set(session_id, json.dumps(value), expire=ttl_seconds)

    def get(self, session_id: str) -> dict | None:
        raw = self._client.get(session_id)
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return json.loads(raw)

    def delete(self, session_id: str) -> None:
        self._client.delete(session_id)

    def close(self) -> None:
        self._client.close()


class DatabaseSessionStorage:
    """Small SQLAlchemy-backed adapter intended for this demonstrator."""

    def __init__(self, url: str) -> None:
        self._engine: Engine = create_engine(url, future=True)
        with self._engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS sessions ("
                    "session_id VARCHAR(255) PRIMARY KEY, "
                    "payload TEXT NOT NULL)"
                )
            )

    def set(self, session_id: str, value: dict, ttl_seconds: int) -> None:
        del ttl_seconds  # Expiration policy is represented in manager settings in this demo.
        payload = json.dumps(value)
        with self._engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO sessions (session_id, payload) VALUES (:id, :payload) "
                    "ON CONFLICT(session_id) DO UPDATE SET payload = excluded.payload"
                ),
                {"id": session_id, "payload": payload},
            )

    def get(self, session_id: str) -> dict | None:
        with self._engine.connect() as connection:
            row = connection.execute(
                text("SELECT payload FROM sessions WHERE session_id = :id"),
                {"id": session_id},
            ).first()
        return json.loads(row[0]) if row else None

    def delete(self, session_id: str) -> None:
        with self._engine.begin() as connection:
            connection.execute(
                text("DELETE FROM sessions WHERE session_id = :id"), {"id": session_id}
            )

    def close(self) -> None:
        self._engine.dispose()


def create_storage(backend: str, url: str | None) -> SessionStorage:
    if backend == "memory":
        return MemorySessionStorage()
    if backend == "redis":
        assert url is not None
        return RedisSessionStorage(url)
    if backend == "memcached":
        assert url is not None
        return MemcachedSessionStorage(url)
    if backend == "database":
        assert url is not None
        return DatabaseSessionStorage(url)
    raise ValueError(f"Unsupported backend: {backend}")
