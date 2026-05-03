from app.core.exceptions import AppError


def ensure_active_user(user: dict) -> None:
    if not bool(user["is_active"]):
        raise AppError(status_code=403, message="Inactive users cannot perform this action.")


def ensure_super_admin(user: dict) -> None:
    if user["role"] != "super_admin":
        raise AppError(status_code=403, message="Super admin permission required.")


def ensure_circle_owner_or_admin(user: dict, circle: dict) -> None:
    if user["role"] == "super_admin":
        return
    if user["role"] == "fan_circle_owner" and circle["owner_user_id"] == user["id"]:
        return
    raise AppError(status_code=403, message="Circle moderation permission required.")
