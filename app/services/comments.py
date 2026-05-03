import sqlite3

from app.core.exceptions import AppError
from app.repositories import posts as post_repo
from app.repositories import users as user_repo
from app.services.analytics import record_post_event


def _path_segment(comment_id: int) -> str:
    return f"{comment_id:010d}"


def create_comment_with_path(
    connection: sqlite3.Connection,
    *,
    post_id: int,
    author_user_id: int,
    content: str,
    parent_comment_id: int | None,
    created_at: str,
) -> dict:
    post = post_repo.get_post_by_id(connection, post_id)
    if not post:
        raise AppError(status_code=404, message="Post not found.")
    if bool(post["is_locked"]):
        raise AppError(status_code=400, message="This post is locked.")

    parent_comment = None
    depth = 0
    if parent_comment_id is not None:
        parent_comment = post_repo.get_comment_by_id(connection, parent_comment_id)
        if not parent_comment or parent_comment["post_id"] != post_id:
            raise AppError(status_code=404, message="Parent comment not found.")
        depth = int(parent_comment["depth"]) + 1

    comment = post_repo.create_comment(
        connection,
        post_id=post_id,
        author_user_id=author_user_id,
        parent_comment_id=parent_comment_id,
        content=content,
        depth=depth,
        created_at=created_at,
    )
    path = _path_segment(comment["id"]) if not parent_comment else f"{parent_comment['path']}/{_path_segment(comment['id'])}"
    post_repo.update_comment_path(connection, comment["id"], path, created_at)
    post_repo.increment_post_comment_count(connection, post_id, 1, created_at)

    event_type = "reply_comment" if parent_comment_id is not None else "create_comment"
    record_post_event(
        connection,
        actor_user_id=author_user_id,
        post_id=post_id,
        comment_id=comment["id"],
        event_type=event_type,
        metadata={"depth": depth},
        created_at=created_at,
    )

    author = user_repo.get_user_by_id(connection, author_user_id)
    refreshed_comment = post_repo.get_comment_by_id(connection, comment["id"])
    refreshed_comment["author_username"] = author["username"]
    refreshed_comment["author_nickname"] = author["nickname"]
    refreshed_comment["author_avatar_url"] = author["avatar_url"]
    return refreshed_comment
