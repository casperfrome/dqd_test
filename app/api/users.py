import sqlite3

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user, get_db, get_optional_current_user
from app.api.serializers import serialize_user_brief, serialize_user_profile
from app.core.exceptions import AppError
from app.core.utils import utc_now_iso
from app.repositories import users as user_repo
from app.schemas.common import AnalyticsResponse, MessageResponse, PaginatedResponse
from app.schemas.users import UserBrief, UserProfile
from app.services.analytics import get_recent_user_events, record_user_event
from app.services.permissions import ensure_active_user


router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.get("/search", response_model=list[UserBrief])
def search_users(
    q: str = Query(min_length=1, max_length=64),
    connection: sqlite3.Connection = Depends(get_db),
) -> list[dict]:
    users = user_repo.search_users(connection, q, limit=10)
    return [serialize_user_brief(u) for u in users]


@router.get("/{user_id}", response_model=UserProfile)
def get_user_profile(
    user_id: int,
    connection: sqlite3.Connection = Depends(get_db),
    current_user: dict | None = Depends(get_optional_current_user),
) -> dict:
    user = user_repo.get_user_by_id(connection, user_id)
    if not user:
        raise AppError(status_code=404, message="User not found.")
    if current_user is not None:
        record_user_event(
            connection,
            actor_user_id=current_user["id"],
            target_user_id=user_id,
            event_type="view_profile",
            metadata={},
            created_at=utc_now_iso(),
        )
    return serialize_user_profile(user)


@router.post("/{user_id}/follow", response_model=MessageResponse)
def follow_user(
    user_id: int,
    connection: sqlite3.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> MessageResponse:
    ensure_active_user(current_user)
    target_user = user_repo.get_user_by_id(connection, user_id)
    if not target_user:
        raise AppError(status_code=404, message="User not found.")
    if current_user["id"] == user_id:
        raise AppError(status_code=400, message="You cannot follow yourself.")
    try:
        user_repo.follow_user(connection, current_user["id"], user_id, utc_now_iso())
    except sqlite3.IntegrityError as exc:
        raise AppError(status_code=409, message="Already following this user.") from exc
    record_user_event(
        connection,
        actor_user_id=current_user["id"],
        target_user_id=user_id,
        event_type="follow",
        metadata={},
        created_at=utc_now_iso(),
    )
    return MessageResponse(message="Followed user successfully.")


@router.delete("/{user_id}/follow", response_model=MessageResponse)
def unfollow_user(
    user_id: int,
    connection: sqlite3.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> MessageResponse:
    ensure_active_user(current_user)
    if not user_repo.get_user_by_id(connection, user_id):
        raise AppError(status_code=404, message="User not found.")
    did_unfollow = user_repo.unfollow_user(connection, current_user["id"], user_id, utc_now_iso())
    if not did_unfollow:
        raise AppError(status_code=404, message="Follow relationship not found.")
    record_user_event(
        connection,
        actor_user_id=current_user["id"],
        target_user_id=user_id,
        event_type="unfollow",
        metadata={},
        created_at=utc_now_iso(),
    )
    return MessageResponse(message="Unfollowed user successfully.")


@router.get("/{user_id}/followers", response_model=PaginatedResponse[UserBrief])
def get_followers(
    user_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    connection: sqlite3.Connection = Depends(get_db),
) -> dict:
    if not user_repo.get_user_by_id(connection, user_id):
        raise AppError(status_code=404, message="User not found.")
    offset = (page - 1) * page_size
    items = [serialize_user_brief(item) for item in user_repo.list_followers(connection, user_id, limit=page_size, offset=offset)]
    return {
        "items": items,
        "total": user_repo.count_followers(connection, user_id),
        "page": page,
        "page_size": page_size,
    }


@router.get("/{user_id}/following", response_model=PaginatedResponse[UserBrief])
def get_following(
    user_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    connection: sqlite3.Connection = Depends(get_db),
) -> dict:
    if not user_repo.get_user_by_id(connection, user_id):
        raise AppError(status_code=404, message="User not found.")
    offset = (page - 1) * page_size
    items = [serialize_user_brief(item) for item in user_repo.list_following(connection, user_id, limit=page_size, offset=offset)]
    return {
        "items": items,
        "total": user_repo.count_following(connection, user_id),
        "page": page,
        "page_size": page_size,
    }


@router.get("/{user_id}/analytics", response_model=AnalyticsResponse)
def get_user_analytics(
    user_id: int,
    connection: sqlite3.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    user = user_repo.get_user_by_id(connection, user_id)
    if not user:
        raise AppError(status_code=404, message="User not found.")
    if current_user["id"] != user_id and current_user["role"] != "super_admin":
        raise AppError(status_code=403, message="You cannot view this user's analytics.")
    summary = {
        "followers_count": user["followers_count"],
        "following_count": user["following_count"],
        "total_likes_received": user["total_likes_received"],
        "total_dislikes_received": user["total_dislikes_received"],
        "is_active": bool(user["is_active"]),
    }
    return {
        "summary": summary,
        "recent_events": get_recent_user_events(connection, user_id),
    }
