"""Tests for package configuration validity."""

import importlib
import re
from pathlib import Path

import pytest


class TestPackageConfiguration:
    """Test suite for package configuration."""

    def test_pyproject_script_import(self) -> None:
        """Test that the script entry point in pyproject.toml is importable."""
        project_root = self._find_project_root()
        pyproject_path = project_root / "pyproject.toml"

        assert pyproject_path.exists(), "pyproject.toml not found"

        content = pyproject_path.read_text(encoding="utf-8")

        match = re.search(r'prompter\s*=\s*"([^"]+)"', content)
        assert match, "Script entry 'prompter' not found in pyproject.toml"

        entry_point = match.group(1)

        if ":" in entry_point:
            module_path = entry_point.split(":")[0]
        else:
            module_path = entry_point

        try:
            module = importlib.import_module(module_path)
            assert module is not None
        except ModuleNotFoundError as e:
            pytest.fail(
                f"Failed to import '{module_path}' from pyproject.toml script entry. "
                f"Error: {e}. "
                f"This may indicate an incorrect path (e.g., 'src.' prefix that shouldn't be there)."
            )

    def test_entry_point_has_app(self) -> None:
        """Test that the entry point module has the 'app' object."""
        project_root = self._find_project_root()
        pyproject_path = project_root / "pyproject.toml"

        content = pyproject_path.read_text(encoding="utf-8")
        match = re.search(r'prompter\s*=\s*"([^"]+)"', content)

        if not match:
            pytest.skip("No prompter entry point found")

        entry_point = match.group(1)

        if ":" in entry_point:
            module_path, attr_name = entry_point.split(":")
        else:
            pytest.skip("Entry point doesn't specify an attribute")

        module = importlib.import_module(module_path)
        assert hasattr(module, attr_name), f"Module '{module_path}' has no attribute '{attr_name}'"

    def _find_project_root(self) -> Path:
        """Find the project root by searching for pyproject.toml."""
        current = Path(__file__).parent

        for parent in [current, *current.parents]:
            if (parent / "pyproject.toml").exists():
                return parent

        pytest.fail("Could not find project root (pyproject.toml)")
