"""Integration tests for Prompter.

Test cases:
- TC-06: Custom logging configuration
- TC-08: Configuration priority (CLI > settings > defaults)
"""

import json
import logging
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from prompter.cli import app


@pytest.fixture
def runner():
    """Create a CliRunner for testing."""
    return CliRunner()


def test_custom_logging_config(tmp_path):
    """TC-06: Verify custom logging configuration via logging.json.

    Requirements:
    - LOG-06: Custom logging.json must override default config
    - Custom config must apply to both FileHandler and StreamHandler
    - Custom format must be visible in output

    Test approach:
    - Create config dir with custom logging.json
    - Call setup_logging directly (not via CLI runner)
    - Verify custom config is loaded and applied
    """
    from prompter.log import setup_logging

    # Create config directory structure
    config_dir = tmp_path / ".config" / "prompter"
    config_dir.mkdir(parents=True)

    # Create custom logging config with distinctive format
    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "custom": {
                "format": "CUSTOM-LOG: %(levelname)s - %(message)s"
            }
        },
        "handlers": {
            "file": {
                "class": "logging.FileHandler",
                "filename": str(config_dir / "prompter.log"),
                "formatter": "custom",
                "level": "DEBUG"
            }
        },
        "root": {
            "level": "DEBUG",
            "handlers": ["file"]
        }
    }

    logging_json_path = config_dir / "logging.json"
    with open(logging_json_path, "w") as f:
        json.dump(logging_config, f)

    # Clear any existing logging configuration
    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    # Setup logging with custom config
    setup_logging(config_dir, verbose=False)

    # Log a test message
    logger = logging.getLogger("prompter.test")
    logger.info("Test message for custom format")

    # Verify custom format appears in log file
    log_file = config_dir / "prompter.log"
    assert log_file.exists()

    log_content = log_file.read_text()
    # Custom format should be present in log messages
    assert "CUSTOM-LOG:" in log_content, f"Custom format not found. Content:\n{log_content}"
    assert "Test message for custom format" in log_content


def test_cli_overrides_settings(runner, tmp_path, monkeypatch):
    """TC-08: Verify CLI arguments override settings.json.

    Requirements:
    - CFG-07: Priority order is CLI > settings > defaults
    - CLI-provided values must take precedence over settings.json

    Test approach:
    - Create settings.json with output="settings.json"
    - Provide --output via CLI with different value
    - Verify CLI value is used
    """
    # Create config directory
    config_dir = tmp_path / ".config" / "prompter"
    config_dir.mkdir(parents=True)

    # Create settings.json with specific values
    settings = {
        "output": "settings-output.json",
        "verbose": False,
        "timeout": 1000
    }
    settings_path = config_dir / "settings.json"
    with open(settings_path, "w") as f:
        json.dump(settings, f)

    # Create input file
    input_file = tmp_path / "prompts.txt"
    input_file.write_text("---\nTest prompt\n")

    # CLI overrides: different output path, verbose=True, timeout=500
    cli_output = tmp_path / "cli-output.json"

    # Mock dependencies
    with patch("prompter.cli.run_prompt") as mock_run:
        mock_run.return_value = ({"response": "test"}, "session-123")

        with patch("shutil.which", return_value="/usr/bin/claude"):
            monkeypatch.setenv("HOME", str(tmp_path))

            result = runner.invoke(
                app,
                [
                    str(input_file),
                    "-o", str(cli_output),
                    "-v",
                    "-t", "500",
                    "--config", str(config_dir)
                ]
            )

    # Verify execution succeeded
    assert result.exit_code == 0

    # Verify CLI output path was used (not settings.json value)
    assert cli_output.exists()
    assert not (tmp_path / "settings-output.json").exists()

    # Verify timeout was passed correctly (CLI value 500, not settings value 1000)
    # mock_run is called with (prompt, session_id, timeout)
    assert mock_run.called
    call_args = mock_run.call_args
    assert call_args[0][2] == 500  # timeout argument


def test_settings_override_defaults(runner, tmp_path, monkeypatch):
    """TC-08: Verify settings.json overrides defaults.

    Requirements:
    - CFG-07: Priority order is CLI > settings > defaults
    - Settings.json values must override defaults when no CLI args provided

    Test approach:
    - Create settings.json with non-default values
    - Run without CLI overrides
    - Verify settings values are used (not defaults)
    """
    # Create config directory
    config_dir = tmp_path / ".config" / "prompter"
    config_dir.mkdir(parents=True)

    # Create settings.json with non-default values
    # Default timeout is 2400, we set 3000
    # Default output is "report.json", we set absolute path
    settings = {
        "output": str(tmp_path / "custom-report.json"),
        "verbose": True,
        "timeout": 3000
    }
    settings_path = config_dir / "settings.json"
    with open(settings_path, "w") as f:
        json.dump(settings, f)

    # Create input file
    input_file = tmp_path / "prompts.txt"
    input_file.write_text("---\nTest prompt\n")

    # Mock dependencies
    with patch("prompter.cli.run_prompt") as mock_run:
        mock_run.return_value = ({"response": "test"}, "session-123")

        with patch("shutil.which", return_value="/usr/bin/claude"):
            monkeypatch.setenv("HOME", str(tmp_path))

            # Run WITHOUT CLI overrides (no -o, -v, -t flags)
            result = runner.invoke(
                app,
                [
                    str(input_file),
                    "--config", str(config_dir)
                ],
                catch_exceptions=False
            )

    # Verify execution succeeded
    assert result.exit_code == 0

    # Verify settings output path was used
    output_path = tmp_path / "custom-report.json"
    assert output_path.exists(), f"Output file not found. Files in {tmp_path}: {list(tmp_path.iterdir())}"

    # Verify timeout from settings was used (3000, not default 2400)
    assert mock_run.called
    call_args = mock_run.call_args
    assert call_args[0][2] == 3000  # timeout argument

    # Verify verbose logging was enabled (settings value, not default False)
    # Check that DEBUG messages appear in log file
    log_file = config_dir / "prompter.log"
    if log_file.exists():
        log_content = log_file.read_text()
        # In verbose mode, DEBUG level messages should be present
        assert "DEBUG" in log_content or "Configuration:" in log_content
