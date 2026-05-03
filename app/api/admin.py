import sqlite3

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, get_db
from app.api.serializers import serialize_post
from app.core.exceptions import AppError
from app.core.utils import utc_now_iso
from app.repositories import fan_circles as fan_circle_repo
from app.repositories import posts as post_repo
from app.repositories import users as user_repo
from app.schemas.common import MessageResponse, OwnerAssignmentRequest, ToggleStateRequest
from app.schemas.posts import PostDetail
from app.services.permissions import ensure_circle_owner_or_admin, ensure_super_admin


router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.post("/fan-circles/{circle_id}/owner", response_model=MessageResponse)
def assign_circle_owner(
    circle_id: int,
    payload: OwnerAssignmentRequest,
    connection: sqlite3.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> MessageResponse:
    ensure_super_admin(current_user)
    circle = fan_circle_repo.get_fan_circle_by_id(connection, circle_id)
    if not circle:
        raise AppError(status_code=404, message="Fan circle not found.")
    owner = user_repo.get_user_by_id(connection, payload.owner_user_id)
    if not owner:
        raise AppError(status_code=404, message="Owner user not found.")
    updated_at = utc_now_iso()
    fan_circle_repo.assign_owner(connection, circle_id, payload.owner_user_id, updated_at)
    if owner["role"] == "normal_user":
        user_repo.set_user_role(connection, owner["id"], "fan_circle_owner", updated_at)
    return MessageResponse(message="Fan circle owner assigned successfully.")


@router.post("/posts/{post_id}/pin", response_model=PostDetail)
def pin_post(
    post_id: int,
    payload: ToggleStateRequest,
    connection: sqlite3.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    post = post_repo.get_post_by_id(connection, post_id)
    if not post:
        raise AppError(status_code=404, message="Post not found.")
    circle = fan_circle_repo.get_fan_circle_by_id(connection, post["fan_circle_id"])
    ensure_circle_owner_or_admin(current_user, circle)
    post_repo.set_post_flag(connection, post_id, "is_pinned", payload.value, utc_now_iso())
    return serialize_post(post_repo.get_post_by_id(connection, post_id))


@router.post("/posts/{post_id}/lock", response_model=PostDetail)
def lock_post(
    post_id: int,
    payload: ToggleStateRequest,
    connection: sqlite3.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    post = post_repo.get_post_by_id(connection, post_id)
    if not post:
        raise AppError(status_code=404, message="Post not found.")
    circle = fan_circle_repo.get_fan_circle_by_id(connection, post["fan_circle_id"])
    ensure_circle_owner_or_admin(current_user, circle)
    post_repo.set_post_flag(connection, post_id, "is_locked", payload.value, utc_now_iso())
    return serialize_post(post_repo.get_post_by_id(connection, post_id))


@router.post("/users/{user_id}/deactivate", response_model=MessageResponse)
def deactivate_user(
    user_id: int,
    connection: sqlite3.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> MessageResponse:
    ensure_super_admin(current_user)
    if not user_repo.get_user_by_id(connection, user_id):
        raise AppError(status_code=404, message="User not found.")
    user_repo.deactivate_user(connection, user_id, utc_now_iso())
    return MessageResponse(message="User deactivated successfully.")
