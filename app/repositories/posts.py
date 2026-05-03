import sqlite3
from typing import Any

from app.repositories.base import fetch_all_dicts, fetch_one_dict


def create_post(
    connection: sqlite3.Connection,
    *,
    fan_circle_id: int,
    author_user_id: int,
    title: str,
    content: str,
    category: str,
    has_poll: bool,
    created_at: str,
) -> dict[str, Any]:
    cursor = connection.execute(
        """
        INSERT INTO posts (
            fan_circle_id, author_user_id, title, content, category, has_poll, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (fan_circle_id, author_user_id, title, content, category, int(has_poll), created_at, created_at),
    )
    return get_post_by_id(connection, cursor.lastrowid)


def create_post_tags(connection: sqlite3.Connection, post_id: int, tags: list[str]) -> None:
    for tag in tags:
        connection.execute(
            "INSERT INTO post_tags (post_id, tag_name) VALUES (?, ?)",
            (post_id, tag),
        )


def create_poll(
    connection: sqlite3.Connection,
    *,
    post_id: int,
    question: str,
    allow_multiple: bool,
    expires_at: str | None,
    options: list[str],
) -> None:
    cursor = connection.execute(
        """
        INSERT INTO post_polls (post_id, question, allow_multiple, expires_at)
        VALUES (?, ?, ?, ?)
        """,
        (post_id, question, int(allow_multiple), expires_at),
    )
    poll_id = cursor.lastrowid
    for option in options:
        connection.execute(
            "INSERT INTO post_poll_options (poll_id, option_text) VALUES (?, ?)",
            (poll_id, option),
        )


def list_posts_by_circle(
    connection: sqlite3.Connection,
    fan_circle_id: int,
    *,
    limit: int,
    offset: int,
) -> list[dict[str, Any]]:
    posts = fetch_all_dicts(
        connection,
        """
        SELECT
            p.*,
            u.username AS author_username,
            u.nickname AS author_nickname,
            u.avatar_url AS author_avatar_url,
            u.role AS author_role
        FROM posts p
        JOIN users u ON u.id = p.author_user_id
        WHERE p.fan_circle_id = ?
        ORDER BY p.is_pinned DESC, p.created_at DESC, p.id DESC
        LIMIT ? OFFSET ?
        """,
        (fan_circle_id, limit, offset),
    )
    post_ids = [p["id"] for p in posts]
    if post_ids:
        placeholders = ",".join("?" for _ in post_ids)
        tag_rows = connection.execute(
            f"SELECT post_id, tag_name FROM post_tags WHERE post_id IN ({placeholders}) ORDER BY id ASC",
            post_ids,
        ).fetchall()
        tags_by_post: dict[int, list[str]] = {}
        for row in tag_rows:
            tags_by_post.setdefault(int(row["post_id"]), []).append(row["tag_name"])
        for post in posts:
            post["tags"] = tags_by_post.get(int(post["id"]), [])
    else:
        for post in posts:
            post["tags"] = []
    return posts


def count_posts_by_circle(connection: sqlite3.Connection, fan_circle_id: int) -> int:
    row = connection.execute(
        "SELECT COUNT(*) AS count FROM posts WHERE fan_circle_id = ?",
        (fan_circle_id,),
    ).fetchone()
    return int(row["count"])


def get_post_by_id(connection: sqlite3.Connection, post_id: int) -> dict[str, Any] | None:
    post = fetch_one_dict(
        connection,
        """
        SELECT
            p.*,
            u.username AS author_username,
            u.nickname AS author_nickname,
            u.avatar_url AS author_avatar_url,
            u.role AS author_role,
            fc.club_name,
            fc.board_name,
            fc.league_name
        FROM posts p
        JOIN users u ON u.id = p.author_user_id
        JOIN fan_circles fc ON fc.id = p.fan_circle_id
        WHERE p.id = ?
        """,
        (post_id,),
    )
    if post:
        post["tags"] = get_post_tags(connection, post_id)
        post["poll"] = get_poll_by_post_id(connection, post_id)
    return post


def get_post_tags(connection: sqlite3.Connection, post_id: int) -> list[str]:
    rows = connection.execute(
        "SELECT tag_name FROM post_tags WHERE post_id = ? ORDER BY id ASC",
        (post_id,),
    ).fetchall()
    return [row["tag_name"] for row in rows]


def get_poll_by_post_id(connection: sqlite3.Connection, post_id: int) -> dict[str, Any] | None:
    poll = fetch_one_dict(connection, "SELECT * FROM post_polls WHERE post_id = ?", (post_id,))
    if not poll:
        return None
    poll["allow_multiple"] = bool(poll["allow_multiple"])
    poll["options"] = fetch_all_dicts(
        connection,
        "SELECT id, option_text, vote_count FROM post_poll_options WHERE poll_id = ? ORDER BY id ASC",
        (poll["id"],),
    )
    return poll


def create_comment(
    connection: sqlite3.Connection,
    *,
    post_id: int,
    author_user_id: int,
    parent_comment_id: int | None,
    content: str,
    depth: int,
    created_at: str,
) -> dict[str, Any]:
    cursor = connection.execute(
        """
        INSERT INTO comments (
            post_id, author_user_id, parent_comment_id, content, depth, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (post_id, author_user_id, parent_comment_id, content, depth, created_at, created_at),
    )
    return get_comment_by_id(connection, cursor.lastrowid)


def update_comment_path(connection: sqlite3.Connection, comment_id: int, path: str, updated_at: str) -> None:
    connection.execute(
        "UPDATE comments SET path = ?, updated_at = ? WHERE id = ?",
        (path, updated_at, comment_id),
    )


def get_comment_by_id(connection: sqlite3.Connection, comment_id: int) -> dict[str, Any] | None:
    return fetch_one_dict(
        connection,
        """
        SELECT
            c.*,
            u.username AS author_username,
            u.nickname AS author_nickname,
            u.avatar_url AS author_avatar_url
        FROM comments c
        JOIN users u ON u.id = c.author_user_id
        WHERE c.id = ?
        """,
        (comment_id,),
    )


def list_comments_by_post(
    connection: sqlite3.Connection,
    post_id: int,
    *,
    limit: int,
    offset: int,
) -> list[dict[str, Any]]:
    return fetch_all_dicts(
        connection,
        """
        SELECT
            c.*,
            u.username AS author_username,
            u.nickname AS author_nickname,
            u.avatar_url AS author_avatar_url
        FROM comments c
        JOIN users u ON u.id = c.author_user_id
        WHERE c.post_id = ?
        ORDER BY c.path ASC
        LIMIT ? OFFSET ?
        """,
        (post_id, limit, offset),
    )


def count_comments_by_post(connection: sqlite3.Connection, post_id: int) -> int:
    row = connection.execute(
        "SELECT COUNT(*) AS count FROM comments WHERE post_id = ?",
        (post_id,),
    ).fetchone()
    return int(row["count"])


def increment_post_comment_count(connection: sqlite3.Connection, post_id: int, delta: int, updated_at: str) -> None:
    connection.execute(
        "UPDATE posts SET comment_count = MAX(comment_count + ?, 0), updated_at = ? WHERE id = ?",
        (delta, updated_at, post_id),
    )


def set_post_flag(connection: sqlite3.Connection, post_id: int, field_name: str, value: bool, updated_at: str) -> None:
    allowed_fields = {"is_pinned", "is_locked"}
    if field_name not in allowed_fields:
        raise ValueError(f"Unsupported post flag field: {field_name}")
    connection.execute(
        f"UPDATE posts SET {field_name} = ?, updated_at = ? WHERE id = ?",
        (int(value), updated_at, post_id),
    )


def adjust_post_feedback_counts(
    connection: sqlite3.Connection,
    post_id: int,
    *,
    like_delta: int = 0,
    dislike_delta: int = 0,
    updated_at: str,
) -> None:
    connection.execute(
        """
        UPDATE posts
        SET
            like_count = MAX(like_count + ?, 0),
            dislike_count = MAX(dislike_count + ?, 0),
            updated_at = ?
        WHERE id = ?
        """,
        (like_delta, dislike_delta, updated_at, post_id),
    )


def adjust_comment_feedback_counts(
    connection: sqlite3.Connection,
    comment_id: int,
    *,
    like_delta: int = 0,
    dislike_delta: int = 0,
    updated_at: str,
) -> None:
    connection.execute(
        """
        UPDATE comments
        SET
            like_count = MAX(like_count + ?, 0),
            dislike_count = MAX(dislike_count + ?, 0),
            updated_at = ?
        WHERE id = ?
        """,
        (like_delta, dislike_delta, updated_at, comment_id),
    )


def get_latest_post_reaction(connection: sqlite3.Connection, actor_user_id: int, post_id: int) -> str | None:
    row = connection.execute(
        """
        SELECT event_type
        FROM post_events
        WHERE actor_user_id = ? AND post_id = ? AND comment_id IS NULL
          AND event_type IN ('like_post', 'dislike_post')
        ORDER BY id DESC
        LIMIT 1
        """,
        (actor_user_id, post_id),
    ).fetchone()
    return str(row["event_type"]) if row else None


def get_latest_comment_reaction(connection: sqlite3.Connection, actor_user_id: int, comment_id: int) -> str | None:
    row = connection.execute(
        """
        SELECT event_type
        FROM post_events
        WHERE actor_user_id = ? AND comment_id = ?
          AND event_type IN ('like_comment', 'dislike_comment')
        ORDER BY id DESC
        LIMIT 1
        """,
        (actor_user_id, comment_id),
    ).fetchone()
    return str(row["event_type"]) if row else None


def get_poll_by_id(connection: sqlite3.Connection, poll_id: int) -> dict[str, Any] | None:
    poll = fetch_one_dict(connection, "SELECT * FROM post_polls WHERE id = ?", (poll_id,))
    if poll:
        poll["allow_multiple"] = bool(poll["allow_multiple"])
    return poll


def get_poll_option(connection: sqlite3.Connection, option_id: int) -> dict[str, Any] | None:
    return fetch_one_dict(connection, "SELECT * FROM post_poll_options WHERE id = ?", (option_id,))


def get_user_poll_votes(connection: sqlite3.Connection, poll_id: int, user_id: int) -> list[dict[str, Any]]:
    return fetch_all_dicts(
        connection,
        "SELECT * FROM post_poll_votes WHERE poll_id = ? AND user_id = ? ORDER BY id ASC",
        (poll_id, user_id),
    )


def record_poll_vote(connection: sqlite3.Connection, poll_id: int, option_id: int, user_id: int, created_at: str) -> None:
    connection.execute(
        """
        INSERT INTO post_poll_votes (poll_id, option_id, user_id, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (poll_id, option_id, user_id, created_at),
    )
    connection.execute(
        "UPDATE post_poll_options SET vote_count = vote_count + 1 WHERE id = ?",
        (option_id,),
    )


def delete_post(connection: sqlite3.Connection, post_id: int) -> bool:
    row = connection.execute("SELECT id FROM posts WHERE id = ?", (post_id,)).fetchone()
    if not row:
        return False
    connection.execute("DELETE FROM post_events WHERE post_id = ?", (post_id,))
    poll = connection.execute("SELECT id FROM post_polls WHERE post_id = ?", (post_id,)).fetchone()
    if poll:
        connection.execute("DELETE FROM post_poll_votes WHERE poll_id = ?", (poll["id"],))
        connection.execute("DELETE FROM post_poll_options WHERE poll_id = ?", (poll["id"],))
        connection.execute("DELETE FROM post_polls WHERE id = ?", (poll["id"],))
    connection.execute("DELETE FROM post_tags WHERE post_id = ?", (post_id,))
    connection.execute("DELETE FROM comments WHERE post_id = ?", (post_id,))
    connection.execute("DELETE FROM posts WHERE id = ?", (post_id,))
    return True


def delete_comment(connection: sqlite3.Connection, comment_id: int) -> dict[str, Any] | None:
    comment = get_comment_by_id(connection, comment_id)
    if not comment:
        return None
    connection.execute(
        "DELETE FROM comments WHERE path LIKE ?",
        (f"{comment['path']}/%",),
    )
    connection.execute("DELETE FROM comments WHERE id = ?", (comment_id,))
    connection.execute(
        "UPDATE posts SET comment_count = MAX(comment_count - 1, 0), updated_at = ? WHERE id = ?",
        (comment.get("updated_at", ""), comment["post_id"]),
    )
    return comment
