"""GeminiRunner — Gemini CLI assistant (GEXE-01..GEXE-13)."""

from __future__ import annotations

import json
import logging
import platform
import shutil
import subprocess
import threading
import time

from ..models import SigtermReceived
from . import register_assistant
from .base import AssistantRunner

logger = logging.getLogger(__name__)


@register_assistant("gemini")
class GeminiRunner(AssistantRunner):
    """Wrapper for Gemini CLI (NDJSON protocol, GEXE-01..GEXE-13)."""

    @property
    def supports_session(self) -> bool:
        return True

    def check_availability(self) -> None:  # RUN-04
        if shutil.which("gemini") is None:
            raise RuntimeError("gemini CLI not found in $PATH")

    def resume_hint(self) -> str | None:  # RUN-05
        if self._session_id:
            return (
                f"To continue this session, run: "
                f"gemini --resume {self._session_id}"
            )
        return None

    def _execute_prompt(
        self, prompt: str, timeout: int
    ) -> tuple[dict | None, str | None]:
        cmd = self._build_command(prompt)
        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )  # GEXE-01

        stderr_thread = threading.Thread(
            target=self._read_stderr, args=(self._process,), daemon=True
        )
        stderr_thread.start()

        deadline = time.monotonic() + timeout

        try:
            result_obj, session_id = self._process_stream(
                self._process, deadline, timeout
            )
            remaining = max(deadline - time.monotonic(), 0)
            self._process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            self._process.kill()
            raise
        except KeyboardInterrupt:
            self._process.kill()
            raise
        except SigtermReceived:
            self._process.kill()
            raise

        if self._process.returncode != 0:
            raise Exception(
                f"gemini exited with code {self._process.returncode}"
            )

        return (result_obj, session_id)

    # --- Internal methods ---

    def _build_command(self, prompt: str) -> list[str]:
        cmd: list[str] = []

        # GEXE-13: stdbuf on Linux/macOS
        if platform.system() in ("Linux", "Darwin"):
            stdbuf_path = shutil.which("stdbuf")
            if stdbuf_path:
                cmd.extend(["stdbuf", "-oL", "-eL"])
            elif platform.system() == "Linux":
                logger.warning(
                    "stdbuf not found, running without line buffering"
                )

        cmd.append("gemini")
        cmd.extend(["-p", prompt])                      # GEXE-02
        cmd.extend(["--output-format", "stream-json"])  # GEXE-03
        cmd.append("-y")                                # GEXE-04

        # GEXE-06: model selection
        model = self._config.get("model")
        if model:
            cmd.extend(["-m", model])

        # GEXE-07: session resume
        if self._session_id:
            cmd.extend(["--resume", self._session_id])

        return cmd

    def _process_stream(
        self,
        process: subprocess.Popen,
        deadline: float,
        timeout: int,
    ) -> tuple[dict | None, str | None]:
        session_id: str | None = None
        result_obj: dict | None = None

        for line in process.stdout:
            if time.monotonic() > deadline:
                raise subprocess.TimeoutExpired(process.args, timeout)

            line = line.strip()
            if not line:
                continue

            event = json.loads(line)

            match event["type"]:
                case "init":
                    session_id = event.get("session_id")
                    logger.info("init: %s", event)

                case "message":
                    if event.get("role") == "assistant":
                        content = event.get("content", "")
                        if content.strip():
                            logger.info(content)

                case "result":
                    result_obj = event
                    stats = event.get("stats", {})
                    logger.info(
                        "result: %s, %dms, tokens: %d",
                        event.get("status", "unknown"),
                        stats.get("duration_ms", 0),
                        stats.get("total_tokens", 0),
                    )
                    logger.debug("result_raw: %s", event)

                case _:
                    logger.debug("event: %s", event)

        return (result_obj, session_id)

    @staticmethod
    def _read_stderr(process: subprocess.Popen) -> None:
        for line in process.stderr:
            line = line.strip()
            if line:
                logger.warning("stderr: %s", line)
