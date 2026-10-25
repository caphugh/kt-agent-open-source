import boto3
import pytest
from botocore.exceptions import (
    EndpointConnectionError,
    NoCredentialsError,
    ReadTimeoutError,
)
from botocore.stub import Stubber

from kt_agent.config import Settings
from kt_agent.llm import (
    LLM,
    LLMAccessDeniedError,
    LLMConfigError,
    LLMResponseError,
    LLMThrottledError,
    LLMUnavailableError,
    Message,
)

MODEL_ID = "us.anthropic.claude-sonnet-5-5"
USER_HELLO = [Message(role="user", text="hello")]


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, profile="ailab", max_tokens=256)


@pytest.fixture
def client():
    # Dummy credentials; the Stubber means no network call is ever made.
    return boto3.client(
        "bedrock-runtime",
        region_name="us-east-1",
        aws_access_key_id="x",
        aws_secret_access_key="x",
    )


def converse_response(text: str = "hi there", blocks: list | None = None) -> dict:
    return {
        "output": {"message": {"role": "assistant", "content": blocks or [{"text": text}]}},
        "stopReason": "end_turn",
        "usage": {"inputTokens": 7, "outputTokens": 3, "totalTokens": 10},
        "metrics": {"latencyMs": 42},
    }


def test_send_success_builds_expected_request(settings, client) -> None:
    messages = [
        Message(role="user", text="hello"),
        Message(role="assistant", text="hi"),
        Message(role="user", text="how are you?"),
    ]
    expected_params = {
        "modelId": MODEL_ID,
        "messages": [
            {"role": "user", "content": [{"text": "hello"}]},
            {"role": "assistant", "content": [{"text": "hi"}]},
            {"role": "user", "content": [{"text": "how are you?"}]},
        ],
        "inferenceConfig": {"maxTokens": 256},
    }
    with Stubber(client) as stubber:
        stubber.add_response("converse", converse_response(), expected_params)
        reply = LLM(settings, client=client).send(messages)

    assert reply.text == "hi there"
    assert reply.model_id == MODEL_ID
    assert reply.input_tokens == 7
    assert reply.output_tokens == 3
    assert reply.stop_reason == "end_turn"
    assert reply.latency_ms >= 0


def test_multiple_text_blocks_are_joined(settings, client) -> None:
    with Stubber(client) as stubber:
        stubber.add_response(
            "converse", converse_response(blocks=[{"text": "a"}, {"text": "b"}])
        )
        reply = LLM(settings, client=client).send(USER_HELLO)

    assert reply.text == "ab"


def test_empty_response_is_error(settings, client) -> None:
    with Stubber(client) as stubber:
        stubber.add_response("converse", converse_response(text="  "))
        with pytest.raises(LLMResponseError):
            LLM(settings, client=client).send(USER_HELLO)


def test_empty_messages_rejected(settings, client) -> None:
    with pytest.raises(ValueError):
        LLM(settings, client=client).send([])


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("AccessDeniedException", LLMAccessDeniedError),
        ("ThrottlingException", LLMThrottledError),
        ("ModelTimeoutException", LLMUnavailableError),
        ("ExpiredTokenException", LLMConfigError),
        ("ValidationException", LLMResponseError),
    ],
)
def test_client_error_mapping(settings, client, code, expected) -> None:
    with Stubber(client) as stubber:
        stubber.add_client_error("converse", service_error_code=code)
        with pytest.raises(expected):
            LLM(settings, client=client).send(USER_HELLO)


class RaisingClient:
    def __init__(self, exc: Exception) -> None:
        self.exc = exc

    def converse(self, **_kwargs):
        raise self.exc


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (NoCredentialsError(), LLMConfigError),
        (ReadTimeoutError(endpoint_url="https://x"), LLMUnavailableError),
        (EndpointConnectionError(endpoint_url="https://x"), LLMUnavailableError),
        (RuntimeError("boom"), LLMResponseError),
    ],
)
def test_non_client_exception_mapping(settings, exc, expected) -> None:
    with pytest.raises(expected):
        LLM(settings, client=RaisingClient(exc)).send(USER_HELLO)


def test_missing_profile_is_config_error() -> None:
    llm = LLM(Settings(_env_file=None, profile=None))

    with pytest.raises(LLMConfigError, match="KT_LLM_PROFILE"):
        llm.send(USER_HELLO)


def test_unknown_profile_is_config_error() -> None:
    llm = LLM(Settings(_env_file=None, profile="definitely-not-a-real-profile"))

    with pytest.raises(LLMConfigError, match="not found"):
        llm.send(USER_HELLO)


def test_constructing_llm_does_not_touch_aws() -> None:
    # Lazy client creation: no profile lookup until send().
    LLM(Settings(_env_file=None, profile="definitely-not-a-real-profile"))
