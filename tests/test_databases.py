import sqlite3
from pathlib import Path

from app.core.config import ROOT_DIR
from app.core.utils import utc_now_iso
from app.services.database_comments import COLUMN_COMMENTS, TABLE_COMMENTS, UNCONFIGURED_COMMENT
from app.services.database_catalog import discover_database_files


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


def test_database_catalog_is_public_by_default(client):
    response = client.get("/api/v1/databases")

    assert response.status_code == 200
    payload = response.json()
    assert payload["access_level"] == "public"
    assert any(database["name"] == "football_domain.db" for database in payload["databases"])

    default_database = next(database for database in payload["databases"] if database["name"] == "football_domain.db")
    table_names = {table["name"] for table in default_database["tables"]}
    assert "users" in table_names
    assert "posts" in table_names
    assert all(len(table["sample_rows"]) <= 5 for table in default_database["tables"])


def test_database_access_level_can_only_be_changed_by_super_admin(client, register_and_login):
    normal_user, normal_headers = register_and_login("normal", "Normal")
    super_user = client.post(
        "/api/v1/auth/register",
        json={"username": "admin", "nickname": "Admin", "password": "password123", "bio": ""},
    ).json()
    _promote_to_super_admin(super_user["id"])
    super_headers = client.post("/api/v1/auth/login", json={"username": "admin", "password": "password123"}).json()
    super_auth = {"Authorization": f"Bearer {super_headers['access_token']}"}

    denied = client.put("/api/v1/databases/access", headers=normal_headers, json={"access_level": "authenticated"})
    assert denied.status_code == 403

    updated = client.put("/api/v1/databases/access", headers=super_auth, json={"access_level": "authenticated"})
    assert updated.status_code == 200
    assert updated.json()["access_level"] == "authenticated"
    assert client.get("/api/v1/databases").status_code == 401
    assert client.get("/api/v1/databases", headers=normal_headers).status_code == 200

    updated = client.put("/api/v1/databases/access", headers=super_auth, json={"access_level": "super_admin"})
    assert updated.status_code == 200
    assert client.get("/api/v1/databases", headers=normal_headers).status_code == 403
    assert client.get("/api/v1/databases", headers=super_auth).status_code == 200

    assert normal_user["role"] == "normal_user"


def test_known_database_tables_and_columns_have_chinese_comments(client):
    from app.core.config import get_settings

    database_path = get_settings().database_path
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        fts_tables = [
            str(row["name"])
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_schema
                WHERE type = 'table' AND lower(sql) LIKE '%using fts5%'
                """,
            ).fetchall()
        ]
        fts_shadow_tables = {
            f"{table_name}{suffix}"
            for table_name in fts_tables
            for suffix in ("_data", "_idx", "_content", "_docsize", "_config")
        }
        tables = [
            str(row["name"])
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_schema
                WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """,
            ).fetchall()
            if str(row["name"]) not in fts_shadow_tables
        ]
        assert tables
        for table_name in tables:
            assert TABLE_COMMENTS.get(table_name) not in {None, UNCONFIGURED_COMMENT}
            columns = connection.execute(f'PRAGMA table_info("{table_name}")').fetchall()
            assert columns
            for column in columns:
                assert COLUMN_COMMENTS.get(table_name, {}).get(str(column["name"])) not in {None, UNCONFIGURED_COMMENT}
    finally:
        connection.close()


def test_database_discovery_skips_node_modules_and_only_returns_sqlite_files():
    databases = discover_database_files(ROOT_DIR)

    assert databases
    assert all(path.suffix.lower() in {".db", ".sqlite", ".sqlite3"} for path in databases)
    assert all(Path("node_modules") not in path.relative_to(ROOT_DIR).parents for path in databases)
