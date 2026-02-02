"""Тесты для модуля runner."""

import json
from unittest.mock import MagicMock, patch

import pytest

from prompter.runner import ClaudeRunner


@pytest.fixture
def mock_popen():
    """Фикстура для мокирования subprocess.Popen."""
    with patch("prompter.runner.subprocess.Popen") as mock:
        process_mock = MagicMock()
        process_mock.communicate.return_value = ('{"session_id": "test-123"}', "")
        mock.return_value = process_mock
        yield mock


class TestClaudeRunner:
    """Тесты для ClaudeRunner."""

    def test_first_run(self, mock_popen: MagicMock) -> None:
        """Проверяет первый запуск без --resume."""
        runner = ClaudeRunner()
        runner.run_prompt("Hello")

        mock_popen.assert_called_once()
        call_args = mock_popen.call_args[0][0]

        assert "--dangerously-skip-permissions" in call_args
        assert "--resume" not in call_args

    def test_subsequent_run(self, mock_popen: MagicMock) -> None:
        """Проверяет повторный запуск с --resume."""
        runner = ClaudeRunner()
        runner.session_id = "existing-session-456"

        runner.run_prompt("Hello again")

        mock_popen.assert_called_once()
        call_args = mock_popen.call_args[0][0]

        assert "--resume" in call_args
        resume_index = call_args.index("--resume")
        assert call_args[resume_index + 1] == "existing-session-456"

    def test_json_parsing(self, mock_popen: MagicMock) -> None:
        """Проверяет корректный парсинг JSON-ответа."""
        expected_response = {
            "session_id": "new-session-789",
            "result": "Hello, world!",
            "cost_usd": 0.01,
        }
        process_mock = mock_popen.return_value
        process_mock.communicate.return_value = (json.dumps(expected_response), "")

        runner = ClaudeRunner()
        result = runner.run_prompt("Test prompt")

        assert result == expected_response
        assert runner.session_id == "new-session-789"

    def test_interruption(self) -> None:
        """Проверяет корректную обработку KeyboardInterrupt."""
        with patch("prompter.runner.subprocess.Popen") as mock_popen:
            process_mock = MagicMock()
            process_mock.communicate.side_effect = KeyboardInterrupt()
            mock_popen.return_value = process_mock

            runner = ClaudeRunner()

            with pytest.raises(KeyboardInterrupt):
                runner.run_prompt("Test")

            process_mock.kill.assert_called_once()
            process_mock.wait.assert_called_once()

    def test_json_decode_error(self) -> None:
        """Проверяет обработку невалидного JSON."""
        with patch("prompter.runner.subprocess.Popen") as mock_popen:
            process_mock = MagicMock()
            process_mock.communicate.return_value = ("not valid json", "")
            mock_popen.return_value = process_mock

            runner = ClaudeRunner()

            with pytest.raises(ValueError, match="Не удалось распарсить"):
                runner.run_prompt("Test")

    def test_stderr_logging(self, mock_popen: MagicMock, caplog) -> None:
        """Проверяет логирование stderr."""
        process_mock = mock_popen.return_value
        process_mock.communicate.return_value = (
            '{"session_id": "test"}',
            "Warning message",
        )

        runner = ClaudeRunner()

        with caplog.at_level("WARNING"):
            runner.run_prompt("Test")

        assert "Warning message" in caplog.text

    def test_session_id_not_overwritten(self, mock_popen: MagicMock) -> None:
        """Проверяет, что session_id не перезаписывается при повторных вызовах."""
        runner = ClaudeRunner()
        runner.session_id = "original-session"

        process_mock = mock_popen.return_value
        process_mock.communicate.return_value = (
            '{"session_id": "new-session"}',
            "",
        )

        runner.run_prompt("Test")

        assert runner.session_id == "original-session"
