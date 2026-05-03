from typing import Literal

from pydantic import Field

from app.schemas.common import BaseSchema
from app.schemas.databases import DatabaseAccessLevel


class CodeFileInfo(BaseSchema):
    path: str
    name: str
    extension: str
    language: str
    size_bytes: int
    line_count: int


class CodeTreeNode(BaseSchema):
    name: str
    path: str
    type: Literal["directory", "file"]
    children: list["CodeTreeNode"]
    file: CodeFileInfo | None = None


class CodeCatalogResponse(BaseSchema):
    access_level: DatabaseAccessLevel
    files: list[CodeFileInfo]
    tree: list[CodeTreeNode]
    file_count: int
    total_size_bytes: int


class CodeFileResponse(CodeFileInfo):
    content: str


class CodeAiStopRequest(BaseSchema):
    stream_id: str = Field(min_length=1)


class CodeAiChatRequest(BaseSchema):
    question: str = Field(min_length=1, max_length=2000)
    session_id: str | None = None
    thinking_enabled: bool = False


class CodeAiSource(BaseSchema):
    fact_id: int
    source_file_path: str
    language: str
    start_line: int
    end_line: int
    title: str
    snippet: str
    score: float | None = None


class CodeAiChatResponse(BaseSchema):
    session_id: str
    user_message_id: int
    assistant_message_id: int
    answer: str
    sources: list[CodeAiSource]


class CodeAiSessionSummary(BaseSchema):
    id: str
    title: str
    created_at: str
    updated_at: str


class CodeAiMessage(BaseSchema):
    id: int
    role: str
    content: str
    thinking_enabled: bool
    thinking_content: str
    input_token_count: int
    output_token_count: int
    is_stopped: bool = False
    retrieved_fact_ids: list[int]
    sources: list[CodeAiSource]
    created_at: str


class CodeAiSessionDetail(CodeAiSessionSummary):
    messages: list[CodeAiMessage]


class CodeAiFactsRebuildResponse(BaseSchema):
    fact_count: int
    rebuilt_at: str


class CodeAiHealthResponse(BaseSchema):
    ok: bool
    model: str
    base_url: str
    error: str | None = None
    available_models: list[str]
