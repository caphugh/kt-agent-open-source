import pytest

from kt_agent.config import Settings


def test_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "PROFILE",
        "REGION",
        "MODEL_ID",
        "MAX_TOKENS",
        "MAX_RETRIES",
        "READ_TIMEOUT",
    ):
        monkeypatch.delenv(f"KT_LLM_{name}", raising=False)

    settings = Settings(_env_file=None)

    assert settings.profile is None
    assert settings.region == "us-east-1"
    assert settings.model_id == "us.anthropic.claude-sonnet-5-5"
    assert settings.max_tokens == 1024
    assert settings.max_retries == 3
    assert settings.read_timeout == 60


def test_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KT_LLM_PROFILE", "ailab")
    monkeypatch.setenv("KT_LLM_REGION", "us-west-2")
    monkeypatch.setenv("KT_LLM_MODEL_ID", "some.model")
    monkeypatch.setenv("KT_LLM_MAX_TOKENS", "200")
    monkeypatch.setenv("KT_LLM_MAX_RETRIES", "5")
    monkeypatch.setenv("KT_LLM_READ_TIMEOUT", "10")

    settings = Settings(_env_file=None)

    assert settings.profile == "ailab"
    assert settings.region == "us-west-2"
    assert settings.model_id == "some.model"
    assert settings.max_tokens == 200
    assert settings.max_retries == 5
    assert settings.read_timeout == 10


def test_invalid_values_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KT_LLM_MAX_TOKENS", "0")

    with pytest.raises(ValueError):
        Settings(_env_file=None)
