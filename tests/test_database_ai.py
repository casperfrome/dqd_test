import json
import sqlite3

from app.core.utils import utc_now_iso
from app.services.ollama_client import OllamaError


def _parse_sse_events(text: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    for block in text.strip().split("\n\n"):
        event_name = ""
        data = "{}"
        for line in block.splitlines():
            if line.startswith("event: "):
                event_name = line.removeprefix("event: ").strip()
            if line.startswith("data: "):
                data = line.removeprefix("data: ")
        if event_name:
            events.append((event_name, json.loads(data)))
    return events


def _promote_to_super_admin(user_id: int) -> None:
    from app.db.connection import create_connection

    connection = create_connection()
    try:
        connection.execute(
            "UPDATE users SET role = 'super_admin', updated_at = ? WHERE id = ?",
            (utc_now_iso(), user_id),
        )
        connection.commit()
    finally:
        connection.close()


def _set_database_access(access_level: str) -> None:
    from app.db.connection import create_connection

    connection = create_connection()
    try:
        connection.execute(
            """
            INSERT INTO system_settings (key, value, updated_at)
            VALUES ('database_access_level', ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (access_level, utc_now_iso()),
        )
        connection.commit()
    finally:
        connection.close()


def _count_rows(table_name: str) -> int:
    from app.db.connection import create_connection

    connection = create_connection()
    try:
        row = connection.execute(f"SELECT COUNT(*) AS count FROM {table_name}").fetchone()
        return int(row["count"])
    finally:
        connection.close()


def test_ai_tables_fact_rebuild_and_retrieval(client, register_and_login):
    from app.db.connection import create_connection
    from app.services.database_ai import retrieve_database_facts

    super_user, _ = register_and_login("admin", "Admin")
    _promote_to_super_admin(super_user["id"])
    super_headers = client.post("/api/v1/auth/login", json={"username": "admin", "password": "password123"}).json()
    super_auth = {"Authorization": f"Bearer {super_headers['access_token']}"}

    rebuild_response = client.post("/api/v1/databases/ai/facts/rebuild", headers=super_auth)
    assert rebuild_response.status_code == 200, rebuild_response.text
    assert rebuild_response.json()["fact_count"] > 0

    connection = create_connection()
    try:
        facts = retrieve_database_facts(connection, "users 表有哪些字段", limit=5)
        assert facts
        assert any("users" in fact["content"] for fact in facts)
    finally:
        connection.close()


def test_initialize_database_migrates_existing_ai_chat_columns(tmp_path):
    from app.core.config import Settings
    from app.db.init_db import initialize_database

    database_path = tmp_path / "legacy.db"
    connection = sqlite3.connect(database_path)
    try:
        connection.executescript(
            """
            CREATE TABLE ai_chat_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                public_id TEXT NOT NULL UNIQUE,
                owner_user_id INTEGER,
                client_id_hash TEXT,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE ai_chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                retrieved_fact_ids_json TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL
            );
            CREATE TABLE ai_chat_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                session_id INTEGER,
                message_id INTEGER,
                actor_user_id INTEGER,
                model TEXT NOT NULL,
                retrieved_fact_ids_json TEXT NOT NULL DEFAULT '[]',
                retrieved_fact_count INTEGER NOT NULL DEFAULT 0,
                duration_ms INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL,
                error_message TEXT,
                created_at TEXT NOT NULL
            );
            """
        )
        connection.commit()
    finally:
        connection.close()

    initialize_database(
        Settings(
            database_url=f"sqlite:///{database_path}",
            jwt_secret_key="test-secret-key-with-at-least-32-bytes",
            static_dir="static",
        ),
    )

    connection = sqlite3.connect(database_path)
    try:
        message_columns = {row[1] for row in connection.execute("PRAGMA table_info(ai_chat_messages)").fetchall()}
        event_columns = {row[1] for row in connection.execute("PRAGMA table_info(ai_chat_events)").fetchall()}
        assert {"thinking_enabled", "thinking_content", "input_token_count", "output_token_count"} <= message_columns
        assert {"thinking_enabled", "input_token_count", "output_token_count"} <= event_columns
    finally:
        connection.close()


def test_ai_chat_creates_session_messages_and_event(client, monkeypatch):
    from app.services import database_ai

    def fake_stream(**kwargs):
        assert kwargs["thinking_enabled"] is False
        yield {"type": "content_delta", "delta": "users 表保存"}
        yield {"type": "content_delta", "delta": "用户账户、角色和资料信息。"}
        yield {"type": "done", "input_token_count": 123, "output_token_count": 45}

    monkeypatch.setattr(database_ai, "stream_chat_with_ollama", fake_stream)

    response = client.post(
        "/api/v1/databases/ai/chat",
        headers={"X-AI-Client-Id": "anonymous-client"},
        json={"question": "users 表是做什么的？"},
    )

    assert response.status_code == 200, response.text
    events = _parse_sse_events(response.text)
    payload = next(data for event, data in events if event == "done")
    assert payload["session_id"]
    assert payload["input_token_count"] == 123
    assert payload["output_token_count"] == 45
    assert payload["sources"]
    assert _count_rows("ai_chat_sessions") == 1
    assert _count_rows("ai_chat_messages") == 2
    assert _count_rows("ai_chat_events") == 1

    sessions_response = client.get("/api/v1/databases/ai/sessions", headers={"X-AI-Client-Id": "anonymous-client"})
    assert sessions_response.status_code == 200
    assert sessions_response.json()[0]["id"] == payload["session_id"]

    detail_response = client.get(
        f"/api/v1/databases/ai/sessions/{payload['session_id']}",
        headers={"X-AI-Client-Id": "anonymous-client"},
    )
    assert detail_response.status_code == 200
    messages = detail_response.json()["messages"]
    assert len(messages) == 2
    assert messages[-1]["content"] == "users 表保存用户账户、角色和资料信息。"
    assert messages[-1]["thinking_enabled"] is False
    assert messages[-1]["thinking_content"] == ""
    assert messages[-1]["input_token_count"] == 123
    assert messages[-1]["output_token_count"] == 45


def test_ai_chat_streams_and_persists_thinking_content(client, monkeypatch):
    from app.services import database_ai

    def fake_stream(**kwargs):
        assert kwargs["thinking_enabled"] is True
        yield {"type": "thinking_delta", "delta": "先检查 users 表。"}
        yield {"type": "content_delta", "delta": "users 表用于用户账户。"}
        yield {"type": "done", "input_token_count": 10, "output_token_count": 20}

    monkeypatch.setattr(database_ai, "stream_chat_with_ollama", fake_stream)

    response = client.post(
        "/api/v1/databases/ai/chat",
        headers={"X-AI-Client-Id": "anonymous-client"},
        json={"question": "users 表是什么？", "thinking_enabled": True},
    )

    assert response.status_code == 200, response.text
    events = _parse_sse_events(response.text)
    assert ("thinking_delta", {"delta": "先检查 users 表。"}) in events
    done = next(data for event, data in events if event == "done")
    detail_response = client.get(
        f"/api/v1/databases/ai/sessions/{done['session_id']}",
        headers={"X-AI-Client-Id": "anonymous-client"},
    )
    message = detail_response.json()["messages"][-1]
    assert message["thinking_enabled"] is True
    assert message["thinking_content"] == "先检查 users 表。"
    assert message["input_token_count"] == 10
    assert message["output_token_count"] == 20


def test_ai_chat_records_failure_event_when_ollama_fails(client, monkeypatch):
    from app.db.connection import create_connection
    from app.services import database_ai

    def fail_chat(**_):
        raise OllamaError("Ollama chat request failed: unavailable")

    monkeypatch.setattr(database_ai, "stream_chat_with_ollama", fail_chat)

    response = client.post(
        "/api/v1/databases/ai/chat",
        headers={"X-AI-Client-Id": "anonymous-client"},
        json={"question": "posts 表有哪些字段？"},
    )

    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    assert events[-1][0] == "error"
    assert "unavailable" in events[-1][1]["message"]
    connection = create_connection()
    try:
        row = connection.execute("SELECT status, error_message FROM ai_chat_events ORDER BY id DESC LIMIT 1").fetchone()
        assert row["status"] == "error"
        assert "unavailable" in row["error_message"]
    finally:
        connection.close()


def test_ai_chat_inherits_database_access_policy(client, register_and_login, monkeypatch):
    from app.services import database_ai

    def fake_stream(**_):
        yield {"type": "content_delta", "delta": "已根据数据库事实回答。"}
        yield {"type": "done", "input_token_count": 1, "output_token_count": 2}

    monkeypatch.setattr(database_ai, "stream_chat_with_ollama", fake_stream)

    normal_user, normal_headers = register_and_login("normal", "Normal")
    super_user, _ = register_and_login("admin", "Admin")
    _promote_to_super_admin(super_user["id"])
    super_headers = client.post("/api/v1/auth/login", json={"username": "admin", "password": "password123"}).json()
    super_auth = {"Authorization": f"Bearer {super_headers['access_token']}"}

    _set_database_access("authenticated")
    anonymous_response = client.post(
        "/api/v1/databases/ai/chat",
        headers={"X-AI-Client-Id": "anonymous-client"},
        json={"question": "数据库有哪些表？"},
    )
    assert anonymous_response.status_code == 401

    normal_response = client.post(
        "/api/v1/databases/ai/chat",
        headers=normal_headers,
        json={"question": "数据库有哪些表？"},
    )
    assert normal_response.status_code == 200

    _set_database_access("super_admin")
    forbidden_response = client.post(
        "/api/v1/databases/ai/chat",
        headers=normal_headers,
        json={"question": "数据库有哪些表？"},
    )
    assert forbidden_response.status_code == 403

    allowed_response = client.post(
        "/api/v1/databases/ai/chat",
        headers=super_auth,
        json={"question": "数据库有哪些表？"},
    )
    assert allowed_response.status_code == 200
    assert normal_user["role"] == "normal_user"
