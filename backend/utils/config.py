import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, model_validator
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")
    app_name: str = "MemoryMesh"
    app_version: str = "1.0.0"
    debug: bool = False
    environment: str = "development"

    host: str = "0.0.0.0"
    port: int = 8000

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/memorymesh"

    @field_validator("database_url", mode="before")
    @classmethod
    def convert_db_url(cls, v: str) -> str:
        if v.startswith("postgres://"):
            return "postgresql+asyncpg://" + v[len("postgres://"):]
        if v.startswith("postgresql://"):
            return "postgresql+asyncpg://" + v[len("postgresql://"):]
        return v

    # Cloud LLM defaults (OpenAI). Override with LLM_* / provider keys in .env.
    llm_provider: str = "openai"
    llm_model: str = "openai/gpt-4o-mini"
    llm_api_key: str = ""
    llm_base_url: str = ""
    embedding_provider: str = "openai"
    embedding_model: str = "openai/text-embedding-3-small"
    embedding_api_key: str = ""
    embedding_dimensions: int = 1536

    vector_db_provider: str = "lancedb"
    vector_db_path: str = "./data/lancedb"

    # When true, memory endpoints fail with 503 if Cognee is inactive.
    cognee_required: bool = False

    @model_validator(mode="after")
    def resolve_api_keys(self) -> "Settings":
        """Prefer explicit LLM_API_KEY; fall back to provider-specific keys."""
        if not self.llm_api_key:
            if self.llm_provider == "openai":
                self.llm_api_key = os.getenv("OPENAI_API_KEY", "")
            elif self.llm_provider == "gemini":
                self.llm_api_key = os.getenv("GEMINI_API_KEY", "")
            elif self.llm_provider == "groq":
                self.llm_api_key = os.getenv("GROQ_API_KEY", "")
            else:
                self.llm_api_key = (
                    os.getenv("LLM_API_KEY")
                    or os.getenv("OPENAI_API_KEY")
                    or os.getenv("GEMINI_API_KEY")
                    or ""
                )
        if not self.embedding_api_key:
            self.embedding_api_key = self.llm_api_key or os.getenv("EMBEDDING_API_KEY", "")
        return self

    upload_dir: str = "./data/uploads"
    graph_db_path: str = "./data/graph"

    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    jwt_secret: str = "change-me-in-production-use-a-long-random-string"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days

def get_settings() -> Settings:
    return Settings()


settings = get_settings()
