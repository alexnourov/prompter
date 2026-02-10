"""Configuration management for Prompter.

This module handles:
- Finding configuration directories across different OS platforms
- Loading settings from JSON files
- Merging CLI arguments with settings and defaults
"""

import json
import logging
import os
import platform
from pathlib import Path

logger = logging.getLogger(__name__)


def find_config_dir(app_name: str, config_override: Path | None = None) -> Path | None:
    """Find configuration directory using priority-based search.

    Priority order (CFG-02):
    1. Explicit override (raises SystemExit if doesn't exist)
    2. OS-specific standard locations
    3. Project root .config directory (fallback)
    4. None if nothing found

    Args:
        app_name: Application name for config directory
        config_override: Optional explicit path to config directory

    Returns:
        Path to config directory, or None if not found

    Raises:
        SystemExit: If config_override is specified but doesn't exist
    """
    # Priority 1: Explicit override
    if config_override is not None:
        if not config_override.is_dir():
            raise SystemExit(f"Config directory does not exist: {config_override}")
        return Path(config_override)

    # Priority 2: OS-specific standard locations
    system = platform.system()

    if system == "Linux":
        # Linux: $XDG_CONFIG_HOME/app_name or ~/.config/app_name
        xdg = os.environ.get("XDG_CONFIG_HOME")
        base = Path(xdg) if xdg else Path.home() / ".config"
        candidate = base / app_name
        if candidate.is_dir():
            return candidate

    elif system == "Darwin":
        # macOS: ~/Library/Application Support/app_name
        base = Path.home() / "Library" / "Application Support"
        candidate = base / app_name
        if candidate.is_dir():
            return candidate

    elif system == "Windows":
        # Windows: %APPDATA%/app_name
        appdata = os.environ.get("APPDATA")
        if appdata:
            base = Path(appdata)
            candidate = base / app_name
            if candidate.is_dir():
                return candidate

    # Priority 3: Fallback to .config in project root (CFG-05)
    # Find project root by looking for pyproject.toml
    current = Path.cwd()
    for parent in [current] + list(current.parents):
        if (parent / "pyproject.toml").exists():
            # Found project root
            config_candidate = parent / ".config"
            if config_candidate.is_dir():
                return config_candidate
            break

    # Priority 4: Nothing found
    return None


def load_settings(config_dir: Path) -> dict:
    """Load settings from settings.json in config directory.

    Args:
        config_dir: Path to configuration directory

    Returns:
        Dictionary of settings, or empty dict if file not found or invalid

    File format (CFG-06):
        - JSON object with configuration keys
        - UTF-8 encoding
        - Missing or invalid file returns empty dict (not an error)
    """
    settings_file = config_dir / "settings.json"

    try:
        with open(settings_file, encoding="utf-8") as f:
            settings = json.load(f)

        if not isinstance(settings, dict):
            logger.warning(f"settings.json is not a JSON object, ignoring")
            return {}

        return settings

    except FileNotFoundError:
        # Not an error - just no settings file
        return {}

    except json.JSONDecodeError as e:
        logger.warning(f"Invalid JSON in settings.json: {e}. Ignoring settings.")
        return {}

    except Exception as e:
        logger.warning(f"Error reading settings.json: {e}. Ignoring settings.")
        return {}


def merge_config(cli_args: dict, settings: dict, defaults: dict) -> dict:
    """Merge configuration from CLI args, settings file, and defaults.

    Priority order (CFG-07):
    1. CLI arguments (if explicitly provided, not None)
    2. Settings from settings.json
    3. Default values

    Type validation:
    - For keys with non-None defaults: validate type matches default type
    - For keys with None defaults: skip type validation (accept any type)
    - Invalid types log WARNING and use default

    Args:
        cli_args: Arguments from command line (may contain None for unspecified)
        settings: Settings loaded from settings.json
        defaults: Default values for all configuration keys

    Returns:
        Merged configuration dictionary
    """
    merged = {}

    for key in defaults:
        # Priority 1: CLI argument explicitly provided
        if cli_args.get(key) is not None:
            merged[key] = cli_args[key]

        # Priority 2: Setting from settings.json
        elif key in settings:
            # Type validation (skip for None-default keys like source_encoding)
            if defaults[key] is None:
                # None-default: accept any type without validation
                merged[key] = settings[key]
            elif not isinstance(settings[key], type(defaults[key])):
                # Type mismatch: log warning and use default
                logger.warning(
                    f"Invalid type for '{key}' in settings.json: "
                    f"expected {type(defaults[key]).__name__}, "
                    f"got {type(settings[key]).__name__}. Using default."
                )
                merged[key] = defaults[key]
            else:
                # Type matches: use setting
                merged[key] = settings[key]

        # Priority 3: Default value
        else:
            merged[key] = defaults[key]

    return merged
