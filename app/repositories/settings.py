import sqlite3


DATABASE_ACCESS_SETTING_KEY = "database_access_level"
DEFAULT_DATABASE_ACCESS_LEVEL = "public"


def get_setting(connection: sqlite3.Connection, key: str, default: str | None = None) -> str | None:
    row = connection.execute(
        "SELECT value FROM system_settings WHERE key = ?",
        (key,),
    ).fetchone()
    return str(row["value"]) if row else default


def set_setting(connection: sqlite3.Connection, key: str, value: str, updated_at: str) -> None:
    connection.execute(
        """
        INSERT INTO system_settings (key, value, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
        """,
        (key, value, updated_at),
    )


def get_database_access_level(connection: sqlite3.Connection) -> str:
    value = get_setting(connection, DATABASE_ACCESS_SETTING_KEY, DEFAULT_DATABASE_ACCESS_LEVEL)
    if value not in {"public", "authenticated", "super_admin"}:
        return DEFAULT_DATABASE_ACCESS_LEVEL
    return value


def set_database_access_level(connection: sqlite3.Connection, value: str, updated_at: str) -> None:
    set_setting(connection, DATABASE_ACCESS_SETTING_KEY, value, updated_at)
