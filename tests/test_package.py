"""Tests for package-level entry points and metadata (CLI-02, CLI-05)."""

from __future__ import annotations

import importlib
import importlib.metadata

from typer.testing import CliRunner

from prompter.cli import app

runner_cli = CliRunner()


class TestPackage:
    """Package entry points and metadata."""

    def test_entry_point_importable(self) -> None:
        """Entry point module from pyproject.toml is importable (CLI-05).

        Reads [project.scripts] 'prompter = "prompter.cli:app"'
        and verifies that 'prompter.cli' imports without error.
        """
        try:
            import tomllib
        except ModuleNotFoundError:
            import tomli as tomllib  # type: ignore[no-redef]

        from pathlib import Path

        toml_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
        data = tomllib.loads(toml_path.read_text(encoding="utf-8"))
        entry = data["project"]["scripts"]["prompter"]
        module_path = entry.split(":")[0]

        assert not module_path.startswith("src."), (
            f"Entry point must not start with 'src.': {module_path}"
        )

        mod = importlib.import_module(module_path)
        assert mod is not None

    def test_main_module_importable(self) -> None:
        """CLI-05: 'python -m prompter' entry point module is importable."""
        import sys
        from unittest.mock import patch

        # Remove cached module so import_module actually executes it
        sys.modules.pop("prompter.__main__", None)

        with patch("prompter.cli.app") as mock_app:
            mod = importlib.import_module("prompter.__main__")

        assert mod is not None
        mock_app.assert_called_once()

    def test_help_flag(self) -> None:
        """--help returns 0 and shows argument descriptions."""
        result = runner_cli.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "INPUT_FILE" in result.output or "input" in result.output.lower()

    def test_version_flag(self) -> None:
        """CLI-02: --version prints version and exits 0."""
        result = runner_cli.invoke(app, ["--version"])
        assert result.exit_code == 0

        expected = importlib.metadata.version("prompter")
        assert expected in result.output.strip()
