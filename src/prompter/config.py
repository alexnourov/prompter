"""Configuration management (CFG-01..CFG-07)."""

from __future__ import annotations

import json
import logging
import os
import platform
from pathlib import Path

logger = logging.getLogger(__name__)


def find_config_dir(
    app_name: str, config_override: Path | None = None
) -> Path | None:
    """Locate the configuration directory (CFG-01..CFG-05).

    Priority:
        1. Explicit override (must exist).
        2. OS-standard config directory.
        3. Fallback: .config in project root (pyproject.toml).
        4. None.
    """
    # 1. Explicit override
    if config_override is not None:
        p = Path(config_override)
        if not p.is_dir():
            raise SystemExit(
                f"Config directory does not exist: {config_override}"
            )
        return p

    # 2. OS-standard directory
    system = platform.system()

    if system == "Linux":
        xdg = os.environ.get("XDG_CONFIG_HOME")
        base = Path(xdg) if xdg else Path.home() / ".config"
        candidate = base / app_name
        if candidate.is_dir():
            return candidate

    elif system == "Darwin":
        base = Path.home() / "Library" / "Application Support"
        candidate = base / app_name
        if candidate.is_dir():
            return candidate

    elif system == "Windows":
        appdata = os.environ.get("APPDATA")
        if appdata:
            base = Path(appdata)
            candidate = base / app_name
            if candidate.is_dir():
                return candidate

    # 3. Fallback: .config in project root (pyproject.toml)
    current = Path.cwd()
    for directory in [current, *current.parents]:
        if (directory / "pyproject.toml").is_file():
            fallback = directory / ".config"
            if fallback.is_dir():
                return fallback
            break

    # 4. Not found
    return None


def load_settings(config_dir: Path) -> dict:
    """Load settings.json from config_dir (CFG-06).

    Returns:
        Parsed dict, or empty dict on error.
    """
    settings_path = config_dir / "settings.json"
    try:
        text = settings_path.read_text(encoding="utf-8")
        return json.loads(text)
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load %s: %s", settings_path, exc)
        return {}


def merge_config(cli_args: dict, settings: dict, defaults: dict) -> dict:
    """Merge CLI args, settings, and defaults (CFG-07).

    Priority: CLI (non-None) > settings.json > defaults.
    Type validation against defaults, skipped for None-default keys.
    """
    merged: dict = {}

    for key in defaults:
        if cli_args.get(key) is not None:
            merged[key] = cli_args[key]
        elif key in settings:
            if defaults[key] is None:
                merged[key] = settings[key]
            elif not isinstance(settings[key], type(defaults[key])):
                logger.warning(
                    "Invalid type for '%s' in settings.json: "
                    "expected %s, got %s. Using default.",
                    key,
                    type(defaults[key]).__name__,
                    type(settings[key]).__name__,
                )
                merged[key] = defaults[key]
            else:
                merged[key] = settings[key]
        else:
            merged[key] = defaults[key]

    return merged
