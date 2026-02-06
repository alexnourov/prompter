"""End-to-end tests for Prompter CLI."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from prompter.main import app


runner = CliRunner()


class TestE2E:
    """End-to-end test suite for Prompter CLI."""

    @patch("prompter.main.ClaudeRunner")
    def test_successful_run(
        self, mock_runner_class: MagicMock, tmp_path: Path
    ) -> None:
        """Test successful execution with mocked ClaudeRunner."""
        prompts_file = tmp_path / "prompts.txt"
        prompts_file.write_text("First prompt\n---\nSecond prompt", encoding="utf-8")

        output_file = tmp_path / "report.json"

        mock_runner = MagicMock()
        mock_runner.run_prompt.return_value = {
            "content": "test",
            "session_id": "123",
        }
        mock_runner_class.return_value = mock_runner

        result = runner.invoke(
            app,
            [str(prompts_file), "--output", str(output_file)],
        )

        assert result.exit_code == 0, f"CLI failed: {result.output}"

        assert output_file.exists(), "Output report file was not created"

        report = json.loads(output_file.read_text(encoding="utf-8"))

        assert len(report) == 2
        assert report[0]["prompt"] == "First prompt"
        assert report[0]["status"] == "success"
        assert report[0]["claude_response"]["content"] == "test"
        assert report[1]["prompt"] == "Second prompt"
        assert report[1]["status"] == "success"

    @patch("prompter.main.ClaudeRunner")
    def test_json_prompts_file(
        self, mock_runner_class: MagicMock, tmp_path: Path
    ) -> None:
        """Test execution with JSON prompts file."""
        prompts_file = tmp_path / "prompts.json"
        prompts_data = ["Prompt one", "Prompt two", "Prompt three"]
        prompts_file.write_text(json.dumps(prompts_data), encoding="utf-8")

        output_file = tmp_path / "report.json"

        mock_runner = MagicMock()
        mock_runner.run_prompt.return_value = {"result": "ok"}
        mock_runner_class.return_value = mock_runner

        result = runner.invoke(
            app,
            [str(prompts_file), "--output", str(output_file)],
        )

        assert result.exit_code == 0

        report = json.loads(output_file.read_text(encoding="utf-8"))
        assert len(report) == 3

    @patch("prompter.main.ClaudeRunner")
    def test_verbose_flag(
        self, mock_runner_class: MagicMock, tmp_path: Path
    ) -> None:
        """Test that verbose flag is passed correctly."""
        prompts_file = tmp_path / "prompts.txt"
        prompts_file.write_text("Test prompt", encoding="utf-8")

        output_file = tmp_path / "report.json"

        mock_runner = MagicMock()
        mock_runner.run_prompt.return_value = {"result": "ok"}
        mock_runner_class.return_value = mock_runner

        result = runner.invoke(
            app,
            [str(prompts_file), "--output", str(output_file), "--verbose"],
        )

        assert result.exit_code == 0

        mock_runner.run_prompt.assert_called_once()
        call_kwargs = mock_runner.run_prompt.call_args[1]
        assert call_kwargs["verbose"] is True

    @patch("prompter.main.ClaudeRunner")
    def test_timeout_flag(
        self, mock_runner_class: MagicMock, tmp_path: Path
    ) -> None:
        """Test that timeout flag is passed correctly."""
        prompts_file = tmp_path / "prompts.txt"
        prompts_file.write_text("Test prompt", encoding="utf-8")

        output_file = tmp_path / "report.json"

        mock_runner = MagicMock()
        mock_runner.run_prompt.return_value = {"result": "ok"}
        mock_runner_class.return_value = mock_runner

        result = runner.invoke(
            app,
            [str(prompts_file), "--output", str(output_file), "--timeout", "1800"],
        )

        assert result.exit_code == 0

        call_kwargs = mock_runner.run_prompt.call_args[1]
        assert call_kwargs["timeout"] == 1800

    @patch("prompter.main.ClaudeRunner")
    def test_error_handling(
        self, mock_runner_class: MagicMock, tmp_path: Path
    ) -> None:
        """Test that errors are handled gracefully and recorded in report."""
        prompts_file = tmp_path / "prompts.txt"
        prompts_file.write_text("Failing prompt\n---\nGood prompt", encoding="utf-8")

        output_file = tmp_path / "report.json"

        mock_runner = MagicMock()
        mock_runner.run_prompt.side_effect = [
            RuntimeError("Claude crashed"),
            {"result": "ok"},
        ]
        mock_runner_class.return_value = mock_runner

        result = runner.invoke(
            app,
            [str(prompts_file), "--output", str(output_file)],
        )

        assert result.exit_code == 0

        report = json.loads(output_file.read_text(encoding="utf-8"))

        assert len(report) == 2
        assert report[0]["status"] == "error"
        assert "Claude crashed" in report[0]["error"]
        assert report[1]["status"] == "success"

    def test_nonexistent_input_file(self, tmp_path: Path) -> None:
        """Test error when input file doesn't exist."""
        nonexistent = tmp_path / "nonexistent.txt"

        result = runner.invoke(app, [str(nonexistent)])

        assert result.exit_code != 0

    @patch("prompter.main.ClaudeRunner")
    def test_empty_prompts_file(
        self, mock_runner_class: MagicMock, tmp_path: Path
    ) -> None:
        """Test handling of empty prompts file."""
        prompts_file = tmp_path / "prompts.txt"
        prompts_file.write_text("", encoding="utf-8")

        output_file = tmp_path / "report.json"

        result = runner.invoke(
            app,
            [str(prompts_file), "--output", str(output_file)],
        )

        assert result.exit_code == 0

    @patch("prompter.main.ClaudeRunner")
    def test_report_contains_timestamps(
        self, mock_runner_class: MagicMock, tmp_path: Path
    ) -> None:
        """Test that report entries contain timestamps."""
        prompts_file = tmp_path / "prompts.txt"
        prompts_file.write_text("Test prompt", encoding="utf-8")

        output_file = tmp_path / "report.json"

        mock_runner = MagicMock()
        mock_runner.run_prompt.return_value = {"result": "ok"}
        mock_runner_class.return_value = mock_runner

        result = runner.invoke(
            app,
            [str(prompts_file), "--output", str(output_file)],
        )

        assert result.exit_code == 0

        report = json.loads(output_file.read_text(encoding="utf-8"))

        assert "timestamp" in report[0]
        assert "T" in report[0]["timestamp"]
