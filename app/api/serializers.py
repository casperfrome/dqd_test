from typing import Any


def serialize_user_brief(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    return {
        "id": row["id"],
        "username": row["username"],
        "nickname": row["nickname"],
        "role": row["role"],
        "avatar_url": row["avatar_url"],
    }


def serialize_user_profile(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "username": row["username"],
        "nickname": row["nickname"],
        "role": row["role"],
        "avatar_url": row["avatar_url"],
        "bio": row["bio"],
        "following_count": row["following_count"],
        "followers_count": row["followers_count"],
        "total_likes_received": row["total_likes_received"],
        "total_dislikes_received": row["total_dislikes_received"],
        "is_active": bool(row["is_active"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def serialize_fan_circle(row: dict[str, Any]) -> dict[str, Any]:
    owner = None
    if row.get("owner_user_id"):
        owner = {
            "id": row["owner_user_id"],
            "username": row["owner_username"],
            "nickname": row["owner_nickname"],
            "role": "fan_circle_owner",
            "avatar_url": row["owner_avatar_url"],
        }
    return {
        "id": row["id"],
        "club_name": row["club_name"],
        "board_name": row["board_name"],
        "league_name": row["league_name"],
        "logo_url": row["logo_url"],
        "description": row["description"],
        "post_count": row["post_count"],
        "follower_count": row["follower_count"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "owner": owner,
    }


def serialize_post(row: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "id": row["id"],
        "fan_circle_id": row["fan_circle_id"],
        "title": row["title"],
        "content": row["content"],
        "category": row["category"],
        "tags": row.get("tags", []),
        "like_count": row["like_count"],
        "dislike_count": row["dislike_count"],
        "comment_count": row["comment_count"],
        "has_poll": bool(row["has_poll"]),
        "is_pinned": bool(row["is_pinned"]),
        "is_locked": bool(row["is_locked"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "author": {
            "id": row["author_user_id"],
            "username": row["author_username"],
            "nickname": row["author_nickname"],
            "role": row.get("author_role", "normal_user"),
            "avatar_url": row["author_avatar_url"],
        },
    }
    if "club_name" in row:
        payload["club_name"] = row["club_name"]
        payload["board_name"] = row["board_name"]
        payload["league_name"] = row["league_name"]
    if row.get("poll") is not None:
        payload["poll"] = row["poll"]
    return payload


def _public_comment_path(path: str) -> str:
    return "/".join(str(int(segment)) if segment.isdigit() else segment for segment in path.split("/"))


def serialize_comment(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "post_id": row["post_id"],
        "parent_comment_id": row["parent_comment_id"],
        "depth": row["depth"],
        "path": _public_comment_path(row["path"]),
        "content": row["content"],
        "like_count": row["like_count"],
        "dislike_count": row["dislike_count"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "author": {
            "id": row["author_user_id"],
            "username": row["author_username"],
            "nickname": row["author_nickname"],
            "avatar_url": row["author_avatar_url"],
        },
    }
