"""Application configuration, loaded from environment variables.

Values come from ``KT_LLM_*`` env vars, optionally via ``backend/.env``.
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="KT_LLM_",
        env_file=BACKEND_DIR / ".env",
        extra="ignore",
    )

    # AWS profile with Bedrock access. Required to call the model, but optional
    # here so the app, CLI --help and /api/health work without it; the LLM layer
    # raises a clear error on first use if it is missing.
    profile: str | None = None
    region: str = "us-east-1"
    model_id: str = "us.anthropic.claude-sonnet-5-5"
    max_tokens: int = Field(default=1024, gt=0)
    max_retries: int = Field(default=3, ge=0)
    read_timeout: float = Field(default=60, gt=0)
