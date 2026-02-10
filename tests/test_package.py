"""Package-level tests for Prompter.

Test cases:
- TC-10: Entry point validation
- TC-05: Help flag
- TC-13: Version flag
- CLI-05: Main module importability
"""

import subprocess
import sys
from importlib.metadata import version
from pathlib import Path
from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

from prompter.cli import app


@pytest.fixture
def runner():
    """Create a CliRunner for testing."""
    return CliRunner()


def test_entry_point_importable():
    """TC-10: Verify entry point is importable without 'src.' prefix.

    Requirements:
    - CLI-04: Entry point "prompter.cli:app" must be importable
    - Package structure must allow import without "src." prefix
    """
    # Verify import path doesn't require "src." prefix
    from prompter.cli import app as imported_app

    assert imported_app is not None
    assert isinstance(imported_app, typer.Typer)


def test_main_module_importable():
    """CLI-05: Verify __main__.py allows module execution.

    Requirements:
    - Module execution via "python -m prompter" must work
    - __main__.py must import and call app
    """
    # Verify __main__.py can be imported
    from prompter import __main__

    # Verify it has the app import
    assert hasattr(__main__, "app")
    assert __main__.app is app


def test_help_flag(runner):
    """TC-05: Verify --help flag displays usage information.

    Requirements:
    - CLI-02: --help must show usage information
    - Must work without providing required input_file argument
    - Output must include:
      - Usage pattern
      - Positional argument description
      - Optional flags description
    """
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Usage:" in result.stdout
    assert "INPUT_FILE" in result.stdout
    assert "--output" in result.stdout or "-o" in result.stdout
    assert "--verbose" in result.stdout or "-v" in result.stdout
    assert "--timeout" in result.stdout or "-t" in result.stdout
    assert "--version" in result.stdout


def test_version_flag(runner):
    """TC-13: Verify --version flag displays version and exits.

    Requirements:
    - CLI-02: --version must display version string
    - Must use version from package metadata (importlib.metadata)
    - Must work without providing required input_file argument
    - Exit code must be 0
    """
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0

    # Get expected version from package metadata
    try:
        expected_version = version("prompter")
    except Exception:
        # If package not installed, use fallback
        expected_version = "0.0.0"

    assert expected_version in result.stdout.strip()
    # Verify output is just the version (no extra text)
    assert result.stdout.strip() == expected_version
