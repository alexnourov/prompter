"""ClaudeRunner — Claude Code CLI assistant (EXE-01..EXE-12)."""

from __future__ import annotations

import json
import logging
import platform
import shutil
import threading
import time
from subprocess import DEVNULL, PIPE, Popen, TimeoutExpired

from ..models import SigtermReceived
from . import register_assistant
from .base import AssistantRunner

logger = logging.getLogger(__name__)


@register_assistant("claude")
class ClaudeRunner(AssistantRunner):
    """Wrapper for Claude Code CLI (NDJSON protocol)."""

    @property
    def supports_session(self) -> bool:
        return True

    def check_availability(self) -> None:  # RUN-04
        if shutil.which("claude") is None:
            raise RuntimeError("claude CLI not found in $PATH")

    def resume_hint(self) -> str | None:  # RUN-05
        if self._session_id:
            return (
                f"To continue this session interactively, "
                f"run: claude --resume {self._session_id}"
            )
        return None

    def _execute_prompt(
        self, prompt: str, timeout: int
    ) -> tuple[dict | None, str | None]:
        cmd = self._build_command(prompt)
        self._process = Popen(
            cmd, stdout=PIPE, stderr=PIPE,
            stdin=DEVNULL, text=True, bufsize=1,
        )  # EXE-01

        stderr_thread = threading.Thread(
            target=self._read_stderr, args=(self._process,), daemon=True
        )
        stderr_thread.start()

        deadline = time.monotonic() + timeout  # ERR-01

        try:
            result_obj, session_id = self._process_stream(
                self._process, deadline, timeout
            )
            remaining = max(deadline - time.monotonic(), 0)
            self._process.wait(timeout=remaining)
        except TimeoutExpired:
            self._process.kill()
            raise
        except KeyboardInterrupt:
            self._process.kill()
            raise
        except SigtermReceived:
            self._process.kill()
            raise

        if self._process.returncode != 0:  # ERR-06
            raise Exception(
                f"claude exited with code {self._process.returncode}"
            )

        return result_obj, session_id

    # --- Internal methods ---

    def _build_command(self, prompt: str) -> list[str]:
        cmd: list[str] = []

        # EXE-09: stdbuf on Linux/macOS
        if platform.system() in ("Linux", "Darwin"):
            stdbuf_path = shutil.which("stdbuf")
            if stdbuf_path:
                cmd.extend(["stdbuf", "-oL", "-eL"])
            elif platform.system() == "Linux":
                logger.warning(
                    "stdbuf not found; output buffering may cause delays"
                )

        cmd.append("claude")
        cmd.extend(["-p", prompt])                      # EXE-02
        cmd.extend(["--output-format", "stream-json"])  # EXE-03
        cmd.append("--verbose")                         # EXE-04
        cmd.append("--dangerously-skip-permissions")    # EXE-05

        if self._session_id is not None:                # EXE-07
            cmd.extend(["--resume", self._session_id])

        return cmd

    def _process_stream(
        self,
        process: Popen,
        deadline: float,
        timeout: int,
    ) -> tuple[dict | None, str | None]:
        session_id: str | None = None
        result_obj: dict | None = None

        for line in process.stdout:
            if time.monotonic() > deadline:  # ERR-01
                raise TimeoutExpired(process.args, timeout)

            line = line.strip()
            if not line:
                continue

            event = json.loads(line)

            match event["type"]:
                case "system":
                    session_id = event["session_id"]
                    logger.debug("system: %s", event)

                case "assistant":
                    message = event.get("message", event)
                    text = self._extract_text(message.get("content", []))
                    if text:  # EXE-12
                        logger.info(text)

                case "progress":
                    content = event.get("content", "")
                    if content:  # EXE-12
                        logger.info(content)

                case "result":
                    result_obj = event
                    logger.info(
                        "result: %s, %dms, $%.4f",
                        event.get("subtype", "unknown"),
                        event.get("duration_ms", 0),
                        event.get("total_cost_usd", 0),
                    )
                    logger.debug("result_raw: %s", event)

        return result_obj, session_id

    @staticmethod
    def _extract_text(content_blocks: list) -> str:
        return "".join(
            block.get("text", "")
            for block in content_blocks
            if block.get("type") == "text"
        )

    @staticmethod
    def _read_stderr(process: Popen) -> None:
        for line in process.stderr:
            line = line.strip()
            if line:
                logger.warning("stderr: %s", line)
