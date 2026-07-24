"""Tests for CLI subcommands, arguments, and failure handling."""

from pathlib import Path

import pytest

from confwall.cli import main


def test_cli_help(capsys: pytest.CaptureFixture[str]):
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "confwall" in captured.out


def test_cli_version(capsys: pytest.CaptureFixture[str]):
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "confwall" in captured.out


def test_cli_no_args(capsys: pytest.CaptureFixture[str]):
    res = main([])
    assert res == 0
    captured = capsys.readouterr()
    assert "confwall" in captured.out


def test_cli_invalid_config(tmp_path: Path):
    res = main(["refresh", "--config", str(tmp_path / "nonexistent.yml")])
    assert res == 1


def test_cli_invalid_now_format(tmp_path: Path):
    cfg_file = tmp_path / "config.yml"
    cfg_file.write_text("venues: {}\n", encoding="utf-8")
    res = main(["refresh", "--config", str(cfg_file), "--now", "invalid-date-string"])
    assert res == 1


def test_cli_serve(monkeypatch):
    server_args = None

    def mock_run_server(directory, host, port):
        nonlocal server_args
        server_args = (directory, host, port)

    monkeypatch.setattr("confwall.cli.run_server", mock_run_server)
    res = main(["serve", "--directory", "build", "--host", "127.0.0.1", "--port", "8080"])
    assert res == 0
    assert server_args == ("build", "127.0.0.1", 8080)


def test_cli_run_success(tmp_path: Path, monkeypatch):
    cfg_file = tmp_path / "config.yml"
    cfg_file.write_text("venues: {}\n", encoding="utf-8")

    def mock_run_refresh(*args, **kwargs):
        return 0

    server_called = False

    def mock_run_server(*args, **kwargs):
        nonlocal server_called
        server_called = True

    monkeypatch.setattr("confwall.cli.run_refresh", mock_run_refresh)
    monkeypatch.setattr("confwall.cli.run_server", mock_run_server)

    res = main(["run", "--config", str(cfg_file)])
    assert res == 0
    assert server_called is True


def test_cli_run_fallback_to_existing_build(tmp_path: Path, monkeypatch):
    cfg_file = tmp_path / "config.yml"
    cfg_file.write_text("venues: {}\n", encoding="utf-8")
    output_dir = tmp_path / "build"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "slides.json").write_text('{"slides": []}', encoding="utf-8")

    def mock_run_refresh(*args, **kwargs):
        return 1

    server_called = False

    def mock_run_server(*args, **kwargs):
        nonlocal server_called
        server_called = True

    monkeypatch.setattr("confwall.cli.run_refresh", mock_run_refresh)
    monkeypatch.setattr("confwall.cli.run_server", mock_run_server)

    res = main(["run", "--config", str(cfg_file), "--output", str(output_dir)])
    assert res == 0
    assert server_called is True


def test_cli_run_fails_with_no_build(tmp_path: Path, monkeypatch):
    cfg_file = tmp_path / "config.yml"
    cfg_file.write_text("venues: {}\n", encoding="utf-8")
    output_dir = tmp_path / "nonexistent_build"

    def mock_run_refresh(*args, **kwargs):
        return 1

    monkeypatch.setattr("confwall.cli.run_refresh", mock_run_refresh)

    res = main(["run", "--config", str(cfg_file), "--output", str(output_dir)])
    assert res == 1
