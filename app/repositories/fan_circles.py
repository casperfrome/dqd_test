import sqlite3
from typing import Any

from app.repositories.base import fetch_all_dicts, fetch_one_dict


def list_fan_circles(connection: sqlite3.Connection, *, limit: int, offset: int) -> list[dict[str, Any]]:
    return fetch_all_dicts(
        connection,
        """
        SELECT
            fc.*,
            u.username AS owner_username,
            u.nickname AS owner_nickname,
            u.avatar_url AS owner_avatar_url
        FROM fan_circles fc
        LEFT JOIN users u ON u.id = fc.owner_user_id
        ORDER BY fc.id ASC
        LIMIT ? OFFSET ?
        """,
        (limit, offset),
    )


def count_fan_circles(connection: sqlite3.Connection) -> int:
    row = connection.execute("SELECT COUNT(*) AS count FROM fan_circles").fetchone()
    return int(row["count"])


def get_fan_circle_by_id(connection: sqlite3.Connection, circle_id: int) -> dict[str, Any] | None:
    return fetch_one_dict(
        connection,
        """
        SELECT
            fc.*,
            u.username AS owner_username,
            u.nickname AS owner_nickname,
            u.avatar_url AS owner_avatar_url
        FROM fan_circles fc
        LEFT JOIN users u ON u.id = fc.owner_user_id
        WHERE fc.id = ?
        """,
        (circle_id,),
    )


def assign_owner(connection: sqlite3.Connection, circle_id: int, owner_user_id: int, updated_at: str) -> None:
    connection.execute(
        "UPDATE fan_circles SET owner_user_id = ?, updated_at = ? WHERE id = ?",
        (owner_user_id, updated_at, circle_id),
    )


def increment_post_count(connection: sqlite3.Connection, circle_id: int, delta: int, updated_at: str) -> None:
    connection.execute(
        "UPDATE fan_circles SET post_count = MAX(post_count + ?, 0), updated_at = ? WHERE id = ?",
        (delta, updated_at, circle_id),
    )
