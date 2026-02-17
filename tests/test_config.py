"""Tests for prompter.config (CFG-01..CFG-07)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from prompter.config import find_config_dir, load_settings, merge_config


# ─── find_config_dir ─────────────────────────────────────────────────────

class TestFindConfigDir:
    """Tests for find_config_dir (CFG-01..CFG-05)."""

    def test_explicit_config_path(self, tmp_path: Path) -> None:
        """CFG-01: explicit --config path that exists → returned as-is."""
        config_dir = tmp_path / "custom"
        config_dir.mkdir()

        result = find_config_dir("prompter", config_override=config_dir)
        assert result == config_dir

    def test_explicit_config_path_not_exists(self) -> None:
        """CFG-01: explicit --config path that doesn't exist → SystemExit."""
        with pytest.raises(SystemExit, match="does not exist"):
            find_config_dir("prompter", config_override=Path("/nonexistent/path"))

    def test_xdg_config_home_set(self, tmp_path: Path) -> None:
        """CFG-02: Linux with $XDG_CONFIG_HOME set → uses it."""
        xdg_dir = tmp_path / "custom_xdg"
        candidate = xdg_dir / "prompter"
        candidate.mkdir(parents=True)

        with patch("prompter.config.platform.system", return_value="Linux"), \
             patch.dict("os.environ", {"XDG_CONFIG_HOME": str(xdg_dir)},
                        clear=False):
            result = find_config_dir("prompter")

        assert result == candidate

    def test_xdg_default(self, tmp_path: Path) -> None:
        """CFG-02: Linux without $XDG_CONFIG_HOME → ~/.config/prompter."""
        home_config = tmp_path / ".config" / "prompter"
        home_config.mkdir(parents=True)

        # Remove XDG_CONFIG_HOME if present, mock home
        env = {k: v for k, v in __import__("os").environ.items()
               if k != "XDG_CONFIG_HOME"}

        with patch("prompter.config.platform.system", return_value="Linux"), \
             patch("prompter.config.Path.home", return_value=tmp_path), \
             patch.dict("os.environ", env, clear=True):
            result = find_config_dir("prompter")

        assert result == home_config

    def test_windows_appdata(self, tmp_path: Path) -> None:
        """CFG-03: Windows with %APPDATA% → uses it."""
        appdata_dir = tmp_path / "AppData" / "Roaming"
        candidate = appdata_dir / "prompter"
        candidate.mkdir(parents=True)

        with patch("prompter.config.platform.system", return_value="Windows"), \
             patch.dict("os.environ", {"APPDATA": str(appdata_dir)},
                        clear=False):
            result = find_config_dir("prompter")

        assert result == candidate

    def test_macos_library(self, tmp_path: Path) -> None:
        """CFG-04: macOS → ~/Library/Application Support/prompter."""
        lib_dir = tmp_path / "Library" / "Application Support" / "prompter"
        lib_dir.mkdir(parents=True)

        with patch("prompter.config.platform.system", return_value="Darwin"), \
             patch("prompter.config.Path.home", return_value=tmp_path):
            result = find_config_dir("prompter")

        assert result == lib_dir

    def test_project_root_fallback(self, tmp_path: Path) -> None:
        """CFG-05: fallback to .config in project root (pyproject.toml)."""
        # Create project structure: tmp_path/project/pyproject.toml + .config/
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        (project_dir / "pyproject.toml").write_text("[project]\n")
        config_dir = project_dir / ".config"
        config_dir.mkdir()

        # Subdir as cwd, OS dirs don't exist
        sub_dir = project_dir / "src" / "pkg"
        sub_dir.mkdir(parents=True)

        with patch("prompter.config.platform.system", return_value="Linux"), \
             patch("prompter.config.Path.home",
                   return_value=tmp_path / "fakehome"), \
             patch("prompter.config.Path.cwd", return_value=sub_dir), \
             patch.dict("os.environ",
                        {k: v for k, v in __import__("os").environ.items()
                         if k != "XDG_CONFIG_HOME"},
                        clear=True):
            result = find_config_dir("prompter")

        assert result == config_dir

    def test_nothing_found(self, tmp_path: Path) -> None:
        """CFG-05: nothing found → None."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        with patch("prompter.config.platform.system", return_value="Linux"), \
             patch("prompter.config.Path.home",
                   return_value=tmp_path / "fakehome"), \
             patch("prompter.config.Path.cwd", return_value=empty_dir), \
             patch.dict("os.environ",
                        {k: v for k, v in __import__("os").environ.items()
                         if k != "XDG_CONFIG_HOME"},
                        clear=True):
            result = find_config_dir("prompter")

        assert result is None


# ─── load_settings ───────────────────────────────────────────────────────

class TestLoadSettings:
    """Tests for load_settings (CFG-06)."""

    def test_load_settings_missing_file(self, tmp_path: Path) -> None:
        """CFG-06: missing settings.json → empty dict."""
        result = load_settings(tmp_path)
        assert result == {}

    def test_load_settings_invalid_json(self, tmp_path: Path) -> None:
        """CFG-06: invalid JSON → empty dict."""
        (tmp_path / "settings.json").write_text("{broken", encoding="utf-8")

        result = load_settings(tmp_path)
        assert result == {}


# ─── merge_config ────────────────────────────────────────────────────────

class TestMergeConfig:
    """Tests for merge_config (CFG-07)."""

    def test_merge_config_priority(self) -> None:
        """TC-08: CLI > settings > defaults priority."""
        cli_args = {"timeout": 100, "verbose": None}
        settings = {"verbose": True, "output": "custom.json"}
        defaults = {"timeout": 2400, "verbose": False, "output": "report.json"}

        result = merge_config(cli_args, settings, defaults)

        # CLI wins (timeout=100, not None)
        assert result["timeout"] == 100
        # settings wins (verbose=True, CLI was None)
        assert result["verbose"] is True
        # settings wins (output="custom.json")
        assert result["output"] == "custom.json"

    def test_merge_config_invalid_type_warns(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """CFG-07: wrong type in settings → warning + default used."""
        cli_args: dict = {}
        settings = {"timeout": "abc"}
        defaults = {"timeout": 2400}

        with caplog.at_level("WARNING", logger="prompter.config"):
            result = merge_config(cli_args, settings, defaults)

        assert result["timeout"] == 2400
        assert any(
            rec.levelname == "WARNING"
            and "timeout" in rec.message
            and "int" in rec.message
            and "str" in rec.message
            for rec in caplog.records
        )
