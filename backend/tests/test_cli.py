import pytest
from typer.testing import CliRunner

from kt_agent import cli
from kt_agent.cli import app
from kt_agent.llm import LLMConfigError, Message, Reply

runner = CliRunner()


def test_help() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "CLI for the KT Agent application." in result.stdout
    assert "init" in result.stdout
    assert "ingest" in result.stdout
    assert "search" in result.stdout
    assert "ask" in result.stdout
    assert "status" in result.stdout
    assert "metrics" in result.stdout
    assert "eval" in result.stdout


def test_eval_help_lists_commands() -> None:
    result = runner.invoke(app, ["eval", "--help"])

    assert result.exit_code == 0
    assert "retrieval" in result.stdout
    assert "answers" in result.stdout


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
            input_tokens=1,
            output_tokens=1,
            stop_reason="end_turn",
            latency_ms=1,
        )


def test_llm_command_prints_reply(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeLLM()
    monkeypatch.setattr(cli, "_build_llm", lambda: fake)

    result = runner.invoke(app, ["llm", "ping"])

    assert result.exit_code == 0
    assert result.stdout.strip() == "pong"
    assert fake.calls == [[Message(role="user", text="ping")]]


def test_llm_command_error_exits_1(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "_build_llm", lambda: FakeLLM(LLMConfigError("no profile")))

    result = runner.invoke(app, ["llm", "ping"])

    assert result.exit_code == 1
    assert "no profile" in result.output
    assert "pong" not in result.output
