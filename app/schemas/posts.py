from datetime import datetime
from enum import Enum

from pydantic import Field, field_validator

from app.schemas.common import BaseSchema
from app.schemas.users import UserBrief


class PostCategory(str, Enum):
    discussion = "discussion"
    news = "news"
    transfer = "transfer"
    match = "match"
    off_topic = "off_topic"


class PollCreateRequest(BaseSchema):
    question: str = Field(min_length=1, max_length=200)
    allow_multiple: bool = False
    expires_at: datetime | None = None
    options: list[str] = Field(min_length=2, max_length=10)

    @field_validator("options")
    @classmethod
    def validate_options(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item.strip()]
        if len(cleaned) < 2:
            raise ValueError("Poll requires at least two non-empty options.")
        return cleaned


class CreatePostRequest(BaseSchema):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)
    category: PostCategory
    tags: list[str] = Field(default_factory=list, max_length=10)
    poll: PollCreateRequest | None = None

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        for tag in value:
            normalized = tag.strip()
            if normalized and normalized not in cleaned:
                cleaned.append(normalized)
        return cleaned


class PollOptionResponse(BaseSchema):
    id: int
    option_text: str
    vote_count: int


class PollResponse(BaseSchema):
    id: int
    question: str
    allow_multiple: bool
    expires_at: datetime | str | None = None
    options: list[PollOptionResponse]


class PostSummary(BaseSchema):
    id: int
    fan_circle_id: int
    title: str
    content: str
    category: PostCategory
    tags: list[str]
    like_count: int
    dislike_count: int
    comment_count: int
    has_poll: bool
    is_pinned: bool
    is_locked: bool
    created_at: datetime | str
    updated_at: datetime | str
    author: UserBrief


class PostDetail(PostSummary):
    club_name: str
    board_name: str
    league_name: str
    poll: PollResponse | None = None


class CreateCommentRequest(BaseSchema):
    content: str = Field(min_length=1)
    parent_comment_id: int | None = None


class CommentAuthor(BaseSchema):
    id: int
    username: str
    nickname: str
    avatar_url: str


class CommentResponse(BaseSchema):
    id: int
    post_id: int
    parent_comment_id: int | None = None
    depth: int
    path: str
    content: str
    like_count: int
    dislike_count: int
    created_at: datetime | str
    updated_at: datetime | str
    author: CommentAuthor


class PollVoteRequest(BaseSchema):
    option_ids: list[int] = Field(min_length=1)
