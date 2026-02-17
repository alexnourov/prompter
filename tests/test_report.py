"""Tests for the prompter.report module."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from prompter.models import PromptResult
from prompter.report import save_report


def _make_result(
    status: str = "success",
    error: str | None = None,
    prompt: str = "test prompt",
    title: str = "Test Title",
    response: dict | None = None,
    timestamp: str = "2026-01-01T12:00:00",
) -> PromptResult:
    """Helper to create a PromptResult with sensible defaults."""
    return PromptResult(
        prompt=prompt,
        title=title,
        assistant_response=response,
        timestamp=timestamp,
        status=status,
        error=error,
    )


class TestSaveReportFields:
    """Tests for field inclusion/exclusion rules."""

    def test_save_report_success(self, tmp_path: Path) -> None:
        """status='success': no 'error' key; 'title' is a string."""
        out = tmp_path / "report.json"
        save_report([_make_result(status="success")], out)

        records = json.loads(out.read_text(encoding="utf-8"))
        assert len(records) == 1
        assert "error" not in records[0]
        assert isinstance(records[0]["title"], str)

    def test_save_report_error(self, tmp_path: Path) -> None:
        """status='error': 'error' key is present."""
        out = tmp_path / "report.json"
        save_report([_make_result(status="error", error="some error")], out)

        records = json.loads(out.read_text(encoding="utf-8"))
        assert records[0]["error"] == "some error"

    def test_save_report_timeout(self, tmp_path: Path) -> None:
        """status='timeout': 'error' key is present."""
        out = tmp_path / "report.json"
        save_report([_make_result(status="timeout", error="timed out")], out)

        records = json.loads(out.read_text(encoding="utf-8"))
        assert records[0]["error"] == "timed out"

    def test_save_report_skipped(self, tmp_path: Path) -> None:
        """status='skipped': no 'error' key."""
        out = tmp_path / "report.json"
        save_report([_make_result(status="skipped")], out)

        records = json.loads(out.read_text(encoding="utf-8"))
        assert "error" not in records[0]


class TestSaveReportEncoding:
    """Tests for encoding and character preservation."""

    def test_save_report_utf8(self, tmp_path: Path) -> None:
        """Cyrillic characters in prompt are preserved in JSON."""
        out = tmp_path / "report.json"
        save_report(
            [_make_result(prompt="Кириллический промпт", title="Заголовок")],
            out,
        )

        raw = out.read_text(encoding="utf-8")
        assert "Кириллический промпт" in raw
        assert "Заголовок" in raw

        records = json.loads(raw)
        assert records[0]["prompt"] == "Кириллический промпт"
        assert records[0]["title"] == "Заголовок"


class TestSaveReportDirs:
    """Tests for directory creation."""

    def test_save_report_creates_dirs(self, tmp_path: Path) -> None:
        """Parent directories are created when they don't exist."""
        out = tmp_path / "a" / "b" / "c" / "report.json"
        assert not out.parent.exists()

        save_report([_make_result()], out)

        assert out.exists()
        records = json.loads(out.read_text(encoding="utf-8"))
        assert len(records) == 1


class TestSaveReportAtomic:
    """Tests for atomic write behavior (REP-03)."""

    def test_atomic_write(self, tmp_path: Path) -> None:
        """REP-03: Data is written to a temp file, then os.replace() moves it."""
        out = tmp_path / "report.json"
        tmp_files_written: list[str] = []
        replace_calls: list[tuple] = []

        original_mkstemp = tempfile.mkstemp
        original_replace = os.replace

        def mock_mkstemp(**kwargs):
            fd, path = original_mkstemp(**kwargs)
            tmp_files_written.append(path)
            return fd, path

        def mock_replace(src, dst):
            replace_calls.append((src, dst))
            return original_replace(src, dst)

        with patch("prompter.report.tempfile.mkstemp", side_effect=mock_mkstemp), \
             patch("prompter.report.os.replace", side_effect=mock_replace):
            save_report([_make_result()], out)

        # Temp file was created in the same directory as the output
        assert len(tmp_files_written) == 1
        assert Path(tmp_files_written[0]).parent == out.resolve().parent

        # os.replace was called: temp → target
        assert len(replace_calls) == 1
        src, dst = replace_calls[0]
        assert src == tmp_files_written[0]
        assert Path(dst) == out.resolve()

        # Final file exists and is valid JSON
        assert out.exists()
        records = json.loads(out.read_text(encoding="utf-8"))
        assert len(records) == 1


class TestSaveReportOverwrite:
    """Tests for overwrite warning."""

    def test_overwrite_warning(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """WARNING logged when overwriting an existing report."""
        out = tmp_path / "report.json"
        out.write_text("[]")

        with caplog.at_level("WARNING", logger="prompter.report"):
            save_report([_make_result()], out)

        assert any("already exists" in rec.message for rec in caplog.records)

    def test_info_log_on_save(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """INFO logged after successful save."""
        out = tmp_path / "report.json"

        with caplog.at_level("INFO", logger="prompter.report"):
            save_report([_make_result()], out)

        assert any("Report saved" in rec.message for rec in caplog.records)
