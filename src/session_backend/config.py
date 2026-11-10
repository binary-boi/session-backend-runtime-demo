"""Validated configuration for the session manager and its storage backend."""

from dataclasses import dataclass
from urllib.parse import urlparse


SUPPORTED_BACKENDS = {"memory", "redis", "memcached", "database"}


@dataclass(frozen=True)
class SessionSettings:
    backend: str = "memory"
    url: str | None = None
    max_sessions: int = 1000
    timeout_seconds: int = 1800
    cleanup_interval_seconds: int = 300
    storage_expiration_seconds: int = 3600

    def __post_init__(self) -> None:
        backend = self.backend.lower().strip()
        object.__setattr__(self, "backend", backend)

        if backend not in SUPPORTED_BACKENDS:
            raise ValueError(
                f"Unsupported backend '{backend}'. Choose one of: "
                f"{', '.join(sorted(SUPPORTED_BACKENDS))}."
            )
        for field_name in (
            "max_sessions",
            "timeout_seconds",
            "cleanup_interval_seconds",
            "storage_expiration_seconds",
        ):
            if getattr(self, field_name) <= 0:
                raise ValueError(f"{field_name} must be greater than zero.")

        if backend == "memory" and self.url:
            raise ValueError("The memory backend does not accept a connection URL.")
        if backend != "memory" and not self.url:
            raise ValueError(f"The {backend} backend requires a connection URL.")

        if self.url:
            parsed = urlparse(self.url)
            expected_schemes = {
                "redis": {"redis", "rediss"},
                "memcached": {"memcached"},
                "database": {"sqlite"},
            }
            if parsed.scheme not in expected_schemes[backend]:
                allowed = ", ".join(sorted(expected_schemes[backend]))
                raise ValueError(
                    f"Invalid URL scheme '{parsed.scheme}' for {backend}; expected {allowed}."
                )
            if backend in {"redis", "memcached"} and not parsed.hostname:
                raise ValueError(f"The {backend} URL must include a hostname.")
