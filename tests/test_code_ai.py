import json

from app.core.utils import utc_now_iso


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


def test_code_catalog_lists_source_files_and_excludes_sensitive_paths(client):
    response = client.get("/api/v1/code/catalog")

    assert response.status_code == 200, response.text
    payload = response.json()
    paths = {file["path"] for file in payload["files"]}
    assert payload["access_level"] == "public"
    assert "app/main.py" in paths
    assert "frontend/src/App.tsx" in paths
    assert all("node_modules" not in path for path in paths)
    assert all("dist/" not in path for path in paths)
    assert all(not path.endswith((".env", ".log", ".db")) for path in paths)

    file_response = client.get("/api/v1/code/file", params={"path": "app/main.py"})
    assert file_response.status_code == 200
    assert "create_app" in file_response.json()["content"]

    traversal_response = client.get("/api/v1/code/file", params={"path": "../.env"})
    assert traversal_response.status_code == 400

    excluded_response = client.get("/api/v1/code/file", params={"path": ".env"})
    assert excluded_response.status_code == 404


def test_code_facts_rebuild_and_retrieval(client, register_and_login):
    from app.db.connection import create_connection
    from app.services.code_ai import retrieve_code_facts

    super_user, _ = register_and_login("admin", "Admin")
    _promote_to_super_admin(super_user["id"])
    token_payload = client.post("/api/v1/auth/login", json={"username": "admin", "password": "password123"}).json()
    super_auth = {"Authorization": f"Bearer {token_payload['access_token']}"}

    rebuild_response = client.post("/api/v1/code/ai/facts/rebuild", headers=super_auth)
    assert rebuild_response.status_code == 200, rebuild_response.text
    assert rebuild_response.json()["fact_count"] > 0

    connection = create_connection()
    try:
        facts = retrieve_code_facts(connection, "create_app DatabaseAiPanel", limit=8)
        assert facts
        assert any(fact["source_file_path"] == "app/main.py" for fact in facts)
        assert any(
            fact["source_file_path"] in (
                "frontend/src/App.tsx",
                "frontend/src/components/databases/DatabaseAiPanel.tsx",
            )
            for fact in facts
        )
        assert all(int(fact["start_line"]) <= int(fact["end_line"]) for fact in facts)
    finally:
        connection.close()


def test_code_ai_chat_creates_session_messages_and_event(client, monkeypatch):
    from app.services import code_ai

    def fake_stream(**kwargs):
        assert kwargs["thinking_enabled"] is False
        yield {"type": "content_delta", "delta": "create_app 在 app/main.py 中注册路由。"}
        yield {"type": "done", "input_token_count": 7, "output_token_count": 9}

    monkeypatch.setattr(code_ai, "stream_chat_with_ollama", fake_stream)

    response = client.post(
        "/api/v1/code/ai/chat",
        headers={"X-AI-Client-Id": "anonymous-client"},
        json={"question": "create_app 做了什么？"},
    )

    assert response.status_code == 200, response.text
    events = _parse_sse_events(response.text)
    payload = next(data for event, data in events if event == "done")
    assert payload["session_id"]
    assert payload["sources"]
    assert _count_rows("ai_code_chat_sessions") == 1
    assert _count_rows("ai_code_chat_messages") == 2
    assert _count_rows("ai_code_chat_events") == 1

    detail_response = client.get(
        f"/api/v1/code/ai/sessions/{payload['session_id']}",
        headers={"X-AI-Client-Id": "anonymous-client"},
    )
    assert detail_response.status_code == 200
    messages = detail_response.json()["messages"]
    assert messages[-1]["content"] == "create_app 在 app/main.py 中注册路由。"
    assert messages[-1]["input_token_count"] == 7
    assert messages[-1]["output_token_count"] == 9


def test_code_ai_inherits_database_access_policy(client, register_and_login, monkeypatch):
    from app.services import code_ai

    def fake_stream(**_):
        yield {"type": "content_delta", "delta": "已根据代码事实回答。"}
        yield {"type": "done", "input_token_count": 1, "output_token_count": 2}

    monkeypatch.setattr(code_ai, "stream_chat_with_ollama", fake_stream)

    normal_user, normal_headers = register_and_login("normal", "Normal")
    super_user, _ = register_and_login("admin", "Admin")
    _promote_to_super_admin(super_user["id"])
    token_payload = client.post("/api/v1/auth/login", json={"username": "admin", "password": "password123"}).json()
    super_auth = {"Authorization": f"Bearer {token_payload['access_token']}"}

    _set_database_access("authenticated")
    anonymous_response = client.get("/api/v1/code/catalog")
    assert anonymous_response.status_code == 401
    normal_response = client.get("/api/v1/code/catalog", headers=normal_headers)
    assert normal_response.status_code == 200

    _set_database_access("super_admin")
    forbidden_response = client.post(
        "/api/v1/code/ai/chat",
        headers=normal_headers,
        json={"question": "代码入口在哪里？"},
    )
    assert forbidden_response.status_code == 403

    allowed_response = client.post(
        "/api/v1/code/ai/chat",
        headers=super_auth,
        json={"question": "代码入口在哪里？"},
    )
    assert allowed_response.status_code == 200
    assert normal_user["role"] == "normal_user"
