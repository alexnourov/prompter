"""Модуль для запуска Claude CLI и управления сессиями."""

import json
import logging
import subprocess
from typing import Any

logger = logging.getLogger(__name__)


class ClaudeRunner:
    """Класс для запуска промптов через Claude CLI.

    Управляет сессией, позволяя вести непрерывный диалог
    с сохранением контекста между запросами.
    """

    def __init__(self) -> None:
        """Инициализация runner'а."""
        self.session_id: str | None = None

    def run_prompt(self, prompt_text: str) -> dict[str, Any]:
        """Выполняет промпт через Claude CLI.

        Args:
            prompt_text: Текст промпта для отправки в Claude.

        Returns:
            Словарь с ответом Claude в формате JSON.

        Raises:
            KeyboardInterrupt: При прерывании пользователем.
            ValueError: При ошибке парсинга JSON-ответа.
        """
        cmd = [
            "claude",
            "-p",
            prompt_text,
            "--output-format",
            "json",
            "--dangerously-skip-permissions",
        ]

        if self.session_id is not None:
            cmd.extend(["--resume", self.session_id])

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        try:
            stdout, stderr = process.communicate()
        except (KeyboardInterrupt, Exception):
            process.kill()
            process.wait()
            raise

        if stderr:
            logger.warning("Claude CLI stderr: %s", stderr.strip())

        try:
            result = json.loads(stdout)
        except json.JSONDecodeError as e:
            logger.error(
                "Ошибка парсинга JSON-ответа: %s. Stdout: %s",
                e,
                stdout[:500] if stdout else "<empty>",
            )
            raise ValueError(f"Не удалось распарсить ответ Claude: {e}") from e

        if self.session_id is None and "session_id" in result:
            self.session_id = result["session_id"]

        return result
