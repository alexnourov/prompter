"""Tests for the prompter.runner subpackage (base + Claude + Aider + Gemini)."""

from __future__ import annotations

import json
import os
import subprocess
from subprocess import DEVNULL
from unittest.mock import MagicMock, call, patch

import pytest

from prompter.models import SessionIntegrityError, SigtermReceived
from prompter.runner import (
    AssistantRunner,
    _REGISTRY,
    create_runner,
    register_assistant,
)
from prompter.runner.aider import AiderRunner
from prompter.runner.claude import ClaudeRunner
from prompter.runner.gemini import GeminiRunner


# ─── Helpers ───────────────────────────────────────────────────────────────

def _ndjson_lines(*events: dict) -> list[str]:
    """Encode dicts as NDJSON lines (with trailing newlines)."""
    return [json.dumps(e) + "\n" for e in events]


def _make_mock_process(
    stdout_lines: list[str] | None = None,
    stderr_lines: list[str] | None = None,
    returncode: int = 0,
) -> MagicMock:
    """Create a mock Popen process with configurable stdout/stderr."""
    proc = MagicMock()
    proc.stdout = iter(stdout_lines or [])
    proc.stderr = iter(stderr_lines or [])
    proc.returncode = returncode
    proc.wait.return_value = returncode
    return proc


SYSTEM_EVENT = {"type": "system", "session_id": "sess_123"}
RESULT_EVENT = {
    "type": "result",
    "subtype": "success",
    "result": "Done",
    "duration_ms": 1500,
    "total_cost_usd": 0.02,
}
STANDARD_STDOUT = _ndjson_lines(SYSTEM_EVENT, RESULT_EVENT)


# ─── Registry and factory ─────────────────────────────────────────────────

class TestRegistry:
    """Tests for assistant registry and factory (RUN-01, RUN-02)."""

    def test_create_runner_claude(self) -> None:
        """create_runner('claude', {}) returns a ClaudeRunner instance."""
        runner = create_runner("claude", {})
        assert isinstance(runner, ClaudeRunner)
        assert isinstance(runner, AssistantRunner)

    def test_create_runner_unknown(self) -> None:
        """create_runner('unknown', {}) raises ValueError."""
        with pytest.raises(ValueError, match="Unknown assistant"):
            create_runner("unknown", {})

    def test_register_custom_assistant(self) -> None:
        """Register a custom assistant via decorator and create it."""

        @register_assistant("custom")
        class CustomRunner(AssistantRunner):
            @property
            def supports_session(self) -> bool:
                return False

            def check_availability(self) -> None:
                pass

            def resume_hint(self) -> str | None:
                return None

            def _execute_prompt(self, prompt, timeout):
                return {"text": "ok"}, None

        try:
            runner = create_runner("custom", {})
            assert isinstance(runner, CustomRunner)
        finally:
            _REGISTRY.pop("custom", None)


# ─── Session integrity (ORC-03, ORC-06, ORC-07) ───────────────────────────

class TestSessionIntegrity:
    """Tests for session validation in the base AssistantRunner."""

    def test_missing_session_id_first_prompt(self) -> None:
        """ORC-03: No session_id from first prompt raises SessionIntegrityError."""
        runner = ClaudeRunner({})
        result_obj = {"type": "result", "text": "response"}

        with patch.object(runner, "_execute_prompt", return_value=(result_obj, None)):
            with pytest.raises(SessionIntegrityError, match="No session_id"):
                runner.run_prompt("prompt1", 2400)

    def test_lost_session_id(self) -> None:
        """ORC-06: Lost session_id on second prompt raises SessionIntegrityError."""
        runner = ClaudeRunner({})
        result_obj = {"type": "result", "text": "response"}

        with patch.object(
            runner, "_execute_prompt", return_value=(result_obj, "sess_abc")
        ):
            runner.run_prompt("prompt1", 2400)

        assert runner._session_id == "sess_abc"

        with patch.object(runner, "_execute_prompt", return_value=(result_obj, None)):
            with pytest.raises(SessionIntegrityError, match="no session_id"):
                runner.run_prompt("prompt2", 2400)

    def test_changed_session_id(self) -> None:
        """ORC-07: Changed session_id raises SessionIntegrityError."""
        runner = ClaudeRunner({})
        result_obj = {"type": "result", "text": "response"}

        with patch.object(
            runner, "_execute_prompt", return_value=(result_obj, "sess_abc")
        ):
            runner.run_prompt("prompt1", 2400)

        with patch.object(
            runner, "_execute_prompt", return_value=(result_obj, "sess_xyz")
        ):
            with pytest.raises(SessionIntegrityError, match="sess_abc.*sess_xyz"):
                runner.run_prompt("prompt2", 2400)


# ─── Session logging (ORC-02) ─────────────────────────────────────────────

class TestSessionLogging:
    """Tests for session logging."""

    def test_session_logging(self, caplog: pytest.LogCaptureFixture) -> None:
        """ORC-02: 'session: new' logged before first prompt."""
        runner = ClaudeRunner({})
        result_obj = {"type": "result", "text": "response"}

        with patch.object(
            runner, "_execute_prompt", return_value=(result_obj, "sess_abc")
        ):
            with caplog.at_level("INFO", logger="prompter.runner.base"):
                runner.run_prompt("prompt1", 2400)

        assert any("session: new" in rec.message for rec in caplog.records)


# ─── Timeout and signal handling ──────────────────────────────────────────

class TestTimeoutAndSignals:
    """Tests for timeout, KeyboardInterrupt, and SIGTERM handling."""

    def test_timeout(self) -> None:
        """TimeoutExpired: process killed and exception re-raised."""
        runner = ClaudeRunner({})
        mock_process = _make_mock_process()
        mock_process.wait.side_effect = subprocess.TimeoutExpired(
            cmd="claude", timeout=1
        )

        with patch("prompter.runner.claude.Popen", return_value=mock_process):
            with pytest.raises(subprocess.TimeoutExpired):
                runner.run_prompt("test", timeout=1)

        mock_process.kill.assert_called()

    def test_keyboard_interrupt_kills_process(self) -> None:
        """INT-02: KeyboardInterrupt kills process and re-raises."""
        runner = ClaudeRunner({})
        mock_process = _make_mock_process()
        mock_process.wait.side_effect = KeyboardInterrupt

        with patch("prompter.runner.claude.Popen", return_value=mock_process):
            with pytest.raises(KeyboardInterrupt):
                runner.run_prompt("test", timeout=2400)

        mock_process.kill.assert_called()

    def test_sigterm_kills_process(self) -> None:
        """INT-04: SigtermReceived kills process and re-raises."""
        runner = ClaudeRunner({})
        mock_process = _make_mock_process()
        mock_process.wait.side_effect = SigtermReceived

        with patch("prompter.runner.claude.Popen", return_value=mock_process):
            with pytest.raises(SigtermReceived):
                runner.run_prompt("test", timeout=2400)

        mock_process.kill.assert_called()


# ─── ClaudeRunner command building ────────────────────────────────────────

class TestClaudeCommandFlags:
    """Tests for ClaudeRunner command construction."""

    def test_command_flags(self) -> None:
        """EXE-01..05, EXE-11: Verify CLI flags and Popen kwargs."""
        runner = create_runner("claude", {})
        mock_process = _make_mock_process(stdout_lines=STANDARD_STDOUT)

        with patch("prompter.runner.claude.Popen", return_value=mock_process) as mock_popen:
            runner.run_prompt("Hello", timeout=2400)

        mock_popen.assert_called_once()
        cmd = mock_popen.call_args[0][0]
        kwargs = mock_popen.call_args[1]

        # EXE-02: prompt flag
        assert "-p" in cmd
        idx_p = cmd.index("-p")
        assert cmd[idx_p + 1] == "Hello"

        # EXE-03: output format
        assert "--output-format" in cmd
        idx_fmt = cmd.index("--output-format")
        assert cmd[idx_fmt + 1] == "stream-json"

        # EXE-04: verbose
        assert "--verbose" in cmd

        # EXE-05: skip permissions
        assert "--dangerously-skip-permissions" in cmd

        # EXE-11: stdin=DEVNULL
        assert kwargs.get("stdin") == DEVNULL

    def test_stdbuf_prefix_on_linux(self) -> None:
        """EXE-09: stdbuf prefix present on Linux when stdbuf is available."""
        runner = create_runner("claude", {})
        mock_process = _make_mock_process(stdout_lines=STANDARD_STDOUT)

        with patch("prompter.runner.claude.Popen", return_value=mock_process) as mock_popen, \
             patch("prompter.runner.claude.platform.system", return_value="Linux"), \
             patch("prompter.runner.claude.shutil.which", return_value="/usr/bin/stdbuf"):
            runner.run_prompt("Hello", 2400)

        cmd = mock_popen.call_args[0][0]
        assert cmd[:3] == ["stdbuf", "-oL", "-eL"]

    def test_stdbuf_fallback(self, caplog: pytest.LogCaptureFixture) -> None:
        """EXE-09: No stdbuf on Linux → warning logged, no stdbuf in cmd."""
        runner = create_runner("claude", {})
        mock_process = _make_mock_process(stdout_lines=STANDARD_STDOUT)

        with patch("prompter.runner.claude.Popen", return_value=mock_process) as mock_popen, \
             patch("prompter.runner.claude.platform.system", return_value="Linux"), \
             patch("prompter.runner.claude.shutil.which", return_value=None):
            with caplog.at_level("WARNING", logger="prompter.runner.claude"):
                runner.run_prompt("Hello", 2400)

        cmd = mock_popen.call_args[0][0]
        assert "stdbuf" not in cmd
        assert any("stdbuf not found" in rec.message for rec in caplog.records)

    def test_stdbuf_prefix_on_macos(self) -> None:
        """EXE-09: stdbuf prefix present on macOS (Darwin)."""
        runner = create_runner("claude", {})
        mock_process = _make_mock_process(stdout_lines=STANDARD_STDOUT)

        with patch("prompter.runner.claude.Popen", return_value=mock_process) as mock_popen, \
             patch("prompter.runner.claude.platform.system", return_value="Darwin"), \
             patch("prompter.runner.claude.shutil.which", return_value="/usr/local/bin/stdbuf"):
            runner.run_prompt("Hello", 2400)

        cmd = mock_popen.call_args[0][0]
        assert cmd[:3] == ["stdbuf", "-oL", "-eL"]


# ─── ClaudeRunner session chaining ────────────────────────────────────────

class TestClaudeCommandChain:
    """Tests for session chaining via --resume flag."""

    def test_command_chain(self) -> None:
        """EXE-07: --resume absent on first call, present on second."""
        runner = create_runner("claude", {})
        mock_process = _make_mock_process(stdout_lines=STANDARD_STDOUT)

        with patch("prompter.runner.claude.Popen", return_value=mock_process) as mock_popen:
            runner.run_prompt("prompt1", 2400)

        cmd1 = mock_popen.call_args[0][0]
        assert "--resume" not in cmd1

        # Second call — process needs fresh stdout iterator
        mock_process2 = _make_mock_process(stdout_lines=STANDARD_STDOUT)

        with patch("prompter.runner.claude.Popen", return_value=mock_process2) as mock_popen2:
            runner.run_prompt("prompt2", 2400)

        cmd2 = mock_popen2.call_args[0][0]
        assert "--resume" in cmd2
        idx = cmd2.index("--resume")
        assert cmd2[idx + 1] == "sess_123"


# ─── ClaudeRunner stream processing ──────────────────────────────────────

class TestClaudeStreamProcessing:
    """Tests for NDJSON stream processing."""

    def test_stream_processing(self, caplog: pytest.LogCaptureFixture) -> None:
        """Verify all event types are processed and logged correctly."""
        events = _ndjson_lines(
            {"type": "system", "session_id": "sess-1"},
            {
                "type": "assistant",
                "message": {
                    "content": [{"type": "text", "text": "Hello"}],
                },
            },
            {"type": "progress", "content": "thinking..."},
            {
                "type": "result",
                "subtype": "success",
                "result": "Done",
                "duration_ms": 1500,
                "total_cost_usd": 0.02,
            },
        )

        runner = create_runner("claude", {})
        mock_process = _make_mock_process(stdout_lines=events)

        with patch("prompter.runner.claude.Popen", return_value=mock_process):
            with caplog.at_level("DEBUG", logger="prompter.runner.claude"):
                result = runner.run_prompt("test", 2400)

        # system → DEBUG
        assert any(
            rec.levelname == "DEBUG" and "system:" in rec.message
            for rec in caplog.records
        )

        # assistant text → INFO
        assert any(
            rec.levelname == "INFO" and "Hello" in rec.message
            for rec in caplog.records
        )

        # progress → INFO
        assert any(
            rec.levelname == "INFO" and "thinking..." in rec.message
            for rec in caplog.records
        )

        # result summary → INFO
        assert any(
            rec.levelname == "INFO"
            and "result: success, 1500ms, $0.0200" in rec.message
            for rec in caplog.records
        )

        # result raw → DEBUG
        assert any(
            rec.levelname == "DEBUG" and "result_raw:" in rec.message
            for rec in caplog.records
        )

        # result_obj contains the result event
        assert result is not None
        assert result["result"] == "Done"

    def test_stream_processing_legacy_format(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Legacy format: assistant event without 'message' wrapper."""
        events = _ndjson_lines(
            {"type": "system", "session_id": "sess-1"},
            {
                "type": "assistant",
                "content": [{"type": "text", "text": "Legacy"}],
            },
            RESULT_EVENT,
        )

        runner = create_runner("claude", {})
        mock_process = _make_mock_process(stdout_lines=events)

        with patch("prompter.runner.claude.Popen", return_value=mock_process):
            with caplog.at_level("INFO", logger="prompter.runner.claude"):
                runner.run_prompt("test", 2400)

        assert any(
            "Legacy" in rec.message for rec in caplog.records
        )

    def test_empty_events_not_logged(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """EXE-12: Empty assistant/progress events are not logged."""
        events = _ndjson_lines(
            {"type": "system", "session_id": "sess-1"},
            {"type": "assistant", "message": {"content": []}},
            {"type": "progress", "content": ""},
            {
                "type": "assistant",
                "message": {
                    "content": [{"type": "text", "text": "Real"}],
                },
            },
            RESULT_EVENT,
        )

        runner = create_runner("claude", {})
        mock_process = _make_mock_process(stdout_lines=events)

        with patch("prompter.runner.claude.Popen", return_value=mock_process):
            with caplog.at_level("INFO", logger="prompter.runner.claude"):
                runner.run_prompt("test", 2400)

        info_msgs = [
            rec.message
            for rec in caplog.records
            if rec.levelname == "INFO" and rec.name == "prompter.runner.claude"
        ]
        # "Real" is logged, but no empty messages
        assert any("Real" in m for m in info_msgs)
        # No empty string logged as a message
        assert all(m.strip() for m in info_msgs)


# ─── ClaudeRunner error handling ──────────────────────────────────────────

class TestClaudeErrors:
    """Tests for error scenarios in ClaudeRunner."""

    def test_malformed_ndjson(self) -> None:
        """ERR-06: Malformed NDJSON raises json.JSONDecodeError."""
        runner = create_runner("claude", {})
        mock_process = _make_mock_process(
            stdout_lines=["{broken json\n"]
        )

        with patch("prompter.runner.claude.Popen", return_value=mock_process):
            with pytest.raises((json.JSONDecodeError, Exception)):
                runner.run_prompt("test", 2400)

    def test_concurrent_stdout_stderr(self) -> None:
        """EXE-08: stdout and stderr processed without deadlock."""
        runner = create_runner("claude", {})
        mock_process = _make_mock_process(
            stdout_lines=STANDARD_STDOUT,
            stderr_lines=["warning line 1\n", "warning line 2\n"],
        )

        with patch("prompter.runner.claude.Popen", return_value=mock_process), \
             patch("prompter.runner.claude.logger") as mock_logger:
            result = runner.run_prompt("test", 2400)

        # Result is correct
        assert result is not None
        assert result["result"] == "Done"

        # stderr logged as WARNING via daemon thread
        warning_calls = [
            str(c) for c in mock_logger.warning.call_args_list
        ]
        assert any("warning line 1" in c for c in warning_calls)
        assert any("warning line 2" in c for c in warning_calls)


# ═══════════════════════════════════════════════════════════════════════════
# AiderRunner tests (AEXE-01..AEXE-12, TS-AIDER)
# ═══════════════════════════════════════════════════════════════════════════

AIDER_STDOUT = ["Hello from aider\n", "Done!\n"]


class TestAider:
    """TC-01-A, TC-16-A, TC-AVAILABILITY-A: AiderRunner tests."""

    # ── TC-AVAILABILITY-A: check_availability ─────────────────────────

    def test_check_availability_aider_with_env_key(self) -> None:
        """AEXE-08: aider in PATH + ANTHROPIC_API_KEY env → no error."""
        runner = AiderRunner({})
        with patch("prompter.runner.aider.shutil.which",
                   return_value="/usr/bin/aider"), \
             patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-xxx"},
                        clear=False):
            runner.check_availability()  # no exception

    def test_check_availability_aider_with_config_key(self) -> None:
        """AEXE-08: api_key in config → no error."""
        runner = AiderRunner({"api_key": "anthropic=sk-ant-xxx"})
        with patch("prompter.runner.aider.shutil.which",
                   return_value="/usr/bin/aider"):
            runner.check_availability()  # no exception

    def test_check_availability_aider_not_found(self) -> None:
        """RUN-04: aider not in PATH → RuntimeError."""
        runner = AiderRunner({})
        with patch("prompter.runner.aider.shutil.which", return_value=None):
            with pytest.raises(RuntimeError, match="not available"):
                runner.check_availability()

    def test_check_availability_aider_no_auth(self) -> None:
        """AEXE-08: no keys anywhere → RuntimeError."""
        runner = AiderRunner({})
        clean_env = {
            k: v for k, v in os.environ.items()
            if not k.endswith("_API_KEY")
        }
        with patch("prompter.runner.aider.shutil.which",
                   return_value="/usr/bin/aider"), \
             patch.dict(os.environ, clean_env, clear=True):
            with pytest.raises(RuntimeError, match="authentication"):
                runner.check_availability()

    # ── TC-01-A: command flags ────────────────────────────────────────

    def test_aider_command_flags(self) -> None:
        """AEXE-01..05, AEXE-07, AEXE-11: core CLI flags present."""
        runner = AiderRunner({})
        mock_process = _make_mock_process(stdout_lines=AIDER_STDOUT)

        with patch("prompter.runner.aider.subprocess.Popen",
                   return_value=mock_process) as mock_popen:
            runner.run_prompt("Do something", timeout=2400)

        cmd = mock_popen.call_args[0][0]

        # AEXE-01
        assert "--message" in cmd
        idx = cmd.index("--message")
        assert cmd[idx + 1] == "Do something"

        # AEXE-02
        assert "--yes-always" in cmd

        # AEXE-03
        assert "--no-stream" in cmd
        assert "--no-pretty" in cmd

        # AEXE-04
        assert "--no-auto-commits" in cmd

        # AEXE-07
        assert "--chat-history-file" in cmd

        # AEXE-11
        assert "--timeout" in cmd
        idx_t = cmd.index("--timeout")
        assert cmd[idx_t + 1] == "2400"

    def test_aider_model_flag(self) -> None:
        """AEXE-06: --model from config."""
        runner = AiderRunner({"model": "claude-3-opus"})
        mock_process = _make_mock_process(stdout_lines=AIDER_STDOUT)

        with patch("prompter.runner.aider.subprocess.Popen",
                   return_value=mock_process) as mock_popen:
            runner.run_prompt("test", 2400)

        cmd = mock_popen.call_args[0][0]
        assert "--model" in cmd
        idx = cmd.index("--model")
        assert cmd[idx + 1] == "claude-3-opus"

    def test_aider_chat_history_restore(self) -> None:
        """AEXE-07: --restore-chat-history appears only from 2nd prompt."""
        runner = AiderRunner({})

        mock_process1 = _make_mock_process(stdout_lines=AIDER_STDOUT)
        with patch("prompter.runner.aider.subprocess.Popen",
                   return_value=mock_process1) as mock_popen1:
            runner.run_prompt("first", 2400)

        cmd1 = mock_popen1.call_args[0][0]
        assert "--restore-chat-history" not in cmd1

        mock_process2 = _make_mock_process(stdout_lines=AIDER_STDOUT)
        with patch("prompter.runner.aider.subprocess.Popen",
                   return_value=mock_process2) as mock_popen2:
            runner.run_prompt("second", 2400)

        cmd2 = mock_popen2.call_args[0][0]
        assert "--restore-chat-history" in cmd2

    def test_aider_stdbuf(self) -> None:
        """AEXE-12: stdbuf prefix on Linux when available."""
        runner = AiderRunner({})
        mock_process = _make_mock_process(stdout_lines=AIDER_STDOUT)

        with patch("prompter.runner.aider.subprocess.Popen",
                   return_value=mock_process) as mock_popen, \
             patch("prompter.runner.aider.platform.system",
                   return_value="Linux"), \
             patch("prompter.runner.aider.shutil.which",
                   return_value="/usr/bin/stdbuf"):
            runner.run_prompt("test", 2400)

        cmd = mock_popen.call_args[0][0]
        assert cmd[:3] == ["stdbuf", "-oL", "-eL"]
        assert cmd[3] == "aider"

    # ── TC-01-A: plain text processing ────────────────────────────────

    def test_aider_plain_text_processing(self) -> None:
        """AEXE-09: multi-line stdout joined into assistant_response."""
        runner = AiderRunner({})
        mock_process = _make_mock_process(
            stdout_lines=["Line 1\n", "Line 2\n", "Line 3\n"]
        )

        with patch("prompter.runner.aider.subprocess.Popen",
                   return_value=mock_process):
            result = runner.run_prompt("test", 2400)

        assert result is not None
        assert result["assistant_response"] == "Line 1\nLine 2\nLine 3"

    def test_aider_empty_stdout(self) -> None:
        """AEXE-09: empty stdout → result_obj is None."""
        runner = AiderRunner({})
        mock_process = _make_mock_process(stdout_lines=["\n", "\n"])

        with patch("prompter.runner.aider.subprocess.Popen",
                   return_value=mock_process):
            result = runner.run_prompt("test", 2400)

        assert result is None

    def test_aider_stderr_warning(self) -> None:
        """AEXE-10: stderr lines logged as WARNING."""
        runner = AiderRunner({})
        mock_process = _make_mock_process(
            stdout_lines=AIDER_STDOUT,
            stderr_lines=["warn 1\n", "warn 2\n"],
        )

        with patch("prompter.runner.aider.subprocess.Popen",
                   return_value=mock_process), \
             patch("prompter.runner.aider.logger") as mock_logger:
            runner.run_prompt("test", 2400)

        warning_calls = [
            str(c) for c in mock_logger.warning.call_args_list
        ]
        assert any("warn 1" in c for c in warning_calls)
        assert any("warn 2" in c for c in warning_calls)

    # ── TC-16-A: resume_hint ──────────────────────────────────────────

    def test_aider_resume_hint(self) -> None:
        """RUN-05: resume_hint contains aider --chat-history-file."""
        runner = AiderRunner({})
        hint = runner.resume_hint()
        assert hint is not None
        assert "aider --chat-history-file" in hint
        assert runner._history_file in hint


# ═══════════════════════════════════════════════════════════════════════════
# GeminiRunner tests (GEXE-01..GEXE-13, TS-GEMINI)
# ═══════════════════════════════════════════════════════════════════════════

GEMINI_INIT_EVENT = {"type": "init", "session_id": "gem-123"}
GEMINI_RESULT_EVENT = {
    "type": "result",
    "status": "success",
    "stats": {"duration_ms": 2000, "total_tokens": 150},
}
GEMINI_STANDARD_STDOUT = _ndjson_lines(GEMINI_INIT_EVENT, GEMINI_RESULT_EVENT)


class TestGemini:
    """TC-01-G, TC-16-G, TC-AVAILABILITY-G: GeminiRunner tests."""

    # ── TC-01-G: command flags ────────────────────────────────────────

    def test_gemini_command_flags(self) -> None:
        """GEXE-02..04: gemini, -p, --output-format stream-json, -y, stdin."""
        runner = GeminiRunner({})
        mock_process = _make_mock_process(stdout_lines=GEMINI_STANDARD_STDOUT)

        with patch("prompter.runner.gemini.subprocess.Popen",
                   return_value=mock_process) as mock_popen:
            runner.run_prompt("Hello Gemini", timeout=2400)

        cmd = mock_popen.call_args[0][0]
        kwargs = mock_popen.call_args[1]

        # GEXE-01: gemini binary
        assert "gemini" in cmd

        # GEXE-02: prompt flag
        assert "-p" in cmd
        idx_p = cmd.index("-p")
        assert cmd[idx_p + 1] == "Hello Gemini"

        # GEXE-03: output format
        assert "--output-format" in cmd
        idx_fmt = cmd.index("--output-format")
        assert cmd[idx_fmt + 1] == "stream-json"

        # GEXE-04: auto-accept
        assert "-y" in cmd

        # stdin=DEVNULL
        assert kwargs.get("stdin") == subprocess.DEVNULL

    def test_gemini_stdbuf(self) -> None:
        """GEXE-13: stdbuf prefix on Linux when available."""
        runner = GeminiRunner({})
        mock_process = _make_mock_process(stdout_lines=GEMINI_STANDARD_STDOUT)

        with patch("prompter.runner.gemini.subprocess.Popen",
                   return_value=mock_process) as mock_popen, \
             patch("prompter.runner.gemini.platform.system",
                   return_value="Linux"), \
             patch("prompter.runner.gemini.shutil.which",
                   return_value="/usr/bin/stdbuf"):
            runner.run_prompt("test", 2400)

        cmd = mock_popen.call_args[0][0]
        assert cmd[:3] == ["stdbuf", "-oL", "-eL"]
        assert cmd[3] == "gemini"

    def test_gemini_model_flag(self) -> None:
        """GEXE-06: -m gemini-2.0-flash in argv."""
        runner = GeminiRunner({"model": "gemini-2.0-flash"})
        mock_process = _make_mock_process(stdout_lines=GEMINI_STANDARD_STDOUT)

        with patch("prompter.runner.gemini.subprocess.Popen",
                   return_value=mock_process) as mock_popen:
            runner.run_prompt("test", 2400)

        cmd = mock_popen.call_args[0][0]
        assert "-m" in cmd
        idx = cmd.index("-m")
        assert cmd[idx + 1] == "gemini-2.0-flash"

    # ── TC-01-G: session chaining ─────────────────────────────────────

    def test_gemini_session(self) -> None:
        """GEXE-07: first without --resume, second with --resume gem-123."""
        runner = GeminiRunner({})

        mock_process1 = _make_mock_process(stdout_lines=GEMINI_STANDARD_STDOUT)
        with patch("prompter.runner.gemini.subprocess.Popen",
                   return_value=mock_process1) as mock_popen1:
            runner.run_prompt("first", 2400)

        cmd1 = mock_popen1.call_args[0][0]
        assert "--resume" not in cmd1

        mock_process2 = _make_mock_process(stdout_lines=GEMINI_STANDARD_STDOUT)
        with patch("prompter.runner.gemini.subprocess.Popen",
                   return_value=mock_process2) as mock_popen2:
            runner.run_prompt("second", 2400)

        cmd2 = mock_popen2.call_args[0][0]
        assert "--resume" in cmd2
        idx = cmd2.index("--resume")
        assert cmd2[idx + 1] == "gem-123"

    # ── TC-01-G: NDJSON stream processing ─────────────────────────────

    def test_gemini_stream_processing(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """GEXE-09: init→INFO, message→INFO, result→INFO+DEBUG."""
        events = _ndjson_lines(
            {"type": "init", "session_id": "gem-1"},
            {
                "type": "message",
                "role": "assistant",
                "content": "Hello from Gemini",
            },
            {
                "type": "result",
                "status": "success",
                "stats": {"duration_ms": 1200, "total_tokens": 100},
            },
        )

        runner = GeminiRunner({})
        mock_process = _make_mock_process(stdout_lines=events)

        with patch("prompter.runner.gemini.subprocess.Popen",
                   return_value=mock_process):
            with caplog.at_level("DEBUG", logger="prompter.runner.gemini"):
                result = runner.run_prompt("test", 2400)

        # init → INFO
        assert any(
            rec.levelname == "INFO" and "init:" in rec.message
            for rec in caplog.records
        )

        # assistant message → INFO
        assert any(
            rec.levelname == "INFO" and "Hello from Gemini" in rec.message
            for rec in caplog.records
        )

        # result summary → INFO
        assert any(
            rec.levelname == "INFO"
            and "result: success, 1200ms, tokens: 100" in rec.message
            for rec in caplog.records
        )

        # result raw → DEBUG
        assert any(
            rec.levelname == "DEBUG" and "result_raw:" in rec.message
            for rec in caplog.records
        )

        assert result is not None
        assert result["status"] == "success"

    def test_gemini_empty_events(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """GEXE-12: empty assistant message content is not logged."""
        events = _ndjson_lines(
            {"type": "init", "session_id": "gem-1"},
            {"type": "message", "role": "assistant", "content": ""},
            {"type": "message", "role": "assistant", "content": "Real"},
            GEMINI_RESULT_EVENT,
        )

        runner = GeminiRunner({})
        mock_process = _make_mock_process(stdout_lines=events)

        with patch("prompter.runner.gemini.subprocess.Popen",
                   return_value=mock_process):
            with caplog.at_level("INFO", logger="prompter.runner.gemini"):
                runner.run_prompt("test", 2400)

        info_msgs = [
            rec.message
            for rec in caplog.records
            if rec.levelname == "INFO" and rec.name == "prompter.runner.gemini"
        ]
        assert any("Real" in m for m in info_msgs)
        assert all(m.strip() for m in info_msgs)

    # ── TC-AVAILABILITY-G: check_availability ─────────────────────────

    def test_gemini_available(self) -> None:
        """RUN-04: gemini in PATH → no error."""
        runner = GeminiRunner({})
        with patch("prompter.runner.gemini.shutil.which",
                   return_value="/usr/bin/gemini"):
            runner.check_availability()  # no exception

    def test_gemini_not_available(self) -> None:
        """RUN-04: gemini not in PATH → RuntimeError."""
        runner = GeminiRunner({})
        with patch("prompter.runner.gemini.shutil.which", return_value=None):
            with pytest.raises(RuntimeError, match="not found"):
                runner.check_availability()

    # ── TC-16-G: resume_hint ──────────────────────────────────────────

    def test_gemini_resume_hint_with_session(self) -> None:
        """RUN-05: resume_hint with session_id set."""
        runner = GeminiRunner({})
        runner._session_id = "gem-abc"
        hint = runner.resume_hint()
        assert hint is not None
        assert "gemini --resume gem-abc" in hint

    def test_gemini_resume_hint_without_session(self) -> None:
        """RUN-05: resume_hint with no session_id → None."""
        runner = GeminiRunner({})
        assert runner._session_id is None
        assert runner.resume_hint() is None

    # ── Deadline in _process_stream ───────────────────────────────────

    def test_gemini_deadline_in_process_stream(self) -> None:
        """ERR-01: deadline exceeded mid-stream → TimeoutExpired + kill."""
        events = _ndjson_lines(
            {"type": "init", "session_id": "gem-1"},
            {"type": "message", "role": "assistant", "content": "Hi"},
            GEMINI_RESULT_EVENT,
        )
        runner = GeminiRunner({})
        mock_process = _make_mock_process(stdout_lines=events)

        # monotonic: first call → 0.0 (deadline=10.0),
        # second call (1st line check) → 5.0,
        # third call (2nd line check) → 11.0 (exceeds deadline)
        with patch("prompter.runner.gemini.subprocess.Popen",
                   return_value=mock_process), \
             patch("prompter.runner.gemini.time.monotonic",
                   side_effect=[0.0, 5.0, 11.0]):
            with pytest.raises(subprocess.TimeoutExpired):
                runner.run_prompt("test", timeout=10)

        mock_process.kill.assert_called()
