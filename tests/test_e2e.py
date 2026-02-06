"""End-to-end tests for Prompter CLI application."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from prompter.main import app


runner = CliRunner()


class TestE2E:
    """End-to-end test suite for Prompter CLI."""

    def test_full_execution(self, tmp_path: Path) -> None:
        """Test full execution flow with mocked ClaudeRunner."""
        prompts_file = tmp_path / "prompts.txt"
        prompts_file.write_text("Prompt 1\n---\nPrompt 2", encoding="utf-8")

        output_file = tmp_path / "report.json"

        mock_response = {"content": "test", "session_id": "123"}

        with patch("prompter.main.ClaudeRunner") as mock_runner_class:
            mock_runner = MagicMock()
            mock_runner.run_prompt.return_value = mock_response
            mock_runner_class.return_value = mock_runner

            with patch("prompter.main.setup_logging"):
                result = runner.invoke(
                    app,
                    [str(prompts_file), "--output", str(output_file)],
                )

        assert result.exit_code == 0, f"Exit code was {result.exit_code}: {result.output}"
        assert output_file.exists(), "Output file was not created"

        report = json.loads(output_file.read_text(encoding="utf-8"))
        assert len(report) == 2
        assert report[0]["status"] == "success"
        assert report[0]["claude_response"] == mock_response
        assert report[1]["status"] == "success"

    def test_version_flag(self) -> None:
        """Test that --version flag shows version and exits."""
        result = runner.invoke(app, ["--version"])

        assert result.exit_code == 0
        assert "version" in result.output.lower()

    def test_single_prompt(self, tmp_path: Path) -> None:
        """Test execution with a single prompt."""
        prompts_file = tmp_path / "prompts.txt"
        prompts_file.write_text("Single prompt", encoding="utf-8")

        output_file = tmp_path / "report.json"

        mock_response = {"result": "Success", "session_id": "abc"}

        with patch("prompter.main.ClaudeRunner") as mock_runner_class:
            mock_runner = MagicMock()
            mock_runner.run_prompt.return_value = mock_response
            mock_runner_class.return_value = mock_runner

            with patch("prompter.main.setup_logging"):
                result = runner.invoke(
                    app,
                    [str(prompts_file), "--output", str(output_file)],
                )

        assert result.exit_code == 0
        report = json.loads(output_file.read_text(encoding="utf-8"))
        assert len(report) == 1
        assert report[0]["prompt"] == "Single prompt"

    def test_json_prompts(self, tmp_path: Path) -> None:
        """Test execution with JSON prompts file."""
        prompts_file = tmp_path / "prompts.json"
        prompts_file.write_text(
            json.dumps(["First prompt", "Second prompt"]),
            encoding="utf-8",
        )

        output_file = tmp_path / "report.json"

        with patch("prompter.main.ClaudeRunner") as mock_runner_class:
            mock_runner = MagicMock()
            mock_runner.run_prompt.return_value = {"result": "ok"}
            mock_runner_class.return_value = mock_runner

            with patch("prompter.main.setup_logging"):
                result = runner.invoke(
                    app,
                    [str(prompts_file), "--output", str(output_file)],
                )

        assert result.exit_code == 0
        report = json.loads(output_file.read_text(encoding="utf-8"))
        assert len(report) == 2

    def test_verbose_flag(self, tmp_path: Path) -> None:
        """Test that verbose flag is passed correctly."""
        prompts_file = tmp_path / "prompts.txt"
        prompts_file.write_text("Test prompt", encoding="utf-8")

        output_file = tmp_path / "report.json"

        with patch("prompter.main.ClaudeRunner") as mock_runner_class:
            mock_runner = MagicMock()
            mock_runner.run_prompt.return_value = {"result": "ok"}
            mock_runner_class.return_value = mock_runner

            with patch("prompter.main.setup_logging") as mock_setup_logging:
                result = runner.invoke(
                    app,
                    [str(prompts_file), "--output", str(output_file), "--verbose"],
                )

                mock_setup_logging.assert_called_once()
                call_args = mock_setup_logging.call_args
                assert call_args[1]["verbose"] is True

        assert result.exit_code == 0

    def test_timeout_option(self, tmp_path: Path) -> None:
        """Test that timeout option is passed to runner."""
        prompts_file = tmp_path / "prompts.txt"
        prompts_file.write_text("Test prompt", encoding="utf-8")

        output_file = tmp_path / "report.json"

        with patch("prompter.main.ClaudeRunner") as mock_runner_class:
            mock_runner = MagicMock()
            mock_runner.run_prompt.return_value = {"result": "ok"}
            mock_runner_class.return_value = mock_runner

            with patch("prompter.main.setup_logging"):
                result = runner.invoke(
                    app,
                    [
                        str(prompts_file),
                        "--output",
                        str(output_file),
                        "--timeout",
                        "3600",
                    ],
                )

                mock_runner.run_prompt.assert_called_once()
                call_kwargs = mock_runner.run_prompt.call_args[1]
                assert call_kwargs["timeout"] == 3600

        assert result.exit_code == 0

    def test_error_handling(self, tmp_path: Path) -> None:
        """Test that errors during prompt execution are handled gracefully."""
        prompts_file = tmp_path / "prompts.txt"
        prompts_file.write_text("Prompt 1\n---\nPrompt 2", encoding="utf-8")

        output_file = tmp_path / "report.json"

        with patch("prompter.main.ClaudeRunner") as mock_runner_class:
            mock_runner = MagicMock()
            mock_runner.run_prompt.side_effect = [
                Exception("Something went wrong"),
                {"result": "ok"},
            ]
            mock_runner_class.return_value = mock_runner

            with patch("prompter.main.setup_logging"):
                result = runner.invoke(
                    app,
                    [str(prompts_file), "--output", str(output_file)],
                )

        assert result.exit_code == 0
        report = json.loads(output_file.read_text(encoding="utf-8"))
        assert len(report) == 2
        assert report[0]["status"] == "error"
        assert "Something went wrong" in report[0]["error"]
        assert report[1]["status"] == "success"

    def test_empty_prompts_file(self, tmp_path: Path) -> None:
        """Test handling of empty prompts file."""
        prompts_file = tmp_path / "prompts.txt"
        prompts_file.write_text("", encoding="utf-8")

        output_file = tmp_path / "report.json"

        with patch("prompter.main.setup_logging"):
            result = runner.invoke(
                app,
                [str(prompts_file), "--output", str(output_file)],
            )

        assert result.exit_code == 0

    def test_nonexistent_input_file(self, tmp_path: Path) -> None:
        """Test handling of non-existent input file."""
        result = runner.invoke(
            app,
            [str(tmp_path / "nonexistent.txt")],
        )

        assert result.exit_code != 0
