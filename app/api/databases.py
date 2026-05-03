import sqlite3

from fastapi import APIRouter, Depends, Header
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials

from app.api.deps import bearer_scheme, get_current_user, get_db, get_optional_current_user
from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.core.security import decode_access_token
from app.core.utils import utc_now_iso
from app.db.connection import create_connection
from app.repositories import settings as settings_repo
from app.repositories import users as user_repo
from app.schemas.databases import (
    DatabaseAccessResponse,
    DatabaseAccessUpdateRequest,
    DatabaseAiChatRequest,
    DatabaseAiChatResponse,
    DatabaseAiFactsRebuildResponse,
    DatabaseAiHealthResponse,
    DatabaseAiSessionDetail,
    DatabaseAiSessionSummary,
    DatabaseCatalogResponse,
)
from app.services import database_ai
from app.services.database_catalog import inspect_databases
from app.services.permissions import ensure_active_user, ensure_super_admin


router = APIRouter(prefix="/api/v1/databases", tags=["databases"])


def _ensure_catalog_access(connection: sqlite3.Connection, current_user: dict | None) -> str:
    access_level = settings_repo.get_database_access_level(connection)
    if access_level == "public":
        return access_level
    if current_user is None:
        raise AppError(status_code=401, message="Authentication required.")
    ensure_active_user(current_user)
    if access_level == "super_admin":
        ensure_super_admin(current_user)
    return access_level


@router.get("/access", response_model=DatabaseAccessResponse)
def get_database_access(connection: sqlite3.Connection = Depends(get_db)) -> DatabaseAccessResponse:
    return DatabaseAccessResponse(access_level=settings_repo.get_database_access_level(connection))


@router.put("/access", response_model=DatabaseAccessResponse)
def update_database_access(
    payload: DatabaseAccessUpdateRequest,
    connection: sqlite3.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> DatabaseAccessResponse:
    ensure_super_admin(current_user)
    settings_repo.set_database_access_level(connection, payload.access_level.value, utc_now_iso())
    return DatabaseAccessResponse(access_level=payload.access_level)


@router.get("", response_model=DatabaseCatalogResponse)
def list_databases(
    connection: sqlite3.Connection = Depends(get_db),
    current_user: dict | None = Depends(get_optional_current_user),
) -> dict:
    access_level = _ensure_catalog_access(connection, current_user)
    return {
        "access_level": access_level,
        "databases": inspect_databases(),
    }


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
def chat_with_database_ai(
    payload: DatabaseAiChatRequest,
    current_user: dict | None = Depends(_get_optional_current_user_for_stream),
    settings: Settings = Depends(get_settings),
    x_ai_client_id: str | None = Header(default=None, alias="X-AI-Client-Id"),
) -> StreamingResponse:
    connection = create_connection()
    try:
        _ensure_catalog_access(connection, current_user)
    finally:
        connection.close()
    return StreamingResponse(
        database_ai.stream_database_question_events(
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


@router.post("/ai/chat/complete", response_model=DatabaseAiChatResponse)
def complete_chat_with_database_ai(
    payload: DatabaseAiChatRequest,
    connection: sqlite3.Connection = Depends(get_db),
    current_user: dict | None = Depends(get_optional_current_user),
    settings: Settings = Depends(get_settings),
    x_ai_client_id: str | None = Header(default=None, alias="X-AI-Client-Id"),
) -> dict:
    _ensure_catalog_access(connection, current_user)
    return database_ai.answer_database_question(
        connection,
        settings,
        question=payload.question,
        session_public_id=payload.session_id,
        current_user=current_user,
        client_id=x_ai_client_id,
    )


@router.get("/ai/sessions", response_model=list[DatabaseAiSessionSummary])
def list_database_ai_sessions(
    connection: sqlite3.Connection = Depends(get_db),
    current_user: dict | None = Depends(get_optional_current_user),
    x_ai_client_id: str | None = Header(default=None, alias="X-AI-Client-Id"),
) -> list[dict]:
    _ensure_catalog_access(connection, current_user)
    return database_ai.list_chat_sessions(
        connection,
        current_user=current_user,
        client_id=x_ai_client_id,
    )


@router.get("/ai/sessions/{session_id}", response_model=DatabaseAiSessionDetail)
def get_database_ai_session(
    session_id: str,
    connection: sqlite3.Connection = Depends(get_db),
    current_user: dict | None = Depends(get_optional_current_user),
    x_ai_client_id: str | None = Header(default=None, alias="X-AI-Client-Id"),
) -> dict:
    _ensure_catalog_access(connection, current_user)
    return database_ai.get_chat_session_detail(
        connection,
        session_public_id=session_id,
        current_user=current_user,
        client_id=x_ai_client_id,
    )


@router.post("/ai/facts/rebuild", response_model=DatabaseAiFactsRebuildResponse)
def rebuild_database_ai_facts(
    connection: sqlite3.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    ensure_super_admin(current_user)
    return database_ai.rebuild_database_facts(connection)


@router.get("/ai/health", response_model=DatabaseAiHealthResponse)
def get_database_ai_health(
    connection: sqlite3.Connection = Depends(get_db),
    current_user: dict | None = Depends(get_optional_current_user),
    settings: Settings = Depends(get_settings),
) -> dict:
    _ensure_catalog_access(connection, current_user)
    return database_ai.check_ollama_health(settings)
