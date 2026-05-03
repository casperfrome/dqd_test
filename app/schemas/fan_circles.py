from datetime import datetime

from app.schemas.common import BaseSchema
from app.schemas.users import UserBrief


class FanCircleBase(BaseSchema):
    id: int
    club_name: str
    board_name: str
    league_name: str
    logo_url: str
    description: str
    post_count: int
    follower_count: int
    created_at: datetime | str
    updated_at: datetime | str


class FanCircleSummary(FanCircleBase):
    owner: UserBrief | None = None


class FanCircleDetail(FanCircleSummary):
    pass
