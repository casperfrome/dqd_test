from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import admin, auth, code, databases, fan_circles, posts, users
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.db.init_db import initialize_database


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    initialize_database(settings)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    register_exception_handlers(app)
    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(fan_circles.router)
    app.include_router(posts.router)
    app.include_router(admin.router)
    app.include_router(databases.router)
    app.include_router(code.router)
    app.mount("/static", StaticFiles(directory=settings.static_path), name="static")
    return app


app = create_app()
