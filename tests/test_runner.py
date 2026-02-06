"""Tests for ClaudeRunner."""

import subprocess
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

from prompter.runner import ClaudeRunner


class TestClaudeRunner:
    """Test suite for ClaudeRunner class."""

    @patch("prompter.runner.subprocess.Popen")
    def test_command_flags(self, mock_popen: MagicMock) -> None:
        """Test that Popen is called with required flags."""
        mock_process = MagicMock()
        mock_process.stdout = iter([
            '{"type": "result", "result": "test"}\n'
        ])
        mock_process.stderr = iter([])
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process

        runner = ClaudeRunner()
        runner.run_prompt("test prompt")

        mock_popen.assert_called_once()
        call_args = mock_popen.call_args[0][0]

        assert "--output-format" in call_args
        assert "stream-json" in call_args
        assert "--verbose" in call_args
        assert "--dangerously-skip-permissions" in call_args

    @patch("prompter.runner.subprocess.Popen")
    def test_resume_flag(self, mock_popen: MagicMock) -> None:
        """Test that --resume flag is added when session_id exists."""
        mock_process = MagicMock()
        mock_process.stdout = iter([
            '{"type": "result", "result": "test"}\n'
        ])
        mock_process.stderr = iter([])
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process

        runner = ClaudeRunner(session_id="existing-session-456")
        runner.run_prompt("test prompt")

        mock_popen.assert_called_once()
        call_args = mock_popen.call_args[0][0]

        assert "--resume" in call_args
        resume_index = call_args.index("--resume")
        assert call_args[resume_index + 1] == "existing-session-456"

    @patch("prompter.runner.subprocess.Popen")
    def test_stream_processing(self, mock_popen: MagicMock) -> None:
        """Test NDJSON stream processing and session_id extraction."""
        mock_process = MagicMock()
        mock_process.stdout = iter([
            '{"type": "system", "session_id": "new-session-123"}\n',
            '{"type": "assistant", "content": [{"type": "text", "text": "Hello"}]}\n',
            '{"type": "result", "result": "Hello world"}\n',
        ])
        mock_process.stderr = iter([])
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process

        runner = ClaudeRunner()
        result = runner.run_prompt("test prompt")

        assert runner.session_id == "new-session-123"
        assert result["type"] == "result"
        assert result["result"] == "Hello world"

    @patch("prompter.runner.logger")
    @patch("prompter.runner.subprocess.Popen")
    def test_realtime_logging(
        self, mock_popen: MagicMock, mock_logger: MagicMock
    ) -> None:
        """Test that assistant content is logged in real-time."""
        mock_process = MagicMock()
        mock_process.stdout = iter([
            '{"type": "assistant", "content": [{"type": "text", "text": "Hello from Claude"}]}\n',
            '{"type": "result", "result": "done"}\n',
        ])
        mock_process.stderr = iter([])
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process

        runner = ClaudeRunner()
        runner.run_prompt("test prompt")

        info_calls = [call for call in mock_logger.info.call_args_list]
        logged_messages = [str(call) for call in info_calls]
        assert any("Hello from Claude" in msg for msg in logged_messages)

    @patch("prompter.runner.subprocess.Popen")
    def test_interruption(self, mock_popen: MagicMock) -> None:
        """Test KeyboardInterrupt handling and re-raising."""
        mock_process = MagicMock()
        mock_process.stdout = iter([])
        mock_process.stderr = iter([])
        mock_process.wait.side_effect = KeyboardInterrupt()
        mock_popen.return_value = mock_process

        runner = ClaudeRunner()

        with pytest.raises(KeyboardInterrupt):
            runner.run_prompt("test prompt")

        mock_process.kill.assert_called_once()

    @patch("prompter.runner.subprocess.Popen")
    def test_timeout(self, mock_popen: MagicMock) -> None:
        """Test TimeoutExpired handling."""
        mock_process = MagicMock()
        mock_process.stdout = iter([])
        mock_process.stderr = iter([])
        mock_process.wait.side_effect = subprocess.TimeoutExpired(cmd="claude", timeout=10)
        mock_popen.return_value = mock_process

        runner = ClaudeRunner()

        with pytest.raises(subprocess.TimeoutExpired):
            runner.run_prompt("test prompt", timeout=10)

        mock_process.kill.assert_called_once()

    @patch("prompter.runner.logger")
    @patch("prompter.runner.subprocess.Popen")
    def test_session_logging(
        self, mock_popen: MagicMock, mock_logger: MagicMock
    ) -> None:
        """Test that session_id is logged at the start of run_prompt."""
        mock_process = MagicMock()
        mock_process.stdout = iter([
            '{"type": "result", "result": "test"}\n'
        ])
        mock_process.stderr = iter([])
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process

        runner = ClaudeRunner()
        runner.session_id = "test-sess"
        runner.run_prompt("test prompt")

        info_calls = [str(call) for call in mock_logger.info.call_args_list]
        assert any("test-sess" in msg for msg in info_calls)
