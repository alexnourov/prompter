"""Tests for configuration management.

Tests cover requirements: CFG-02, CFG-05, CFG-06, CFG-07.
Includes TC-07, TC-08.
"""

import json
import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from prompter.config import find_config_dir, load_settings, merge_config


class TestFindConfigDir:
    """Tests for configuration directory search (TC-07, CFG-02)."""

    def test_explicit_config_path(self, tmp_path: Path) -> None:
        """Test explicit --config path when directory exists."""
        config_path = tmp_path / "custom_config"
        config_path.mkdir()

        result = find_config_dir("prompter", config_override=config_path)

        assert result == config_path

    def test_explicit_config_path_not_exists(self, tmp_path: Path) -> None:
        """Test explicit --config path raises SystemExit when directory doesn't exist."""
        nonexistent = tmp_path / "nonexistent"

        with pytest.raises(SystemExit, match="Config directory does not exist"):
            find_config_dir("prompter", config_override=nonexistent)

    def test_xdg_config_home_set(self, tmp_path: Path) -> None:
        """Test XDG_CONFIG_HOME on Linux when set (CFG-02)."""
        xdg_config = tmp_path / "custom_xdg"
        prompter_config = xdg_config / "prompter"
        prompter_config.mkdir(parents=True)

        with patch("prompter.config.platform.system", return_value="Linux"), \
             patch.dict("os.environ", {"XDG_CONFIG_HOME": str(xdg_config)}):

            result = find_config_dir("prompter")

            assert result == prompter_config

    def test_xdg_default(self, tmp_path: Path) -> None:
        """Test default ~/.config/prompter on Linux when XDG_CONFIG_HOME not set."""
        home_config = tmp_path / ".config" / "prompter"
        home_config.mkdir(parents=True)

        with patch("prompter.config.platform.system", return_value="Linux"), \
             patch("prompter.config.Path.home", return_value=tmp_path), \
             patch.dict("os.environ", {}, clear=True):

            result = find_config_dir("prompter")

            assert result == home_config

    def test_windows_appdata(self, tmp_path: Path) -> None:
        """Test %APPDATA% on Windows (CFG-02)."""
        appdata = tmp_path / "AppData" / "Roaming"
        prompter_config = appdata / "prompter"
        prompter_config.mkdir(parents=True)

        with patch("prompter.config.platform.system", return_value="Windows"), \
             patch.dict("os.environ", {"APPDATA": str(appdata)}):

            result = find_config_dir("prompter")

            assert result == prompter_config

    def test_macos_library(self, tmp_path: Path) -> None:
        """Test ~/Library/Application Support on macOS (CFG-02)."""
        library = tmp_path / "Library" / "Application Support" / "prompter"
        library.mkdir(parents=True)

        with patch("prompter.config.platform.system", return_value="Darwin"), \
             patch("prompter.config.Path.home", return_value=tmp_path):

            result = find_config_dir("prompter")

            assert result == library

    def test_project_root_fallback(self, tmp_path: Path) -> None:
        """Test fallback to project root .config directory (CFG-05)."""
        # Create project structure
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / "pyproject.toml").touch()

        config_dir = project_root / ".config"
        config_dir.mkdir()

        work_dir = project_root / "subdir"
        work_dir.mkdir()

        with patch("prompter.config.platform.system", return_value="Linux"), \
             patch("prompter.config.Path.cwd", return_value=work_dir), \
             patch("prompter.config.Path.home", return_value=tmp_path / "home"), \
             patch.dict("os.environ", {}, clear=True):

            result = find_config_dir("prompter")

            assert result == config_dir

    def test_nothing_found(self, tmp_path: Path) -> None:
        """Test that None is returned when no config directory found."""
        # Mock to return non-existent paths
        with patch("prompter.config.platform.system", return_value="Linux"), \
             patch("prompter.config.Path.home", return_value=tmp_path / "nonexistent_home"), \
             patch("prompter.config.Path.cwd", return_value=tmp_path / "nonexistent_work"), \
             patch.dict("os.environ", {}, clear=True):

            result = find_config_dir("prompter")

            assert result is None


class TestLoadSettings:
    """Tests for settings loading (CFG-06)."""

    def test_load_settings_success(self, tmp_path: Path) -> None:
        """Test successful loading of settings.json."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        settings_file = config_dir / "settings.json"
        settings_data = {"timeout": 3600, "verbose": True, "output": "custom.json"}
        settings_file.write_text(json.dumps(settings_data), encoding="utf-8")

        result = load_settings(config_dir)

        assert result == settings_data

    def test_load_settings_missing_file(self, tmp_path: Path) -> None:
        """Test that missing settings.json returns empty dict (CFG-06)."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        # No settings.json created

        result = load_settings(config_dir)

        assert result == {}

    def test_load_settings_invalid_json(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """Test that invalid JSON returns empty dict with warning (CFG-06)."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        settings_file = config_dir / "settings.json"
        settings_file.write_text("{broken json", encoding="utf-8")

        with caplog.at_level(logging.WARNING):
            result = load_settings(config_dir)

            assert result == {}
            assert any("Invalid JSON" in record.message for record in caplog.records)

    def test_load_settings_not_object(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """Test that JSON array (not object) returns empty dict with warning."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        settings_file = config_dir / "settings.json"
        settings_file.write_text('["not", "an", "object"]', encoding="utf-8")

        with caplog.at_level(logging.WARNING):
            result = load_settings(config_dir)

            assert result == {}
            assert any("not a JSON object" in record.message for record in caplog.records)

    def test_load_settings_utf8(self, tmp_path: Path) -> None:
        """Test UTF-8 encoding support in settings.json."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        settings_file = config_dir / "settings.json"
        settings_data = {"output": "отчёт.json", "comment": "Кириллица ©"}
        settings_file.write_text(json.dumps(settings_data, ensure_ascii=False), encoding="utf-8")

        result = load_settings(config_dir)

        assert result == settings_data
        assert result["output"] == "отчёт.json"


class TestMergeConfig:
    """Tests for configuration merging (TC-08, CFG-07)."""

    def test_merge_config_priority(self) -> None:
        """Test priority: CLI > settings > defaults (TC-08, CFG-07)."""
        cli_args = {
            "timeout": 100,  # Explicitly set
            "verbose": None,  # Not set (None means user didn't provide it)
            "output": None,  # Not set
        }

        settings = {
            "verbose": True,
            "output": "custom.json",
        }

        defaults = {
            "timeout": 2400,
            "verbose": False,
            "output": "report.json",
        }

        result = merge_config(cli_args, settings, defaults)

        # CLI wins for timeout
        assert result["timeout"] == 100

        # Settings wins over default for verbose (CLI was None)
        assert result["verbose"] is True

        # Settings wins over default for output
        assert result["output"] == "custom.json"

    def test_merge_config_all_defaults(self) -> None:
        """Test that defaults are used when CLI and settings are empty."""
        cli_args = {
            "timeout": None,
            "verbose": None,
            "output": None,
        }

        settings = {}

        defaults = {
            "timeout": 2400,
            "verbose": False,
            "output": "report.json",
        }

        result = merge_config(cli_args, settings, defaults)

        assert result == defaults

    def test_merge_config_cli_overrides_all(self) -> None:
        """Test that CLI arguments override both settings and defaults."""
        cli_args = {
            "timeout": 500,
            "verbose": True,
            "output": "cli.json",
        }

        settings = {
            "timeout": 1000,
            "verbose": False,
            "output": "settings.json",
        }

        defaults = {
            "timeout": 2400,
            "verbose": False,
            "output": "report.json",
        }

        result = merge_config(cli_args, settings, defaults)

        assert result["timeout"] == 500
        assert result["verbose"] is True
        assert result["output"] == "cli.json"

    def test_merge_config_invalid_type_warns(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that invalid type in settings logs warning and uses default (CFG-07)."""
        cli_args = {
            "timeout": None,
            "verbose": None,
        }

        settings = {
            "timeout": "abc",  # Should be int
            "verbose": "yes",  # Should be bool
        }

        defaults = {
            "timeout": 2400,
            "verbose": False,
        }

        with caplog.at_level(logging.WARNING):
            result = merge_config(cli_args, settings, defaults)

            # Should use defaults due to type mismatch
            assert result["timeout"] == 2400
            assert result["verbose"] is False

            # Check warnings were logged
            log_messages = [record.message for record in caplog.records]
            assert any("timeout" in msg and "expected int" in msg for msg in log_messages)
            assert any("verbose" in msg and "expected bool" in msg for msg in log_messages)

    def test_merge_config_none_default_no_validation(self) -> None:
        """Test that keys with None default skip type validation (CFG-07)."""
        cli_args = {
            "source_encoding": None,  # Not set
        }

        settings = {
            "source_encoding": "utf-8",  # String value
        }

        defaults = {
            "source_encoding": None,  # None default - no type validation
        }

        result = merge_config(cli_args, settings, defaults)

        # Should accept string even though default is None
        assert result["source_encoding"] == "utf-8"

    def test_merge_config_none_default_accepts_any_type(self) -> None:
        """Test that None-default keys accept any type without warning."""
        cli_args = {
            "source_encoding": None,
        }

        settings = {
            "source_encoding": 123,  # Integer (unusual but should be accepted)
        }

        defaults = {
            "source_encoding": None,
        }

        result = merge_config(cli_args, settings, defaults)

        # Should accept integer without warning
        assert result["source_encoding"] == 123

    def test_merge_config_partial_settings(self) -> None:
        """Test merging when settings only partially overlap with defaults."""
        cli_args = {
            "timeout": None,
            "verbose": None,
            "output": None,
        }

        settings = {
            "verbose": True,  # Only verbose in settings
        }

        defaults = {
            "timeout": 2400,
            "verbose": False,
            "output": "report.json",
        }

        result = merge_config(cli_args, settings, defaults)

        assert result["timeout"] == 2400  # From default
        assert result["verbose"] is True  # From settings
        assert result["output"] == "report.json"  # From default


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_find_config_dir_multiple_pyproject(self, tmp_path: Path) -> None:
        """Test that find_config_dir finds nearest pyproject.toml."""
        # Create nested structure with multiple pyproject.toml files
        outer = tmp_path / "outer"
        outer.mkdir()
        (outer / "pyproject.toml").touch()

        inner = outer / "inner"
        inner.mkdir()
        (inner / "pyproject.toml").touch()
        (inner / ".config").mkdir()

        work_dir = inner / "src"
        work_dir.mkdir()

        with patch("prompter.config.platform.system", return_value="Linux"), \
             patch("prompter.config.Path.cwd", return_value=work_dir), \
             patch("prompter.config.Path.home", return_value=tmp_path / "home"), \
             patch.dict("os.environ", {}, clear=True):

            result = find_config_dir("prompter")

            # Should find inner .config (nearest pyproject.toml)
            assert result == inner / ".config"

    def test_load_settings_permission_error(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        """Test that permission errors are handled gracefully."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        settings_file = config_dir / "settings.json"
        settings_file.write_text('{"test": 1}', encoding="utf-8")

        # Mock open to raise PermissionError
        with patch("builtins.open", side_effect=PermissionError("Access denied")), \
             caplog.at_level(logging.WARNING):

            result = load_settings(config_dir)

            assert result == {}
            assert any("Error reading settings.json" in record.message for record in caplog.records)
