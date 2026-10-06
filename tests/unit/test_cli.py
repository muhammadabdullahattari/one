from src.sdk.cli import app
from typer.testing import CliRunner

runner = CliRunner()


def test_cli_version_command() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "Task Engine v" in result.output


def test_cli_help_command() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Event-Driven Distributed Task Processing Engine CLI" in result.output
    assert "worker" in result.output
    assert "scheduler" in result.output
    assert "db" in result.output
    assert "api" in result.output


def test_cli_worker_help() -> None:
    result = runner.invoke(app, ["worker", "--help"])
    assert result.exit_code == 0
    assert "Worker lifecycle commands" in result.output
    assert "start" in result.output


def test_cli_scheduler_help() -> None:
    result = runner.invoke(app, ["scheduler", "--help"])
    assert result.exit_code == 0
    assert "Scheduler daemon lifecycle commands" in result.output
    assert "start" in result.output


def test_cli_db_help() -> None:
    result = runner.invoke(app, ["db", "--help"])
    assert result.exit_code == 0
    assert "Database migration and maintenance commands" in result.output
    assert "migrate" in result.output
    assert "rollback" in result.output
