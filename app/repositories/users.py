import sqlite3
from typing import Any

from app.repositories.base import fetch_all_dicts, fetch_one_dict


def create_user(
    connection: sqlite3.Connection,
    *,
    username: str,
    nickname: str,
    password_hash: str,
    avatar_url: str,
    role: str = "normal_user",
    bio: str = "",
    created_at: str,
) -> dict[str, Any]:
    cursor = connection.execute(
        """
        INSERT INTO users (
            username, nickname, password_hash, role, avatar_url, bio, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (username, nickname, password_hash, role, avatar_url, bio, created_at, created_at),
    )
    return get_user_by_id(connection, cursor.lastrowid)


def get_user_by_id(connection: sqlite3.Connection, user_id: int) -> dict[str, Any] | None:
    return fetch_one_dict(connection, "SELECT * FROM users WHERE id = ?", (user_id,))


def get_user_by_username(connection: sqlite3.Connection, username: str) -> dict[str, Any] | None:
    return fetch_one_dict(connection, "SELECT * FROM users WHERE username = ?", (username,))


def list_followers(connection: sqlite3.Connection, user_id: int, *, limit: int, offset: int) -> list[dict[str, Any]]:
    return fetch_all_dicts(
        connection,
        """
        SELECT u.*
        FROM user_follows uf
        JOIN users u ON u.id = uf.follower_user_id
        WHERE uf.followed_user_id = ?
        ORDER BY uf.created_at DESC
        LIMIT ? OFFSET ?
        """,
        (user_id, limit, offset),
    )


def count_followers(connection: sqlite3.Connection, user_id: int) -> int:
    row = connection.execute(
        "SELECT COUNT(*) AS count FROM user_follows WHERE followed_user_id = ?",
        (user_id,),
    ).fetchone()
    return int(row["count"])


def list_following(connection: sqlite3.Connection, user_id: int, *, limit: int, offset: int) -> list[dict[str, Any]]:
    return fetch_all_dicts(
        connection,
        """
        SELECT u.*
        FROM user_follows uf
        JOIN users u ON u.id = uf.followed_user_id
        WHERE uf.follower_user_id = ?
        ORDER BY uf.created_at DESC
        LIMIT ? OFFSET ?
        """,
        (user_id, limit, offset),
    )


def count_following(connection: sqlite3.Connection, user_id: int) -> int:
    row = connection.execute(
        "SELECT COUNT(*) AS count FROM user_follows WHERE follower_user_id = ?",
        (user_id,),
    ).fetchone()
    return int(row["count"])


def follow_user(connection: sqlite3.Connection, follower_user_id: int, followed_user_id: int, created_at: str) -> None:
    connection.execute(
        """
        INSERT INTO user_follows (follower_user_id, followed_user_id, created_at)
        VALUES (?, ?, ?)
        """,
        (follower_user_id, followed_user_id, created_at),
    )
    connection.execute(
        "UPDATE users SET following_count = following_count + 1, updated_at = ? WHERE id = ?",
        (created_at, follower_user_id),
    )
    connection.execute(
        "UPDATE users SET followers_count = followers_count + 1, updated_at = ? WHERE id = ?",
        (created_at, followed_user_id),
    )


def unfollow_user(connection: sqlite3.Connection, follower_user_id: int, followed_user_id: int, updated_at: str) -> bool:
    cursor = connection.execute(
        "DELETE FROM user_follows WHERE follower_user_id = ? AND followed_user_id = ?",
        (follower_user_id, followed_user_id),
    )
    if cursor.rowcount:
        connection.execute(
            "UPDATE users SET following_count = CASE WHEN following_count > 0 THEN following_count - 1 ELSE 0 END, updated_at = ? WHERE id = ?",
            (updated_at, follower_user_id),
        )
        connection.execute(
            "UPDATE users SET followers_count = CASE WHEN followers_count > 0 THEN followers_count - 1 ELSE 0 END, updated_at = ? WHERE id = ?",
            (updated_at, followed_user_id),
        )
        return True
    return False


def set_user_role(connection: sqlite3.Connection, user_id: int, role: str, updated_at: str) -> None:
    connection.execute(
        "UPDATE users SET role = ?, updated_at = ? WHERE id = ?",
        (role, updated_at, user_id),
    )


def set_user_avatar(connection: sqlite3.Connection, user_id: int, avatar_url: str, updated_at: str) -> None:
    connection.execute(
        "UPDATE users SET avatar_url = ?, updated_at = ? WHERE id = ?",
        (avatar_url, updated_at, user_id),
    )


def deactivate_user(connection: sqlite3.Connection, user_id: int, updated_at: str) -> None:
    connection.execute(
        "UPDATE users SET is_active = 0, updated_at = ? WHERE id = ?",
        (updated_at, user_id),
    )


def adjust_user_feedback_counts(
    connection: sqlite3.Connection,
    user_id: int,
    *,
    like_delta: int = 0,
    dislike_delta: int = 0,
    updated_at: str,
) -> None:
    connection.execute(
        """
        UPDATE users
        SET
            total_likes_received = MAX(total_likes_received + ?, 0),
            total_dislikes_received = MAX(total_dislikes_received + ?, 0),
            updated_at = ?
        WHERE id = ?
        """,
        (like_delta, dislike_delta, updated_at, user_id),
    )
