"""Модуль для чтения промптов и сохранения отчётов."""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class PromptReader:
    """Класс для чтения промптов из файлов различных форматов."""

    def read(self, file_path: Path) -> list[str]:
        """Читает промпты из файла.

        Args:
            file_path: Путь к файлу с промптами.

        Returns:
            Список строк-промптов.

        Raises:
            FileNotFoundError: Если файл не найден.
            ValueError: Если формат файла не поддерживается.
        """
        if not file_path.exists():
            logger.error("Файл не найден: %s", file_path)
            raise FileNotFoundError(f"Файл не найден: {file_path}")

        suffix = file_path.suffix.lower()

        if suffix in (".txt", ".md"):
            return self._read_text(file_path)
        elif suffix == ".json":
            return self._read_json(file_path)
        else:
            logger.error("Неподдерживаемый формат файла: %s", suffix)
            raise ValueError(f"Неподдерживаемый формат файла: {suffix}")

    def _read_text(self, file_path: Path) -> list[str]:
        """Читает текстовый файл и разбивает по разделителю ---."""
        content = file_path.read_text(encoding="utf-8")
        prompts = content.split("---")
        return [p.strip() for p in prompts if p.strip()]

    def _read_json(self, file_path: Path) -> list[str]:
        """Читает JSON-файл как список строк."""
        content = file_path.read_text(encoding="utf-8")
        data = json.loads(content)

        if not isinstance(data, list):
            raise ValueError("JSON-файл должен содержать список строк")

        return [str(item).strip() for item in data if str(item).strip()]


class SessionLogger:
    """Класс для сохранения отчётов о сессиях."""

    def save_report(
        self, report_data: list[dict[str, Any]], output_path: Path
    ) -> None:
        """Сохраняет отчёт в JSON-файл.

        Args:
            report_data: Список словарей с данными отчёта.
            output_path: Путь для сохранения отчёта.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        output_path.write_text(
            json.dumps(report_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        logger.info("Отчёт сохранён: %s", output_path)
