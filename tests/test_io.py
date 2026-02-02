"""Тесты для модуля io."""

import json
from pathlib import Path

import pytest

from prompter.io import PromptReader, SessionLogger


class TestPromptReader:
    """Тесты для PromptReader."""

    def test_read_txt_md(self, tmp_path: Path) -> None:
        """Проверяет чтение текстового файла с разделителем ---."""
        file_path = tmp_path / "prompts.txt"
        file_path.write_text("Prompt 1\n---\nPrompt 2", encoding="utf-8")

        reader = PromptReader()
        result = reader.read(file_path)

        assert len(result) == 2
        assert result[0] == "Prompt 1"
        assert result[1] == "Prompt 2"

    def test_read_md_file(self, tmp_path: Path) -> None:
        """Проверяет чтение markdown-файла."""
        file_path = tmp_path / "prompts.md"
        file_path.write_text("First\n---\nSecond\n---\nThird", encoding="utf-8")

        reader = PromptReader()
        result = reader.read(file_path)

        assert len(result) == 3
        assert result == ["First", "Second", "Third"]

    def test_read_json(self, tmp_path: Path) -> None:
        """Проверяет чтение JSON-списка."""
        file_path = tmp_path / "prompts.json"
        prompts = ["Prompt A", "Prompt B", "Prompt C"]
        file_path.write_text(json.dumps(prompts), encoding="utf-8")

        reader = PromptReader()
        result = reader.read(file_path)

        assert result == prompts

    def test_read_file_not_found(self) -> None:
        """Проверяет обработку отсутствующего файла."""
        reader = PromptReader()

        with pytest.raises(FileNotFoundError, match="Файл не найден"):
            reader.read(Path("/nonexistent/file.txt"))

    def test_read_unsupported_format(self, tmp_path: Path) -> None:
        """Проверяет обработку неподдерживаемого формата."""
        file_path = tmp_path / "prompts.xml"
        file_path.write_text("<prompts></prompts>", encoding="utf-8")

        reader = PromptReader()

        with pytest.raises(ValueError, match="Неподдерживаемый формат"):
            reader.read(file_path)

    def test_read_strips_whitespace(self, tmp_path: Path) -> None:
        """Проверяет удаление лишних пробелов."""
        file_path = tmp_path / "prompts.txt"
        file_path.write_text("  Prompt 1  \n---\n  Prompt 2  \n", encoding="utf-8")

        reader = PromptReader()
        result = reader.read(file_path)

        assert result == ["Prompt 1", "Prompt 2"]

    def test_read_skips_empty_prompts(self, tmp_path: Path) -> None:
        """Проверяет пропуск пустых промптов."""
        file_path = tmp_path / "prompts.txt"
        file_path.write_text("Prompt 1\n---\n   \n---\nPrompt 2", encoding="utf-8")

        reader = PromptReader()
        result = reader.read(file_path)

        assert len(result) == 2


class TestSessionLogger:
    """Тесты для SessionLogger."""

    def test_save_report(self, tmp_path: Path) -> None:
        """Проверяет сохранение отчёта в JSON."""
        output_path = tmp_path / "report.json"
        report_data = [
            {"prompt": "Hello", "response": "Hi there!"},
            {"prompt": "Bye", "response": "Goodbye!"},
        ]

        logger = SessionLogger()
        logger.save_report(report_data, output_path)

        assert output_path.exists()

        saved_data = json.loads(output_path.read_text(encoding="utf-8"))
        assert saved_data == report_data

    def test_save_report_creates_directories(self, tmp_path: Path) -> None:
        """Проверяет создание родительских директорий."""
        output_path = tmp_path / "nested" / "dir" / "report.json"
        report_data = [{"test": "data"}]

        logger = SessionLogger()
        logger.save_report(report_data, output_path)

        assert output_path.exists()

    def test_save_report_ensure_ascii_false(self, tmp_path: Path) -> None:
        """Проверяет сохранение кириллицы без экранирования."""
        output_path = tmp_path / "report.json"
        report_data = [{"prompt": "Привет", "response": "Здравствуйте!"}]

        logger = SessionLogger()
        logger.save_report(report_data, output_path)

        content = output_path.read_text(encoding="utf-8")
        assert "Привет" in content
        assert "\\u" not in content

    def test_save_report_indent(self, tmp_path: Path) -> None:
        """Проверяет форматирование с отступами."""
        output_path = tmp_path / "report.json"
        report_data = [{"key": "value"}]

        logger = SessionLogger()
        logger.save_report(report_data, output_path)

        content = output_path.read_text(encoding="utf-8")
        assert "  " in content  # indent=2
