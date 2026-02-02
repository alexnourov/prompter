"""Тесты для проверки корректности конфигурации пакета."""

import importlib
import tomllib
from pathlib import Path


def _find_project_root() -> Path:
    """Ищет корень проекта по наличию pyproject.toml."""
    current = Path(__file__).resolve().parent

    for parent in [current, *current.parents]:
        if (parent / "pyproject.toml").exists():
            return parent

    raise FileNotFoundError("pyproject.toml не найден")


class TestPackageConfiguration:
    """Тесты конфигурации пакета."""

    def test_scripts_importable(self) -> None:
        """Проверяет, что все скрипты из pyproject.toml можно импортировать."""
        project_root = _find_project_root()
        pyproject_path = project_root / "pyproject.toml"

        content = pyproject_path.read_text(encoding="utf-8")
        config = tomllib.loads(content)

        scripts = config.get("project", {}).get("scripts", {})
        assert scripts, "Секция [project.scripts] не найдена или пуста"

        for script_name, entry_point in scripts.items():
            # Извлекаем путь импорта (часть до двоеточия)
            module_path = entry_point.split(":")[0]

            try:
                module = importlib.import_module(module_path)
            except ModuleNotFoundError as e:
                raise AssertionError(
                    f"Не удалось импортировать модуль '{module_path}' "
                    f"для скрипта '{script_name}'. "
                    f"Возможно, путь содержит лишний префикс 'src.'. "
                    f"Ошибка: {e}"
                ) from e

            # Проверяем, что объект (функция/app) существует в модуле
            attr_name = entry_point.split(":")[1] if ":" in entry_point else None
            if attr_name:
                assert hasattr(module, attr_name), (
                    f"Модуль '{module_path}' не содержит атрибут '{attr_name}'"
                )

    def test_prompter_script_exists(self) -> None:
        """Проверяет наличие скрипта prompter."""
        project_root = _find_project_root()
        pyproject_path = project_root / "pyproject.toml"

        content = pyproject_path.read_text(encoding="utf-8")
        config = tomllib.loads(content)

        scripts = config.get("project", {}).get("scripts", {})
        assert "prompter" in scripts, "Скрипт 'prompter' не найден в [project.scripts]"

    def test_prompter_entry_point_valid(self) -> None:
        """Проверяет корректность entry point для prompter."""
        project_root = _find_project_root()
        pyproject_path = project_root / "pyproject.toml"

        content = pyproject_path.read_text(encoding="utf-8")
        config = tomllib.loads(content)

        entry_point = config["project"]["scripts"]["prompter"]

        # Проверяем формат
        assert ":" in entry_point, "Entry point должен содержать ':'"
        assert not entry_point.startswith("src."), (
            "Entry point не должен начинаться с 'src.'"
        )

        module_path, attr_name = entry_point.split(":")
        assert module_path == "prompter.main", f"Ожидался 'prompter.main', получен '{module_path}'"
        assert attr_name == "app", f"Ожидался 'app', получен '{attr_name}'"
