import json
import sqlite3
from typing import Any

from app.repositories.base import fetch_all_dicts, fetch_one_dict


def count_facts(connection: sqlite3.Connection) -> int:
    row = connection.execute("SELECT COUNT(*) AS count FROM ai_code_facts").fetchone()
    return int(row["count"])


def get_latest_fact_updated_at(connection: sqlite3.Connection) -> str | None:
    row = connection.execute("SELECT MAX(updated_at) AS updated_at FROM ai_code_facts").fetchone()
    return str(row["updated_at"]) if row and row["updated_at"] else None


def get_existing_hashes(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute("SELECT content_hash FROM ai_code_facts").fetchall()
    return {str(row["content_hash"]) for row in rows}


def delete_facts_by_hashes(connection: sqlite3.Connection, hashes: set[str]) -> None:
    if not hashes:
        return
    placeholders = ",".join("?" for _ in hashes)
    connection.execute(
        f"DELETE FROM ai_code_fact_fts WHERE rowid IN (SELECT id FROM ai_code_facts WHERE content_hash IN ({placeholders}))",
        tuple(hashes),
    )
    connection.execute(
        f"DELETE FROM ai_code_facts WHERE content_hash IN ({placeholders})",
        tuple(hashes),
    )


def clear_facts(connection: sqlite3.Connection) -> None:
    connection.execute("DELETE FROM ai_code_fact_fts")
    connection.execute("DELETE FROM ai_code_facts")


def insert_fact(
    connection: sqlite3.Connection,
    *,
    source_file_path: str,
    language: str,
    start_line: int,
    end_line: int,
    title: str,
    content: str,
    metadata: dict[str, Any],
    content_hash: str,
    generated_at: str,
    updated_at: str,
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO ai_code_facts (
            source_file_path,
            language,
            start_line,
            end_line,
            title,
            content,
            metadata_json,
            content_hash,
            generated_at,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            source_file_path,
            language,
            start_line,
            end_line,
            title,
            content,
            json.dumps(metadata, ensure_ascii=False),
            content_hash,
            generated_at,
            updated_at,
        ),
    )
    fact_id = int(cursor.lastrowid)
    connection.execute(
        "INSERT INTO ai_code_fact_fts(rowid, source_file_path, title, content) VALUES (?, ?, ?, ?)",
        (fact_id, source_file_path, title, content),
    )
    return fact_id


def search_facts(connection: sqlite3.Connection, match_query: str, *, limit: int) -> list[dict[str, Any]]:
    rows = fetch_all_dicts(
        connection,
        """
        SELECT
            f.id,
            f.source_file_path,
            f.language,
            f.start_line,
            f.end_line,
            f.title,
            f.content,
            f.metadata_json,
            bm25(ai_code_fact_fts) AS score
        FROM ai_code_fact_fts
        JOIN ai_code_facts f ON f.id = ai_code_fact_fts.rowid
        WHERE ai_code_fact_fts MATCH ?
        ORDER BY score
        LIMIT ?
        """,
        (match_query, limit),
    )
    return [_decode_metadata(row) for row in rows]


def list_recent_facts(connection: sqlite3.Connection, *, limit: int) -> list[dict[str, Any]]:
    rows = fetch_all_dicts(
        connection,
        """
        SELECT
            id,
            source_file_path,
            language,
            start_line,
            end_line,
            title,
            content,
            metadata_json,
            0 AS score
        FROM ai_code_facts
        ORDER BY updated_at DESC, id DESC
        LIMIT ?
        """,
        (limit,),
    )
    return [_decode_metadata(row) for row in rows]


def get_facts_by_ids(connection: sqlite3.Connection, fact_ids: list[int]) -> list[dict[str, Any]]:
    if not fact_ids:
        return []
    placeholders = ",".join("?" for _ in fact_ids)
    rows = fetch_all_dicts(
        connection,
        f"""
        SELECT
            id,
            source_file_path,
            language,
            start_line,
            end_line,
            title,
            content,
            metadata_json,
            0 AS score
        FROM ai_code_facts
        WHERE id IN ({placeholders})
        """,
        tuple(fact_ids),
    )
    by_id = {int(row["id"]): _decode_metadata(row) for row in rows}
    return [by_id[fact_id] for fact_id in fact_ids if fact_id in by_id]


def create_session(
    connection: sqlite3.Connection,
    *,
    public_id: str,
    owner_user_id: int | None,
    client_id_hash: str | None,
    title: str,
    created_at: str,
) -> dict[str, Any]:
    cursor = connection.execute(
        """
        INSERT INTO ai_code_chat_sessions (public_id, owner_user_id, client_id_hash, title, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (public_id, owner_user_id, client_id_hash, title, created_at, created_at),
    )
    return get_session_by_id(connection, int(cursor.lastrowid))


def get_session_by_id(connection: sqlite3.Connection, session_id: int) -> dict[str, Any] | None:
    return fetch_one_dict(connection, "SELECT * FROM ai_code_chat_sessions WHERE id = ?", (session_id,))


def get_session_by_public_id(connection: sqlite3.Connection, public_id: str) -> dict[str, Any] | None:
    return fetch_one_dict(connection, "SELECT * FROM ai_code_chat_sessions WHERE public_id = ?", (public_id,))


def list_sessions_for_owner(connection: sqlite3.Connection, owner_user_id: int, *, limit: int = 30) -> list[dict[str, Any]]:
    return fetch_all_dicts(
        connection,
        """
        SELECT *
        FROM ai_code_chat_sessions
        WHERE owner_user_id = ?
        ORDER BY updated_at DESC
        LIMIT ?
        """,
        (owner_user_id, limit),
    )


def list_sessions_for_client(connection: sqlite3.Connection, client_id_hash: str, *, limit: int = 30) -> list[dict[str, Any]]:
    return fetch_all_dicts(
        connection,
        """
        SELECT *
        FROM ai_code_chat_sessions
        WHERE owner_user_id IS NULL AND client_id_hash = ?
        ORDER BY updated_at DESC
        LIMIT ?
        """,
        (client_id_hash, limit),
    )


def update_session_timestamp(connection: sqlite3.Connection, session_id: int, updated_at: str) -> None:
    connection.execute(
        "UPDATE ai_code_chat_sessions SET updated_at = ? WHERE id = ?",
        (updated_at, session_id),
    )


def insert_message(
    connection: sqlite3.Connection,
    *,
    session_id: int,
    role: str,
    content: str,
    retrieved_fact_ids: list[int],
    thinking_enabled: bool = False,
    thinking_content: str = "",
    input_token_count: int = 0,
    output_token_count: int = 0,
    created_at: str,
) -> dict[str, Any]:
    cursor = connection.execute(
        """
        INSERT INTO ai_code_chat_messages (
            session_id,
            role,
            content,
            retrieved_fact_ids_json,
            thinking_enabled,
            thinking_content,
            input_token_count,
            output_token_count,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            session_id,
            role,
            content,
            json.dumps(retrieved_fact_ids),
            int(thinking_enabled),
            thinking_content,
            input_token_count,
            output_token_count,
            created_at,
        ),
    )
    update_session_timestamp(connection, session_id, created_at)
    return get_message_by_id(connection, int(cursor.lastrowid))


def get_message_by_id(connection: sqlite3.Connection, message_id: int) -> dict[str, Any] | None:
    row = fetch_one_dict(connection, "SELECT * FROM ai_code_chat_messages WHERE id = ?", (message_id,))
    return _decode_message(row) if row else None


def list_messages(connection: sqlite3.Connection, session_id: int) -> list[dict[str, Any]]:
    rows = fetch_all_dicts(
        connection,
        """
        SELECT *
        FROM ai_code_chat_messages
        WHERE session_id = ?
        ORDER BY created_at, id
        """,
        (session_id,),
    )
    return [_decode_message(row) for row in rows]


def insert_event(
    connection: sqlite3.Connection,
    *,
    event_type: str,
    session_id: int | None,
    message_id: int | None,
    actor_user_id: int | None,
    model: str,
    retrieved_fact_ids: list[int],
    thinking_enabled: bool = False,
    input_token_count: int = 0,
    output_token_count: int = 0,
    duration_ms: int,
    status: str,
    error_message: str | None,
    created_at: str,
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO ai_code_chat_events (
            event_type,
            session_id,
            message_id,
            actor_user_id,
            model,
            retrieved_fact_ids_json,
            retrieved_fact_count,
            thinking_enabled,
            input_token_count,
            output_token_count,
            duration_ms,
            status,
            error_message,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_type,
            session_id,
            message_id,
            actor_user_id,
            model,
            json.dumps(retrieved_fact_ids),
            len(retrieved_fact_ids),
            int(thinking_enabled),
            input_token_count,
            output_token_count,
            duration_ms,
            status,
            error_message,
            created_at,
        ),
    )
    return int(cursor.lastrowid)


def _decode_metadata(row: dict[str, Any]) -> dict[str, Any]:
    row["metadata"] = json.loads(str(row.pop("metadata_json") or "{}"))
    return row


def _decode_message(row: dict[str, Any]) -> dict[str, Any]:
    row["retrieved_fact_ids"] = json.loads(str(row.pop("retrieved_fact_ids_json") or "[]"))
    row["thinking_enabled"] = bool(row["thinking_enabled"])
    return row
