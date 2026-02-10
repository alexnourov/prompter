"""Data models for Prompter application.

This module defines core data structures used throughout the application:
- PromptResult: represents the outcome of executing a single prompt
- SigtermReceived: signal exception for graceful shutdown
"""

import dataclasses
from typing import Any


class SigtermReceived(Exception):
    """Raised when SIGTERM signal is received."""

    pass


@dataclasses.dataclass
class PromptResult:
    """Result of executing a single prompt with Claude CLI.

    Attributes:
        prompt: Original prompt text that was sent to Claude
        claude_response: Parsed result event object from Claude, or None if not applicable
        timestamp: ISO 8601 timestamp without microseconds and timezone (YYYY-MM-DDTHH:MM:SS)
        status: Execution status - one of: "success", "skipped", "error", "timeout"
        error: Error message for status "error" or "timeout", None otherwise
    """

    prompt: str
    claude_response: dict[str, Any] | None
    timestamp: str
    status: str
    error: str | None = None

    def __post_init__(self) -> None:
        """Validate status field value."""
        valid_statuses = {"success", "skipped", "error", "timeout"}
        if self.status not in valid_statuses:
            raise ValueError(
                f"Invalid status '{self.status}'. Must be one of: {', '.join(sorted(valid_statuses))}"
            )
