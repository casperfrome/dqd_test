from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = Field(default="FootballDomain", alias="APP_NAME")
    database_url: str = Field(default="sqlite:///./football_domain.db", alias="DATABASE_URL")
    jwt_secret_key: str = Field(default="change-me-in-production", alias="JWT_SECRET_KEY")
    jwt_expire_minutes: int = Field(default=120, alias="JWT_EXPIRE_MINUTES")
    static_dir: str = Field(default="static", alias="STATIC_DIR")
    ollama_base_url: str = Field(default="http://127.0.0.1:11434", alias="OLLAMA_BASE_URL")
    ai_chat_model: str = Field(default="qwen3:8b", alias="AI_CHAT_MODEL")
    ai_fact_refresh_ttl_seconds: int = Field(default=300, alias="AI_FACT_REFRESH_TTL_SECONDS")
    ai_rag_top_k: int = Field(default=8, alias="AI_RAG_TOP_K")

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @property
    def database_path(self) -> Path:
        raw = self.database_url.removeprefix("sqlite:///")
        path = Path(raw)
        if not path.is_absolute():
            path = ROOT_DIR / path
        return path.resolve()

    @property
    def static_path(self) -> Path:
        path = Path(self.static_dir)
        if not path.is_absolute():
            path = ROOT_DIR / path
        return path.resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
