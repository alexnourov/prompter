"""Tests for config module."""

import json
import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from src.prompter.config import find_config_dir, load_settings, setup_logging


class TestFindConfigDir:
    """Test suite for find_config_dir function."""

    def test_find_config_dir_explicit(self, tmp_path: Path) -> None:
        """Test that explicit config_arg is returned when provided."""
        explicit_path = tmp_path / "custom_config"
        explicit_path.mkdir()

        result = find_config_dir("prompter", config_arg=explicit_path)

        assert result == explicit_path

    def test_find_config_dir_explicit_not_exists(self, tmp_path: Path) -> None:
        """Test that explicit config_arg is returned even if it doesn't exist."""
        explicit_path = tmp_path / "nonexistent_config"

        result = find_config_dir("prompter", config_arg=explicit_path)

        assert result == explicit_path

    def test_find_config_dir_xdg(self, tmp_path: Path) -> None:
        """Test that XDG config path is returned when it exists."""
        xdg_config = tmp_path / ".config" / "prompter"
        xdg_config.mkdir(parents=True)

        with patch.dict("os.environ", {"XDG_CONFIG_HOME": ""}, clear=False):
            with patch("src.prompter.config.Path.home", return_value=tmp_path):
                result = find_config_dir("prompter")

        assert result == xdg_config

    def test_find_config_dir_xdg_env_variable(self, tmp_path: Path) -> None:
        """Test that XDG_CONFIG_HOME environment variable is respected."""
        custom_xdg = tmp_path / "custom_xdg"
        custom_xdg.mkdir()
        app_config = custom_xdg / "prompter"
        app_config.mkdir()

        with patch.dict("os.environ", {"XDG_CONFIG_HOME": str(custom_xdg)}):
            with patch("src.prompter.config.platform.system", return_value="Linux"):
                result = find_config_dir("prompter")

        assert result == app_config

    def test_find_config_dir_windows(self, tmp_path: Path) -> None:
        """Test that APPDATA is used on Windows."""
        appdata = tmp_path / "AppData" / "Roaming"
        appdata.mkdir(parents=True)
        app_config = appdata / "prompter"
        app_config.mkdir()

        with patch("src.prompter.config.platform.system", return_value="Windows"):
            with patch.dict("os.environ", {"APPDATA": str(appdata)}):
                result = find_config_dir("prompter")

        assert result == app_config

    def test_find_config_dir_project_fallback(self, tmp_path: Path) -> None:
        """Test fallback to project .config directory."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / "pyproject.toml").write_text("[tool.poetry]")
        project_config = project_root / ".config"
        project_config.mkdir()

        with patch("src.prompter.config.Path.cwd", return_value=project_root):
            with patch("src.prompter.config.Path.home", return_value=tmp_path / "home"):
                with patch.dict("os.environ", {"XDG_CONFIG_HOME": ""}, clear=False):
                    result = find_config_dir("prompter")

        assert result == project_config


class TestLoadSettings:
    """Test suite for load_settings function."""

    def test_load_settings(self, tmp_path: Path) -> None:
        """Test loading settings from valid JSON file."""
        settings_data = {"timeout": 3600, "verbose": True}
        settings_file = tmp_path / "setting.json"
        settings_file.write_text(json.dumps(settings_data), encoding="utf-8")

        result = load_settings(tmp_path)

        assert result == settings_data

    def test_load_settings_file_not_found(self, tmp_path: Path) -> None:
        """Test that empty dict is returned when file doesn't exist."""
        result = load_settings(tmp_path)

        assert result == {}

    def test_load_settings_invalid_json(self, tmp_path: Path) -> None:
        """Test that empty dict is returned for invalid JSON."""
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

    def test_setup_logging_levels_verbose_false(self, tmp_path: Path) -> None:
        """Test that console handler is INFO when verbose=False."""
        setup_logging(tmp_path, verbose=False)

        root_logger = logging.getLogger()
        console_handler = None
        file_handler = None

        for handler in root_logger.handlers:
            if isinstance(handler, logging.StreamHandler) and not isinstance(
                handler, logging.FileHandler
            ):
                console_handler = handler
            elif isinstance(handler, logging.FileHandler):
                file_handler = handler

        assert console_handler is not None
        assert console_handler.level == logging.INFO

        assert file_handler is not None
        assert file_handler.level == logging.DEBUG

    def test_setup_logging_levels_verbose_true(self, tmp_path: Path) -> None:
        """Test that console handler is DEBUG when verbose=True."""
        setup_logging(tmp_path, verbose=True)

        root_logger = logging.getLogger()
        console_handler = None

        for handler in root_logger.handlers:
            if isinstance(handler, logging.StreamHandler) and not isinstance(
                handler, logging.FileHandler
            ):
                console_handler = handler

        assert console_handler is not None
        assert console_handler.level == logging.DEBUG

    def test_setup_logging_creates_log_file(self, tmp_path: Path) -> None:
        """Test that log file is created in config directory."""
        setup_logging(tmp_path, verbose=False)

        log_file = tmp_path / "prompter.log"
        assert log_file.exists()

    def test_setup_logging_from_config_file(self, tmp_path: Path) -> None:
        """Test logging setup from logger.json config file."""
        logger_config = {
            "version": 1,
            "disable_existing_loggers": False,
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "level": "WARNING",
                    "stream": "ext://sys.stdout",
                },
                "file": {
                    "class": "logging.FileHandler",
                    "level": "WARNING",
                    "filename": str(tmp_path / "app.log"),
                },
            },
            "root": {"level": "WARNING", "handlers": ["console", "file"]},
        }
        config_file = tmp_path / "logger.json"
        config_file.write_text(json.dumps(logger_config), encoding="utf-8")

        setup_logging(tmp_path, verbose=False)

        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG

        console_handler = None
        file_handler = None
        for handler in root_logger.handlers:
            if isinstance(handler, logging.StreamHandler) and not isinstance(
                handler, logging.FileHandler
            ):
                console_handler = handler
            elif isinstance(handler, logging.FileHandler):
                file_handler = handler

        assert console_handler is not None
        assert console_handler.level == logging.INFO

        assert file_handler is not None
        assert file_handler.level == logging.DEBUG

    def test_setup_logging_from_config_file_verbose(self, tmp_path: Path) -> None:
        """Test logging setup from logger.json with verbose=True."""
        logger_config = {
            "version": 1,
            "disable_existing_loggers": False,
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "level": "WARNING",
                    "stream": "ext://sys.stdout",
                },
            },
            "root": {"level": "WARNING", "handlers": ["console"]},
        }
        config_file = tmp_path / "logger.json"
        config_file.write_text(json.dumps(logger_config), encoding="utf-8")

        setup_logging(tmp_path, verbose=True)

        root_logger = logging.getLogger()
        console_handler = None
        for handler in root_logger.handlers:
            if isinstance(handler, logging.StreamHandler) and not isinstance(
                handler, logging.FileHandler
            ):
                console_handler = handler

        assert console_handler is not None
        assert console_handler.level == logging.DEBUG
