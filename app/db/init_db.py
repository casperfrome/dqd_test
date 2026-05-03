import sqlite3
from pathlib import Path

from app.core.config import ROOT_DIR, Settings
from app.db.connection import create_connection


SQL_DIR = ROOT_DIR / "sql"


def _read_sql_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _column_exists(connection: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    rows = connection.execute(f'PRAGMA table_info("{table_name}")').fetchall()
    return any(row["name"] == column_name for row in rows)


def _ensure_column(connection: sqlite3.Connection, table_name: str, column_name: str, definition: str) -> None:
    if not _column_exists(connection, table_name, column_name):
        connection.execute(f'ALTER TABLE "{table_name}" ADD COLUMN {column_name} {definition}')


def _run_lightweight_migrations(connection: sqlite3.Connection) -> None:
    _ensure_column(connection, "ai_chat_messages", "thinking_enabled", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(connection, "ai_chat_messages", "thinking_content", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(connection, "ai_chat_messages", "input_token_count", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(connection, "ai_chat_messages", "output_token_count", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(connection, "ai_chat_events", "thinking_enabled", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(connection, "ai_chat_events", "input_token_count", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(connection, "ai_chat_events", "output_token_count", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(connection, "ai_chat_messages", "is_stopped", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(connection, "ai_code_chat_messages", "is_stopped", "INTEGER NOT NULL DEFAULT 0")


def initialize_database(settings: Settings) -> None:
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = create_connection(settings)
    try:
        connection.executescript(_read_sql_file(SQL_DIR / "001_init.sql"))
        _run_lightweight_migrations(connection)
        connection.executescript(_read_sql_file(SQL_DIR / "002_seed.sql"))
        connection.commit()
    finally:
        connection.close()
