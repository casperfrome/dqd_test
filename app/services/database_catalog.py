import os
import sqlite3
from pathlib import Path
from typing import Any

from app.core.config import ROOT_DIR
from app.services.database_comments import get_column_comment, get_table_comment


DATABASE_EXTENSIONS = {".db", ".sqlite", ".sqlite3"}
SKIPPED_DIRECTORIES = {
    ".cache",
    ".git",
    ".idea",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "venv",
}


def quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def is_sqlite_database(path: Path) -> bool:
    try:
        with path.open("rb") as file:
            return file.read(16) == b"SQLite format 3\x00"
    except OSError:
        return False


def discover_database_files(root: Path = ROOT_DIR) -> list[Path]:
    databases: list[Path] = []
    for current_root, dirs, files in os.walk(root):
        dirs[:] = [name for name in dirs if name not in SKIPPED_DIRECTORIES]
        current_path = Path(current_root)
        for file_name in files:
            path = current_path / file_name
            if path.suffix.lower() in DATABASE_EXTENSIONS and is_sqlite_database(path):
                databases.append(path.resolve())
    return sorted(databases, key=lambda item: str(item.relative_to(root)))


def inspect_databases(root: Path = ROOT_DIR) -> list[dict[str, Any]]:
    return [inspect_database(path, root) for path in discover_database_files(root)]


def inspect_database(path: Path, root: Path = ROOT_DIR) -> dict[str, Any]:
    database = {
        "name": path.name,
        "path": str(path.relative_to(root)),
        "size_bytes": path.stat().st_size,
        "table_count": 0,
        "status": "ok",
        "error": None,
        "tables": [],
    }
    try:
        connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        try:
            tables = _list_tables(connection)
            database["tables"] = [_inspect_table(connection, table_name) for table_name in tables]
            database["table_count"] = len(database["tables"])
        finally:
            connection.close()
    except sqlite3.Error as exc:
        database["status"] = "error"
        database["error"] = str(exc)
        database["tables"] = []
        database["table_count"] = 0
    return database


def _list_tables(connection: sqlite3.Connection) -> list[str]:
    fts_shadow_tables = set(_list_fts_shadow_tables(connection))
    rows = connection.execute(
        """
        SELECT name
        FROM sqlite_schema
        WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """,
    ).fetchall()
    return [str(row["name"]) for row in rows if str(row["name"]) not in fts_shadow_tables]


def _list_fts_shadow_tables(connection: sqlite3.Connection) -> list[str]:
    rows = connection.execute(
        """
        SELECT name
        FROM sqlite_schema
        WHERE type = 'table' AND lower(sql) LIKE '%using fts5%'
        """,
    ).fetchall()
    suffixes = ("_data", "_idx", "_content", "_docsize", "_config")
    return [f"{row['name']}{suffix}" for row in rows for suffix in suffixes]


def _inspect_table(connection: sqlite3.Connection, table_name: str) -> dict[str, Any]:
    quoted_table = quote_identifier(table_name)
    columns = _get_columns(connection, table_name, quoted_table)
    return {
        "name": table_name,
        "comment": get_table_comment(table_name),
        "row_count": _count_rows(connection, quoted_table),
        "columns": columns,
        "foreign_keys": _get_foreign_keys(connection, quoted_table),
        "indexes": _get_indexes(connection, quoted_table),
        "sample_rows": _get_sample_rows(connection, quoted_table),
    }


def _get_columns(connection: sqlite3.Connection, table_name: str, quoted_table: str) -> list[dict[str, Any]]:
    rows = connection.execute(f"PRAGMA table_info({quoted_table})").fetchall()
    return [
        {
            "name": str(row["name"]),
            "comment": get_column_comment(table_name, str(row["name"])),
            "type": str(row["type"] or ""),
            "not_null": bool(row["notnull"]),
            "default_value": None if row["dflt_value"] is None else str(row["dflt_value"]),
            "primary_key": int(row["pk"]) > 0,
            "primary_key_position": int(row["pk"]),
        }
        for row in rows
    ]


def _get_foreign_keys(connection: sqlite3.Connection, quoted_table: str) -> list[dict[str, Any]]:
    rows = connection.execute(f"PRAGMA foreign_key_list({quoted_table})").fetchall()
    return [
        {
            "id": int(row["id"]),
            "sequence": int(row["seq"]),
            "from_column": str(row["from"]),
            "to_table": str(row["table"]),
            "to_column": None if row["to"] is None else str(row["to"]),
            "on_update": str(row["on_update"]),
            "on_delete": str(row["on_delete"]),
        }
        for row in rows
    ]


def _get_indexes(connection: sqlite3.Connection, quoted_table: str) -> list[dict[str, Any]]:
    indexes = []
    for row in connection.execute(f"PRAGMA index_list({quoted_table})").fetchall():
        index_name = str(row["name"])
        quoted_index = quote_identifier(index_name)
        columns = [
            str(column["name"])
            for column in connection.execute(f"PRAGMA index_info({quoted_index})").fetchall()
            if column["name"] is not None
        ]
        indexes.append(
            {
                "name": index_name,
                "unique": bool(row["unique"]),
                "origin": str(row["origin"]),
                "columns": columns,
            },
        )
    return indexes


def _count_rows(connection: sqlite3.Connection, quoted_table: str) -> int:
    row = connection.execute(f"SELECT COUNT(*) AS count FROM {quoted_table}").fetchone()
    return int(row["count"])


def _get_sample_rows(connection: sqlite3.Connection, quoted_table: str) -> list[dict[str, Any]]:
    rows = connection.execute(f"SELECT * FROM {quoted_table} ORDER BY RANDOM() LIMIT 5").fetchall()
    return [{key: _normalize_value(row[key]) for key in row.keys()} for row in rows]


def _normalize_value(value: Any) -> Any:
    if isinstance(value, bytes):
        return value.hex()
    return value
