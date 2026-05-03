import sqlite3

from fastapi import APIRouter, Depends, status

from app.api.deps import get_current_user, get_db
from app.api.serializers import serialize_user_profile
from app.core.exceptions import AppError
from app.core.security import create_access_token, hash_password, verify_password
from app.core.utils import utc_now_iso
from app.repositories import users as user_repo
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.schemas.users import UserProfile
from app.services.analytics import record_user_event
from app.services.permissions import ensure_active_user


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _default_avatar_for_user(user_id: int) -> str:
    avatar_index = ((user_id - 1) % 3) + 1
    return f"/static/avatars/avatar-{avatar_index}.svg"


@router.post("/register", response_model=UserProfile, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, connection: sqlite3.Connection = Depends(get_db)) -> dict:
    existing_user = user_repo.get_user_by_username(connection, payload.username)
    if existing_user:
        raise AppError(status_code=409, message="Username already exists.")

    created_at = utc_now_iso()
    user = user_repo.create_user(
        connection,
        username=payload.username,
        nickname=payload.nickname,
        password_hash=hash_password(payload.password),
        avatar_url="/static/avatars/avatar-1.svg",
        bio=payload.bio,
        created_at=created_at,
    )
    avatar_url = _default_avatar_for_user(user["id"])
    user_repo.set_user_avatar(connection, user["id"], avatar_url, created_at)
    record_user_event(
        connection,
        actor_user_id=user["id"],
        target_user_id=user["id"],
        event_type="register",
        metadata={"username": payload.username},
        created_at=created_at,
    )
    refreshed_user = user_repo.get_user_by_id(connection, user["id"])
    return serialize_user_profile(refreshed_user)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, connection: sqlite3.Connection = Depends(get_db)) -> TokenResponse:
    user = user_repo.get_user_by_username(connection, payload.username)
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise AppError(status_code=401, message="Invalid username or password.")
    ensure_active_user(user)
    created_at = utc_now_iso()
    record_user_event(
        connection,
        actor_user_id=user["id"],
        target_user_id=user["id"],
        event_type="login",
        metadata={},
        created_at=created_at,
    )
    token = create_access_token(str(user["id"]), {"username": user["username"], "role": user["role"]})
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserProfile)
def get_me(current_user: dict = Depends(get_current_user)) -> dict:
    return serialize_user_profile(current_user)
