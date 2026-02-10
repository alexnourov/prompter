"""Tests for logging configuration.

Tests cover requirements: LOG-01..LOG-07.
Includes TC-17, TC-11.
"""

import json
import logging
from pathlib import Path

import pytest

from prompter.log import setup_logging


@pytest.fixture(autouse=True)
def reset_logging():
    """Reset logging configuration before and after each test."""
    # Clear handlers before test
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(logging.WARNING)  # Default level

    yield

    # Clear handlers after test
    root_logger.handlers.clear()
    root_logger.setLevel(logging.WARNING)


class TestFallbackConfiguration:
    """Tests for default (fallback) logging configuration (TC-17, LOG-05, LOG-07)."""

    def test_fallback_file_handler_format(self, tmp_path: Path) -> None:
        """Test FileHandler format in fallback mode (LOG-05)."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        # No logging.json created - should use fallback

        setup_logging(config_dir, verbose=False)

        root_logger = logging.getLogger()
        file_handler = None
        for handler in root_logger.handlers:
            if isinstance(handler, logging.FileHandler):
                file_handler = handler
                break

        assert file_handler is not None, "FileHandler not found"

        # Check format
        formatter = file_handler.formatter
        assert formatter is not None
        expected_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        assert formatter._fmt == expected_format

        # Check date format (LOG-05, REP-04: no microseconds)
        expected_datefmt = "%Y-%m-%d %H:%M:%S"
        assert formatter.datefmt == expected_datefmt, "Date format should be without microseconds"

    def test_fallback_console_handler_format(self, tmp_path: Path) -> None:
        """Test StreamHandler format in fallback mode (LOG-05)."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        # No logging.json created - should use fallback

        setup_logging(config_dir, verbose=False)

        root_logger = logging.getLogger()
        stream_handler = None
        for handler in root_logger.handlers:
            if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
                stream_handler = handler
                break

        assert stream_handler is not None, "StreamHandler not found"

        # Check format
        formatter = stream_handler.formatter
        assert formatter is not None
        expected_format = "%(asctime)s - %(message)s"
        assert formatter._fmt == expected_format

        # Check date format (LOG-05, REP-04: no microseconds)
        expected_datefmt = "%Y-%m-%d %H:%M:%S"
        assert formatter.datefmt == expected_datefmt, "Date format should be without microseconds"

    def test_fallback_log_file_path(self, tmp_path: Path) -> None:
        """Test log file path in fallback mode (LOG-07)."""
        # Test with config_dir specified
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        setup_logging(config_dir, verbose=False)

        root_logger = logging.getLogger()
        file_handler = None
        for handler in root_logger.handlers:
            if isinstance(handler, logging.FileHandler):
                file_handler = handler
                break

        assert file_handler is not None
        expected_path = config_dir / "prompter.log"
        assert Path(file_handler.baseFilename) == expected_path

    def test_fallback_log_file_path_no_config_dir(self) -> None:
        """Test log file path when config_dir is None (LOG-07)."""
        setup_logging(None, verbose=False)

        root_logger = logging.getLogger()
        file_handler = None
        for handler in root_logger.handlers:
            if isinstance(handler, logging.FileHandler):
                file_handler = handler
                break

        assert file_handler is not None
        expected_path = Path.cwd() / "prompter.log"
        assert Path(file_handler.baseFilename) == expected_path


class TestLogLevels:
    """Tests for log levels configuration (TC-11, LOG-06)."""

    def test_console_info_by_default(self, tmp_path: Path) -> None:
        """Test console handler is INFO by default (verbose=False) (LOG-06)."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        setup_logging(config_dir, verbose=False)

        root_logger = logging.getLogger()

        # Find StreamHandler (console)
        stream_handler = None
        for handler in root_logger.handlers:
            if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
                stream_handler = handler
                break

        # Find FileHandler
        file_handler = None
        for handler in root_logger.handlers:
            if isinstance(handler, logging.FileHandler):
                file_handler = handler
                break

        assert stream_handler is not None, "StreamHandler not found"
        assert file_handler is not None, "FileHandler not found"

        # Check levels
        assert stream_handler.level == logging.INFO, "Console should be INFO when verbose=False"
        assert file_handler.level == logging.DEBUG, "File should always be DEBUG"

    def test_console_debug_when_verbose(self, tmp_path: Path) -> None:
        """Test console handler is DEBUG when verbose=True (LOG-06)."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        setup_logging(config_dir, verbose=True)

        root_logger = logging.getLogger()

        # Find StreamHandler (console)
        stream_handler = None
        for handler in root_logger.handlers:
            if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
                stream_handler = handler
                break

        # Find FileHandler
        file_handler = None
        for handler in root_logger.handlers:
            if isinstance(handler, logging.FileHandler):
                file_handler = handler
                break

        assert stream_handler is not None, "StreamHandler not found"
        assert file_handler is not None, "FileHandler not found"

        # Check levels
        assert stream_handler.level == logging.DEBUG, "Console should be DEBUG when verbose=True"
        assert file_handler.level == logging.DEBUG, "File should always be DEBUG"

    def test_root_logger_always_debug(self, tmp_path: Path) -> None:
        """Test root logger is always DEBUG (LOG-06)."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        # Test with verbose=False
        setup_logging(config_dir, verbose=False)
        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG, "Root logger should always be DEBUG"

        # Reset and test with verbose=True
        root_logger.handlers.clear()
        setup_logging(config_dir, verbose=True)
        assert root_logger.level == logging.DEBUG, "Root logger should always be DEBUG"


class TestCustomConfiguration:
    """Tests for custom logging.json configuration (LOG-02, LOG-03, LOG-04)."""

    def test_custom_config_loaded(self, tmp_path: Path) -> None:
        """Test that custom logging.json is loaded (LOG-02, LOG-03)."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        # Create custom logging.json
        logging_config = {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "custom": {
                    "format": "CUSTOM: %(message)s"
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "custom",
                    "level": "WARNING"
                }
            },
            "root": {
                "level": "DEBUG",
                "handlers": ["console"]
            }
        }

        logging_json = config_dir / "logging.json"
        logging_json.write_text(json.dumps(logging_config), encoding="utf-8")

        setup_logging(config_dir, verbose=False)

        root_logger = logging.getLogger()

        # Should have one handler (from custom config)
        assert len(root_logger.handlers) >= 1

        # Find console handler
        console_handler = None
        for handler in root_logger.handlers:
            if isinstance(handler, logging.StreamHandler):
                console_handler = handler
                break

        assert console_handler is not None
        assert console_handler.level == logging.WARNING
        assert console_handler.formatter._fmt == "CUSTOM: %(message)s"

    def test_custom_config_invalid_falls_back(self, tmp_path: Path, capfd) -> None:
        """Test that invalid logging.json falls back to default (LOG-02)."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        # Create invalid logging.json
        logging_json = config_dir / "logging.json"
        logging_json.write_text("{broken json", encoding="utf-8")

        setup_logging(config_dir, verbose=False)

        # Check that warning was printed
        captured = capfd.readouterr()
        assert "Failed to load logging.json" in captured.out

        # Should have fallback handlers
        root_logger = logging.getLogger()
        assert len(root_logger.handlers) == 2  # File + Console

    def test_no_logging_json_uses_fallback(self, tmp_path: Path) -> None:
        """Test that missing logging.json uses fallback (LOG-05)."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        # No logging.json created

        setup_logging(config_dir, verbose=False)

        root_logger = logging.getLogger()

        # Should have 2 handlers: FileHandler + StreamHandler
        assert len(root_logger.handlers) == 2

        handler_types = [type(h).__name__ for h in root_logger.handlers]
        assert "FileHandler" in handler_types
        assert "StreamHandler" in handler_types


class TestLogFileCreation:
    """Tests for log file creation."""

    def test_log_file_created(self, tmp_path: Path) -> None:
        """Test that log file is created when logging occurs."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        setup_logging(config_dir, verbose=False)

        # Write a log message
        logger = logging.getLogger("test")
        logger.info("Test message")

        # Check that log file was created
        log_file = config_dir / "prompter.log"
        assert log_file.exists()

        # Verify content
        content = log_file.read_text(encoding="utf-8")
        assert "Test message" in content

    def test_log_file_utf8_encoding(self, tmp_path: Path) -> None:
        """Test that log file supports UTF-8 encoding."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        setup_logging(config_dir, verbose=False)

        # Write UTF-8 message
        logger = logging.getLogger("test")
        logger.info("Тестовое сообщение © €")

        # Read and verify
        log_file = config_dir / "prompter.log"
        content = log_file.read_text(encoding="utf-8")
        assert "Тестовое сообщение © €" in content


class TestMultipleSetupCalls:
    """Tests for calling setup_logging multiple times."""

    def test_multiple_calls_clear_handlers(self, tmp_path: Path) -> None:
        """Test that calling setup_logging multiple times clears old handlers."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        # First call
        setup_logging(config_dir, verbose=False)
        root_logger = logging.getLogger()
        first_handler_count = len(root_logger.handlers)
        assert first_handler_count == 2  # File + Console

        # Second call
        setup_logging(config_dir, verbose=True)
        second_handler_count = len(root_logger.handlers)
        assert second_handler_count == 2  # Should still be 2, not 4

        # Handlers should be new instances
        assert first_handler_count == second_handler_count
