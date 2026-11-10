from session_backend.storage import DatabaseSessionStorage


def test_database_storage_round_trip(tmp_path) -> None:
    db_path = tmp_path / "sessions.db"
    storage = DatabaseSessionStorage(f"sqlite:///{db_path}")
    storage.set("session-1", {"user": "akshay", "role": "demo"}, ttl_seconds=300)

    assert storage.get("session-1") == {"user": "akshay", "role": "demo"}

    storage.delete("session-1")
    assert storage.get("session-1") is None
    storage.close()
