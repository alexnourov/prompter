"""Tests for ClaudeRunner class."""

import subprocess
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from src.prompter.runner import ClaudeRunner


class TestClaudeRunner:
    """Test suite for ClaudeRunner."""

    def test_command_flags(self) -> None:
        """Test that Popen is called with required flags."""
        runner = ClaudeRunner()

        with patch("src.prompter.runner.subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.stdout = iter([])
            mock_process.stderr = iter([])
            mock_process.wait.return_value = 0
            mock_popen.return_value = mock_process

            runner.run_prompt("test prompt")

            mock_popen.assert_called_once()
            call_args = mock_popen.call_args
            command = call_args[0][0]

            assert "--output-format" in command
            assert "stream-json" in command
            assert "--verbose" in command
            assert "--dangerously-skip-permissions" in command

    def test_resume_flag(self) -> None:
        """Test that --resume flag is added when session_id exists."""
        runner = ClaudeRunner()
        runner.session_id = "existing-session-456"

        with patch("src.prompter.runner.subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.stdout = iter([])
            mock_process.stderr = iter([])
            mock_process.wait.return_value = 0
            mock_popen.return_value = mock_process

            runner.run_prompt("test prompt")

            call_args = mock_popen.call_args
            command = call_args[0][0]

            assert "--resume" in command
            resume_index = command.index("--resume")
            assert command[resume_index + 1] == "existing-session-456"

    def test_stream_processing(self) -> None:
        """Test NDJSON stream processing and session_id extraction."""
        runner = ClaudeRunner()

        ndjson_lines = [
            '{"type": "system", "session_id": "new-session-123"}',
            '{"type": "assistant", "content": [{"type": "text", "text": "Hello"}]}',
            '{"type": "result", "result": "Hello world"}',
        ]

        with patch("src.prompter.runner.subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.stdout = iter([line + "\n" for line in ndjson_lines])
            mock_process.stderr = iter([])
            mock_process.wait.return_value = 0
            mock_popen.return_value = mock_process

            result = runner.run_prompt("test prompt")

            assert runner.session_id == "new-session-123"
            assert result["type"] == "result"
            assert result["result"] == "Hello world"

    def test_realtime_logging(self) -> None:
        """Test that assistant responses are logged."""
        runner = ClaudeRunner()

        ndjson_lines = [
            '{"type": "assistant", "content": [{"type": "text", "text": "Hello from Claude"}]}',
            '{"type": "result", "result": "done"}',
        ]

        with patch("src.prompter.runner.subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.stdout = iter([line + "\n" for line in ndjson_lines])
            mock_process.stderr = iter([])
            mock_process.wait.return_value = 0
            mock_popen.return_value = mock_process

            with patch("src.prompter.runner.logger") as mock_logger:
                runner.run_prompt("test prompt")

                info_calls = [
                    call for call in mock_logger.info.call_args_list
                    if len(call[0]) > 1 and "Hello from Claude" in str(call[0])
                ]
                assert len(info_calls) > 0, "Assistant message should be logged"

    def test_interruption(self) -> None:
        """Test KeyboardInterrupt handling - process killed and exception re-raised."""
        runner = ClaudeRunner()

        with patch("src.prompter.runner.subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.stdout = iter([])
            mock_process.stderr = iter([])
            mock_process.wait.side_effect = KeyboardInterrupt()
            mock_popen.return_value = mock_process

            with pytest.raises(KeyboardInterrupt):
                runner.run_prompt("test prompt")

            mock_process.kill.assert_called_once()

    def test_timeout(self) -> None:
        """Test TimeoutExpired handling."""
        runner = ClaudeRunner()

        with patch("src.prompter.runner.subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.stdout = iter([])
            mock_process.stderr = iter([])
            mock_process.wait.side_effect = subprocess.TimeoutExpired(
                cmd="claude", timeout=10
            )
            mock_popen.return_value = mock_process

            with pytest.raises(subprocess.TimeoutExpired):
                runner.run_prompt("test prompt", timeout=10)

            mock_process.kill.assert_called_once()

    def test_session_logging(self) -> None:
        """Test that existing session_id is logged at start."""
        runner = ClaudeRunner()
        runner.session_id = "test-sess"

        with patch("src.prompter.runner.subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.stdout = iter([])
            mock_process.stderr = iter([])
            mock_process.wait.return_value = 0
            mock_popen.return_value = mock_process

            with patch("src.prompter.runner.logger") as mock_logger:
                runner.run_prompt("test prompt")

                info_calls = mock_logger.info.call_args_list
                session_logged = any(
                    "test-sess" in str(call) for call in info_calls
                )
                assert session_logged, "Session ID should be logged"

    def test_new_session_logging(self) -> None:
        """Test that new session message is logged when no session_id."""
        runner = ClaudeRunner()

        with patch("src.prompter.runner.subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.stdout = iter([])
            mock_process.stderr = iter([])
            mock_process.wait.return_value = 0
            mock_popen.return_value = mock_process

            with patch("src.prompter.runner.logger") as mock_logger:
                runner.run_prompt("test prompt")

                info_calls = mock_logger.info.call_args_list
                new_session_logged = any(
                    "new session" in str(call).lower() for call in info_calls
                )
                assert new_session_logged, "New session message should be logged"

    def test_stderr_logging(self) -> None:
        """Test that stderr output is logged as warning."""
        runner = ClaudeRunner()

        with patch("src.prompter.runner.subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.stdout = iter(['{"type": "result", "result": "ok"}\n'])
            mock_process.stderr = iter(["Warning: something happened\n"])
            mock_process.wait.return_value = 0
            mock_popen.return_value = mock_process

            with patch("src.prompter.runner.logger") as mock_logger:
                runner.run_prompt("test prompt")

                warning_calls = mock_logger.warning.call_args_list
                stderr_logged = any(
                    "something happened" in str(call) for call in warning_calls
                )
                assert stderr_logged, "Stderr should be logged as warning"

    def test_empty_result(self) -> None:
        """Test that empty dict is returned when no valid result received."""
        runner = ClaudeRunner()

        with patch("src.prompter.runner.subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.stdout = iter([])
            mock_process.stderr = iter([])
            mock_process.wait.return_value = 0
            mock_popen.return_value = mock_process

            result = runner.run_prompt("test prompt")

            assert result == {}

    def test_linux_stdbuf_prefix(self) -> None:
        """Test that stdbuf prefix is added on Linux."""
        runner = ClaudeRunner()

        with patch("src.prompter.runner.platform.system", return_value="Linux"):
            with patch("src.prompter.runner.subprocess.Popen") as mock_popen:
                mock_process = MagicMock()
                mock_process.stdout = iter([])
                mock_process.stderr = iter([])
                mock_process.wait.return_value = 0
                mock_popen.return_value = mock_process

                runner.run_prompt("test prompt")

                call_args = mock_popen.call_args
                command = call_args[0][0]

                assert command[0] == "stdbuf"
                assert "-oL" in command
                assert "-eL" in command

    def test_non_linux_no_stdbuf(self) -> None:
        """Test that stdbuf prefix is not added on non-Linux systems."""
        runner = ClaudeRunner()

        with patch("src.prompter.runner.platform.system", return_value="Darwin"):
            with patch("src.prompter.runner.subprocess.Popen") as mock_popen:
                mock_process = MagicMock()
                mock_process.stdout = iter([])
                mock_process.stderr = iter([])
                mock_process.wait.return_value = 0
                mock_popen.return_value = mock_process

                runner.run_prompt("test prompt")

                call_args = mock_popen.call_args
                command = call_args[0][0]

                assert command[0] == "claude"
                assert "stdbuf" not in command
