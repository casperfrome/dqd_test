def test_startup_and_seed_data(client):
    docs_response = client.get("/docs")
    assert docs_response.status_code == 200

    avatar_response = client.get("/static/avatars/avatar-1.svg")
    assert avatar_response.status_code == 200
    assert "<svg" in avatar_response.text

    logo_response = client.get("/static/logos/juventus.svg")
    assert logo_response.status_code == 200

    circles_response = client.get("/api/v1/fan-circles")
    assert circles_response.status_code == 200
    payload = circles_response.json()
    assert payload["total"] == 4
    assert {item["club_name"] for item in payload["items"]} == {"尤文图斯", "拜仁慕尼黑", "曼彻斯特联", "切尔西"}
