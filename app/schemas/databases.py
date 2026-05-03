from enum import Enum
from typing import Any

from pydantic import Field

from app.schemas.common import BaseSchema


class DatabaseAccessLevel(str, Enum):
    public = "public"
    authenticated = "authenticated"
    super_admin = "super_admin"


class DatabaseAccessResponse(BaseSchema):
    access_level: DatabaseAccessLevel


class DatabaseAccessUpdateRequest(BaseSchema):
    access_level: DatabaseAccessLevel


class DatabaseColumn(BaseSchema):
    name: str
    comment: str
    type: str
    not_null: bool
    default_value: str | None = None
    primary_key: bool
    primary_key_position: int


class DatabaseForeignKey(BaseSchema):
    id: int
    sequence: int
    from_column: str
    to_table: str
    to_column: str | None = None
    on_update: str
    on_delete: str


class DatabaseIndex(BaseSchema):
    name: str
    unique: bool
    origin: str
    columns: list[str]


class DatabaseTable(BaseSchema):
    name: str
    comment: str
    row_count: int
    columns: list[DatabaseColumn]
    foreign_keys: list[DatabaseForeignKey]
    indexes: list[DatabaseIndex]
    sample_rows: list[dict[str, Any]]


class DatabaseInfo(BaseSchema):
    name: str
    path: str
    size_bytes: int
    table_count: int
    status: str
    error: str | None = None
    tables: list[DatabaseTable]


class DatabaseCatalogResponse(BaseSchema):
    access_level: DatabaseAccessLevel
    databases: list[DatabaseInfo]


class DatabaseAiChatRequest(BaseSchema):
    question: str = Field(min_length=1, max_length=2000)
    session_id: str | None = None
    thinking_enabled: bool = False


class DatabaseAiSource(BaseSchema):
    fact_id: int
    fact_type: str
    title: str
    source_database_path: str
    source_table_name: str | None = None
    source_column_name: str | None = None
    snippet: str
    score: float | None = None


class DatabaseAiStopRequest(BaseSchema):
    stream_id: str = Field(min_length=1)


class DatabaseAiChatResponse(BaseSchema):
    session_id: str
    user_message_id: int
    assistant_message_id: int
    answer: str
    sources: list[DatabaseAiSource]


class DatabaseAiSessionSummary(BaseSchema):
    id: str
    title: str
    created_at: str
    updated_at: str


class DatabaseAiMessage(BaseSchema):
    id: int
    role: str
    content: str
    thinking_enabled: bool
    thinking_content: str
    input_token_count: int
    output_token_count: int
    is_stopped: bool = False
    retrieved_fact_ids: list[int]
    sources: list[DatabaseAiSource]
    created_at: str


class DatabaseAiSessionDetail(DatabaseAiSessionSummary):
    messages: list[DatabaseAiMessage]


class DatabaseAiFactsRebuildResponse(BaseSchema):
    fact_count: int
    rebuilt_at: str


class DatabaseAiHealthResponse(BaseSchema):
    ok: bool
    model: str
    base_url: str
    error: str | None = None
    available_models: list[str]
