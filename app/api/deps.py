import sqlite3
from collections.abc import Generator

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.exceptions import AppError
from app.core.security import decode_access_token
from app.db.connection import create_connection
from app.repositories import users as user_repo
from app.services.permissions import ensure_active_user


bearer_scheme = HTTPBearer(auto_error=False)


def get_db() -> Generator[sqlite3.Connection, None, None]:
    connection = create_connection()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    connection: sqlite3.Connection = Depends(get_db),
) -> dict | None:
    if credentials is None:
        return None
    payload = decode_access_token(credentials.credentials)
    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise AppError(status_code=401, message="Invalid or expired token.") from exc
    user = user_repo.get_user_by_id(connection, user_id)
    if not user:
        raise AppError(status_code=401, message="User not found.")
    return user


def get_current_user(
    current_user: dict | None = Depends(get_optional_current_user),
) -> dict:
    if current_user is None:
        raise AppError(status_code=401, message="Authentication required.")
    ensure_active_user(current_user)
    return current_user
