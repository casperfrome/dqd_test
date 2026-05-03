from datetime import datetime
from enum import Enum

from app.schemas.common import BaseSchema


class UserRole(str, Enum):
    super_admin = "super_admin"
    fan_circle_owner = "fan_circle_owner"
    normal_user = "normal_user"


class UserBrief(BaseSchema):
    id: int
    username: str
    nickname: str
    role: UserRole
    avatar_url: str


class UserProfile(BaseSchema):
    id: int
    username: str
    nickname: str
    role: UserRole
    avatar_url: str
    bio: str
    following_count: int
    followers_count: int
    total_likes_received: int
    total_dislikes_received: int
    is_active: bool
    created_at: datetime | str
    updated_at: datetime | str
