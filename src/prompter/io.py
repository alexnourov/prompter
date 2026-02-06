"""IO module for reading prompts and saving session reports."""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class PromptReader:
    """Reader class for loading prompts from files.

    Supports .txt, .md (separated by ---) and .json (list of strings) formats.
    """

    def read(self, file_path: Path) -> list[str]:
        """Read prompts from a file.

        Args:
            file_path: Path to the prompts file.

        Returns:
            List of prompt strings.

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

        Args:
            file_path: Path to the file.

        Returns:
            List of prompts split by '---' separator.
        """
        content = file_path.read_text(encoding="utf-8")
        parts = content.split("---")
        prompts = [part.strip() for part in parts if part.strip()]
        logger.debug("Read %d prompts from %s", len(prompts), file_path)
        return prompts

    def _read_json_file(self, file_path: Path) -> list[str]:
        """Read prompts from a JSON file.

        Args:
            file_path: Path to the JSON file.

        Returns:
            List of prompt strings.

        Raises:
            ValueError: If JSON is not a list of strings.
        """
        content = file_path.read_text(encoding="utf-8")
        data = json.loads(content)

        if not isinstance(data, list):
            logger.error("JSON file must contain a list, got: %s", type(data).__name__)
            raise ValueError("JSON file must contain a list of strings")

        prompts = []
        for i, item in enumerate(data):
            if not isinstance(item, str):
                logger.error("Item at index %d is not a string: %s", i, type(item).__name__)
                raise ValueError(f"Item at index {i} is not a string")
            prompts.append(item.strip())

        prompts = [p for p in prompts if p]
        logger.debug("Read %d prompts from %s", len(prompts), file_path)
        return prompts


class SessionLogger:
    """Logger class for saving session reports to JSON files."""

    def save_report(self, report_data: list[dict[str, Any]], output_path: Path) -> None:
        """Save session report to a JSON file.

        Args:
            report_data: List of dictionaries containing session history.
            output_path: Path to the output JSON file.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        output_path.write_text(
            json.dumps(report_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        logger.info("Report saved to %s", output_path)
