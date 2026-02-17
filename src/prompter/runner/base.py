"""Abstract base class for AI assistant runners (RUN-03..RUN-08)."""

from __future__ import annotations

import abc
import logging

from ..models import SessionIntegrityError

logger = logging.getLogger(__name__)


class AssistantRunner(abc.ABC):
    """Stateful wrapper around an AI assistant."""

    def __init__(self, config: dict) -> None:
        self._config = config
        self._session_id: str | None = None
        self._prompt_count: int = 0

    # --- Abstract methods (RUN-03, RUN-04, RUN-05, RUN-07) ---

    @property
    @abc.abstractmethod
    def supports_session(self) -> bool:
        """RUN-03: Whether the assistant supports sessions."""

    @abc.abstractmethod
    def check_availability(self) -> None:
        """Check that the assistant is ready (RUN-04).

        Raises:
            RuntimeError: if the assistant is unavailable.
        """

    @abc.abstractmethod
    def resume_hint(self) -> str | None:
        """Hint for manual session recovery (RUN-05).

        Returns:
            A command/instruction string, or None.
        """

    @abc.abstractmethod
    def _execute_prompt(
        self, prompt: str, timeout: int
    ) -> tuple[dict | None, str | None]:
        """Execute a prompt and return (result_obj, session_id).

        Internal method — called from run_prompt().
        Implementations must NOT manage session_id; the base class does that.

        Raises:
            subprocess.TimeoutExpired, KeyboardInterrupt, SigtermReceived,
            Exception.
        """

    # --- Public method (RUN-07) ---

    def run_prompt(self, prompt: str, timeout: int) -> dict | None:
        """Execute a prompt with session management (RUN-06, RUN-07).

        Returns:
            result_obj (dict | None).

        Raises:
            SessionIntegrityError: session integrity violated (RUN-08).
            subprocess.TimeoutExpired, KeyboardInterrupt, SigtermReceived,
            Exception.
        """
        self._prompt_count += 1

        # ORC-02: log session before each prompt
        if self.supports_session:
            logger.info("session: %s", self._session_id or "new")

        result_obj, new_session_id = self._execute_prompt(prompt, timeout)

        # RUN-06: session management
        if self.supports_session:
            self._validate_session(new_session_id)
            self._session_id = new_session_id

        return result_obj

    # --- Session integrity checks ---

    def _validate_session(self, new_session_id: str | None) -> None:
        """Validate session_id integrity (ORC-03, ORC-06, ORC-07).

        Raises:
            SessionIntegrityError: on violation.
        """
        if self._prompt_count == 1:
            # ORC-03: first prompt — session_id must be present
            if new_session_id is None:
                raise SessionIntegrityError(
                    "No session_id received from first prompt"
                )
        else:
            # ORC-06: lost session_id
            if new_session_id is None:
                raise SessionIntegrityError(
                    f"Session integrity error: no session_id received "
                    f"(expected {self._session_id!r})"
                )
            # ORC-07: changed session_id
            if new_session_id != self._session_id:
                raise SessionIntegrityError(
                    f"Session integrity error: session_id changed "
                    f"from {self._session_id!r} to {new_session_id!r}"
                )

    # --- Process management ---

    def kill(self) -> None:
        """Terminate the current assistant process (RUN-07, RUN-08)."""
        process = getattr(self, "_process", None)
        if process and hasattr(process, "kill"):
            process.kill()
