import json
import sqlite3
from typing import Any

from app.repositories.base import fetch_all_dicts


def record_user_event(
    connection: sqlite3.Connection,
    *,
    actor_user_id: int | None,
    target_user_id: int | None,
    event_type: str,
    metadata: dict[str, Any] | None,
    created_at: str,
) -> None:
    connection.execute(
        """
        INSERT INTO user_events (actor_user_id, target_user_id, event_type, metadata_json, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (actor_user_id, target_user_id, event_type, json.dumps(metadata or {}, ensure_ascii=False), created_at),
    )


def record_fan_circle_event(
    connection: sqlite3.Connection,
    *,
    actor_user_id: int | None,
    fan_circle_id: int,
    event_type: str,
    metadata: dict[str, Any] | None,
    created_at: str,
) -> None:
    connection.execute(
        """
        INSERT INTO fan_circle_events (actor_user_id, fan_circle_id, event_type, metadata_json, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (actor_user_id, fan_circle_id, event_type, json.dumps(metadata or {}, ensure_ascii=False), created_at),
    )


def record_post_event(
    connection: sqlite3.Connection,
    *,
    actor_user_id: int | None,
    post_id: int,
    comment_id: int | None,
    event_type: str,
    metadata: dict[str, Any] | None,
    created_at: str,
) -> None:
    connection.execute(
        """
        INSERT INTO post_events (actor_user_id, post_id, comment_id, event_type, metadata_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (actor_user_id, post_id, comment_id, event_type, json.dumps(metadata or {}, ensure_ascii=False), created_at),
    )


def get_recent_user_events(connection: sqlite3.Connection, user_id: int, *, limit: int = 10) -> list[dict[str, Any]]:
    return _decode_events(
        fetch_all_dicts(
            connection,
            """
            SELECT id, actor_user_id, target_user_id, event_type, metadata_json, created_at
            FROM user_events
            WHERE target_user_id = ? OR actor_user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, user_id, limit),
        )
    )


def get_recent_fan_circle_events(connection: sqlite3.Connection, fan_circle_id: int, *, limit: int = 10) -> list[dict[str, Any]]:
    return _decode_events(
        fetch_all_dicts(
            connection,
            """
            SELECT id, actor_user_id, fan_circle_id, event_type, metadata_json, created_at
            FROM fan_circle_events
            WHERE fan_circle_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (fan_circle_id, limit),
        )
    )


def get_recent_post_events(connection: sqlite3.Connection, post_id: int, *, limit: int = 10) -> list[dict[str, Any]]:
    return _decode_events(
        fetch_all_dicts(
            connection,
            """
            SELECT id, actor_user_id, post_id, comment_id, event_type, metadata_json, created_at
            FROM post_events
            WHERE post_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (post_id, limit),
        )
    )


def _decode_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for event in events:
        event["metadata"] = json.loads(event.pop("metadata_json"))
    return events
