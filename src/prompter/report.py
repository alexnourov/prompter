"""Report generation: serialize prompt results to JSON (REP-01..REP-06)."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path

from .models import PromptResult

logger = logging.getLogger(__name__)


def save_report(results: list[PromptResult], output_path: Path) -> None:
    """Save prompt execution results to a JSON report file.

    Writing is atomic: data goes to a temp file first, then os.replace()
    moves it to the target path (REP-03).
    """
    output_path = output_path.resolve()

    if output_path.exists():
        logger.warning("Report file already exists, overwriting: %s", output_path)

    records: list[dict] = []
    for r in results:
        entry: dict = {
            "title": r.title,
            "prompt": r.prompt,
            "assistant_response": r.assistant_response,
            "timestamp": r.timestamp,
            "status": r.status,
        }
        if r.status in ("error", "timeout"):
            entry["error"] = r.error
        records.append(entry)

    data = json.dumps(records, ensure_ascii=False, indent=2)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(
        dir=output_path.parent, suffix=".tmp", prefix=".report_"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
        os.replace(tmp_path, output_path)
    except BaseException:
        # Clean up temp file on any failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    logger.info("Report saved to %s", output_path)
