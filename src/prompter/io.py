"""IO module for reading prompts and writing reports."""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class PromptReader:
    """Reader class for loading prompts from various file formats.

    Supports .txt, .md files (split by separator) and .json files
    (expects a list of strings).
    """

    SEPARATOR = "\n---\n"

    def read(self, file_path: Path) -> list[str]:
        """Read prompts from a file.

        Args:
            file_path: Path to the prompts file.

        Returns:
            A list of prompt strings.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the file format is unsupported or content is invalid.
        """
        if not file_path.exists():
            logger.error("File not found: %s", file_path)
            raise FileNotFoundError(f"File not found: {file_path}")

        suffix = file_path.suffix.lower()

        if suffix in (".txt", ".md"):
            return self._read_text_file(file_path)
        elif suffix == ".json":
            return self._read_json_file(file_path)
        else:
            logger.error("Unsupported file format: %s", suffix)
            raise ValueError(f"Unsupported file format: {suffix}")

    def _read_text_file(self, file_path: Path) -> list[str]:
        """Read prompts from a text or markdown file.

        Prompts are separated by '---' on its own line.

        Args:
            file_path: Path to the text file.

        Returns:
            A list of prompt strings.
        """
        content = file_path.read_text(encoding="utf-8")
        prompts = content.split(self.SEPARATOR)
        prompts = [p.strip() for p in prompts if p.strip()]
        logger.info("Loaded %d prompts from %s", len(prompts), file_path)
        return prompts

    def _read_json_file(self, file_path: Path) -> list[str]:
        """Read prompts from a JSON file.

        Expects a JSON array of strings.

        Args:
            file_path: Path to the JSON file.

        Returns:
            A list of prompt strings.

        Raises:
            ValueError: If the JSON is not a list of strings.
        """
        content = file_path.read_text(encoding="utf-8")
        data = json.loads(content)

        if not isinstance(data, list):
            logger.error("JSON file must contain a list, got: %s", type(data).__name__)
            raise ValueError("JSON file must contain a list of strings")

        if not all(isinstance(item, str) for item in data):
            logger.error("JSON list must contain only strings")
            raise ValueError("JSON file must contain a list of strings")

        prompts = [p.strip() for p in data if p.strip()]
        logger.info("Loaded %d prompts from %s", len(prompts), file_path)
        return prompts


class SessionLogger:
    """Logger class for saving session reports.

    Saves execution history as JSON files.
    """

    def save_report(
        self, report_data: list[dict[str, Any]], output_path: Path
    ) -> None:
        """Save execution report to a JSON file.

        Args:
            report_data: List of result dictionaries from prompt executions.
            output_path: Path where the report should be saved.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(report_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("Report saved to %s", output_path)
