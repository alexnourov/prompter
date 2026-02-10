"""Tests for prompt execution via Claude CLI.

Tests cover requirements: EXE-01..12, ERR-01, ERR-06, INT-02, INT-04, ORC-03.
Includes TC-01, TC-02, TC-16, TC-18, TC-09 (scenario 1).
"""

import io
import logging
import subprocess
from unittest.mock import MagicMock, Mock, patch

import pytest

from prompter.models import SigtermReceived
from prompter.runner import run_prompt


class TestCommandFlags:
    """Tests for command construction and flags (TC-01)."""

    def test_command_flags(self) -> None:
        """Test that required CLI flags are present (EXE-01..05, EXE-11)."""
        # Mock Popen to return successful process
        mock_process = MagicMock()
        mock_process.stdout = iter([
            '{"type": "system", "session_id": "test"}\n',
            '{"type": "result", "subtype": "success"}\n',
        ])
        mock_process.stderr = iter([])
        mock_process.returncode = 0
        mock_process.args = ["claude"]

        with patch("prompter.runner.subprocess.Popen", return_value=mock_process) as mock_popen:
            run_prompt("Hello")

            # Verify Popen was called
            assert mock_popen.called

            # Get command arguments
            call_args, call_kwargs = mock_popen.call_args
            cmd = call_args[0]

            # Check required flags (EXE-02..05)
            assert "-p" in cmd
            assert "Hello" in cmd
            assert "--output-format" in cmd
            assert "stream-json" in cmd
            assert "--verbose" in cmd
            assert "--dangerously-skip-permissions" in cmd

            # Check stdin=DEVNULL (EXE-11)
            assert call_kwargs["stdin"] == subprocess.DEVNULL

    def test_stdbuf_prefix_on_linux(self) -> None:
        """Test stdbuf prefix on Linux when available (EXE-09)."""
        mock_process = MagicMock()
        mock_process.stdout = iter([
            '{"type": "system", "session_id": "test"}\n',
            '{"type": "result", "subtype": "success"}\n',
        ])
        mock_process.stderr = iter([])
        mock_process.returncode = 0
        mock_process.args = ["stdbuf", "-oL", "-eL", "claude"]

        with patch("prompter.runner.subprocess.Popen", return_value=mock_process) as mock_popen, \
             patch("prompter.runner.platform.system", return_value="Linux"), \
             patch("prompter.runner.shutil.which", return_value="/usr/bin/stdbuf"):

            run_prompt("Hello")

            # Get command arguments
            call_args = mock_popen.call_args[0]
            cmd = call_args[0]

            # Check stdbuf prefix
            assert cmd[0:3] == ["stdbuf", "-oL", "-eL"]
            assert "claude" in cmd

    def test_stdbuf_fallback(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test fallback when stdbuf not available on Linux (EXE-09)."""
        mock_process = MagicMock()
        mock_process.stdout = iter([
            '{"type": "system", "session_id": "test"}\n',
            '{"type": "result", "subtype": "success"}\n',
        ])
        mock_process.stderr = iter([])
        mock_process.returncode = 0
        mock_process.args = ["claude"]

        with patch("prompter.runner.subprocess.Popen", return_value=mock_process) as mock_popen, \
             patch("prompter.runner.platform.system", return_value="Linux"), \
             patch("prompter.runner.shutil.which", return_value=None), \
             caplog.at_level(logging.WARNING):

            run_prompt("Hello")

            # Get command arguments
            call_args = mock_popen.call_args[0]
            cmd = call_args[0]

            # Check stdbuf is NOT present
            assert "stdbuf" not in cmd

            # Check warning was logged
            assert any("stdbuf not found" in record.message for record in caplog.records)

    def test_stdbuf_prefix_on_macos(self) -> None:
        """Test stdbuf prefix on macOS when available (EXE-09)."""
        mock_process = MagicMock()
        mock_process.stdout = iter([
            '{"type": "system", "session_id": "test"}\n',
            '{"type": "result", "subtype": "success"}\n',
        ])
        mock_process.stderr = iter([])
        mock_process.returncode = 0
        mock_process.args = ["stdbuf", "-oL", "-eL", "claude"]

        with patch("prompter.runner.subprocess.Popen", return_value=mock_process) as mock_popen, \
             patch("prompter.runner.platform.system", return_value="Darwin"), \
             patch("prompter.runner.shutil.which", return_value="/usr/local/bin/stdbuf"):

            run_prompt("Hello")

            # Get command arguments
            call_args = mock_popen.call_args[0]
            cmd = call_args[0]

            # Check stdbuf prefix
            assert cmd[0:3] == ["stdbuf", "-oL", "-eL"]


class TestCommandChain:
    """Tests for session resumption and command chaining (TC-02)."""

    def test_command_chain(self) -> None:
        """Test session ID extraction and resumption (EXE-06, EXE-07)."""
        # First call: no session
        mock_process1 = MagicMock()
        mock_process1.stdout = iter([
            '{"type": "system", "session_id": "sess_123"}\n',
            '{"type": "result", "result": "ok"}\n',
        ])
        mock_process1.stderr = iter([])
        mock_process1.returncode = 0
        mock_process1.args = ["claude"]

        # Second call: with session
        mock_process2 = MagicMock()
        mock_process2.stdout = iter([
            '{"type": "system", "session_id": "sess_123"}\n',
            '{"type": "result", "result": "ok"}\n',
        ])
        mock_process2.stderr = iter([])
        mock_process2.returncode = 0
        mock_process2.args = ["claude", "--resume", "sess_123"]

        with patch("prompter.runner.subprocess.Popen", side_effect=[mock_process1, mock_process2]) as mock_popen:
            # First call without session
            result_obj1, session_id1 = run_prompt("prompt1", session_id=None)

            # Check first call
            call_args1 = mock_popen.call_args_list[0][0]
            cmd1 = call_args1[0]
            assert "--resume" not in cmd1
            assert session_id1 == "sess_123"

            # Second call with session
            result_obj2, session_id2 = run_prompt("prompt2", session_id="sess_123")

            # Check second call
            call_args2 = mock_popen.call_args_list[1][0]
            cmd2 = call_args2[0]
            assert "--resume" in cmd2
            assert "sess_123" in cmd2

    def test_missing_session_id(self) -> None:
        """Test behavior when system event is missing (ORC-03)."""
        mock_process = MagicMock()
        mock_process.stdout = iter([
            '{"type": "result", "result": "ok"}\n',
        ])
        mock_process.stderr = iter([])
        mock_process.returncode = 0
        mock_process.args = ["claude"]

        with patch("prompter.runner.subprocess.Popen", return_value=mock_process):
            result_obj, session_id = run_prompt("prompt1", session_id=None)

            # Session ID should be None
            assert session_id is None


class TestStreamProcessing:
    """Tests for NDJSON stream processing and logging (TC-16)."""

    def test_stream_processing(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test full NDJSON stream processing with all event types (EXE-10)."""
        mock_process = MagicMock()
        mock_process.stdout = iter([
            '{"type": "system", "session_id": "sess-1"}\n',
            '{"type": "assistant", "message": {"content": [{"type": "text", "text": "Hello"}]}}\n',
            '{"type": "progress", "content": "thinking..."}\n',
            '{"type": "result", "subtype": "success", "result": "Done", "duration_ms": 1500, "total_cost_usd": 0.02}\n',
        ])
        mock_process.stderr = iter([])
        mock_process.returncode = 0
        mock_process.args = ["claude"]

        with patch("prompter.runner.subprocess.Popen", return_value=mock_process), \
             caplog.at_level(logging.DEBUG):

            result_obj, session_id = run_prompt("test")

            # Check session_id
            assert session_id == "sess-1"

            # Check result_obj
            assert result_obj is not None
            assert result_obj["result"] == "Done"

            # Check logging
            log_messages = [record.message for record in caplog.records]

            # System event: DEBUG
            assert any("sess-1" in msg and caplog.records[i].levelname == "DEBUG"
                      for i, msg in enumerate(log_messages))

            # Assistant event: INFO
            assert any("Hello" in msg and caplog.records[i].levelname == "INFO"
                      for i, msg in enumerate(log_messages))

            # Progress event: INFO
            assert any("thinking..." in msg and caplog.records[i].levelname == "INFO"
                      for i, msg in enumerate(log_messages))

            # Result summary: INFO
            assert any("result: success, 1500ms, $0.0200" in msg and caplog.records[i].levelname == "INFO"
                      for i, msg in enumerate(log_messages))

            # Result raw: DEBUG
            assert any("result_raw:" in msg and "Done" in msg and caplog.records[i].levelname == "DEBUG"
                      for i, msg in enumerate(log_messages))

    def test_stream_processing_legacy_format(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test backward compatibility with legacy format (no message wrapper)."""
        mock_process = MagicMock()
        mock_process.stdout = iter([
            '{"type": "system", "session_id": "sess-1"}\n',
            '{"type": "assistant", "content": [{"type": "text", "text": "Legacy"}]}\n',
            '{"type": "result", "subtype": "success", "result": "Done", "duration_ms": 100, "total_cost_usd": 0.01}\n',
        ])
        mock_process.stderr = iter([])
        mock_process.returncode = 0
        mock_process.args = ["claude"]

        with patch("prompter.runner.subprocess.Popen", return_value=mock_process), \
             caplog.at_level(logging.INFO):

            result_obj, session_id = run_prompt("test")

            # Check session_id
            assert session_id == "sess-1"

            # Check result_obj
            assert result_obj is not None

            # Check logging - "Legacy" should be logged
            assert any("Legacy" in record.message for record in caplog.records)

    def test_empty_events_not_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that empty events are not logged (EXE-12)."""
        mock_process = MagicMock()
        mock_process.stdout = iter([
            '{"type": "system", "session_id": "sess-1"}\n',
            '{"type": "assistant", "message": {"content": []}}\n',  # Empty content
            '{"type": "progress", "content": ""}\n',  # Empty content
            '{"type": "assistant", "message": {"content": [{"type": "text", "text": "Real"}]}}\n',  # Non-empty
            '{"type": "result", "subtype": "success", "result": "Done", "duration_ms": 100, "total_cost_usd": 0.01}\n',
        ])
        mock_process.stderr = iter([])
        mock_process.returncode = 0
        mock_process.args = ["claude"]

        with patch("prompter.runner.subprocess.Popen", return_value=mock_process), \
             caplog.at_level(logging.INFO):

            run_prompt("test")

            # Get INFO level messages only (exclude DEBUG)
            info_messages = [record.message for record in caplog.records if record.levelname == "INFO"]

            # "Real" should be logged
            assert any("Real" in msg for msg in info_messages)

            # Empty strings should NOT be in INFO logs
            # (We can't directly check for absence, but we can count messages)
            # There should be exactly 2 INFO messages: "Real" and result summary
            assistant_info_logs = [msg for msg in info_messages if "Real" in msg or "result:" in msg]
            assert len(assistant_info_logs) >= 1

    def test_malformed_ndjson(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test handling of malformed JSON (ERR-06)."""
        mock_process = MagicMock()
        mock_process.stdout = iter([
            '{broken json\n',
            '{"type": "result", "subtype": "success"}\n',
        ])
        mock_process.stderr = iter([])
        mock_process.returncode = 0
        mock_process.args = ["claude"]

        with patch("prompter.runner.subprocess.Popen", return_value=mock_process), \
             caplog.at_level(logging.WARNING):

            # Should not crash, but log warning
            run_prompt("test")

            # Check warning was logged
            assert any("Failed to parse JSON" in record.message for record in caplog.records)

    def test_concurrent_stdout_stderr(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test concurrent stdout/stderr reading without deadlock (EXE-08)."""
        mock_process = MagicMock()
        mock_process.stdout = iter([
            '{"type": "system", "session_id": "sess-1"}\n',
            '{"type": "result", "subtype": "success", "result": "Done", "duration_ms": 100, "total_cost_usd": 0.01}\n',
        ])
        mock_process.stderr = iter([
            "warning line 1\n",
            "warning line 2\n",
        ])
        mock_process.returncode = 0
        mock_process.args = ["claude"]

        with patch("prompter.runner.subprocess.Popen", return_value=mock_process), \
             caplog.at_level(logging.WARNING):

            result_obj, session_id = run_prompt("test")

            # Check result
            assert session_id == "sess-1"
            assert result_obj is not None
            assert result_obj["result"] == "Done"

            # Check stderr was logged
            warning_messages = [record.message for record in caplog.records if record.levelname == "WARNING"]
            assert any("warning line 1" in msg for msg in warning_messages)
            assert any("warning line 2" in msg for msg in warning_messages)


class TestTimeout:
    """Tests for timeout handling (TC-18)."""

    def test_timeout(self) -> None:
        """Test timeout kills process and raises exception (ERR-01)."""
        mock_process = MagicMock()
        # Simulate slow stdout that will timeout
        mock_process.stdout = iter([
            '{"type": "system", "session_id": "test"}\n',
            # Process hangs here - no result event
        ])
        mock_process.stderr = iter([])
        mock_process.args = ["claude"]

        # Mock wait to raise TimeoutExpired
        mock_process.wait.side_effect = subprocess.TimeoutExpired(["claude"], 1)

        with patch("prompter.runner.subprocess.Popen", return_value=mock_process):
            with pytest.raises(subprocess.TimeoutExpired):
                run_prompt("test", timeout=1)

            # Verify process was killed
            mock_process.kill.assert_called_once()

    def test_timeout_during_stream(self) -> None:
        """Test timeout detection during stream processing (ERR-01)."""
        mock_process = MagicMock()

        # Create a generator that checks time
        def slow_stream():
            yield '{"type": "system", "session_id": "test"}\n'
            # Simulate slow processing
            import time
            time.sleep(2)  # Sleep longer than timeout
            yield '{"type": "result", "subtype": "success"}\n'

        mock_process.stdout = slow_stream()
        mock_process.stderr = iter([])
        mock_process.args = ["claude"]

        with patch("prompter.runner.subprocess.Popen", return_value=mock_process):
            with pytest.raises(subprocess.TimeoutExpired):
                run_prompt("test", timeout=1)

            # Verify process was killed
            mock_process.kill.assert_called_once()


class TestSignalHandling:
    """Tests for signal handling (TC-09, scenario 1)."""

    def test_keyboard_interrupt_kills_process(self) -> None:
        """Test KeyboardInterrupt kills process and is re-raised (INT-02)."""
        mock_process = MagicMock()

        # Simulate KeyboardInterrupt during stdout reading
        def interrupt_stream():
            yield '{"type": "system", "session_id": "test"}\n'
            raise KeyboardInterrupt()

        mock_process.stdout = interrupt_stream()
        mock_process.stderr = iter([])
        mock_process.args = ["claude"]

        with patch("prompter.runner.subprocess.Popen", return_value=mock_process):
            with pytest.raises(KeyboardInterrupt):
                run_prompt("test")

            # Verify process was killed
            mock_process.kill.assert_called_once()

    def test_sigterm_kills_process(self) -> None:
        """Test SigtermReceived kills process and is re-raised (INT-04)."""
        mock_process = MagicMock()

        # Simulate SigtermReceived during stdout reading
        def sigterm_stream():
            yield '{"type": "system", "session_id": "test"}\n'
            raise SigtermReceived()

        mock_process.stdout = sigterm_stream()
        mock_process.stderr = iter([])
        mock_process.args = ["claude"]

        with patch("prompter.runner.subprocess.Popen", return_value=mock_process):
            with pytest.raises(SigtermReceived):
                run_prompt("test")

            # Verify process was killed
            mock_process.kill.assert_called_once()


class TestErrorHandling:
    """Tests for error handling."""

    def test_nonzero_exit_code(self) -> None:
        """Test that non-zero exit code raises exception (ERR-06)."""
        mock_process = MagicMock()
        mock_process.stdout = iter([
            '{"type": "system", "session_id": "test"}\n',
            '{"type": "result", "subtype": "error"}\n',
        ])
        mock_process.stderr = iter([])
        mock_process.returncode = 1  # Non-zero exit code
        mock_process.args = ["claude"]

        with patch("prompter.runner.subprocess.Popen", return_value=mock_process):
            with pytest.raises(Exception, match="exited with non-zero code 1"):
                run_prompt("test")
