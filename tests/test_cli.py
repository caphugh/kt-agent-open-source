from typer.testing import CliRunner

from kt_agent.cli import app

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
