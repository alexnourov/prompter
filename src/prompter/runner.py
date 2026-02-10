"""Prompt execution via Claude CLI.

This module handles execution of prompts through the claude CLI tool,
processing NDJSON output streams and managing timeouts.
"""

import json
import logging
import platform
import shutil
import subprocess
import threading
import time
from subprocess import DEVNULL, PIPE

from .models import SigtermReceived

logger = logging.getLogger(__name__)


def run_prompt(
    prompt: str,
    session_id: str | None = None,
    timeout: int = 2400,
) -> tuple[dict | None, str | None]:
    """Execute a prompt using Claude CLI.

    Args:
        prompt: The prompt text to send to Claude
        session_id: Optional session ID to resume conversation (EXE-07)
        timeout: Timeout in seconds (default: 2400s = 40min) (ERR-01)

    Returns:
        Tuple of (result_object, session_id) where:
        - result_object: The parsed 'result' event from Claude, or None
        - session_id: Session ID from 'system' event, or None if not received

    Raises:
        subprocess.TimeoutExpired: If execution exceeds timeout (process killed)
        KeyboardInterrupt: If SIGINT received (process killed, re-raised)
        SigtermReceived: If SIGTERM received (process killed, re-raised)
        Exception: On non-zero exit code or other errors
    """
    # Build command (EXE-01, EXE-02..07, EXE-09)
    cmd = _build_command(prompt, session_id)

    # Start process with stdout/stderr pipes (EXE-01)
    process = subprocess.Popen(
        cmd,
        stdout=PIPE,
        stderr=PIPE,
        stdin=DEVNULL,
        text=True,
        bufsize=1,  # Line-buffered
    )

    # Start background thread for stderr logging
    def log_stderr() -> None:
        """Read stderr and log as WARNING."""
        if process.stderr:
            for line in process.stderr:
                line = line.strip()
                if line:
                    logger.warning(f"claude stderr: {line}")

    stderr_thread = threading.Thread(target=log_stderr, daemon=True)
    stderr_thread.start()

    # Calculate absolute deadline (ERR-01)
    deadline = time.monotonic() + timeout

    try:
        # Process NDJSON stream (EXE-08, EXE-10)
        result_obj, session_id_out = _process_stream(process, deadline, timeout)

        # Wait for process completion with remaining timeout
        remaining = max(deadline - time.monotonic(), 0)
        process.wait(timeout=remaining)

        # Check exit code (ERR-06)
        if process.returncode != 0:
            raise Exception(
                f"Claude CLI exited with non-zero code {process.returncode}. "
                f"Command: {' '.join(cmd)}"
            )

        return (result_obj, session_id_out)

    except subprocess.TimeoutExpired:
        # Kill process and re-raise (ERR-01)
        process.kill()
        raise

    except KeyboardInterrupt:
        # Kill process and re-raise (INT-02)
        process.kill()
        raise

    except SigtermReceived:
        # Kill process and re-raise (INT-04)
        process.kill()
        raise


def _build_command(prompt: str, session_id: str | None) -> list[str]:
    """Build command line arguments for claude CLI.

    Args:
        prompt: The prompt text
        session_id: Optional session ID to resume

    Returns:
        List of command arguments
    """
    cmd: list[str] = []

    # Platform-specific stdbuf prefix (EXE-09)
    system = platform.system()
    if system in ("Linux", "Darwin"):
        stdbuf_path = shutil.which("stdbuf")
        if stdbuf_path:
            cmd.extend(["stdbuf", "-oL", "-eL"])
        elif system == "Linux":
            # On Linux, warn if stdbuf is missing
            logger.warning(
                "stdbuf not found on Linux. Install coreutils for optimal buffering. "
                "Proceeding without stdbuf."
            )
        # On macOS (Darwin), stdbuf is optional - no warning needed

    # Base command
    cmd.append("claude")

    # Prompt with -p flag (EXE-02)
    cmd.extend(["-p", prompt])

    # Output format (EXE-03)
    cmd.extend(["--output-format", "stream-json"])

    # Verbose mode (EXE-04)
    cmd.append("--verbose")

    # Skip permissions (EXE-05)
    cmd.append("--dangerously-skip-permissions")

    # Resume session if provided (EXE-07)
    if session_id is not None:
        cmd.extend(["--resume", session_id])

    return cmd


def _process_stream(
    process: subprocess.Popen,
    deadline: float,
    timeout: int,
) -> tuple[dict | None, str | None]:
    """Process NDJSON stream from Claude CLI stdout.

    Args:
        process: The subprocess instance
        deadline: Absolute deadline (monotonic time) for timeout check
        timeout: Original timeout value (for TimeoutExpired exception)

    Returns:
        Tuple of (result_object, session_id)

    Raises:
        subprocess.TimeoutExpired: If deadline exceeded (ERR-01)
    """
    session_id: str | None = None
    result_obj: dict | None = None

    assert process.stdout is not None

    for line in process.stdout:
        # Check deadline before processing (ERR-01)
        if time.monotonic() > deadline:
            raise subprocess.TimeoutExpired(process.args, timeout)

        line = line.strip()
        if not line:
            continue

        try:
            event = json.loads(line)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON line: {e}. Line: {line[:100]}")
            continue

        event_type = event.get("type")

        match event_type:
            case "system":
                # Extract session_id (EXE-06)
                session_id = event.get("session_id")
                logger.debug(f"system: {event}")

            case "assistant":
                # Extract and log assistant message (EXE-10)
                # CLI >= 2.1: message.content; fallback: content
                message = event.get("message", event)
                text = _extract_text(message.get("content", []))
                if text:  # EXE-12: only log non-empty
                    logger.info(text)

            case "progress":
                # Log progress updates (EXE-10)
                content = event.get("content", "")
                if content:  # EXE-12: only log non-empty
                    logger.info(content)

            case "result":
                # Store result and log summary (EXE-10)
                result_obj = event
                subtype = event.get("subtype", "unknown")
                duration_ms = event.get("duration_ms", 0)
                cost_usd = event.get("total_cost_usd", 0.0)
                logger.info(f"result: {subtype}, {duration_ms}ms, ${cost_usd:.4f}")
                logger.debug(f"result_raw: {event}")

    return (result_obj, session_id)


def _extract_text(content: list | str) -> str:
    """Extract text from Claude message content.

    Args:
        content: Content field from message (array of content blocks or string)

    Returns:
        Concatenated text from all text blocks
    """
    if isinstance(content, str):
        return content

    if not isinstance(content, list):
        return ""

    texts: list[str] = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            text = block.get("text", "")
            if text:
                texts.append(text)

    return "\n".join(texts)
