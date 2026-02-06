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

    This class manages the interaction with the `claude` CLI tool,
    handling session persistence, real-time output streaming, and
    result parsing.

    Attributes:
        session_id: The current session ID for conversation continuity.
    """

    def __init__(self) -> None:
        """Initialize ClaudeRunner with empty session state."""
        self.session_id: str | None = None

    def run_prompt(
        self,
        prompt_text: str,
        timeout: int = 2400,
        verbose: bool = False,
    ) -> dict[str, Any]:
        """Execute a prompt via Claude Code CLI and return the result.

        Args:
            prompt_text: The prompt text to send to Claude.
            timeout: Maximum time in seconds to wait for completion.
            verbose: If True, enable additional debug logging.

        Returns:
            A dictionary containing the result from Claude, typically
            including the response content and metadata.

        Raises:
            subprocess.TimeoutExpired: If the process exceeds the timeout.
            KeyboardInterrupt: If the user interrupts execution.
        """
        if self.session_id:
            logger.info("Starting prompt with session_id: %s", self.session_id)
        else:
            logger.info("Starting new session")

        command = self._build_command(prompt_text)
        logger.debug("Executing command: %s", " ".join(command))

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )

        result_holder: dict[str, Any] = {"result": None, "last_json": None}
        lock = threading.Lock()

        stdout_thread = threading.Thread(
            target=self._read_stdout,
            args=(process.stdout, result_holder, lock, verbose),
            daemon=True,
        )
        stderr_thread = threading.Thread(
            target=self._read_stderr,
            args=(process.stderr,),
            daemon=True,
        )

        stdout_thread.start()
        stderr_thread.start()

        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            logger.error("Process timed out after %d seconds", timeout)
            process.kill()
            stdout_thread.join(timeout=1)
            stderr_thread.join(timeout=1)
            raise
        except KeyboardInterrupt:
            logger.warning("Received keyboard interrupt, terminating process")
            process.kill()
            stdout_thread.join(timeout=1)
            stderr_thread.join(timeout=1)
            raise

        stdout_thread.join(timeout=5)
        stderr_thread.join(timeout=5)

        with lock:
            if result_holder["result"] is not None:
                return result_holder["result"]
            if result_holder["last_json"] is not None:
                return result_holder["last_json"]

        logger.warning("No valid result received from Claude")
        return {}

    def _build_command(self, prompt_text: str) -> list[str]:
        """Build the command list for subprocess execution.

        Args:
            prompt_text: The prompt text to include in the command.

        Returns:
            A list of command arguments ready for Popen.
        """
        command: list[str] = []

        if platform.system() == "Linux":
            command.extend(["stdbuf", "-oL", "-eL"])

        command.extend([
            "claude",
            "-p",
            prompt_text,
            "--output-format",
            "stream-json",
            "--verbose",
            "--dangerously-skip-permissions",
        ])

        if self.session_id:
            command.extend(["--resume", self.session_id])

        return command

    def _read_stdout(
        self,
        stream: Any,
        result_holder: dict[str, Any],
        lock: threading.Lock,
        verbose: bool,
    ) -> None:
        """Read and process stdout stream from Claude CLI.

        Parses NDJSON output, extracts session info, logs responses,
        and captures the final result.

        Args:
            stream: The stdout stream from the subprocess.
            result_holder: Shared dict to store result and last JSON.
            lock: Threading lock for safe access to result_holder.
            verbose: If True, log additional debug information.
        """
        if stream is None:
            return

        for line in stream:
            line = line.rstrip("\n\r")
            if not line:
                continue

            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                logger.debug("Raw output: %s", line)
                continue

            with lock:
                result_holder["last_json"] = data

            event_type = data.get("type")

            if event_type == "system":
                self._handle_system_event(data)
            elif event_type == "assistant":
                self._handle_assistant_event(data, verbose)
            elif event_type == "result":
                with lock:
                    result_holder["result"] = data
                logger.debug("Received result event")
            else:
                logger.debug("Event type '%s': %s", event_type, data)

    def _read_stderr(self, stream: Any) -> None:
        """Read and log stderr stream from Claude CLI.

        Args:
            stream: The stderr stream from the subprocess.
        """
        if stream is None:
            return

        for line in stream:
            line = line.rstrip("\n\r")
            if line:
                logger.warning("stderr: %s", line)

    def _handle_system_event(self, data: dict[str, Any]) -> None:
        """Handle system events, extracting session ID.

        Args:
            data: The parsed system event data.
        """
        session_id = data.get("session_id")
        if session_id and not self.session_id:
            self.session_id = session_id
            logger.info("Session ID acquired: %s", session_id)

    def _handle_assistant_event(self, data: dict[str, Any], verbose: bool) -> None:
        """Handle assistant events, logging response content.

        Args:
            data: The parsed assistant event data.
            verbose: If True, log full event data at debug level.
        """
        content = data.get("content")
        if content is None:
            message = data.get("message", {})
            content = message.get("content")

        if content:
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        logger.info("Assistant: %s", block.get("text", ""))
            elif isinstance(content, str):
                logger.info("Assistant: %s", content)

        if verbose:
            logger.debug("Assistant event: %s", data)
