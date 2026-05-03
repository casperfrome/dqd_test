import sqlite3

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials

from app.api.deps import bearer_scheme, get_current_user, get_db, get_optional_current_user
from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.core.security import decode_access_token
from app.db.connection import create_connection
from app.repositories import settings as settings_repo
from app.repositories import users as user_repo
from app.schemas.code import (
    CodeAiChatRequest,
    CodeAiChatResponse,
    CodeAiFactsRebuildResponse,
    CodeAiHealthResponse,
    CodeAiSessionDetail,
    CodeAiSessionSummary,
    CodeCatalogResponse,
    CodeFileResponse,
)
from app.services import code_ai
from app.services.code_catalog import inspect_code_catalog, read_code_file
from app.services.permissions import ensure_active_user, ensure_super_admin


router = APIRouter(prefix="/api/v1/code", tags=["code"])


def _ensure_code_access(connection: sqlite3.Connection, current_user: dict | None) -> str:
    access_level = settings_repo.get_database_access_level(connection)
    if access_level == "public":
        return access_level
    if current_user is None:
        raise AppError(status_code=401, message="Authentication required.")
    ensure_active_user(current_user)
    if access_level == "super_admin":
        ensure_super_admin(current_user)
    return access_level


@router.get("/catalog", response_model=CodeCatalogResponse)
def get_code_catalog(
    connection: sqlite3.Connection = Depends(get_db),
    current_user: dict | None = Depends(get_optional_current_user),
) -> dict:
    access_level = _ensure_code_access(connection, current_user)
    return {
        "access_level": access_level,
        **inspect_code_catalog(),
    }


@router.get("/file", response_model=CodeFileResponse)
def get_code_file(
    path: str = Query(min_length=1),
    connection: sqlite3.Connection = Depends(get_db),
    current_user: dict | None = Depends(get_optional_current_user),
) -> dict:
    _ensure_code_access(connection, current_user)
    return read_code_file(path)


def _get_optional_current_user_for_stream(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict | None:
    if credentials is None:
        return None
    payload = decode_access_token(credentials.credentials)
    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise AppError(status_code=401, message="Invalid or expired token.") from exc
    connection = create_connection()
    try:
        user = user_repo.get_user_by_id(connection, user_id)
        if not user:
            raise AppError(status_code=401, message="User not found.")
        return user
    finally:
        connection.close()


@router.post("/ai/chat")
def chat_with_code_ai(
    payload: CodeAiChatRequest,
    current_user: dict | None = Depends(_get_optional_current_user_for_stream),
    settings: Settings = Depends(get_settings),
    x_ai_client_id: str | None = Header(default=None, alias="X-AI-Client-Id"),
) -> StreamingResponse:
    connection = create_connection()
    try:
        _ensure_code_access(connection, current_user)
    finally:
        connection.close()
    return StreamingResponse(
        code_ai.stream_code_question_events(
            settings,
            question=payload.question,
            session_public_id=payload.session_id,
            current_user=current_user,
            client_id=x_ai_client_id,
            thinking_enabled=payload.thinking_enabled,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/ai/chat/complete", response_model=CodeAiChatResponse)
def complete_chat_with_code_ai(
    payload: CodeAiChatRequest,
    connection: sqlite3.Connection = Depends(get_db),
    current_user: dict | None = Depends(get_optional_current_user),
    settings: Settings = Depends(get_settings),
    x_ai_client_id: str | None = Header(default=None, alias="X-AI-Client-Id"),
) -> dict:
    _ensure_code_access(connection, current_user)
    return code_ai.answer_code_question(
        connection,
        settings,
        question=payload.question,
        session_public_id=payload.session_id,
        current_user=current_user,
        client_id=x_ai_client_id,
    )


@router.get("/ai/sessions", response_model=list[CodeAiSessionSummary])
def list_code_ai_sessions(
    connection: sqlite3.Connection = Depends(get_db),
    current_user: dict | None = Depends(get_optional_current_user),
    x_ai_client_id: str | None = Header(default=None, alias="X-AI-Client-Id"),
) -> list[dict]:
    _ensure_code_access(connection, current_user)
    return code_ai.list_chat_sessions(
        connection,
        current_user=current_user,
        client_id=x_ai_client_id,
    )


@router.get("/ai/sessions/{session_id}", response_model=CodeAiSessionDetail)
def get_code_ai_session(
    session_id: str,
    connection: sqlite3.Connection = Depends(get_db),
    current_user: dict | None = Depends(get_optional_current_user),
    x_ai_client_id: str | None = Header(default=None, alias="X-AI-Client-Id"),
) -> dict:
    _ensure_code_access(connection, current_user)
    return code_ai.get_chat_session_detail(
        connection,
        session_public_id=session_id,
        current_user=current_user,
        client_id=x_ai_client_id,
    )


@router.post("/ai/facts/rebuild", response_model=CodeAiFactsRebuildResponse)
def rebuild_code_ai_facts(
    connection: sqlite3.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    ensure_super_admin(current_user)
    return code_ai.rebuild_code_facts(connection)


@router.get("/ai/health", response_model=CodeAiHealthResponse)
def get_code_ai_health(
    connection: sqlite3.Connection = Depends(get_db),
    current_user: dict | None = Depends(get_optional_current_user),
    settings: Settings = Depends(get_settings),
) -> dict:
    _ensure_code_access(connection, current_user)
    return code_ai.check_ollama_health(settings)
