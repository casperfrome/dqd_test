def test_fan_circle_detail_posts_and_analytics(client, register_and_login):
    _, headers = register_and_login("poster", "Poster")

    list_response = client.get("/api/v1/fan-circles")
    assert list_response.status_code == 200
    bayern_circle = next(item for item in list_response.json()["items"] if item["club_name"] == "拜仁慕尼黑")

    detail_response = client.get(f"/api/v1/fan-circles/{bayern_circle['id']}", headers=headers)
    assert detail_response.status_code == 200
    assert detail_response.json()["league_name"] == "Bundesliga"

    create_post_response = client.post(
        f"/api/v1/fan-circles/{bayern_circle['id']}/posts",
        headers=headers,
        json={
            "title": "欧冠展望",
            "content": "这一场高位压迫会很关键。",
            "category": "discussion",
            "tags": ["欧冠", "战术"],
            "poll": None,
        },
    )
    assert create_post_response.status_code == 201
    assert create_post_response.json()["fan_circle_id"] == bayern_circle["id"]

    posts_response = client.get(f"/api/v1/fan-circles/{bayern_circle['id']}/posts", headers=headers)
    assert posts_response.status_code == 200
    assert posts_response.json()["total"] == 1
    assert posts_response.json()["items"][0]["tags"] == ["欧冠", "战术"]

    analytics_response = client.get(f"/api/v1/fan-circles/{bayern_circle['id']}/analytics")
    assert analytics_response.status_code == 200
    assert analytics_response.json()["summary"]["post_count"] == 1
    event_types = [event["event_type"] for event in analytics_response.json()["recent_events"]]
    assert "view_circle" in event_types
    assert "list_posts" in event_types
    assert "create_post" in event_types
