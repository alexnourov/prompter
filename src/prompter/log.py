"""Logging configuration for Prompter.

This module handles logging setup with support for:
- Custom configuration via logging.json (LOG-02, LOG-03, LOG-04)
- Fallback to default configuration (LOG-05)
- Dual output: file (always DEBUG) + console (INFO or DEBUG based on --verbose) (LOG-06)
"""

import json
import logging
import logging.config
from pathlib import Path


def setup_logging(config_dir: Path | None, verbose: bool) -> None:
    """Set up logging configuration.

    Configuration priority (LOG-01):
    1. Custom config from logging.json if present (LOG-02, LOG-03)
    2. Fallback to default configuration (LOG-05)

    Args:
        config_dir: Configuration directory (may be None if not found)
        verbose: Enable verbose console output (--verbose flag)

    Logging behavior (LOG-06):
    - Root logger: always DEBUG level
    - File handler: always DEBUG level (full logs to file)
    - Console handler: DEBUG if verbose=True, INFO otherwise
    """
    # Try to load custom configuration (LOG-02, LOG-03)
    if config_dir is not None:
        config_file = config_dir / "logging.json"
        if config_file.exists():
            try:
                with open(config_file, encoding="utf-8") as f:
                    config = json.load(f)

                # Apply custom configuration (LOG-03, LOG-04)
                logging.config.dictConfig(config)
                return

            except (json.JSONDecodeError, ValueError, KeyError) as e:
                # If custom config fails, fall through to default
                # Use print here since logging isn't configured yet
                print(f"Warning: Failed to load logging.json: {e}. Using default configuration.")

    # Fallback to default configuration (LOG-05)
    _setup_default_logging(config_dir, verbose)


def _setup_default_logging(config_dir: Path | None, verbose: bool) -> None:
    """Set up default logging configuration when logging.json is not found.

    Configuration (LOG-05):
    - File handler: prompter.log with DEBUG level, detailed format
    - Console handler: INFO/DEBUG level based on verbose flag, simple format
    - Root logger: DEBUG level (filtering happens at handler level)

    Args:
        config_dir: Configuration directory for log file location
        verbose: Enable verbose console output
    """
    # Determine log file location
    if config_dir is not None:
        log_file = config_dir / "prompter.log"
    else:
        log_file = Path.cwd() / "prompter.log"

    # Create formatters (LOG-05)
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    console_formatter = logging.Formatter(
        "%(asctime)s - %(message)s"
    )

    # File handler: always DEBUG (LOG-06)
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)

    # Console handler: DEBUG if verbose, otherwise INFO (LOG-06)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    console_handler.setFormatter(console_formatter)

    # Configure root logger (LOG-06)
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Always DEBUG at root level

    # Clear any existing handlers (in case setup_logging is called multiple times)
    root_logger.handlers.clear()

    # Add handlers
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
