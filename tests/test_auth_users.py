import jwt


def test_register_login_me_and_duplicate_username(client):
    register_response = client.post(
        "/api/v1/auth/register",
        json={"username": "alice", "nickname": "Alice", "password": "password123", "bio": "juve fan"},
    )
    assert register_response.status_code == 201
    assert register_response.json()["avatar_url"].startswith("/static/avatars/avatar-")

    duplicate_response = client.post(
        "/api/v1/auth/register",
        json={"username": "alice", "nickname": "Alice2", "password": "password123", "bio": ""},
    )
    assert duplicate_response.status_code == 409

    login_response = client.post("/api/v1/auth/login", json={"username": "alice", "password": "password123"})
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    me_response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_response.status_code == 200
    assert me_response.json()["username"] == "alice"


def test_follow_unfollow_and_user_analytics(client, register_and_login):
    user_1, headers_1 = register_and_login("alice", "Alice")
    user_2, headers_2 = register_and_login("bob", "Bob")

    follow_response = client.post(f"/api/v1/users/{user_2['id']}/follow", headers=headers_1)
    assert follow_response.status_code == 200

    profile_response = client.get(f"/api/v1/users/{user_2['id']}", headers=headers_1)
    assert profile_response.status_code == 200
    assert profile_response.json()["followers_count"] == 1

    followers_response = client.get(f"/api/v1/users/{user_2['id']}/followers")
    assert followers_response.status_code == 200
    assert followers_response.json()["total"] == 1
    assert followers_response.json()["items"][0]["username"] == "alice"

    analytics_response = client.get(f"/api/v1/users/{user_2['id']}/analytics", headers=headers_2)
    assert analytics_response.status_code == 200
    event_types = [event["event_type"] for event in analytics_response.json()["recent_events"]]
    assert "register" in event_types
    assert "follow" in event_types

    unfollow_response = client.delete(f"/api/v1/users/{user_2['id']}/follow", headers=headers_1)
    assert unfollow_response.status_code == 200

    updated_profile = client.get(f"/api/v1/users/{user_2['id']}")
    assert updated_profile.status_code == 200
    assert updated_profile.json()["followers_count"] == 0


def test_signed_token_without_subject_is_rejected(client):
    from app.core.config import get_settings

    token = jwt.encode({"username": "alice"}, get_settings().jwt_secret_key, algorithm="HS256")
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
