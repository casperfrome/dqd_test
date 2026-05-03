import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    database_path = tmp_path / "test_football_domain.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes")
    monkeypatch.setenv("STATIC_DIR", str((ROOT_DIR / "static").resolve()))

    from app.core.config import get_settings

    get_settings.cache_clear()

    from app.main import create_app

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client

    get_settings.cache_clear()


@pytest.fixture
def db_connection():
    from app.db.connection import create_connection

    connection = create_connection()
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


@pytest.fixture
def create_user(client: TestClient):
    def _create_user(username: str, nickname: str, password: str = "password123", bio: str = "") -> dict:
        response = client.post(
            "/api/v1/auth/register",
            json={"username": username, "nickname": nickname, "password": password, "bio": bio},
        )
        assert response.status_code == 201, response.text
        return response.json()

    return _create_user


@pytest.fixture
def login_user(client: TestClient):
    def _login_user(username: str, password: str = "password123") -> dict[str, str]:
        response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
        assert response.status_code == 200, response.text
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _login_user


@pytest.fixture
def register_and_login(create_user, login_user):
    def _register_and_login(username: str, nickname: str, password: str = "password123") -> tuple[dict, dict[str, str]]:
        user = create_user(username, nickname, password)
        headers = login_user(username, password)
        return user, headers

    return _register_and_login
