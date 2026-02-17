"""Logging configuration (LOG-01..LOG-06, REP-04)."""

from __future__ import annotations

import json
import logging
import logging.config
from pathlib import Path

logger = logging.getLogger(__name__)

_DATE_FMT = "%Y-%m-%d %H:%M:%S"
_FILE_FMT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
_CONSOLE_FMT = "%(asctime)s - %(message)s"


def setup_logging(config_dir: Path | None, verbose: bool) -> None:
    """Configure logging from JSON config or fallback (LOG-01..LOG-06).

    Args:
        config_dir: Directory containing logging.json, or None.
        verbose: If True, console handler uses DEBUG; otherwise INFO.
    """
    # 1. Try custom config file (LOG-02, LOG-03)
    if config_dir is not None:
        config_file = config_dir / "logging.json"
        if config_file.is_file():
            try:
                text = config_file.read_text(encoding="utf-8")
                config = json.loads(text)
                logging.config.dictConfig(config)  # LOG-03, LOG-04
                return
            except Exception as exc:
                # Fallback on any error — will set up default below
                logging.getLogger(__name__).warning(
                    "Failed to load %s: %s. Using fallback.", config_file, exc
                )

    # 2. Fallback configuration (LOG-05)
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)  # LOG-06: root always DEBUG

    # FileHandler — DEBUG level, detailed format
    log_dir = config_dir if config_dir is not None else Path.cwd()
    log_file = log_dir / "prompter.log"

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)  # LOG-06
    file_handler.setFormatter(
        logging.Formatter(_FILE_FMT, datefmt=_DATE_FMT)
    )

    # StreamHandler — DEBUG/INFO based on verbose
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    stream_handler.setFormatter(
        logging.Formatter(_CONSOLE_FMT, datefmt=_DATE_FMT)
    )

    root.addHandler(file_handler)
    root.addHandler(stream_handler)
