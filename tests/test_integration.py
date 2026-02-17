"""Integration tests: config + logging + CLI pipeline (CFG-07, LOG-02, LOG-03)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from prompter.cli import app
from prompter.models import Prompt

runner_cli = CliRunner()


def _make_runner() -> MagicMock:
    mock = MagicMock()
    mock.supports_session = True
    mock.check_availability.return_value = None
    mock.resume_hint.return_value = None
    mock.run_prompt.return_value = {"result": "ok"}
    return mock


class TestIntegration:
    """End-to-end integration through main() with real config/logging."""

    def test_custom_logging_config(self, tmp_path: Path) -> None:
        """CFG-01 + LOG-03: logging.json from app-name config dir is loaded."""
        # Create config dir with logging.json
        config_dir = tmp_path / "custom_app"
        config_dir.mkdir()

        logging_config = {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "custom": {"format": "[CUSTOM] %(message)s"}
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "custom",
                }
            },
            "root": {"level": "DEBUG", "handlers": ["console"]},
        }
        (config_dir / "logging.json").write_text(
            json.dumps(logging_config), encoding="utf-8"
        )

        input_file = tmp_path / "input.txt"
        input_file.write_text("prompt body\n")

        mock_runner = _make_runner()

        with (
            patch("prompter.cli.prepare_prompts", return_value=[Prompt("P", "b")]),
            patch("prompter.cli.create_runner", return_value=mock_runner),
            patch.dict("os.environ", {"XDG_CONFIG_HOME": str(tmp_path)}),
            patch("logging.config.dictConfig") as mock_dict_config,
        ):
            result = runner_cli.invoke(
                app,
                [str(input_file), "--app-name", "custom_app"],
            )

        assert result.exit_code == 0
        mock_dict_config.assert_called_once()
        loaded_config = mock_dict_config.call_args[0][0]
        assert loaded_config["formatters"]["custom"]["format"] == "[CUSTOM] %(message)s"

    def test_cli_overrides_settings(self, tmp_path: Path) -> None:
        """CFG-07: CLI --verbose overrides settings.json verbose=false."""
        config_dir = tmp_path / "cfg"
        config_dir.mkdir()
        (config_dir / "settings.json").write_text(
            json.dumps({"verbose": False}), encoding="utf-8"
        )

        input_file = tmp_path / "input.txt"
        input_file.write_text("prompt body\n")

        mock_runner = _make_runner()

        with (
            patch("prompter.cli.prepare_prompts", return_value=[Prompt("P", "b")]),
            patch("prompter.cli.create_runner", return_value=mock_runner),
            patch("prompter.cli.setup_logging") as mock_setup,
        ):
            result = runner_cli.invoke(
                app,
                [
                    str(input_file),
                    "--verbose",
                    "--config", str(config_dir),
                ],
            )

        assert result.exit_code == 0
        mock_setup.assert_called_once()
        _, called_verbose = mock_setup.call_args[0]
        assert called_verbose is True

    def test_settings_override_defaults(self, tmp_path: Path) -> None:
        """CFG-07: settings.json verbose=true overrides default false."""
        config_dir = tmp_path / "cfg"
        config_dir.mkdir()
        (config_dir / "settings.json").write_text(
            json.dumps({"verbose": True}), encoding="utf-8"
        )

        input_file = tmp_path / "input.txt"
        input_file.write_text("prompt body\n")

        mock_runner = _make_runner()

        with (
            patch("prompter.cli.prepare_prompts", return_value=[Prompt("P", "b")]),
            patch("prompter.cli.create_runner", return_value=mock_runner),
            patch("prompter.cli.setup_logging") as mock_setup,
        ):
            result = runner_cli.invoke(
                app,
                [
                    str(input_file),
                    "--config", str(config_dir),
                ],
            )

        assert result.exit_code == 0
        mock_setup.assert_called_once()
        _, called_verbose = mock_setup.call_args[0]
        assert called_verbose is True
