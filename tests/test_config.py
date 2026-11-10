import pytest

from session_backend import SessionSettings


def test_redis_url_accepts_non_default_host_port_and_database() -> None:
    settings = SessionSettings(backend="redis", url="redis://cache.internal:6380/3")
    assert settings.url == "redis://cache.internal:6380/3"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"backend": "unknown"},
        {"backend": "redis"},
        {"backend": "redis", "url": "http://localhost:6379/0"},
        {"backend": "memory", "url": "redis://localhost:6379/0"},
        {"max_sessions": 0},
    ],
)
def test_invalid_configuration_is_rejected(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        SessionSettings(**kwargs)
