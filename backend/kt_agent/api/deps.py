"""Cached FastAPI dependencies. Override these in tests via
``app.dependency_overrides``."""

from functools import lru_cache

from kt_agent.config import Settings
from kt_agent.llm import LLM


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_llm() -> LLM:
    return LLM(get_settings())
