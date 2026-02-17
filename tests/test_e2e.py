"""End-to-end tests: real assistant execution (TC-04).

These tests launch a real AI assistant (claude CLI by default).
Marked with @pytest.mark.e2e — exclude from regular runs:
    pytest -m "not e2e"
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.e2e
class TestEndToEndExecution:
    """E2E tests using real claude CLI."""

    @pytest.fixture(autouse=True)
    def _check_claude_available(self) -> None:
        """Skip if claude CLI is not available."""
        if shutil.which("claude") is None:
            pytest.skip("claude CLI not found in $PATH")

    def test_full_cycle(self, tmp_path: Path) -> None:
        """TC-04: full cycle with specs/test_prompts.adoc."""
        prompts_file = Path("specs/test_prompts.adoc").resolve()
        assert prompts_file.is_file(), f"Missing: {prompts_file}"

        report_path = tmp_path / "report.json"

        result = subprocess.run(
            [
                "python", "-m", "prompter",
                str(prompts_file),
                "-o", str(report_path),
            ],
            capture_output=True,
            text=True,
            timeout=600,
            cwd=str(tmp_path),
        )

        # Report file exists and is valid JSON
        assert report_path.is_file(), "report.json not created"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert isinstance(report, list)
        assert len(report) > 0

        # All prompts succeeded
        for i, entry in enumerate(report):
            assert entry["status"] == "success", (
                f"Prompt {i + 1} ({entry.get('title', '?')}): "
                f"status={entry['status']}, error={entry.get('error')}"
            )

        # tstutil artifact created
        cli_file = tmp_path / "src" / "tstutil" / "cli.py"
        assert cli_file.is_file(), "src/tstutil/cli.py not created by assistant"

        # No permission denials in output
        combined_output = (result.stdout or "") + (result.stderr or "")
        assert "permission_denied" not in combined_output.lower()
        assert "permission denied" not in combined_output.lower()

    def test_full_cycle_md(self, tmp_path: Path) -> None:
        """TC-04: full cycle with specs/test_prompts.md."""
        prompts_file = Path("specs/test_prompts.md").resolve()
        assert prompts_file.is_file(), f"Missing: {prompts_file}"

        report_path = tmp_path / "report.json"

        result = subprocess.run(
            [
                "python", "-m", "prompter",
                str(prompts_file),
                "-o", str(report_path),
            ],
            capture_output=True,
            text=True,
            timeout=600,
            cwd=str(tmp_path),
        )

        assert result.returncode == 0, (
            f"Exit code: {result.returncode}\n"
            f"stderr: {result.stderr[:500] if result.stderr else ''}"
        )

        # Report file exists and is valid JSON
        assert report_path.is_file(), "report.json not created"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        assert isinstance(report, list)
        assert len(report) > 0

        # All prompts succeeded
        for i, entry in enumerate(report):
            assert entry["status"] == "success", (
                f"Prompt {i + 1} ({entry.get('title', '?')}): "
                f"status={entry['status']}, error={entry.get('error')}"
            )

        # tstutil artifact created
        cli_file = tmp_path / "src" / "tstutil" / "cli.py"
        assert cli_file.is_file(), "src/tstutil/cli.py not created by assistant"
