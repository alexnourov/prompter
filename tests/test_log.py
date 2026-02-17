"""Tests for prompter.log (LOG-01..LOG-07, REP-04)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from prompter.log import setup_logging


@pytest.fixture(autouse=True)
def _clean_root_handlers():
    """Remove all handlers from root logger before and after each test."""
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level
    root.handlers.clear()
    yield
    root.handlers.clear()
    root.handlers.extend(original_handlers)
    root.setLevel(original_level)


def _find_handler(handler_type: type) -> logging.Handler | None:
    """Find the first handler of the given type on the root logger."""
    for h in logging.getLogger().handlers:
        if type(h) is handler_type:
            return h
    return None


class TestFallbackLogging:
    """Tests for fallback logging configuration (LOG-05..LOG-07)."""

    def test_fallback_file_handler_format(self, tmp_path: Path) -> None:
        """LOG-05/REP-04: FileHandler format and datefmt."""
        setup_logging(config_dir=tmp_path, verbose=False)

        fh = _find_handler(logging.FileHandler)
        assert fh is not None

        fmt = fh.formatter
        assert fmt is not None
        assert fmt._fmt == "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        assert fmt.datefmt == "%Y-%m-%d %H:%M:%S"

    def test_fallback_console_handler_format(self, tmp_path: Path) -> None:
        """LOG-05/REP-04: StreamHandler format and datefmt."""
        setup_logging(config_dir=tmp_path, verbose=False)

        sh = _find_handler(logging.StreamHandler)
        assert sh is not None

        fmt = sh.formatter
        assert fmt is not None
        assert fmt._fmt == "%(asctime)s - %(message)s"
        assert fmt.datefmt == "%Y-%m-%d %H:%M:%S"

    def test_fallback_log_file_path(self, tmp_path: Path) -> None:
        """LOG-07: log file in config_dir, or cwd when None."""
        # With config_dir
        setup_logging(config_dir=tmp_path, verbose=False)

        fh = _find_handler(logging.FileHandler)
        assert fh is not None
        assert Path(fh.baseFilename) == tmp_path / "prompter.log"

        # Clean up for second call
        fh.close()
        root = logging.getLogger()
        root.handlers.clear()

        # With config_dir=None → cwd
        setup_logging(config_dir=None, verbose=False)

        fh2 = _find_handler(logging.FileHandler)
        assert fh2 is not None
        assert Path(fh2.baseFilename) == Path.cwd() / "prompter.log"

        # Clean up created log file
        fh2.close()
        log_file = Path.cwd() / "prompter.log"
        if log_file.exists():
            log_file.unlink()

    def test_console_info_by_default(self, tmp_path: Path) -> None:
        """LOG-06: verbose=False → StreamHandler INFO, FileHandler DEBUG."""
        setup_logging(config_dir=tmp_path, verbose=False)

        sh = _find_handler(logging.StreamHandler)
        assert sh is not None
        assert sh.level == logging.INFO

        fh = _find_handler(logging.FileHandler)
        assert fh is not None
        assert fh.level == logging.DEBUG

    def test_console_debug_when_verbose(self, tmp_path: Path) -> None:
        """LOG-06: verbose=True → StreamHandler DEBUG, FileHandler DEBUG."""
        setup_logging(config_dir=tmp_path, verbose=True)

        sh = _find_handler(logging.StreamHandler)
        assert sh is not None
        assert sh.level == logging.DEBUG

        fh = _find_handler(logging.FileHandler)
        assert fh is not None
        assert fh.level == logging.DEBUG
