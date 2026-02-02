"""Модуль для работы с конфигурацией приложения."""

import json
import logging
import logging.config
import os
import platform
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def find_config_dir(app_name: str, config_arg: Path | None = None) -> Path:
    """Определяет путь к папке с конфигурацией.

    Приоритет:
    1. Аргумент config_arg (если передан).
    2. XDG-стандарт (~/.config/<app_name> на Linux, %APPDATA%/<app_name> на Windows).
    3. Папка .config в корне проекта (ищется по pyproject.toml).

    Args:
        app_name: Имя приложения для формирования пути.
        config_arg: Явно указанный путь к конфигурации.

    Returns:
        Путь к директории конфигурации.
    """
    # Приоритет 1: явный аргумент
    if config_arg is not None:
        return config_arg

    # Приоритет 2: XDG-стандарт
    xdg_path = _get_xdg_config_path(app_name)
    if xdg_path.exists():
        return xdg_path

    # Приоритет 3: .config в корне проекта
    project_root = _find_project_root()
    if project_root is not None:
        project_config = project_root / ".config"
        if project_config.exists():
            return project_config

    # Fallback: XDG-путь (даже если не существует)
    return xdg_path


def _get_xdg_config_path(app_name: str) -> Path:
    """Возвращает путь к конфигу по XDG-стандарту."""
    system = platform.system()

    if system == "Windows":
        base = os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")
        return Path(base) / app_name
    else:
        # Linux, macOS и другие Unix-подобные
        xdg_config = os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")
        return Path(xdg_config) / app_name


def _find_project_root() -> Path | None:
    """Ищет корень проекта по наличию pyproject.toml."""
    current = Path.cwd()

    for parent in [current, *current.parents]:
        if (parent / "pyproject.toml").exists():
            return parent

    return None


def load_settings(config_dir: Path) -> dict[str, Any]:
    """Загружает настройки из setting.json.

    Args:
        config_dir: Путь к директории конфигурации.

    Returns:
        Словарь настроек или пустой dict при ошибке.
    """
    settings_path = config_dir / "setting.json"

    if not settings_path.exists():
        return {}

    try:
        content = settings_path.read_text(encoding="utf-8")
        return json.loads(content)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("Ошибка чтения настроек из %s: %s", settings_path, e)
        return {}


def setup_logging(config_dir: Path, verbose: bool = False) -> None:
    """Настраивает систему логирования.

    Args:
        config_dir: Путь к директории конфигурации.
        verbose: Включить подробный вывод (уровень DEBUG).
    """
    logger_config_path = config_dir / "logger.json"

    if logger_config_path.exists():
        try:
            content = logger_config_path.read_text(encoding="utf-8")
            config = json.loads(content)
            logging.config.dictConfig(config)
        except (OSError, json.JSONDecodeError, ValueError) as e:
            logging.warning("Ошибка загрузки конфига логгера: %s", e)
            _setup_basic_logging()
    else:
        _setup_basic_logging()

    # Override уровня при verbose
    if verbose:
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        for handler in root_logger.handlers:
            handler.setLevel(logging.DEBUG)


def _setup_basic_logging() -> None:
    """Настраивает базовое логирование."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(message)s",
    )
