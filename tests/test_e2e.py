"""End-to-end тесты для Prompter CLI."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from prompter.main import app

runner = CliRunner()


@pytest.fixture
def prompts_file(tmp_path: Path) -> Path:
    """Создаёт временный файл с промптами."""
    file_path = tmp_path / "prompts.txt"
    file_path.write_text("Prompt 1\n---\nPrompt 2", encoding="utf-8")
    return file_path


@pytest.fixture
def mock_run_prompt():
    """Мокает ClaudeRunner.run_prompt."""
    with patch("prompter.main.ClaudeRunner") as mock_class:
        mock_instance = MagicMock()
        mock_instance.run_prompt.return_value = {
            "content": "test",
            "session_id": "123",
        }
        mock_class.return_value = mock_instance
        yield mock_instance


class TestE2E:
    """End-to-end тесты."""

    def test_successful_run(
        self, tmp_path: Path, prompts_file: Path, mock_run_prompt: MagicMock
    ) -> None:
        """Проверяет успешный запуск приложения."""
        output_path = tmp_path / "report.json"

        result = runner.invoke(
            app,
            [str(prompts_file), "--output", str(output_path)],
        )

        assert result.exit_code == 0, f"Ошибка: {result.output}"
        assert output_path.exists()

        report = json.loads(output_path.read_text(encoding="utf-8"))
        assert len(report) == 2
        assert report[0]["prompt"] == "Prompt 1"
        assert report[0]["response"]["content"] == "test"
        assert report[1]["prompt"] == "Prompt 2"

    def test_run_prompt_called_for_each_prompt(
        self, tmp_path: Path, prompts_file: Path, mock_run_prompt: MagicMock
    ) -> None:
        """Проверяет, что run_prompt вызывается для каждого промпта."""
        output_path = tmp_path / "report.json"

        runner.invoke(
            app,
            [str(prompts_file), "--output", str(output_path)],
        )

        assert mock_run_prompt.run_prompt.call_count == 2
        mock_run_prompt.run_prompt.assert_any_call("Prompt 1")
        mock_run_prompt.run_prompt.assert_any_call("Prompt 2")

    def test_verbose_mode(
        self, tmp_path: Path, prompts_file: Path, mock_run_prompt: MagicMock
    ) -> None:
        """Проверяет работу verbose режима."""
        output_path = tmp_path / "report.json"

        result = runner.invoke(
            app,
            [str(prompts_file), "--output", str(output_path), "--verbose"],
        )

        assert result.exit_code == 0

    def test_report_structure(
        self, tmp_path: Path, prompts_file: Path, mock_run_prompt: MagicMock
    ) -> None:
        """Проверяет структуру отчёта."""
        output_path = tmp_path / "report.json"

        runner.invoke(
            app,
            [str(prompts_file), "--output", str(output_path)],
        )

        report = json.loads(output_path.read_text(encoding="utf-8"))

        for item in report:
            assert "prompt_index" in item
            assert "prompt" in item
            assert "response" in item

        assert report[0]["prompt_index"] == 1
        assert report[1]["prompt_index"] == 2

    def test_json_prompts_file(
        self, tmp_path: Path, mock_run_prompt: MagicMock
    ) -> None:
        """Проверяет работу с JSON-файлом промптов."""
        prompts_file = tmp_path / "prompts.json"
        prompts_file.write_text('["Hello", "World"]', encoding="utf-8")
        output_path = tmp_path / "report.json"

        result = runner.invoke(
            app,
            [str(prompts_file), "--output", str(output_path)],
        )

        assert result.exit_code == 0

        report = json.loads(output_path.read_text(encoding="utf-8"))
        assert len(report) == 2
        assert report[0]["prompt"] == "Hello"
        assert report[1]["prompt"] == "World"

    def test_nonexistent_input_file(self, tmp_path: Path) -> None:
        """Проверяет обработку несуществующего файла."""
        result = runner.invoke(
            app,
            [str(tmp_path / "nonexistent.txt")],
        )

        assert result.exit_code != 0

    def test_output_directory_created(
        self, tmp_path: Path, prompts_file: Path, mock_run_prompt: MagicMock
    ) -> None:
        """Проверяет создание вложенных директорий для отчёта."""
        output_path = tmp_path / "nested" / "dir" / "report.json"

        result = runner.invoke(
            app,
            [str(prompts_file), "--output", str(output_path)],
        )

        assert result.exit_code == 0
        assert output_path.exists()
