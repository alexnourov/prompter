"""Tests for CLI application.

Tests cover requirements: INT-01..04, ERR-10, ERR-11, CLI-01..05.
Includes TC-09 (interruption scenarios).
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from prompter.cli import app
from prompter.models import SigtermReceived

runner = CliRunner()


class TestInterruption:
    """Tests for interruption handling (TC-09, INT-01, INT-03)."""

    def test_interrupt_repeat(self, tmp_path: Path) -> None:
        """Test (R)epeat option after KeyboardInterrupt (TC-09, scenario 2)."""
        # Create prompts file
        prompts_file = tmp_path / "prompts.txt"
        prompts_file.write_text("meta\n---\nPrompt 1\n---\nPrompt 2")
        output_file = tmp_path / "report.json"

        # Mock run_prompt: first call raises KeyboardInterrupt, next two succeed
        mock_run_prompt = MagicMock()
        mock_run_prompt.side_effect = [
            KeyboardInterrupt(),  # First call
            ({"result": "ok"}, "sess1"),  # Repeat of first
            ({"result": "ok"}, "sess1"),  # Second prompt
        ]

        # Mock input to return "R" (repeat)
        mock_input = MagicMock(return_value="R")

        with patch("prompter.cli.run_prompt", mock_run_prompt), \
             patch("prompter.cli.input", mock_input), \
             patch("prompter.cli.shutil.which", return_value="/usr/bin/claude"):

            result = runner.invoke(app, [str(prompts_file), "-o", str(output_file)])

            # Should succeed
            assert result.exit_code == 0

            # run_prompt should be called 3 times (1st + repeat + 2nd)
            assert mock_run_prompt.call_count == 3

            # Verify report
            with open(output_file) as f:
                report = json.load(f)
            assert len(report) == 2
            assert all(r["status"] == "success" for r in report)

    def test_interrupt_next(self, tmp_path: Path) -> None:
        """Test (N)ext option after KeyboardInterrupt (TC-09, scenario 3)."""
        # Create prompts file
        prompts_file = tmp_path / "prompts.txt"
        prompts_file.write_text("meta\n---\nPrompt 1\n---\nPrompt 2")
        output_file = tmp_path / "report.json"

        # Mock run_prompt: first call raises KeyboardInterrupt, second succeeds
        mock_run_prompt = MagicMock()
        mock_run_prompt.side_effect = [
            KeyboardInterrupt(),  # First call
            ({"result": "ok"}, "sess1"),  # Second prompt
        ]

        # Mock input to return "N" (next/skip)
        mock_input = MagicMock(return_value="N")

        with patch("prompter.cli.run_prompt", mock_run_prompt), \
             patch("prompter.cli.input", mock_input), \
             patch("prompter.cli.shutil.which", return_value="/usr/bin/claude"):

            result = runner.invoke(app, [str(prompts_file), "-o", str(output_file)])

            # Should succeed
            assert result.exit_code == 0

            # run_prompt should be called twice
            assert mock_run_prompt.call_count == 2

            # Verify report
            with open(output_file) as f:
                report = json.load(f)
            assert len(report) == 2
            assert report[0]["status"] == "skipped"
            assert report[1]["status"] == "success"

    def test_interrupt_exit(self, tmp_path: Path) -> None:
        """Test (E)xit option after KeyboardInterrupt (TC-09, scenario 4, INT-03)."""
        # Create prompts file
        prompts_file = tmp_path / "prompts.txt"
        prompts_file.write_text("meta\n---\nPrompt 1\n---\nPrompt 2\n---\nPrompt 3")
        output_file = tmp_path / "report.json"

        # Mock run_prompt: first call raises KeyboardInterrupt
        mock_run_prompt = MagicMock()
        mock_run_prompt.side_effect = [KeyboardInterrupt()]

        # Mock input to return "E" (exit)
        mock_input = MagicMock(return_value="E")

        with patch("prompter.cli.run_prompt", mock_run_prompt), \
             patch("prompter.cli.input", mock_input), \
             patch("prompter.cli.shutil.which", return_value="/usr/bin/claude"):

            result = runner.invoke(app, [str(prompts_file), "-o", str(output_file)])

            # Should succeed (exit is clean shutdown)
            assert result.exit_code == 0

            # run_prompt should be called once
            assert mock_run_prompt.call_count == 1

            # Verify report
            with open(output_file) as f:
                report = json.load(f)
            assert len(report) == 1  # Only first prompt
            assert report[0]["status"] == "error"
            assert "error" in report[0]
            assert "Interrupted by user" in report[0]["error"]

    def test_interrupt_invalid_then_repeat(self, tmp_path: Path) -> None:
        """Test invalid input followed by (R)epeat (TC-09, scenario 5)."""
        # Create prompts file
        prompts_file = tmp_path / "prompts.txt"
        prompts_file.write_text("meta\n---\nPrompt 1\n---\nPrompt 2")
        output_file = tmp_path / "report.json"

        # Mock run_prompt: first call raises KeyboardInterrupt, next two succeed
        mock_run_prompt = MagicMock()
        mock_run_prompt.side_effect = [
            KeyboardInterrupt(),  # First call
            ({"result": "ok"}, "sess1"),  # Repeat of first
            ({"result": "ok"}, "sess1"),  # Second prompt
        ]

        # Mock input: first returns "X" (invalid), second returns "R"
        mock_input = MagicMock(side_effect=["X", "R"])

        with patch("prompter.cli.run_prompt", mock_run_prompt), \
             patch("prompter.cli.input", mock_input), \
             patch("prompter.cli.shutil.which", return_value="/usr/bin/claude"):

            result = runner.invoke(app, [str(prompts_file), "-o", str(output_file)])

            # Should succeed
            assert result.exit_code == 0

            # input() should be called twice (invalid, then valid)
            assert mock_input.call_count == 2

            # run_prompt should be called 3 times (1st + repeat + 2nd)
            assert mock_run_prompt.call_count == 3

    def test_interrupt_next_first_prompt_new_session(self, tmp_path: Path) -> None:
        """Test (N)ext on first prompt establishes new session (TC-09, scenario 6)."""
        # Create prompts file
        prompts_file = tmp_path / "prompts.txt"
        prompts_file.write_text("meta\n---\nPrompt 1\n---\nPrompt 2")
        output_file = tmp_path / "report.json"

        # Mock run_prompt: first call raises KeyboardInterrupt, second returns new session
        mock_run_prompt = MagicMock()
        mock_run_prompt.side_effect = [
            KeyboardInterrupt(),  # First call
            ({"result": "ok"}, "sess_new"),  # Second prompt (new session)
        ]

        # Mock input to return "N" (next/skip)
        mock_input = MagicMock(return_value="N")

        with patch("prompter.cli.run_prompt", mock_run_prompt), \
             patch("prompter.cli.input", mock_input), \
             patch("prompter.cli.shutil.which", return_value="/usr/bin/claude"):

            result = runner.invoke(app, [str(prompts_file), "-o", str(output_file)])

            # Should succeed (no session integrity error since session_id was None)
            assert result.exit_code == 0

            # Verify report
            with open(output_file) as f:
                report = json.load(f)
            assert len(report) == 2
            assert report[0]["status"] == "skipped"
            assert report[1]["status"] == "success"


class TestSigterm:
    """Tests for SIGTERM handling (TC-09, scenario 7, INT-04)."""

    def test_sigterm_graceful_termination(self, tmp_path: Path) -> None:
        """Test graceful termination on SIGTERM (TC-09, scenario 7)."""
        # Create prompts file
        prompts_file = tmp_path / "prompts.txt"
        prompts_file.write_text("meta\n---\nPrompt 1\n---\nPrompt 2\n---\nPrompt 3")
        output_file = tmp_path / "report.json"

        # Mock run_prompt: first call raises SigtermReceived
        mock_run_prompt = MagicMock()
        mock_run_prompt.side_effect = [SigtermReceived()]

        with patch("prompter.cli.run_prompt", mock_run_prompt), \
             patch("prompter.cli.shutil.which", return_value="/usr/bin/claude"):

            result = runner.invoke(app, [str(prompts_file), "-o", str(output_file)])

            # Should exit with 143 (SIGTERM exit code)
            assert result.exit_code == 143

            # run_prompt should be called once
            assert mock_run_prompt.call_count == 1

            # Verify report
            with open(output_file) as f:
                report = json.load(f)
            assert len(report) == 1  # Only first prompt
            assert report[0]["status"] == "error"
            assert "error" in report[0]
            assert "Terminated by SIGTERM" in report[0]["error"]


class TestRepeatedInterrupt:
    """Tests for repeated SIGINT (TC-09, scenario 8)."""

    def test_interrupt_repeated_sigint(self, tmp_path: Path) -> None:
        """Test repeated Ctrl+C during R/N/E prompt (TC-09, scenario 8)."""
        # Create prompts file
        prompts_file = tmp_path / "prompts.txt"
        prompts_file.write_text("meta\n---\nPrompt 1\n---\nPrompt 2")
        output_file = tmp_path / "report.json"

        # Mock run_prompt: first call raises KeyboardInterrupt
        mock_run_prompt = MagicMock()
        mock_run_prompt.side_effect = [KeyboardInterrupt()]

        # Mock input to raise KeyboardInterrupt (simulating Ctrl+C during prompt)
        mock_input = MagicMock(side_effect=KeyboardInterrupt())

        with patch("prompter.cli.run_prompt", mock_run_prompt), \
             patch("prompter.cli.input", mock_input), \
             patch("prompter.cli.shutil.which", return_value="/usr/bin/claude"):

            result = runner.invoke(app, [str(prompts_file), "-o", str(output_file)])

            # Should exit with 130 (POSIX SIGINT)
            assert result.exit_code == 130

            # run_prompt should be called once
            assert mock_run_prompt.call_count == 1

            # Report should NOT be saved (KeyboardInterrupt before save)
            assert not output_file.exists()


class TestErrorCases:
    """Tests for error handling scenarios."""

    def test_claude_cli_not_found(self, tmp_path: Path) -> None:
        """Test error when claude CLI is not in PATH (ORC-09)."""
        # Create prompts file
        prompts_file = tmp_path / "prompts.txt"
        prompts_file.write_text("meta\n---\nPrompt 1")
        output_file = tmp_path / "report.json"

        # Mock shutil.which to return None (claude not found)
        with patch("prompter.cli.shutil.which", return_value=None):
            result = runner.invoke(app, [str(prompts_file), "-o", str(output_file)])

            # Should exit with code 1
            assert result.exit_code == 1

    def test_input_file_not_found(self) -> None:
        """Test error when input file doesn't exist (ERR-10)."""
        result = runner.invoke(app, ["/nonexistent/file.txt"])

        # Should exit with error (Typer validates file existence)
        assert result.exit_code != 0

    def test_invalid_timeout_value(self, tmp_path: Path) -> None:
        """Test error when timeout is below minimum (CLI-05)."""
        # Create prompts file
        prompts_file = tmp_path / "prompts.txt"
        prompts_file.write_text("Prompt 1")

        # Try to set timeout below minimum (10)
        result = runner.invoke(app, [str(prompts_file), "-t", "5"])

        # Should exit with error
        assert result.exit_code != 0


class TestVersionFlag:
    """Tests for --version flag (CLI-02)."""

    def test_version_flag_without_input(self) -> None:
        """Test --version works without input_file (CLI-02)."""
        result = runner.invoke(app, ["--version"])

        # Should succeed
        assert result.exit_code == 0

        # Should print version
        assert "0.1.8" in result.stdout or "0.0.0" in result.stdout

    def test_version_flag_eager(self, tmp_path: Path) -> None:
        """Test --version is eager (exits before other validation)."""
        # Don't create the file - it shouldn't matter
        nonexistent = tmp_path / "nonexistent.txt"

        result = runner.invoke(app, [str(nonexistent), "--version"])

        # Should succeed (version checked before file validation)
        assert result.exit_code == 0
        assert "0.1.8" in result.stdout or "0.0.0" in result.stdout


class TestConfiguration:
    """Tests for configuration system integration (CFG-01, CFG-07)."""

    def test_cli_args_override_defaults(self, tmp_path: Path) -> None:
        """Test CLI arguments override default values."""
        # Create prompts file
        prompts_file = tmp_path / "prompts.txt"
        prompts_file.write_text("meta\n---\nPrompt 1")
        output_file = tmp_path / "custom_output.json"

        # Mock run_prompt to succeed
        mock_run_prompt = MagicMock(return_value=({"result": "ok"}, "sess1"))

        with patch("prompter.cli.run_prompt", mock_run_prompt), \
             patch("prompter.cli.shutil.which", return_value="/usr/bin/claude"):

            result = runner.invoke(
                app,
                [str(prompts_file), "-o", str(output_file), "-t", "100"]
            )

            # Should succeed
            assert result.exit_code == 0

            # Verify custom output file was used
            assert output_file.exists()

            # Verify timeout was passed to run_prompt
            call_kwargs = mock_run_prompt.call_args
            # timeout is 3rd positional arg
            assert call_kwargs[0][2] == 100

    def test_settings_file_loaded(self, tmp_path: Path) -> None:
        """Test settings.json is loaded and merged (CFG-06, CFG-07)."""
        # Create config directory with settings.json
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        settings_file = config_dir / "settings.json"
        settings_file.write_text(json.dumps({"timeout": 500, "verbose": True}))

        # Create prompts file
        prompts_file = tmp_path / "prompts.txt"
        prompts_file.write_text("meta\n---\nPrompt 1")
        output_file = tmp_path / "report.json"

        # Mock run_prompt to succeed
        mock_run_prompt = MagicMock(return_value=({"result": "ok"}, "sess1"))

        with patch("prompter.cli.run_prompt", mock_run_prompt), \
             patch("prompter.cli.shutil.which", return_value="/usr/bin/claude"):

            result = runner.invoke(
                app,
                [str(prompts_file), "-o", str(output_file), "-c", str(config_dir)]
            )

            # Should succeed
            assert result.exit_code == 0

            # Verify timeout from settings was used
            call_kwargs = mock_run_prompt.call_args
            assert call_kwargs[0][2] == 500  # timeout from settings.json


class TestSessionControl:
    """Tests for session management (TC-12, EXE-06, ORC-02, LOG-08)."""

    def test_session_id_logged(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """Test session_id is logged before each prompt (ORC-02)."""
        import logging

        # Create prompts file
        prompts_file = tmp_path / "prompts.txt"
        prompts_file.write_text("meta\n---\nPrompt 1\n---\nPrompt 2")
        output_file = tmp_path / "report.json"

        # Mock run_prompt to return session_id
        mock_run_prompt = MagicMock()
        mock_run_prompt.side_effect = [
            ({"result": "ok1"}, "sess_abc"),
            ({"result": "ok2"}, "sess_abc"),
        ]

        with patch("prompter.cli.run_prompt", mock_run_prompt), \
             patch("prompter.cli.shutil.which", return_value="/usr/bin/claude"), \
             caplog.at_level(logging.INFO):

            result = runner.invoke(app, [str(prompts_file), "-o", str(output_file)])

            # Should succeed
            assert result.exit_code == 0

            # Check that session_id was logged at INFO level
            info_messages = [r.message for r in caplog.records if r.levelname == "INFO"]
            assert any("sess_abc" in msg for msg in info_messages)

    def test_session_restore_command_logged(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """Test session restore command is logged (LOG-08)."""
        import logging

        # Create prompts file
        prompts_file = tmp_path / "prompts.txt"
        prompts_file.write_text("meta\n---\nPrompt 1")
        output_file = tmp_path / "report.json"

        # Mock run_prompt to return session_id
        mock_run_prompt = MagicMock(return_value=({"result": "ok"}, "sess_abc"))

        with patch("prompter.cli.run_prompt", mock_run_prompt), \
             patch("prompter.cli.shutil.which", return_value="/usr/bin/claude"), \
             caplog.at_level(logging.INFO):

            result = runner.invoke(app, [str(prompts_file), "-o", str(output_file)])

            # Should succeed
            assert result.exit_code == 0

            # Check that restore command was logged
            info_messages = [r.message for r in caplog.records if r.levelname == "INFO"]
            assert any("claude --resume sess_abc" in msg for msg in info_messages)

    def test_session_restore_command_not_logged_without_session(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test session restore command not logged when no session (LOG-08)."""
        import logging

        # Create prompts file
        prompts_file = tmp_path / "prompts.txt"
        prompts_file.write_text("meta\n---\nPrompt 1")
        output_file = tmp_path / "report.json"

        # Mock run_prompt to return None session_id (fatal error ORC-03)
        mock_run_prompt = MagicMock(return_value=({"result": "ok"}, None))

        with patch("prompter.cli.run_prompt", mock_run_prompt), \
             patch("prompter.cli.shutil.which", return_value="/usr/bin/claude"), \
             caplog.at_level(logging.INFO):

            result = runner.invoke(app, [str(prompts_file), "-o", str(output_file)])

            # Should fail with exit code 1
            assert result.exit_code == 1

            # Check that restore command was NOT logged
            all_messages = [r.message for r in caplog.records]
            assert not any("claude --resume" in msg for msg in all_messages)


class TestErrorResilience:
    """Tests for error resilience (TC-14, ERR-01, ERR-06, REP-02, REP-05, REP-06, ERR-10)."""

    def test_error_and_timeout_do_not_stop_execution(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test execution continues after errors and timeouts (TC-14)."""
        import logging
        import subprocess

        # Create prompts file with 4 prompts
        prompts_file = tmp_path / "prompts.txt"
        prompts_file.write_text("meta\n---\nPrompt 1\n---\nPrompt 2\n---\nPrompt 3\n---\nPrompt 4")
        output_file = tmp_path / "report.json"

        # Mock run_prompt with various outcomes
        mock_run_prompt = MagicMock()
        mock_run_prompt.side_effect = [
            ({"result": "ok"}, "sess1"),  # Prompt 1: success
            Exception("fail"),  # Prompt 2: error
            subprocess.TimeoutExpired("claude", 100),  # Prompt 3: timeout
            ({"result": "ok2"}, "sess1"),  # Prompt 4: success
        ]

        with patch("prompter.cli.run_prompt", mock_run_prompt), \
             patch("prompter.cli.shutil.which", return_value="/usr/bin/claude"), \
             caplog.at_level(logging.ERROR):

            result = runner.invoke(app, [str(prompts_file), "-o", str(output_file)])

            # Should succeed (no unhandled exceptions)
            assert result.exit_code == 0

            # Check errors were logged
            error_messages = [r.message for r in caplog.records if r.levelname == "ERROR"]
            assert len(error_messages) >= 2  # At least error and timeout

            # Verify report
            with open(output_file) as f:
                report = json.load(f)

            assert len(report) == 4
            assert report[0]["status"] == "success"
            assert report[1]["status"] == "error"
            assert "error" in report[1]
            assert report[2]["status"] == "timeout"
            assert "error" in report[2]
            assert report[3]["status"] == "success"

    def test_fatal_error_missing_session_id(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test fatal error when first prompt doesn't return session_id (ORC-03, ERR-11)."""
        import logging

        # Create prompts file
        prompts_file = tmp_path / "prompts.txt"
        prompts_file.write_text("meta\n---\nPrompt 1\n---\nPrompt 2")
        output_file = tmp_path / "report.json"

        # Mock run_prompt to return None session_id
        mock_run_prompt = MagicMock(return_value=({"result": "ok"}, None))

        with patch("prompter.cli.run_prompt", mock_run_prompt), \
             patch("prompter.cli.shutil.which", return_value="/usr/bin/claude"), \
             caplog.at_level(logging.ERROR):

            result = runner.invoke(app, [str(prompts_file), "-o", str(output_file)])

            # Should exit with code 1
            assert result.exit_code == 1

            # Check error was logged
            error_messages = [r.message for r in caplog.records if r.levelname == "ERROR"]
            assert any("session_id" in msg for msg in error_messages)

            # Verify report
            with open(output_file) as f:
                report = json.load(f)

            assert len(report) == 1
            assert report[0]["status"] == "error"
            assert "error" in report[0]

            # Second prompt not executed
            assert mock_run_prompt.call_count == 1

    def test_session_integrity_lost_session_id(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test fatal error when session_id is lost on prompt N>1 (ORC-04)."""
        import logging

        # Create prompts file
        prompts_file = tmp_path / "prompts.txt"
        prompts_file.write_text("meta\n---\nPrompt 1\n---\nPrompt 2\n---\nPrompt 3")
        output_file = tmp_path / "report.json"

        # Mock run_prompt: first returns session, second loses it
        mock_run_prompt = MagicMock()
        mock_run_prompt.side_effect = [
            ({"result": "ok"}, "sess_abc"),  # Prompt 1: establish session
            ({"result": "ok2"}, None),  # Prompt 2: lost session_id
        ]

        with patch("prompter.cli.run_prompt", mock_run_prompt), \
             patch("prompter.cli.shutil.which", return_value="/usr/bin/claude"), \
             caplog.at_level(logging.ERROR):

            result = runner.invoke(app, [str(prompts_file), "-o", str(output_file)])

            # Should exit with code 1
            assert result.exit_code == 1

            # Check error was logged with reason
            error_messages = [r.message for r in caplog.records if r.levelname == "ERROR"]
            assert any("session_id" in msg.lower() for msg in error_messages)

            # Verify report
            with open(output_file) as f:
                report = json.load(f)

            assert len(report) == 2
            assert report[0]["status"] == "success"
            assert report[1]["status"] == "error"
            assert "error" in report[1]
            assert "Session integrity error" in report[1]["error"]

            # Third prompt not executed
            assert mock_run_prompt.call_count == 2

    def test_session_integrity_changed_session_id(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test fatal error when session_id changes on prompt N>1 (ORC-04)."""
        import logging

        # Create prompts file
        prompts_file = tmp_path / "prompts.txt"
        prompts_file.write_text("meta\n---\nPrompt 1\n---\nPrompt 2\n---\nPrompt 3")
        output_file = tmp_path / "report.json"

        # Mock run_prompt: session_id changes
        mock_run_prompt = MagicMock()
        mock_run_prompt.side_effect = [
            ({"result": "ok"}, "sess_abc"),  # Prompt 1
            ({"result": "ok2"}, "sess_xyz"),  # Prompt 2: different session_id
        ]

        with patch("prompter.cli.run_prompt", mock_run_prompt), \
             patch("prompter.cli.shutil.which", return_value="/usr/bin/claude"), \
             caplog.at_level(logging.ERROR):

            result = runner.invoke(app, [str(prompts_file), "-o", str(output_file)])

            # Should exit with code 1
            assert result.exit_code == 1

            # Check error was logged with both session IDs
            error_messages = [r.message for r in caplog.records if r.levelname == "ERROR"]
            assert any("sess_abc" in msg and "sess_xyz" in msg for msg in error_messages)

            # Verify report
            with open(output_file) as f:
                report = json.load(f)

            assert len(report) == 2
            assert report[0]["status"] == "success"
            assert report[1]["status"] == "error"
            assert "error" in report[1]
            assert "sess_abc" in report[1]["error"]
            assert "sess_xyz" in report[1]["error"]

            # Third prompt not executed
            assert mock_run_prompt.call_count == 2

    def test_exception_before_execution_loop(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test graceful handling of exception before execution_loop (ERR-10)."""
        import logging

        # Create prompts file
        prompts_file = tmp_path / "prompts.txt"
        prompts_file.write_text("meta\n---\nPrompt 1")
        output_file = tmp_path / "report.json"

        # Mock prepare_prompts to raise exception
        with patch("prompter.cli.prepare_prompts", side_effect=RuntimeError("parse failure")), \
             patch("prompter.cli.shutil.which", return_value="/usr/bin/claude"), \
             caplog.at_level(logging.ERROR):

            result = runner.invoke(app, [str(prompts_file), "-o", str(output_file)])

            # Should exit with code 1
            assert result.exit_code == 1

            # Check error was logged
            error_messages = [r.message for r in caplog.records if r.levelname == "ERROR"]
            assert any("parse failure" in msg for msg in error_messages)


class TestReportStructure:
    """Tests for report structure (TC-15, REP-01, REP-02, REP-04, REP-05, REP-06)."""

    def test_report_structure(self, tmp_path: Path) -> None:
        """Test report contains all required fields with correct structure (TC-15)."""
        import subprocess

        # Create prompts file
        prompts_file = tmp_path / "prompts.txt"
        prompts_file.write_text("meta\n---\nPrompt 1\n---\nPrompt 2\n---\nPrompt 3\n---\nPrompt 4")
        output_file = tmp_path / "report.json"

        # Mock run_prompt to produce all 4 statuses
        mock_run_prompt = MagicMock()
        mock_run_prompt.side_effect = [
            ({"result": "ok"}, "sess1"),  # Success
            KeyboardInterrupt(),  # Will be skipped via input("N")
            Exception("test error"),  # Error
            subprocess.TimeoutExpired("claude", 100),  # Timeout
        ]

        # Mock input for KeyboardInterrupt
        mock_input = MagicMock(return_value="N")

        with patch("prompter.cli.run_prompt", mock_run_prompt), \
             patch("prompter.cli.input", mock_input), \
             patch("prompter.cli.shutil.which", return_value="/usr/bin/claude"):

            result = runner.invoke(app, [str(prompts_file), "-o", str(output_file)])

            # Should succeed
            assert result.exit_code == 0

            # Verify report
            with open(output_file) as f:
                report = json.load(f)

            # Should be valid JSON array
            assert isinstance(report, list)
            assert len(report) == 4

            # Check each record
            for record in report:
                # Required fields
                assert "prompt" in record
                assert isinstance(record["prompt"], str)
                assert "claude_response" in record
                assert "timestamp" in record
                assert "status" in record

                # Validate status
                assert record["status"] in ("success", "skipped", "error", "timeout")

                # Validate timestamp format (ISO 8601, no microseconds)
                import re
                assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$", record["timestamp"])

            # Check error field presence based on status
            assert "error" not in report[0]  # success
            assert "error" not in report[1]  # skipped
            assert "error" in report[2]  # error
            assert "error" in report[3]  # timeout

    def test_report_overwrite_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test warning when overwriting existing report (REP-02)."""
        import logging

        # Create prompts file
        prompts_file = tmp_path / "prompts.txt"
        prompts_file.write_text("meta\n---\nPrompt 1")
        output_file = tmp_path / "report.json"

        # Create existing report file
        output_file.write_text('{"old": "data"}')

        # Mock run_prompt
        mock_run_prompt = MagicMock(return_value=({"result": "ok"}, "sess1"))

        with patch("prompter.cli.run_prompt", mock_run_prompt), \
             patch("prompter.cli.shutil.which", return_value="/usr/bin/claude"), \
             caplog.at_level(logging.WARNING):

            result = runner.invoke(app, [str(prompts_file), "-o", str(output_file)])

            # Should succeed
            assert result.exit_code == 0

            # Check warning was logged
            warning_messages = [r.message for r in caplog.records if r.levelname == "WARNING"]
            assert any("already exists" in msg or "overwrite" in msg.lower() for msg in warning_messages)

            # Verify report was overwritten with valid JSON
            with open(output_file) as f:
                report = json.load(f)

            assert isinstance(report, list)
            assert len(report) == 1

    def test_user_messages_english(self, tmp_path: Path) -> None:
        """Test all user messages are in English (DOC-03)."""
        # Create prompts file
        prompts_file = tmp_path / "prompts.txt"
        prompts_file.write_text("meta\n---\nPrompt 1")
        output_file = tmp_path / "report.json"

        # Mock run_prompt to trigger KeyboardInterrupt (shows R/N/E prompt)
        mock_run_prompt = MagicMock(side_effect=KeyboardInterrupt())

        # Mock input to return "E" (will trigger user prompt)
        mock_input = MagicMock(return_value="E")

        with patch("prompter.cli.run_prompt", mock_run_prompt), \
             patch("prompter.cli.input", mock_input) as patched_input, \
             patch("prompter.cli.shutil.which", return_value="/usr/bin/claude"):

            result = runner.invoke(app, [str(prompts_file), "-o", str(output_file)])

            # Get the prompt text passed to input()
            if patched_input.called:
                input_prompt = patched_input.call_args[0][0]

                # Check for ASCII-only (no Cyrillic)
                # Allow standard ASCII + some common symbols
                try:
                    input_prompt.encode('ascii')
                    # If encoding succeeds, it's ASCII-only
                    assert True
                except UnicodeEncodeError:
                    # Contains non-ASCII characters
                    pytest.fail(f"User prompt contains non-ASCII characters: {input_prompt}")
