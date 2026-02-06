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
    """Determine the configuration directory path.

    Priority order:
    1. Explicit config_arg if provided
    2. XDG standard (~/.config/<app_name> on Linux, %APPDATA%/<app_name> on Windows)
    3. .config folder in project root (found by locating pyproject.toml)

    Args:
        app_name: Application name for the config directory.
        config_arg: Explicit path to config directory (highest priority).

    Returns:
        Path to the configuration directory.
    """
    if config_arg is not None:
        return config_arg

    xdg_config = _get_xdg_config_dir(app_name)
    if xdg_config.exists():
        return xdg_config

    project_config = _find_project_config_dir()
    if project_config is not None and project_config.exists():
        return project_config

    return xdg_config


def _get_xdg_config_dir(app_name: str) -> Path:
    """Get XDG-compliant config directory.

    Args:
        app_name: Application name for the config directory.

    Returns:
        Path to XDG config directory.
    """
    system = platform.system()

    if system == "Windows":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / app_name
        return Path.home() / "AppData" / "Roaming" / app_name

    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config_home:
        return Path(xdg_config_home) / app_name

    return Path.home() / ".config" / app_name


def _find_project_config_dir() -> Path | None:
    """Find .config directory in project root.

    Searches for pyproject.toml by traversing up from current directory.

    Returns:
        Path to .config in project root, or None if not found.
    """
    current = Path.cwd()

    for parent in [current, *current.parents]:
        pyproject = parent / "pyproject.toml"
        if pyproject.exists():
            return parent / ".config"

    return None


def load_settings(config_dir: Path) -> dict[str, Any]:
    """Load application settings from config directory.

    Args:
        config_dir: Path to the configuration directory.

    Returns:
        Dictionary of settings, or empty dict if file not found or invalid.
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
    """Configure logging for the application.

    If logger.json exists in config_dir, uses dictConfig with modified levels.
    Otherwise, sets up basic logging with console and file handlers.

    Args:
        config_dir: Path to the configuration directory.
        verbose: If True, set console handler to DEBUG level.
    """
    logger_config_file = config_dir / "logger.json"

    if logger_config_file.exists():
        _setup_logging_from_file(logger_config_file, verbose)
    else:
        _setup_logging_fallback(config_dir, verbose)


def _setup_logging_from_file(config_file: Path, verbose: bool) -> None:
    """Configure logging from JSON config file.

    Args:
        config_file: Path to logger.json file.
        verbose: If True, set console handler to DEBUG level.
    """
    try:
        content = config_file.read_text(encoding="utf-8")
        config = json.loads(content)
    except (json.JSONDecodeError, OSError) as e:
        print(f"Warning: Failed to load logger config: {e}")
        _setup_logging_fallback(config_file.parent, verbose)
        return

    handlers = config.get("handlers", {})
    for handler_name, handler_config in handlers.items():
        handler_name_lower = handler_name.lower()
        handler_class = handler_config.get("class", "").lower()

        is_console = (
            "console" in handler_name_lower
            or "stream" in handler_name_lower
            or "streamhandler" in handler_class
        )
        is_file = (
            "file" in handler_name_lower
            or "filehandler" in handler_class
        )

        if is_console:
            handler_config["level"] = "DEBUG" if verbose else "INFO"
        elif is_file:
            handler_config["level"] = "DEBUG"

    if "root" in config:
        config["root"]["level"] = "DEBUG"

    logging.config.dictConfig(config)


def _setup_logging_fallback(config_dir: Path, verbose: bool) -> None:
    """Configure basic logging when no config file exists.

    Args:
        config_dir: Path to the configuration directory for log file.
        verbose: If True, set console handler to DEBUG level.
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
