"""Тесты для модуля config."""

import json
import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from prompter.config import find_config_dir, load_settings, setup_logging


class TestFindConfigDir:
    """Тесты для find_config_dir."""

    def test_find_config_dir_explicit(self, tmp_path: Path) -> None:
        """Проверяет, что явно переданный путь возвращается без изменений."""
        explicit_path = tmp_path / "my_config"

        result = find_config_dir("myapp", config_arg=explicit_path)

        assert result == explicit_path

    def test_find_config_dir_xdg(self, tmp_path: Path) -> None:
        """Проверяет определение пути по XDG-стандарту."""
        xdg_config = tmp_path / ".config"
        xdg_config.mkdir()
        app_config = xdg_config / "testapp"
        app_config.mkdir()

        with patch.dict("os.environ", {"XDG_CONFIG_HOME": str(xdg_config)}):
            result = find_config_dir("testapp", config_arg=None)

        assert result == app_config

    def test_find_config_dir_xdg_home_fallback(self, tmp_path: Path) -> None:
        """Проверяет fallback на ~/.config при отсутствии XDG_CONFIG_HOME."""
        home_config = tmp_path / ".config" / "myapp"
        home_config.mkdir(parents=True)

        with (
            patch.dict("os.environ", {}, clear=True),
            patch("pathlib.Path.home", return_value=tmp_path),
        ):
            # Убираем XDG_CONFIG_HOME из окружения
            import os
            env_backup = os.environ.pop("XDG_CONFIG_HOME", None)
            try:
                result = find_config_dir("myapp", config_arg=None)
            finally:
                if env_backup:
                    os.environ["XDG_CONFIG_HOME"] = env_backup

        assert result == home_config

    def test_find_config_dir_project_root(self, tmp_path: Path) -> None:
        """Проверяет поиск .config в корне проекта."""
        # Создаём структуру проекта
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / "pyproject.toml").write_text("[tool.poetry]")
        project_config = project_root / ".config"
        project_config.mkdir()

        with (
            patch("prompter.config.Path.cwd", return_value=project_root),
            patch.dict("os.environ", {"XDG_CONFIG_HOME": str(tmp_path / "nonexistent")}),
        ):
            result = find_config_dir("myapp", config_arg=None)

        assert result == project_config

    def test_find_config_dir_fallback_to_xdg(self, tmp_path: Path) -> None:
        """Проверяет fallback на XDG когда ничего не найдено."""
        with (
            patch("prompter.config.Path.cwd", return_value=tmp_path),
            patch.dict("os.environ", {"XDG_CONFIG_HOME": str(tmp_path / ".config")}),
        ):
            result = find_config_dir("fallbackapp", config_arg=None)

        assert result == tmp_path / ".config" / "fallbackapp"


class TestLoadSettings:
    """Тесты для load_settings."""

    def test_load_settings(self, tmp_path: Path) -> None:
        """Проверяет загрузку настроек из setting.json."""
        settings = {"key": "value", "number": 42, "nested": {"a": 1}}
        settings_path = tmp_path / "setting.json"
        settings_path.write_text(json.dumps(settings), encoding="utf-8")

        result = load_settings(tmp_path)

        assert result == settings

    def test_load_settings_file_not_found(self, tmp_path: Path) -> None:
        """Проверяет возврат пустого dict при отсутствии файла."""
        result = load_settings(tmp_path)

        assert result == {}

    def test_load_settings_invalid_json(self, tmp_path: Path) -> None:
        """Проверяет возврат пустого dict при невалидном JSON."""
        settings_path = tmp_path / "setting.json"
        settings_path.write_text("not valid json {", encoding="utf-8")

        result = load_settings(tmp_path)

        assert result == {}


class TestSetupLogging:
    """Тесты для setup_logging."""

    def test_setup_logging_basic(self, tmp_path: Path) -> None:
        """Проверяет базовую настройку логирования."""
        # Сбрасываем конфигурацию логгера
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        setup_logging(tmp_path, verbose=False)

        assert root_logger.level == logging.INFO

    def test_setup_logging_verbose(self, tmp_path: Path) -> None:
        """Проверяет включение verbose режима."""
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        setup_logging(tmp_path, verbose=True)

        assert root_logger.level == logging.DEBUG

    def test_setup_logging_from_config(self, tmp_path: Path) -> None:
        """Проверяет загрузку конфигурации из logger.json."""
        logger_config = {
            "version": 1,
            "disable_existing_loggers": False,
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "level": "WARNING",
                }
            },
            "root": {
                "level": "WARNING",
                "handlers": ["console"],
            },
        }
        config_path = tmp_path / "logger.json"
        config_path.write_text(json.dumps(logger_config), encoding="utf-8")

        setup_logging(tmp_path, verbose=False)

        root_logger = logging.getLogger()
        assert root_logger.level == logging.WARNING
