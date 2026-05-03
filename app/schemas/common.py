from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MessageResponse(BaseSchema):
    message: str


class ToggleStateRequest(BaseSchema):
    value: bool = True


class OwnerAssignmentRequest(BaseSchema):
    owner_user_id: int


class AnalyticsEvent(BaseSchema):
    id: int
    event_type: str
    created_at: datetime | str
    actor_user_id: int | None = None
    target_user_id: int | None = None
    fan_circle_id: int | None = None
    post_id: int | None = None
    comment_id: int | None = None
    metadata: dict


class AnalyticsResponse(BaseSchema):
    summary: dict
    recent_events: list[AnalyticsEvent]


ItemT = TypeVar("ItemT")


class PaginatedResponse(BaseSchema, Generic[ItemT]):
    items: list[ItemT]
    total: int
    page: int
    page_size: int
