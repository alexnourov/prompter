"""Configuration module for Prompter application."""

import json
import logging
import logging.config
import os
import platform
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def find_config_dir(app_name: str, config_arg: Path | None = None) -> Path:
    """Find the configuration directory.

    Priority:
    1. Explicit config_arg if provided
    2. XDG standard (~/.config/<app_name> on Linux, %APPDATA%/<app_name> on Windows)
    3. .config folder in project root (found by searching for pyproject.toml)

    Args:
        app_name: Name of the application.
        config_arg: Explicit path to config directory (highest priority).

    Returns:
        Path to the configuration directory.
    """
    if config_arg is not None:
        return config_arg

    if platform.system() == "Windows":
        appdata = os.environ.get("APPDATA")
        if appdata:
            xdg_path = Path(appdata) / app_name
            if xdg_path.exists():
                return xdg_path
    else:
        xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
        if xdg_config_home:
            xdg_path = Path(xdg_config_home) / app_name
        else:
            xdg_path = Path.home() / ".config" / app_name

        if xdg_path.exists():
            return xdg_path

    project_root = _find_project_root()
    if project_root:
        project_config = project_root / ".config"
        if project_config.exists():
            return project_config

    if platform.system() == "Windows":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / app_name
        return Path.home() / app_name
    else:
        xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
        if xdg_config_home:
            return Path(xdg_config_home) / app_name
        return Path.home() / ".config" / app_name


def _find_project_root() -> Path | None:
    """Find the project root by searching for pyproject.toml.

    Returns:
        Path to project root or None if not found.
    """
    current = Path.cwd()

    for parent in [current, *current.parents]:
        if (parent / "pyproject.toml").exists():
            return parent

    return None


def load_settings(config_dir: Path) -> dict[str, Any]:
    """Load settings from setting.json in config directory.

    Args:
        config_dir: Path to the configuration directory.

    Returns:
        Dictionary with settings or empty dict if file not found or invalid.
    """
    settings_file = config_dir / "setting.json"

    if not settings_file.exists():
        logger.debug("Settings file not found: %s", settings_file)
        return {}

    try:
        content = settings_file.read_text(encoding="utf-8")
        settings = json.loads(content)
        logger.debug("Loaded settings from %s", settings_file)
        return settings
    except json.JSONDecodeError as e:
        logger.warning("Failed to parse settings file: %s", e)
        return {}
    except OSError as e:
        logger.warning("Failed to read settings file: %s", e)
        return {}


def setup_logging(config_dir: Path, verbose: bool = False) -> None:
    """Setup logging configuration.

    If logger.json exists in config_dir, use it with dictConfig.
    Otherwise, fall back to basicConfig with console and file handlers.

    Args:
        config_dir: Path to the configuration directory.
        verbose: Whether to enable verbose (DEBUG) console output.
    """
    logger_config_file = config_dir / "logger.json"

    if logger_config_file.exists():
        _setup_from_config_file(logger_config_file, verbose)
    else:
        _setup_fallback_logging(config_dir, verbose)


def _setup_from_config_file(config_file: Path, verbose: bool) -> None:
    """Setup logging from a JSON config file.

    Args:
        config_file: Path to logger.json.
        verbose: Whether to enable verbose console output.
    """
    try:
        content = config_file.read_text(encoding="utf-8")
        config = json.loads(content)

        handlers = config.get("handlers", {})
        for handler_name, handler_config in handlers.items():
            handler_class = handler_config.get("class", "")

            if "StreamHandler" in handler_class or handler_name in ("console", "stream"):
                handler_config["level"] = "DEBUG" if verbose else "INFO"

            elif "FileHandler" in handler_class or handler_name == "file":
                handler_config["level"] = "DEBUG"

        if "root" in config:
            config["root"]["level"] = "DEBUG"

        logging.config.dictConfig(config)

    except (json.JSONDecodeError, OSError) as e:
        print(f"Warning: Failed to load logger config: {e}")
        _setup_fallback_logging(config_file.parent, verbose)


def _setup_fallback_logging(config_dir: Path, verbose: bool) -> None:
    """Setup fallback logging with basicConfig.

    Args:
        config_dir: Path to the configuration directory.
        verbose: Whether to enable verbose console output.
    """
    config_dir.mkdir(parents=True, exist_ok=True)

    log_file = config_dir / "prompter.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    formatter = logging.Formatter("%(asctime)s - %(message)s")

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
