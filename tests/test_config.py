"""Tests for config module."""

import json
import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from prompter.config import find_config_dir, load_settings, setup_logging


class TestFindConfigDir:
    """Test suite for find_config_dir function."""

    def test_find_config_dir_explicit(self, tmp_path: Path) -> None:
        """Test that explicit config_arg is returned as-is."""
        explicit_path = tmp_path / "my_config"

        result = find_config_dir("test_app", config_arg=explicit_path)

        assert result == explicit_path

    def test_find_config_dir_xdg_linux(self, tmp_path: Path) -> None:
        """Test XDG path on Linux."""
        xdg_config = tmp_path / ".config" / "test_app"
        xdg_config.mkdir(parents=True)

        with patch("prompter.config.platform.system", return_value="Linux"):
            with patch.dict("os.environ", {"XDG_CONFIG_HOME": str(tmp_path / ".config")}):
                result = find_config_dir("test_app")

        assert result == xdg_config

    def test_find_config_dir_xdg_default(self, tmp_path: Path) -> None:
        """Test default XDG path (~/.config) when XDG_CONFIG_HOME is not set."""
        fake_home = tmp_path / "home"
        config_dir = fake_home / ".config" / "test_app"
        config_dir.mkdir(parents=True)

        with patch("prompter.config.platform.system", return_value="Linux"):
            with patch.dict("os.environ", {}, clear=True):
                with patch("prompter.config.Path.home", return_value=fake_home):
                    result = find_config_dir("test_app")

        assert result == config_dir

    def test_find_config_dir_windows(self, tmp_path: Path) -> None:
        """Test APPDATA path on Windows."""
        appdata = tmp_path / "AppData" / "Roaming"
        config_dir = appdata / "test_app"
        config_dir.mkdir(parents=True)

        with patch("prompter.config.platform.system", return_value="Windows"):
            with patch.dict("os.environ", {"APPDATA": str(appdata)}):
                result = find_config_dir("test_app")

        assert result == config_dir

    def test_find_config_dir_project_root(self, tmp_path: Path) -> None:
        """Test fallback to project .config directory."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / "pyproject.toml").write_text("[tool.poetry]", encoding="utf-8")
        config_dir = project_root / ".config"
        config_dir.mkdir()

        with patch("prompter.config.platform.system", return_value="Linux"):
            with patch.dict("os.environ", {}, clear=True):
                with patch("prompter.config.Path.home", return_value=tmp_path / "nonexistent"):
                    with patch("prompter.config.Path.cwd", return_value=project_root):
                        result = find_config_dir("test_app")

        assert result == config_dir


class TestLoadSettings:
    """Test suite for load_settings function."""

    def test_load_settings(self, tmp_path: Path) -> None:
        """Test loading settings from setting.json."""
        settings_file = tmp_path / "setting.json"
        settings_data = {"timeout": 3600, "verbose": True}
        settings_file.write_text(json.dumps(settings_data), encoding="utf-8")

        result = load_settings(tmp_path)

        assert result == settings_data

    def test_load_settings_file_not_found(self, tmp_path: Path) -> None:
        """Test empty dict returned when file doesn't exist."""
        result = load_settings(tmp_path)

        assert result == {}

    def test_load_settings_invalid_json(self, tmp_path: Path) -> None:
        """Test empty dict returned on invalid JSON."""
        settings_file = tmp_path / "setting.json"
        settings_file.write_text("not valid json {", encoding="utf-8")

        result = load_settings(tmp_path)

        assert result == {}


class TestSetupLogging:
    """Test suite for setup_logging function."""

    def teardown_method(self) -> None:
        """Clean up logging handlers after each test."""
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
            handler.close()

    def test_setup_logging_fallback_verbose_false(self, tmp_path: Path) -> None:
        """Test fallback logging with verbose=False."""
        setup_logging(tmp_path, verbose=False)

        root_logger = logging.getLogger()

        console_handlers = [
            h for h in root_logger.handlers
            if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
        ]
        file_handlers = [
            h for h in root_logger.handlers
            if isinstance(h, logging.FileHandler)
        ]

        assert len(console_handlers) >= 1
        assert console_handlers[0].level == logging.INFO

        assert len(file_handlers) >= 1
        assert file_handlers[0].level == logging.DEBUG

    def test_setup_logging_fallback_verbose_true(self, tmp_path: Path) -> None:
        """Test fallback logging with verbose=True."""
        setup_logging(tmp_path, verbose=True)

        root_logger = logging.getLogger()

        console_handlers = [
            h for h in root_logger.handlers
            if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
        ]

        assert len(console_handlers) >= 1
        assert console_handlers[0].level == logging.DEBUG

    def test_setup_logging_from_config_file(self, tmp_path: Path) -> None:
        """Test logging setup from logger.json config file."""
        logger_config = {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "simple": {
                    "format": "%(asctime)s - %(message)s"
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "level": "WARNING",
                    "formatter": "simple"
                },
                "file": {
                    "class": "logging.FileHandler",
                    "level": "WARNING",
                    "formatter": "simple",
                    "filename": str(tmp_path / "test.log")
                }
            },
            "root": {
                "level": "WARNING",
                "handlers": ["console", "file"]
            }
        }

        config_file = tmp_path / "logger.json"
        config_file.write_text(json.dumps(logger_config), encoding="utf-8")

        setup_logging(tmp_path, verbose=False)

        root_logger = logging.getLogger()

        assert root_logger.level == logging.DEBUG

        console_handlers = [
            h for h in root_logger.handlers
            if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
        ]
        file_handlers = [
            h for h in root_logger.handlers
            if isinstance(h, logging.FileHandler)
        ]

        if console_handlers:
            assert console_handlers[0].level == logging.INFO

        if file_handlers:
            assert file_handlers[0].level == logging.DEBUG

    def test_setup_logging_creates_log_file(self, tmp_path: Path) -> None:
        """Test that log file is created in fallback mode."""
        setup_logging(tmp_path, verbose=False)

        log_file = tmp_path / "prompter.log"
        assert log_file.exists()
