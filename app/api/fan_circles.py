import sqlite3

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_user, get_db, get_optional_current_user
from app.api.serializers import serialize_fan_circle, serialize_post
from app.core.exceptions import AppError
from app.core.utils import utc_now_iso
from app.repositories import fan_circles as fan_circle_repo
from app.repositories import posts as post_repo
from app.schemas.common import AnalyticsResponse, PaginatedResponse
from app.schemas.fan_circles import FanCircleDetail, FanCircleSummary
from app.schemas.posts import CreatePostRequest, PostDetail, PostSummary
from app.services.analytics import get_recent_fan_circle_events, record_fan_circle_event
from app.services.permissions import ensure_active_user


router = APIRouter(prefix="/api/v1/fan-circles", tags=["fan-circles"])


@router.get("", response_model=PaginatedResponse[FanCircleSummary])
def get_fan_circles(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    connection: sqlite3.Connection = Depends(get_db),
) -> dict:
    offset = (page - 1) * page_size
    items = [serialize_fan_circle(item) for item in fan_circle_repo.list_fan_circles(connection, limit=page_size, offset=offset)]
    return {"items": items, "total": fan_circle_repo.count_fan_circles(connection), "page": page, "page_size": page_size}


@router.get("/{circle_id}", response_model=FanCircleDetail)
def get_fan_circle(
    circle_id: int,
    connection: sqlite3.Connection = Depends(get_db),
    current_user: dict | None = Depends(get_optional_current_user),
) -> dict:
    circle = fan_circle_repo.get_fan_circle_by_id(connection, circle_id)
    if not circle:
        raise AppError(status_code=404, message="Fan circle not found.")
    record_fan_circle_event(
        connection,
        actor_user_id=current_user["id"] if current_user else None,
        fan_circle_id=circle_id,
        event_type="view_circle",
        metadata={},
        created_at=utc_now_iso(),
    )
    return serialize_fan_circle(circle)


@router.get("/{circle_id}/posts", response_model=PaginatedResponse[PostSummary])
def get_circle_posts(
    circle_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    connection: sqlite3.Connection = Depends(get_db),
    current_user: dict | None = Depends(get_optional_current_user),
) -> dict:
    circle = fan_circle_repo.get_fan_circle_by_id(connection, circle_id)
    if not circle:
        raise AppError(status_code=404, message="Fan circle not found.")
    offset = (page - 1) * page_size
    items = [serialize_post(item) for item in post_repo.list_posts_by_circle(connection, circle_id, limit=page_size, offset=offset)]
    record_fan_circle_event(
        connection,
        actor_user_id=current_user["id"] if current_user else None,
        fan_circle_id=circle_id,
        event_type="list_posts",
        metadata={"page": page, "page_size": page_size},
        created_at=utc_now_iso(),
    )
    return {"items": items, "total": post_repo.count_posts_by_circle(connection, circle_id), "page": page, "page_size": page_size}


@router.post("/{circle_id}/posts", response_model=PostDetail, status_code=status.HTTP_201_CREATED)
def create_post(
    circle_id: int,
    payload: CreatePostRequest,
    connection: sqlite3.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    ensure_active_user(current_user)
    circle = fan_circle_repo.get_fan_circle_by_id(connection, circle_id)
    if not circle:
        raise AppError(status_code=404, message="Fan circle not found.")
    created_at = utc_now_iso()
    post = post_repo.create_post(
        connection,
        fan_circle_id=circle_id,
        author_user_id=current_user["id"],
        title=payload.title,
        content=payload.content,
        category=payload.category.value,
        has_poll=payload.poll is not None,
        created_at=created_at,
    )
    if payload.tags:
        post_repo.create_post_tags(connection, post["id"], payload.tags)
    if payload.poll is not None:
        post_repo.create_poll(
            connection,
            post_id=post["id"],
            question=payload.poll.question,
            allow_multiple=payload.poll.allow_multiple,
            expires_at=payload.poll.expires_at.isoformat() if payload.poll.expires_at else None,
            options=payload.poll.options,
        )
    fan_circle_repo.increment_post_count(connection, circle_id, 1, created_at)
    record_fan_circle_event(
        connection,
        actor_user_id=current_user["id"],
        fan_circle_id=circle_id,
        event_type="create_post",
        metadata={"post_id": post["id"]},
        created_at=created_at,
    )
    created_post = post_repo.get_post_by_id(connection, post["id"])
    return serialize_post(created_post)


@router.get("/{circle_id}/analytics", response_model=AnalyticsResponse)
def get_fan_circle_analytics(circle_id: int, connection: sqlite3.Connection = Depends(get_db)) -> dict:
    circle = fan_circle_repo.get_fan_circle_by_id(connection, circle_id)
    if not circle:
        raise AppError(status_code=404, message="Fan circle not found.")
    summary = {
        "post_count": circle["post_count"],
        "follower_count": circle["follower_count"],
        "league_name": circle["league_name"],
    }
    return {"summary": summary, "recent_events": get_recent_fan_circle_events(connection, circle_id)}
