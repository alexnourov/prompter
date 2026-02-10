"""Tests for report generation and saving.

Tests cover requirements: REP-02, REP-03, REP-04, REP-05, REP-06 (TC-15).
"""

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from prompter.models import PromptResult
from prompter.report import save_report


class TestReportSaving:
    """Tests for save_report functionality."""

    def test_save_report_success(self, tmp_path: Path) -> None:
        """Test that 'error' field is NOT included for status='success' (REP-06)."""
        output_path = tmp_path / "report.json"
        results = [
            PromptResult(
                prompt="test prompt",
                claude_response={"result": "ok"},
                timestamp="2024-01-01T12:00:00",
                status="success",
                error=None,
            )
        ]

        save_report(results, output_path)

        # Read and verify JSON
        with open(output_path, encoding="utf-8") as f:
            data = json.load(f)

        assert len(data) == 1
        record = data[0]
        assert record["prompt"] == "test prompt"
        assert record["status"] == "success"
        assert "error" not in record  # Key must NOT be present

    def test_save_report_error(self, tmp_path: Path) -> None:
        """Test that 'error' field IS included for status='error' (REP-06)."""
        output_path = tmp_path / "report.json"
        results = [
            PromptResult(
                prompt="test prompt",
                claude_response=None,
                timestamp="2024-01-01T12:00:00",
                status="error",
                error="some error message",
            )
        ]

        save_report(results, output_path)

        # Read and verify JSON
        with open(output_path, encoding="utf-8") as f:
            data = json.load(f)

        assert len(data) == 1
        record = data[0]
        assert record["status"] == "error"
        assert "error" in record  # Key must be present
        assert record["error"] == "some error message"

    def test_save_report_timeout(self, tmp_path: Path) -> None:
        """Test that 'error' field IS included for status='timeout' (REP-06)."""
        output_path = tmp_path / "report.json"
        results = [
            PromptResult(
                prompt="test prompt",
                claude_response=None,
                timestamp="2024-01-01T12:00:00",
                status="timeout",
                error="timeout exceeded",
            )
        ]

        save_report(results, output_path)

        # Read and verify JSON
        with open(output_path, encoding="utf-8") as f:
            data = json.load(f)

        assert len(data) == 1
        record = data[0]
        assert record["status"] == "timeout"
        assert "error" in record  # Key must be present
        assert record["error"] == "timeout exceeded"

    def test_save_report_skipped(self, tmp_path: Path) -> None:
        """Test that 'error' field is NOT included for status='skipped' (REP-06)."""
        output_path = tmp_path / "report.json"
        results = [
            PromptResult(
                prompt="test prompt",
                claude_response=None,
                timestamp="2024-01-01T12:00:00",
                status="skipped",
                error=None,
            )
        ]

        save_report(results, output_path)

        # Read and verify JSON
        with open(output_path, encoding="utf-8") as f:
            data = json.load(f)

        assert len(data) == 1
        record = data[0]
        assert record["status"] == "skipped"
        assert "error" not in record  # Key must NOT be present

    def test_save_report_utf8(self, tmp_path: Path) -> None:
        """Test UTF-8 encoding with Cyrillic characters (REP-02)."""
        output_path = tmp_path / "report.json"
        results = [
            PromptResult(
                prompt="Тестовый промпт с кириллицей © €",
                claude_response={"answer": "Ответ на русском"},
                timestamp="2024-01-01T12:00:00",
                status="success",
            )
        ]

        save_report(results, output_path)

        # Read raw file to verify encoding
        raw_content = output_path.read_text(encoding="utf-8")
        assert "Тестовый промпт с кириллицей © €" in raw_content
        assert "Ответ на русском" in raw_content

        # Verify JSON parsing
        with open(output_path, encoding="utf-8") as f:
            data = json.load(f)

        assert data[0]["prompt"] == "Тестовый промпт с кириллицей © €"
        assert data[0]["claude_response"]["answer"] == "Ответ на русском"

    def test_save_report_creates_dirs(self, tmp_path: Path) -> None:
        """Test that parent directories are created if they don't exist."""
        output_path = tmp_path / "nested" / "deep" / "path" / "report.json"
        results = [
            PromptResult(
                prompt="test",
                claude_response=None,
                timestamp="2024-01-01T12:00:00",
                status="success",
            )
        ]

        # Parent dirs should not exist yet
        assert not output_path.parent.exists()

        save_report(results, output_path)

        # Verify dirs were created and file exists
        assert output_path.parent.exists()
        assert output_path.exists()

    def test_save_report_overwrites_existing(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """Test that existing file is overwritten with WARNING log."""
        output_path = tmp_path / "report.json"

        # Create initial file
        results1 = [
            PromptResult(
                prompt="first",
                claude_response=None,
                timestamp="2024-01-01T12:00:00",
                status="success",
            )
        ]
        save_report(results1, output_path)

        # Overwrite with new data
        results2 = [
            PromptResult(
                prompt="second",
                claude_response=None,
                timestamp="2024-01-01T13:00:00",
                status="success",
            )
        ]

        import logging

        with caplog.at_level(logging.WARNING):
            save_report(results2, output_path)

        # Check warning was logged
        assert any("already exists and will be overwritten" in record.message for record in caplog.records)

        # Verify new data
        with open(output_path, encoding="utf-8") as f:
            data = json.load(f)

        assert len(data) == 1
        assert data[0]["prompt"] == "second"

    def test_save_report_multiple_results(self, tmp_path: Path) -> None:
        """Test saving multiple results in one report."""
        output_path = tmp_path / "report.json"
        results = [
            PromptResult(
                prompt="prompt 1",
                claude_response={"result": "1"},
                timestamp="2024-01-01T12:00:00",
                status="success",
            ),
            PromptResult(
                prompt="prompt 2",
                claude_response=None,
                timestamp="2024-01-01T12:01:00",
                status="error",
                error="failed",
            ),
            PromptResult(
                prompt="prompt 3",
                claude_response=None,
                timestamp="2024-01-01T12:02:00",
                status="skipped",
            ),
        ]

        save_report(results, output_path)

        with open(output_path, encoding="utf-8") as f:
            data = json.load(f)

        assert len(data) == 3
        assert data[0]["prompt"] == "prompt 1"
        assert "error" not in data[0]
        assert data[1]["prompt"] == "prompt 2"
        assert "error" in data[1]
        assert data[2]["prompt"] == "prompt 3"
        assert "error" not in data[2]


class TestAtomicWrite:
    """Tests for atomic write functionality (REP-03)."""

    def test_atomic_write(self, tmp_path: Path) -> None:
        """Test that write is atomic: temp file → os.replace (REP-03)."""
        output_path = tmp_path / "report.json"
        results = [
            PromptResult(
                prompt="test",
                claude_response=None,
                timestamp="2024-01-01T12:00:00",
                status="success",
            )
        ]

        # Mock os.replace to verify it's called
        with patch("prompter.report.os.replace") as mock_replace:
            save_report(results, output_path)

            # Verify os.replace was called with correct arguments
            expected_temp = output_path.with_suffix(".tmp")
            mock_replace.assert_called_once_with(expected_temp, output_path)

    def test_atomic_write_cleans_temp_on_error(self, tmp_path: Path) -> None:
        """Test that temporary file is cleaned up if error occurs during write."""
        output_path = tmp_path / "report.json"
        temp_path = output_path.with_suffix(".tmp")
        results = [
            PromptResult(
                prompt="test",
                claude_response=None,
                timestamp="2024-01-01T12:00:00",
                status="success",
            )
        ]

        # Mock json.dump to raise an error
        with patch("prompter.report.json.dump", side_effect=ValueError("mock error")):
            with pytest.raises(ValueError, match="mock error"):
                save_report(results, output_path)

            # Verify temp file was cleaned up
            assert not temp_path.exists()

    def test_atomic_write_real_scenario(self, tmp_path: Path) -> None:
        """Test real atomic write without mocks - verify temp file doesn't remain."""
        output_path = tmp_path / "report.json"
        temp_path = output_path.with_suffix(".tmp")
        results = [
            PromptResult(
                prompt="test",
                claude_response={"result": "ok"},
                timestamp="2024-01-01T12:00:00",
                status="success",
            )
        ]

        save_report(results, output_path)

        # Verify final file exists and temp file was removed
        assert output_path.exists()
        assert not temp_path.exists()

        # Verify content is correct
        with open(output_path, encoding="utf-8") as f:
            data = json.load(f)
        assert len(data) == 1
        assert data[0]["prompt"] == "test"


class TestJSONFormat:
    """Tests for JSON format requirements (REP-02, REP-06)."""

    def test_json_format_indent(self, tmp_path: Path) -> None:
        """Test that JSON is formatted with indent=2."""
        output_path = tmp_path / "report.json"
        results = [
            PromptResult(
                prompt="test",
                claude_response={"nested": {"value": 1}},
                timestamp="2024-01-01T12:00:00",
                status="success",
            )
        ]

        save_report(results, output_path)

        # Read raw content and check indentation
        raw_content = output_path.read_text(encoding="utf-8")
        # Should have 2-space indentation
        assert "  {" in raw_content or "  \"" in raw_content

    def test_json_format_ensure_ascii_false(self, tmp_path: Path) -> None:
        """Test that ensure_ascii=False (non-ASCII chars not escaped)."""
        output_path = tmp_path / "report.json"
        results = [
            PromptResult(
                prompt="тест",
                claude_response=None,
                timestamp="2024-01-01T12:00:00",
                status="success",
            )
        ]

        save_report(results, output_path)

        # Read raw content - should contain actual UTF-8 chars, not \uXXXX
        raw_content = output_path.read_text(encoding="utf-8")
        assert "тест" in raw_content
        assert "\\u" not in raw_content  # No Unicode escapes

    def test_json_all_fields_present(self, tmp_path: Path) -> None:
        """Test that all required fields are present in JSON."""
        output_path = tmp_path / "report.json"
        results = [
            PromptResult(
                prompt="test prompt",
                claude_response={"result": "ok"},
                timestamp="2024-01-01T12:00:00",
                status="success",
            )
        ]

        save_report(results, output_path)

        with open(output_path, encoding="utf-8") as f:
            data = json.load(f)

        record = data[0]
        # Required fields
        assert "prompt" in record
        assert "claude_response" in record
        assert "timestamp" in record
        assert "status" in record
        # Verify values
        assert record["prompt"] == "test prompt"
        assert record["claude_response"] == {"result": "ok"}
        assert record["timestamp"] == "2024-01-01T12:00:00"
        assert record["status"] == "success"
