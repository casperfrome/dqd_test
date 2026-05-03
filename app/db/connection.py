import sqlite3
from collections.abc import Generator
from contextlib import contextmanager

from app.core.config import Settings, get_settings


def create_connection(settings: Settings | None = None) -> sqlite3.Connection:
    resolved_settings = settings or get_settings()
    connection = sqlite3.connect(
        resolved_settings.database_path,
        check_same_thread=False,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    return connection


@contextmanager
def db_session(settings: Settings | None = None) -> Generator[sqlite3.Connection, None, None]:
    connection = create_connection(settings)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
