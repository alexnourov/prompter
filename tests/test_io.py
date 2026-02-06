"""Tests for IO module."""

import json
from pathlib import Path

import pytest

from prompter.io import PromptReader, SessionLogger


class TestPromptReader:
    """Test suite for PromptReader class."""

    def test_read_txt_md(self, tmp_path: Path) -> None:
        """Test reading prompts from txt/md file with --- separator."""
        file_path = tmp_path / "prompts.txt"
        file_path.write_text("Prompt 1\n---\nPrompt 2", encoding="utf-8")

        reader = PromptReader()
        prompts = reader.read(file_path)

        assert len(prompts) == 2
        assert prompts[0] == "Prompt 1"
        assert prompts[1] == "Prompt 2"

    def test_read_txt_with_extra_whitespace(self, tmp_path: Path) -> None:
        """Test that whitespace is properly stripped."""
        file_path = tmp_path / "prompts.md"
        file_path.write_text("  Prompt 1  \n---\n  Prompt 2  \n---\n", encoding="utf-8")

        reader = PromptReader()
        prompts = reader.read(file_path)

        assert len(prompts) == 2
        assert prompts[0] == "Prompt 1"
        assert prompts[1] == "Prompt 2"

    def test_read_json(self, tmp_path: Path) -> None:
        """Test reading prompts from JSON file."""
        file_path = tmp_path / "prompts.json"
        data = ["First prompt", "Second prompt", "Third prompt"]
        file_path.write_text(json.dumps(data), encoding="utf-8")

        reader = PromptReader()
        prompts = reader.read(file_path)

        assert len(prompts) == 3
        assert prompts[0] == "First prompt"
        assert prompts[1] == "Second prompt"
        assert prompts[2] == "Third prompt"

    def test_read_file_not_found(self, tmp_path: Path) -> None:
        """Test FileNotFoundError for missing file."""
        file_path = tmp_path / "nonexistent.txt"

        reader = PromptReader()

        with pytest.raises(FileNotFoundError):
            reader.read(file_path)

    def test_read_unsupported_format(self, tmp_path: Path) -> None:
        """Test ValueError for unsupported file format."""
        file_path = tmp_path / "prompts.yaml"
        file_path.write_text("test", encoding="utf-8")

        reader = PromptReader()

        with pytest.raises(ValueError, match="Unsupported file format"):
            reader.read(file_path)

    def test_read_json_invalid_type(self, tmp_path: Path) -> None:
        """Test ValueError when JSON is not a list."""
        file_path = tmp_path / "prompts.json"
        file_path.write_text('{"key": "value"}', encoding="utf-8")

        reader = PromptReader()

        with pytest.raises(ValueError, match="must contain a list"):
            reader.read(file_path)


class TestSessionLogger:
    """Test suite for SessionLogger class."""

    def test_save_report(self, tmp_path: Path) -> None:
        """Test saving report to JSON file."""
        output_path = tmp_path / "report.json"
        report_data = [
            {"prompt": "Hello", "response": "Hi there"},
            {"prompt": "How are you?", "response": "I'm fine"},
        ]

        logger = SessionLogger()
        logger.save_report(report_data, output_path)

        assert output_path.exists()

        saved_data = json.loads(output_path.read_text(encoding="utf-8"))
        assert saved_data == report_data

    def test_save_report_creates_parent_dirs(self, tmp_path: Path) -> None:
        """Test that parent directories are created if they don't exist."""
        output_path = tmp_path / "nested" / "dir" / "report.json"
        report_data = [{"test": "data"}]

        logger = SessionLogger()
        logger.save_report(report_data, output_path)

        assert output_path.exists()
        assert output_path.parent.exists()

    def test_save_report_unicode(self, tmp_path: Path) -> None:
        """Test that unicode characters are preserved (ensure_ascii=False)."""
        output_path = tmp_path / "report.json"
        report_data = [{"prompt": "Привет", "response": "Здравствуйте"}]

        logger = SessionLogger()
        logger.save_report(report_data, output_path)

        content = output_path.read_text(encoding="utf-8")
        assert "Привет" in content
        assert "Здравствуйте" in content
