def test_posts_comments_votes_and_permissions(client, register_and_login, db_connection):
    admin_user, admin_headers = register_and_login("admin_user", "Admin")
    owner_user, owner_headers = register_and_login("owner_user", "Owner")
    normal_user, normal_headers = register_and_login("normal_user", "Normal")

    db_connection.execute(
        "UPDATE users SET role = 'super_admin', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (admin_user["id"],),
    )
    db_connection.commit()

    circles_response = client.get("/api/v1/fan-circles")
    circle = next(item for item in circles_response.json()["items"] if item["club_name"] == "切尔西")

    assign_owner_response = client.post(
        f"/api/v1/admin/fan-circles/{circle['id']}/owner",
        headers=admin_headers,
        json={"owner_user_id": owner_user["id"]},
    )
    assert assign_owner_response.status_code == 200

    post_response = client.post(
        f"/api/v1/fan-circles/{circle['id']}/posts",
        headers=normal_headers,
        json={
            "title": "首发该怎么排",
            "content": "我想看 4-2-3-1。",
            "category": "match",
            "tags": ["阵容", "比赛日"],
            "poll": {
                "question": "你支持哪种阵型？",
                "allow_multiple": False,
                "expires_at": None,
                "options": ["4-2-3-1", "3-4-2-1"],
            },
        },
    )
    assert post_response.status_code == 201
    post_id = post_response.json()["id"]
    poll_id = post_response.json()["poll"]["id"]
    option_id = post_response.json()["poll"]["options"][0]["id"]
    assert poll_id > 0

    forbidden_pin_response = client.post(
        f"/api/v1/admin/posts/{post_id}/pin",
        headers=normal_headers,
        json={"value": True},
    )
    assert forbidden_pin_response.status_code == 403

    like_post_response = client.post(f"/api/v1/posts/{post_id}/like", headers=owner_headers)
    assert like_post_response.status_code == 200
    assert like_post_response.json()["like_count"] == 1

    comment_response = client.post(
        f"/api/v1/posts/{post_id}/comments",
        headers=owner_headers,
        json={"content": "我更喜欢双后腰。", "parent_comment_id": None},
    )
    assert comment_response.status_code == 201
    parent_comment_id = comment_response.json()["id"]
    assert comment_response.json()["depth"] == 0
    parent_comment_path = comment_response.json()["path"]
    assert parent_comment_path == str(parent_comment_id)

    reply_response = client.post(
        f"/api/v1/comments/{parent_comment_id}/reply",
        headers=normal_headers,
        json={"content": "同意，而且边路需要速度。", "parent_comment_id": None},
    )
    assert reply_response.status_code == 201
    assert reply_response.json()["depth"] == 1
    assert reply_response.json()["path"].startswith(f"{parent_comment_id}/")

    list_comments_response = client.get(f"/api/v1/posts/{post_id}/comments")
    assert list_comments_response.status_code == 200
    assert list_comments_response.json()["total"] == 2

    like_comment_response = client.post(f"/api/v1/comments/{parent_comment_id}/like", headers=normal_headers)
    assert like_comment_response.status_code == 200
    assert like_comment_response.json()["like_count"] == 1

    vote_response = client.post(
        f"/api/v1/posts/{post_id}/vote",
        headers=owner_headers,
        json={"option_ids": [option_id]},
    )
    assert vote_response.status_code == 200
    updated_options = vote_response.json()["poll"]["options"]
    assert next(option for option in updated_options if option["id"] == option_id)["vote_count"] == 1

    lock_response = client.post(
        f"/api/v1/admin/posts/{post_id}/lock",
        headers=owner_headers,
        json={"value": True},
    )
    assert lock_response.status_code == 200
    assert lock_response.json()["is_locked"] is True

    locked_comment_response = client.post(
        f"/api/v1/posts/{post_id}/comments",
        headers=normal_headers,
        json={"content": "锁帖后不该成功", "parent_comment_id": None},
    )
    assert locked_comment_response.status_code == 400

    analytics_response = client.get(f"/api/v1/posts/{post_id}/analytics")
    assert analytics_response.status_code == 200
    event_types = [event["event_type"] for event in analytics_response.json()["recent_events"]]
    assert "like_post" in event_types
    assert "create_comment" in event_types
    assert "reply_comment" in event_types
    assert "vote_poll" in event_types

    deactivate_response = client.post(f"/api/v1/admin/users/{normal_user['id']}/deactivate", headers=admin_headers)
    assert deactivate_response.status_code == 200

    failed_login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "normal_user", "password": "password123"},
    )
    assert failed_login_response.status_code == 403


def test_deactivated_owner_token_cannot_moderate_posts(client, register_and_login, db_connection):
    admin_user, admin_headers = register_and_login("admin_user", "Admin")
    owner_user, owner_headers = register_and_login("owner_user", "Owner")
    _, poster_headers = register_and_login("poster_user", "Poster")

    db_connection.execute(
        "UPDATE users SET role = 'super_admin', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (admin_user["id"],),
    )
    db_connection.commit()

    circle = client.get("/api/v1/fan-circles").json()["items"][0]
    assign_owner_response = client.post(
        f"/api/v1/admin/fan-circles/{circle['id']}/owner",
        headers=admin_headers,
        json={"owner_user_id": owner_user["id"]},
    )
    assert assign_owner_response.status_code == 200

    post_response = client.post(
        f"/api/v1/fan-circles/{circle['id']}/posts",
        headers=poster_headers,
        json={"title": "Lineup", "content": "Who starts?", "category": "discussion", "tags": [], "poll": None},
    )
    assert post_response.status_code == 201

    deactivate_response = client.post(f"/api/v1/admin/users/{owner_user['id']}/deactivate", headers=admin_headers)
    assert deactivate_response.status_code == 200

    stale_token_response = client.post(
        f"/api/v1/admin/posts/{post_response.json()['id']}/pin",
        headers=owner_headers,
        json={"value": True},
    )
    assert stale_token_response.status_code == 403


def test_comment_paths_sort_by_tree_order_when_ids_reach_two_digits(client, register_and_login):
    _, headers = register_and_login("commenter", "Commenter")
    circle = client.get("/api/v1/fan-circles").json()["items"][0]
    post_response = client.post(
        f"/api/v1/fan-circles/{circle['id']}/posts",
        headers=headers,
        json={"title": "Thread", "content": "Nested comments", "category": "discussion", "tags": [], "poll": None},
    )
    assert post_response.status_code == 201
    post_id = post_response.json()["id"]

    root_response = client.post(
        f"/api/v1/posts/{post_id}/comments",
        headers=headers,
        json={"content": "root", "parent_comment_id": None},
    )
    assert root_response.status_code == 201
    root_id = root_response.json()["id"]
    reply_ids = []
    for index in range(12):
        reply_response = client.post(
            f"/api/v1/comments/{root_id}/reply",
            headers=headers,
            json={"content": f"reply {index}", "parent_comment_id": None},
        )
        assert reply_response.status_code == 201
        reply_ids.append(reply_response.json()["id"])

    comments_response = client.get(f"/api/v1/posts/{post_id}/comments", params={"page_size": 20})
    assert comments_response.status_code == 200
    returned_ids = [item["id"] for item in comments_response.json()["items"]]
    assert returned_ids == [root_id, *reply_ids]
