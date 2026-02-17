"""Core data structures and exceptions for the Prompter application."""

from __future__ import annotations

import dataclasses


class SigtermReceived(Exception):
    """Raised when SIGTERM signal is received."""


class SessionIntegrityError(Exception):
    """Raised by AssistantRunner when session integrity is violated (RUN-08).

    Cases: missing session_id after first prompt (ORC-03),
    lost session_id (ORC-06), changed session_id (ORC-07).
    """


@dataclasses.dataclass
class Prompt:
    """A single prompt to be sent to an AI assistant."""

    title: str  # Prompt title (PRE-05), max 80 characters
    body: str   # Full prompt text to send to the assistant


@dataclasses.dataclass
class PromptResult:
    """Result of executing a single prompt."""

    prompt: str                      # Original prompt text (body)
    title: str                       # Prompt title (PRE-05)
    assistant_response: dict | None  # Result object from the assistant, or None
    timestamp: str                   # YYYY-MM-DDTHH:MM:SS (no microseconds, no timezone)
    status: str                      # "success" | "skipped" | "error" | "timeout"
    error: str | None = None         # Only for status "error" or "timeout"
