"""Tests for package configuration validity."""

import importlib
import re
from pathlib import Path

import pytest


class TestPackageConfig:
    """Test suite for package configuration."""

    def test_pyproject_script_import(self) -> None:
        """Test that the script entry point in pyproject.toml is importable.

        This test ensures that the package is correctly configured for
        installation - the import path should not contain 'src.' prefix.
        """
        pyproject_path = self._find_pyproject()
        assert pyproject_path is not None, "pyproject.toml not found"

        content = pyproject_path.read_text(encoding="utf-8")

        match = re.search(r'prompter\s*=\s*"([^"]+)"', content)
        assert match is not None, "Script entry 'prompter' not found in pyproject.toml"

        entry_point = match.group(1)
        module_path = entry_point.split(":")[0]

        assert not module_path.startswith("src."), (
            f"Module path should not start with 'src.': {module_path}"
        )

        try:
            module = importlib.import_module(module_path)
            assert module is not None
        except ModuleNotFoundError as e:
            pytest.fail(
                f"Failed to import module '{module_path}' from pyproject.toml: {e}"
            )

    def test_app_object_exists(self) -> None:
        """Test that the app object exists in the main module."""
        pyproject_path = self._find_pyproject()
        assert pyproject_path is not None

        content = pyproject_path.read_text(encoding="utf-8")
        match = re.search(r'prompter\s*=\s*"([^"]+)"', content)
        assert match is not None

        entry_point = match.group(1)
        module_path, obj_name = entry_point.split(":")

        module = importlib.import_module(module_path)
        assert hasattr(module, obj_name), (
            f"Object '{obj_name}' not found in module '{module_path}'"
        )

    def _find_pyproject(self) -> Path | None:
        """Find pyproject.toml by traversing up from current directory.

        Returns:
            Path to pyproject.toml or None if not found.
        """
        current = Path(__file__).resolve().parent

        for parent in [current, *current.parents]:
            pyproject = parent / "pyproject.toml"
            if pyproject.exists():
                return pyproject

        return None
