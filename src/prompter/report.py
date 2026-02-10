"""Report generation and saving functionality.

This module handles creation and atomic saving of execution reports in JSON format.
"""

import json
import logging
import os
from pathlib import Path

from .models import PromptResult

logger = logging.getLogger(__name__)


def save_report(results: list[PromptResult], output_path: Path) -> None:
    """Save execution results to a JSON report file.

    The function performs atomic write operation using a temporary file
    to prevent data corruption in case of interruption.

    Args:
        results: List of prompt execution results
        output_path: Path where to save the report

    File format (REP-02, REP-06):
        - UTF-8 encoding
        - JSON array of records
        - Each record contains: prompt, claude_response, timestamp, status
        - Field 'error' is included ONLY if status is "error" or "timeout"
        - indent=2, ensure_ascii=False for readability
    """
    # Create parent directories if needed
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Warn if overwriting existing file
    if output_path.exists():
        logger.warning(f"Report file {output_path} already exists and will be overwritten")

    # Prepare JSON data (REP-02, REP-06)
    report_data = []
    for result in results:
        record = {
            "prompt": result.prompt,
            "claude_response": result.claude_response,
            "timestamp": result.timestamp,
            "status": result.status,
        }

        # Include 'error' field ONLY for error/timeout statuses
        if result.status in ("error", "timeout"):
            record["error"] = result.error

        report_data.append(record)

    # Atomic write: write to temporary file, then replace (REP-03)
    # Use same directory to ensure atomic rename on same filesystem
    temp_path = output_path.with_suffix(".tmp")

    try:
        # Write to temporary file
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(
                report_data,
                f,
                indent=2,
                ensure_ascii=False,
            )

        # Atomic replace
        os.replace(temp_path, output_path)

        logger.info(f"Report saved to {output_path} ({len(results)} result(s))")

    except Exception:
        # Clean up temporary file on error
        if temp_path.exists():
            temp_path.unlink()
        raise
