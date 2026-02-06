"""Tests for IO module - PromptReader and SessionLogger."""

import json
from pathlib import Path

import pytest

from src.prompter.io import PromptReader, SessionLogger


class TestPromptReader:
    """Test suite for PromptReader."""

    def test_read_txt_md(self, tmp_path: Path) -> None:
        """Test reading prompts from txt/md file with separator."""
        content = """Prompt 1
---
Prompt 2
---
Prompt 3"""
        test_file = tmp_path / "prompts.txt"
        test_file.write_text(content, encoding="utf-8")

        reader = PromptReader()
        prompts = reader.read(test_file)

        assert prompts == ["Prompt 1", "Prompt 2", "Prompt 3"]

    def test_read_txt_with_whitespace(self, tmp_path: Path) -> None:
        """Test that extra whitespace is stripped from prompts."""
        content = """  Prompt with spaces
---

  Another prompt
"""
        test_file = tmp_path / "prompts.txt"
        test_file.write_text(content, encoding="utf-8")

        reader = PromptReader()
        prompts = reader.read(test_file)

        assert prompts == ["Prompt with spaces", "Another prompt"]

    def test_read_md_file(self, tmp_path: Path) -> None:
        """Test reading prompts from markdown file."""
        content = """# First prompt
---
# Second prompt"""
        test_file = tmp_path / "prompts.md"
        test_file.write_text(content, encoding="utf-8")

        reader = PromptReader()
        prompts = reader.read(test_file)

        assert prompts == ["# First prompt", "# Second prompt"]

    def test_read_json(self, tmp_path: Path) -> None:
        """Test reading prompts from JSON file."""
        prompts_data = ["Prompt 1", "Prompt 2", "Prompt 3"]
        test_file = tmp_path / "prompts.json"
        test_file.write_text(json.dumps(prompts_data), encoding="utf-8")

        reader = PromptReader()
        prompts = reader.read(test_file)

        assert prompts == ["Prompt 1", "Prompt 2", "Prompt 3"]

    def test_read_json_with_whitespace(self, tmp_path: Path) -> None:
        """Test that whitespace is stripped from JSON prompts."""
        prompts_data = ["  Prompt 1  ", "Prompt 2", "  "]
        test_file = tmp_path / "prompts.json"
        test_file.write_text(json.dumps(prompts_data), encoding="utf-8")

        reader = PromptReader()
        prompts = reader.read(test_file)

        assert prompts == ["Prompt 1", "Prompt 2"]

    def test_file_not_found(self) -> None:
        """Test that FileNotFoundError is raised for missing file."""
        reader = PromptReader()

        with pytest.raises(FileNotFoundError):
            reader.read(Path("/nonexistent/path/prompts.txt"))

    def test_unsupported_format(self, tmp_path: Path) -> None:
        """Test that ValueError is raised for unsupported file format."""
        test_file = tmp_path / "prompts.yaml"
        test_file.write_text("key: value", encoding="utf-8")

        reader = PromptReader()

        with pytest.raises(ValueError, match="Unsupported file format"):
            reader.read(test_file)

    def test_json_not_list(self, tmp_path: Path) -> None:
        """Test that ValueError is raised when JSON is not a list."""
        test_file = tmp_path / "prompts.json"
        test_file.write_text('{"key": "value"}', encoding="utf-8")

        reader = PromptReader()

        with pytest.raises(ValueError, match="list of strings"):
            reader.read(test_file)

    def test_json_not_strings(self, tmp_path: Path) -> None:
        """Test that ValueError is raised when JSON list contains non-strings."""
        test_file = tmp_path / "prompts.json"
        test_file.write_text('[1, 2, 3]', encoding="utf-8")

        reader = PromptReader()

        with pytest.raises(ValueError, match="list of strings"):
            reader.read(test_file)

    def test_empty_prompts_filtered(self, tmp_path: Path) -> None:
        """Test that empty prompts are filtered out."""
        content = """Prompt 1
---

---
Prompt 2"""
        test_file = tmp_path / "prompts.txt"
        test_file.write_text(content, encoding="utf-8")

        reader = PromptReader()
        prompts = reader.read(test_file)

        assert prompts == ["Prompt 1", "Prompt 2"]


class TestSessionLogger:
    """Test suite for SessionLogger."""

    def test_save_report(self, tmp_path: Path) -> None:
        """Test saving report to JSON file."""
        report_data = [
            {"prompt": "test1", "result": "response1"},
            {"prompt": "test2", "result": "response2"},
        ]
        output_path = tmp_path / "report.json"

        logger = SessionLogger()
        logger.save_report(report_data, output_path)

        assert output_path.exists()
        saved_data = json.loads(output_path.read_text(encoding="utf-8"))
        assert saved_data == report_data

    def test_save_report_creates_directories(self, tmp_path: Path) -> None:
        """Test that parent directories are created if they don't exist."""
        report_data = [{"prompt": "test", "result": "response"}]
        output_path = tmp_path / "nested" / "dirs" / "report.json"

        logger = SessionLogger()
        logger.save_report(report_data, output_path)

        assert output_path.exists()
        assert output_path.parent.exists()

    def test_save_report_unicode(self, tmp_path: Path) -> None:
        """Test that unicode characters are preserved (ensure_ascii=False)."""
        report_data = [{"prompt": "Привет", "result": "Мир"}]
        output_path = tmp_path / "report.json"

        logger = SessionLogger()
        logger.save_report(report_data, output_path)

        content = output_path.read_text(encoding="utf-8")
        assert "Привет" in content
        assert "Мир" in content

    def test_save_report_indentation(self, tmp_path: Path) -> None:
        """Test that JSON is saved with indent=2."""
        report_data = [{"key": "value"}]
        output_path = tmp_path / "report.json"

        logger = SessionLogger()
        logger.save_report(report_data, output_path)

        content = output_path.read_text(encoding="utf-8")
        expected = json.dumps(report_data, indent=2, ensure_ascii=False)
        assert content == expected
