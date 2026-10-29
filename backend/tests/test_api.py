from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from kt_agent.api.app import app
from kt_agent.api.deps import get_llm
from kt_agent.llm import (
    LLMAccessDeniedError,
    LLMConfigError,
    LLMResponseError,
    LLMThrottledError,
    LLMUnavailableError,
    Message,
    Reply,
)


class FakeLLM:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[list[Message]] = []

    def send(self, messages: list[Message]) -> Reply:
        self.calls.append(messages)
        if self.error:
            raise self.error
        return Reply(
            text="pong",
            model_id="test-model",
            input_tokens=4,
            output_tokens=2,
            stop_reason="end_turn",
            latency_ms=12,
        )


@pytest.fixture
def client() -> Iterator[TestClient]:
    yield TestClient(app)
    app.dependency_overrides.clear()


def use_llm(llm: FakeLLM) -> None:
    app.dependency_overrides[get_llm] = lambda: llm


def test_health(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"status": "ok"}


def test_complete_success(client: TestClient) -> None:
    fake = FakeLLM()
    use_llm(fake)

    response = client.post("/api/llm/complete", json={"prompt": "ping"})

    assert response.status_code == 200
    assert response.json() == {
        "response": "pong",
        "model_id": "test-model",
        "usage": {"input_tokens": 4, "output_tokens": 2},
        "latency_ms": 12,
    }
    assert fake.calls == [[Message(role="user", text="ping")]]


@pytest.mark.parametrize("body", [{}, {"prompt": ""}])
def test_complete_rejects_bad_body(client: TestClient, body: dict) -> None:
    use_llm(FakeLLM())

    assert client.post("/api/llm/complete", json=body).status_code == 422


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (LLMConfigError("no profile"), 503),
        (LLMAccessDeniedError("denied"), 503),
        (LLMThrottledError("slow down"), 503),
        (LLMUnavailableError("timeout"), 503),
        (LLMResponseError("bad"), 502),
    ],
)
def test_complete_maps_errors(client: TestClient, error: Exception, status: int) -> None:
    use_llm(FakeLLM(error=error))

    response = client.post("/api/llm/complete", json={"prompt": "ping"})

    assert response.status_code == status
    assert response.json() == {"detail": str(error)}
