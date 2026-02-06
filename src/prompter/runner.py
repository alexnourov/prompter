"""Claude Runner module for executing prompts via Claude Code CLI."""

import json
import logging
import platform
import shlex
import subprocess
import threading
from typing import Any

logger = logging.getLogger(__name__)


class ClaudeRunner:
    """Runner class for executing prompts via Claude Code CLI.

    This class manages the interaction with the Claude CLI, handling
    session persistence, real-time output processing, and result extraction.

    Attributes:
        session_id: The current session ID for maintaining conversation context.
    """

    def __init__(self, session_id: str | None = None) -> None:
        """Initialize the ClaudeRunner.

        Args:
            session_id: Optional session ID to resume a previous conversation.
        """
        self.session_id: str | None = session_id
        self._result: dict[str, Any] | None = None
        self._last_json: dict[str, Any] | None = None
        self._lock = threading.Lock()

    def _build_command(self, prompt_text: str) -> list[str]:
        """Build the command to execute Claude CLI.

        Args:
            prompt_text: The prompt text to send to Claude.

        Returns:
            List of command arguments.
        """
        cmd: list[str] = []

        if platform.system() == "Linux":
            cmd.extend(["stdbuf", "-oL", "-eL"])

        cmd.extend([
            "claude",
            "-p", prompt_text,
            "--output-format", "stream-json",
            "--verbose",
            "--dangerously-skip-permissions",
        ])

        if self.session_id:
            cmd.extend(["--resume", self.session_id])

        return cmd

    def _read_stderr(self, process: subprocess.Popen) -> None:
        """Read stderr from the process and log warnings.

        Args:
            process: The subprocess to read from.
        """
        if process.stderr is None:
            return

        for line in process.stderr:
            line = line.rstrip("\n\r")
            if line:
                logger.warning("stderr: %s", line)

    def _process_json_event(self, event: dict[str, Any], verbose: bool) -> None:
        """Process a JSON event from Claude CLI output.

        Args:
            event: The parsed JSON event.
            verbose: Whether to log verbose output.
        """
        event_type = event.get("type")

        if event_type == "system":
            new_session_id = event.get("session_id")
            if new_session_id and not self.session_id:
                with self._lock:
                    self.session_id = new_session_id
                logger.info("Session ID acquired: %s", new_session_id)

        elif event_type == "assistant":
            content = event.get("content") or event.get("message", {}).get("content")
            if content:
                if isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            logger.info("Assistant: %s", block.get("text", ""))
                elif isinstance(content, str):
                    logger.info("Assistant: %s", content)

        elif event_type == "result":
            with self._lock:
                self._result = event

        else:
            logger.debug("Event [%s]: %s", event_type, event)

    def _read_stdout(self, process: subprocess.Popen, verbose: bool) -> None:
        """Read stdout from the process and process JSON events.

        Args:
            process: The subprocess to read from.
            verbose: Whether to log verbose output.
        """
        if process.stdout is None:
            return

        for line in process.stdout:
            line = line.rstrip("\n\r")
            if not line:
                continue

            try:
                event = json.loads(line)
                with self._lock:
                    self._last_json = event
                self._process_json_event(event, verbose)
            except json.JSONDecodeError:
                logger.debug("Raw output: %s", line)

    def run_prompt(
        self,
        prompt_text: str,
        timeout: int = 2400,
        verbose: bool = False,
    ) -> dict[str, Any]:
        """Execute a prompt using Claude CLI.

        Args:
            prompt_text: The prompt text to send to Claude.
            timeout: Maximum time to wait for completion in seconds.
            verbose: Whether to enable verbose logging.

        Returns:
            The result dictionary from Claude CLI.

        Raises:
            subprocess.TimeoutExpired: If the command times out.
            KeyboardInterrupt: If the user interrupts execution.
            RuntimeError: If no valid response is received.
        """
        if self.session_id:
            logger.info("Starting prompt with session_id: %s", self.session_id)
        else:
            logger.info("Starting new session")

        self._result = None
        self._last_json = None

        cmd = self._build_command(prompt_text)
        logger.debug("Executing command: %s", shlex.join(cmd))

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )

        stdout_thread = threading.Thread(
            target=self._read_stdout,
            args=(process, verbose),
            daemon=True,
        )
        stderr_thread = threading.Thread(
            target=self._read_stderr,
            args=(process,),
            daemon=True,
        )

        stdout_thread.start()
        stderr_thread.start()

        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            logger.error("Command timed out after %d seconds", timeout)
            process.kill()
            process.wait()
            raise
        except KeyboardInterrupt:
            logger.warning("Keyboard interrupt received, terminating process")
            process.kill()
            process.wait()
            raise

        stdout_thread.join(timeout=5.0)
        stderr_thread.join(timeout=5.0)

        with self._lock:
            if self._result is not None:
                return self._result
            if self._last_json is not None:
                return self._last_json

        raise RuntimeError("No valid response received from Claude CLI")
