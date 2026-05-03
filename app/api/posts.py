import sqlite3
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_user, get_db, get_optional_current_user
from app.api.serializers import serialize_comment, serialize_post
from app.core.exceptions import AppError
from app.core.utils import utc_now_iso
from app.repositories import fan_circles as fan_circle_repo
from app.repositories import posts as post_repo
from app.repositories import users as user_repo
from app.schemas.common import AnalyticsResponse, MessageResponse, PaginatedResponse
from app.schemas.posts import CommentResponse, CreateCommentRequest, PollVoteRequest, PostDetail
from app.services.analytics import get_recent_post_events, record_post_event
from app.services.comments import create_comment_with_path
from app.services.permissions import ensure_active_user


router = APIRouter(prefix="/api/v1", tags=["posts"])


def _get_post_or_404(connection: sqlite3.Connection, post_id: int) -> dict:
    post = post_repo.get_post_by_id(connection, post_id)
    if not post:
        raise AppError(status_code=404, message="Post not found.")
    return post


def _apply_post_reaction(
    connection: sqlite3.Connection,
    *,
    post: dict,
    actor_user_id: int,
    desired_event: str,
) -> dict:
    now = utc_now_iso()
    latest_event = post_repo.get_latest_post_reaction(connection, actor_user_id, post["id"])
    like_delta = 0
    dislike_delta = 0
    user_like_delta = 0
    user_dislike_delta = 0
    if latest_event == desired_event:
        raise AppError(status_code=409, message="Duplicate reaction is not allowed.")
    if desired_event == "like_post":
        like_delta = 1
        user_like_delta = 1
        if latest_event == "dislike_post":
            dislike_delta = -1
            user_dislike_delta = -1
    else:
        dislike_delta = 1
        user_dislike_delta = 1
        if latest_event == "like_post":
            like_delta = -1
            user_like_delta = -1
    post_repo.adjust_post_feedback_counts(connection, post["id"], like_delta=like_delta, dislike_delta=dislike_delta, updated_at=now)
    user_repo.adjust_user_feedback_counts(
        connection,
        post["author_user_id"],
        like_delta=user_like_delta,
        dislike_delta=user_dislike_delta,
        updated_at=now,
    )
    record_post_event(
        connection,
        actor_user_id=actor_user_id,
        post_id=post["id"],
        comment_id=None,
        event_type=desired_event,
        metadata={},
        created_at=now,
    )
    return _get_post_or_404(connection, post["id"])


def _apply_comment_reaction(
    connection: sqlite3.Connection,
    *,
    comment: dict,
    actor_user_id: int,
    desired_event: str,
) -> dict:
    now = utc_now_iso()
    latest_event = post_repo.get_latest_comment_reaction(connection, actor_user_id, comment["id"])
    like_delta = 0
    dislike_delta = 0
    user_like_delta = 0
    user_dislike_delta = 0
    if latest_event == desired_event:
        raise AppError(status_code=409, message="Duplicate reaction is not allowed.")
    if desired_event == "like_comment":
        like_delta = 1
        user_like_delta = 1
        if latest_event == "dislike_comment":
            dislike_delta = -1
            user_dislike_delta = -1
    else:
        dislike_delta = 1
        user_dislike_delta = 1
        if latest_event == "like_comment":
            like_delta = -1
            user_like_delta = -1
    post_repo.adjust_comment_feedback_counts(connection, comment["id"], like_delta=like_delta, dislike_delta=dislike_delta, updated_at=now)
    user_repo.adjust_user_feedback_counts(
        connection,
        comment["author_user_id"],
        like_delta=user_like_delta,
        dislike_delta=user_dislike_delta,
        updated_at=now,
    )
    record_post_event(
        connection,
        actor_user_id=actor_user_id,
        post_id=comment["post_id"],
        comment_id=comment["id"],
        event_type=desired_event,
        metadata={},
        created_at=now,
    )
    return post_repo.get_comment_by_id(connection, comment["id"])


@router.get("/posts/{post_id}", response_model=PostDetail)
def get_post(
    post_id: int,
    connection: sqlite3.Connection = Depends(get_db),
    current_user: dict | None = Depends(get_optional_current_user),
) -> dict:
    post = _get_post_or_404(connection, post_id)
    record_post_event(
        connection,
        actor_user_id=current_user["id"] if current_user else None,
        post_id=post_id,
        comment_id=None,
        event_type="view_post",
        metadata={},
        created_at=utc_now_iso(),
    )
    return serialize_post(post)


@router.post("/posts/{post_id}/like", response_model=PostDetail)
def like_post(
    post_id: int,
    connection: sqlite3.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    ensure_active_user(current_user)
    post = _get_post_or_404(connection, post_id)
    return serialize_post(_apply_post_reaction(connection, post=post, actor_user_id=current_user["id"], desired_event="like_post"))


@router.post("/posts/{post_id}/dislike", response_model=PostDetail)
def dislike_post(
    post_id: int,
    connection: sqlite3.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    ensure_active_user(current_user)
    post = _get_post_or_404(connection, post_id)
    return serialize_post(_apply_post_reaction(connection, post=post, actor_user_id=current_user["id"], desired_event="dislike_post"))


@router.post("/posts/{post_id}/vote", response_model=PostDetail)
def vote_post_poll(
    post_id: int,
    payload: PollVoteRequest,
    connection: sqlite3.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    ensure_active_user(current_user)
    post = _get_post_or_404(connection, post_id)
    poll = post_repo.get_poll_by_post_id(connection, post_id)
    if not poll:
        raise AppError(status_code=404, message="Poll not found.")
    unique_option_ids = list(dict.fromkeys(payload.option_ids))
    if not poll["allow_multiple"] and len(unique_option_ids) > 1:
        raise AppError(status_code=400, message="This poll allows only one option.")
    if poll["expires_at"]:
        expires_at = datetime.fromisoformat(poll["expires_at"])
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            raise AppError(status_code=400, message="This poll has expired.")
    existing_votes = post_repo.get_user_poll_votes(connection, poll["id"], current_user["id"])
    if existing_votes and not poll["allow_multiple"]:
        raise AppError(status_code=409, message="You have already voted in this poll.")
    existing_option_ids = {vote["option_id"] for vote in existing_votes}
    now = utc_now_iso()
    for option_id in unique_option_ids:
        if option_id in existing_option_ids:
            raise AppError(status_code=409, message="Duplicate poll vote is not allowed.")
        option = post_repo.get_poll_option(connection, option_id)
        if not option or option["poll_id"] != poll["id"]:
            raise AppError(status_code=404, message="Poll option not found.")
        post_repo.record_poll_vote(connection, poll["id"], option_id, current_user["id"], now)
    record_post_event(
        connection,
        actor_user_id=current_user["id"],
        post_id=post_id,
        comment_id=None,
        event_type="vote_poll",
        metadata={"option_ids": unique_option_ids},
        created_at=now,
    )
    return serialize_post(_get_post_or_404(connection, post_id))


@router.post("/posts/{post_id}/comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
def create_comment(
    post_id: int,
    payload: CreateCommentRequest,
    connection: sqlite3.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    ensure_active_user(current_user)
    comment = create_comment_with_path(
        connection,
        post_id=post_id,
        author_user_id=current_user["id"],
        content=payload.content,
        parent_comment_id=payload.parent_comment_id,
        created_at=utc_now_iso(),
    )
    return serialize_comment(comment)


@router.get("/posts/{post_id}/comments", response_model=PaginatedResponse[CommentResponse])
def list_comments(
    post_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    connection: sqlite3.Connection = Depends(get_db),
) -> dict:
    _get_post_or_404(connection, post_id)
    offset = (page - 1) * page_size
    items = [serialize_comment(item) for item in post_repo.list_comments_by_post(connection, post_id, limit=page_size, offset=offset)]
    return {"items": items, "total": post_repo.count_comments_by_post(connection, post_id), "page": page, "page_size": page_size}


@router.post("/comments/{comment_id}/reply", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
def reply_comment(
    comment_id: int,
    payload: CreateCommentRequest,
    connection: sqlite3.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    ensure_active_user(current_user)
    parent_comment = post_repo.get_comment_by_id(connection, comment_id)
    if not parent_comment:
        raise AppError(status_code=404, message="Comment not found.")
    comment = create_comment_with_path(
        connection,
        post_id=parent_comment["post_id"],
        author_user_id=current_user["id"],
        content=payload.content,
        parent_comment_id=comment_id,
        created_at=utc_now_iso(),
    )
    return serialize_comment(comment)


@router.post("/comments/{comment_id}/like", response_model=CommentResponse)
def like_comment(
    comment_id: int,
    connection: sqlite3.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    ensure_active_user(current_user)
    comment = post_repo.get_comment_by_id(connection, comment_id)
    if not comment:
        raise AppError(status_code=404, message="Comment not found.")
    return serialize_comment(_apply_comment_reaction(connection, comment=comment, actor_user_id=current_user["id"], desired_event="like_comment"))


@router.post("/comments/{comment_id}/dislike", response_model=CommentResponse)
def dislike_comment(
    comment_id: int,
    connection: sqlite3.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    ensure_active_user(current_user)
    comment = post_repo.get_comment_by_id(connection, comment_id)
    if not comment:
        raise AppError(status_code=404, message="Comment not found.")
    return serialize_comment(_apply_comment_reaction(connection, comment=comment, actor_user_id=current_user["id"], desired_event="dislike_comment"))


@router.get("/posts/{post_id}/analytics", response_model=AnalyticsResponse)
def get_post_analytics(post_id: int, connection: sqlite3.Connection = Depends(get_db)) -> dict:
    post = _get_post_or_404(connection, post_id)
    summary = {
        "like_count": post["like_count"],
        "dislike_count": post["dislike_count"],
        "comment_count": post["comment_count"],
        "has_poll": bool(post["has_poll"]),
        "is_pinned": bool(post["is_pinned"]),
        "is_locked": bool(post["is_locked"]),
    }
    return {"summary": summary, "recent_events": get_recent_post_events(connection, post_id)}
