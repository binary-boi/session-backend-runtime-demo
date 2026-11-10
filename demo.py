"""Run a local demonstration of switching the active session backend."""

from session_backend import SessionService, SessionSettings


def main() -> None:
    service = SessionService(SessionSettings(backend="memory"))
    try:
        service.manager.save("demo-session", {"user": "demo-user", "role": "viewer"})
        print(f"Initial backend: {service.settings.backend}")
        print(f"Initial session: {service.manager.load('demo-session')}")

        database_settings = SessionSettings(
            backend="database",
            url="sqlite:///./demo_sessions.db",
            max_sessions=1000,
            timeout_seconds=1800,
            cleanup_interval_seconds=300,
            storage_expiration_seconds=3600,
        )
        service.reconfigure(database_settings)
        print(f"Updated backend: {service.settings.backend}")
        print(f"Manager generation: {service.generation}")
        print("A new manager is active and configured for SQLite storage.")
    finally:
        service.close()


if __name__ == "__main__":
    main()
