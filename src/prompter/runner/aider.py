"""AiderRunner — Aider CLI assistant (AEXE-01..AEXE-12)."""

from __future__ import annotations

import logging
import os
import platform
import shutil
import subprocess
import tempfile
import threading
import time

from ..models import SigtermReceived
from . import register_assistant
from .base import AssistantRunner

logger = logging.getLogger(__name__)


@register_assistant("aider")
class AiderRunner(AssistantRunner):
    """Wrapper for Aider CLI (plain text protocol, AEXE-01..AEXE-12)."""

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        # AEXE-07: temporary file for chat history
        fd, self._history_file = tempfile.mkstemp(
            suffix=".md", prefix="aider-history-"
        )
        os.close(fd)

    @property
    def supports_session(self) -> bool:
        return False

    def check_availability(self) -> None:  # RUN-04, AEXE-08
        """Check aider binary and authentication."""
        if shutil.which("aider") is None:
            raise RuntimeError(
                "aider is not available in $PATH. "
                "Please install: pip install aider-chat"
            )
        # Authentication check: config keys or env vars
        if self._config.get("api_key"):
            return
        if self._config.get("anthropic_api_key") or os.environ.get(
            "ANTHROPIC_API_KEY"
        ):
            return
        if self._config.get("openai_api_key") or os.environ.get(
            "OPENAI_API_KEY"
        ):
            return
        # Generic provider keys in config: *_api_key
        _RESERVED = {"api_key", "anthropic_api_key", "openai_api_key"}
        for key, value in self._config.items():
            if (
                key.upper().endswith("_API_KEY")
                and key not in _RESERVED
                and value
            ):
                return
        # Check common env vars
        for env_var in os.environ:
            if env_var.endswith("_API_KEY") and os.environ[env_var]:
                return
        raise RuntimeError(
            "Aider authentication not configured. "
            "Set an API key env var (ANTHROPIC_API_KEY, OPENAI_API_KEY, "
            "DEEPSEEK_API_KEY, etc.) or configure 'api_key' in aider settings."
        )

    def resume_hint(self) -> str | None:  # RUN-05
        """Return hint for continuing session with history file."""
        return (
            f"To continue this session, run: "
            f"aider --chat-history-file {self._history_file} ..."
        )

    def _execute_prompt(
        self, prompt: str, timeout: int
    ) -> tuple[dict | None, str | None]:
        """Run aider CLI, process plain text stdout."""
        cmd = self._build_command(prompt, timeout)
        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,  # AEXE-05
            text=True,
            bufsize=1,
        )

        stderr_thread = threading.Thread(
            target=self._read_stderr, args=(self._process,), daemon=True
        )
        stderr_thread.start()  # AEXE-10

        deadline = time.monotonic() + timeout

        try:
            result_obj = self._process_output(self._process, deadline, timeout)
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
                f"aider exited with code {self._process.returncode}"
            )

        return (result_obj, None)  # session_id is always None

    # --- Internal methods ---

    def _build_command(self, prompt: str, timeout: int) -> list[str]:
        """Build aider CLI command (AEXE-01..07, AEXE-11, AEXE-12)."""
        cmd: list[str] = []

        # AEXE-12: stdbuf on Linux/macOS
        if platform.system() in ("Linux", "Darwin"):
            stdbuf_path = shutil.which("stdbuf")
            if stdbuf_path:
                cmd.extend(["stdbuf", "-oL", "-eL"])
            elif platform.system() == "Linux":
                logger.warning(
                    "stdbuf not found; output buffering may cause delays"
                )

        cmd.append("aider")
        cmd.extend(["--message", prompt])              # AEXE-01
        cmd.extend([
            "--yes-always",                            # AEXE-02
            "--no-suggest-shell-commands",              # AEXE-02
            "--no-fancy-input",                         # AEXE-02
            "--no-detect-urls",                         # AEXE-02
            "--no-show-release-notes",                  # AEXE-02
            "--no-check-update",                        # AEXE-02
            "--no-analytics",                           # AEXE-02
            "--no-stream",                              # AEXE-03
            "--no-pretty",                              # AEXE-03
            "--no-auto-commits",                        # AEXE-04
        ])
        cmd.extend([
            "--chat-history-file", self._history_file,  # AEXE-07
            "--timeout", str(timeout),                  # AEXE-11
        ])

        if self._prompt_count > 1:                     # AEXE-07
            cmd.append("--restore-chat-history")

        # AEXE-06: model selection
        model = self._config.get("model")
        if model:
            cmd.extend(["--model", model])

        # AEXE-08: authentication args
        cmd.extend(self._get_auth_args())

        return cmd

    def _get_auth_args(self) -> list[str]:
        """Build authentication CLI args from config."""
        args: list[str] = []
        api_key = self._config.get("api_key")
        if api_key:
            args.extend(["--api-key", api_key])
        else:
            anthropic_key = self._config.get("anthropic_api_key")
            if anthropic_key:
                args.extend(["--anthropic-api-key", anthropic_key])
            openai_key = self._config.get("openai_api_key")
            if openai_key:
                args.extend(["--openai-api-key", openai_key])
            # Generic provider keys: key_api_key → --api-key provider=value
            _RESERVED = {"api_key", "anthropic_api_key", "openai_api_key"}
            for key, value in self._config.items():
                upper_key = key.upper()
                if (
                    upper_key.endswith("_API_KEY")
                    and key not in _RESERVED
                    and value
                ):
                    provider = upper_key.removesuffix("_API_KEY").lower()
                    args.extend(["--api-key", f"{provider}={value}"])
        return args

    def _process_output(
        self,
        process: subprocess.Popen,
        deadline: float,
        timeout: int,
    ) -> dict | None:
        """Process plain text stdout (AEXE-09)."""
        lines: list[str] = []
        for line in process.stdout:
            if time.monotonic() > deadline:
                raise subprocess.TimeoutExpired(process.args, timeout)
            line = line.rstrip("\n")
            if line:
                logger.info(line)
            lines.append(line)

        full_text = "\n".join(lines).strip()
        if not full_text:
            return None
        return {"assistant_response": full_text}

    @staticmethod
    def _read_stderr(process: subprocess.Popen) -> None:
        """Background stderr reading (AEXE-10)."""
        for line in process.stderr:
            line = line.strip()
            if line:
                logger.warning("stderr: %s", line)
