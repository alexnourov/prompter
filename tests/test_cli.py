"""Tests for prompter.cli (INT-01..INT-04, TC-12..TC-22, ORC, ERR, LOG-08, REP, DOC-03)."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from prompter.cli import app, execution_loop
from prompter.models import Prompt, PromptResult, SessionIntegrityError, SigtermReceived

runner_cli = CliRunner()


# ─── Helpers ───────────────────────────────────────────────────────────────

def _make_runner(side_effects: list | None = None) -> MagicMock:
    """Create a mock AssistantRunner with controlled run_prompt behavior."""
    mock = MagicMock()
    mock.supports_session = True
    mock.check_availability.return_value = None
    mock.resume_hint.return_value = None
    if side_effects is not None:
        mock.run_prompt.side_effect = side_effects
    else:
        mock.run_prompt.return_value = {"assistant_response": "ok"}
    return mock


def _invoke_main(
    tmp_path: Path,
    mock_runner: MagicMock,
    prompts: list[Prompt],
    *,
    extra_args: list[str] | None = None,
    settings: dict | None = None,
    config_dir: Path | None = None,
) -> tuple:
    """Invoke main() via CliRunner with standard mocks.

    Returns (result, output_path).
    """
    input_file = tmp_path / "prompts.txt"
    input_file.write_text("placeholder\n")
    output = tmp_path / "report.json"
    args = [str(input_file), "-o", str(output)]
    if extra_args:
        args.extend(extra_args)

    with (
        patch("prompter.cli.prepare_prompts", return_value=prompts),
        patch("prompter.cli.create_runner", return_value=mock_runner),
        patch("prompter.cli.find_config_dir", return_value=config_dir),
        patch("prompter.cli.load_settings", return_value=settings or {}),
        patch("prompter.cli.setup_logging"),
    ):
        result = runner_cli.invoke(app, args)

    return result, output


TWO_PROMPTS = [Prompt("First", "body1"), Prompt("Second", "body2")]
FOUR_PROMPTS = [
    Prompt("P1", "body1"),
    Prompt("P2", "body2"),
    Prompt("P3", "body3"),
    Prompt("P4", "body4"),
]


# ─── Interrupt tests ──────────────────────────────────────────────────────

class TestInterrupt:
    """Interrupt scenarios (INT-01..INT-03)."""

    def test_interrupt_repeat(self, tmp_path: Path) -> None:
        """INT-01: KeyboardInterrupt → 'R' → repeat same prompt (TC-10)."""
        output = tmp_path / "report.json"
        call_count = 0

        def run_prompt_side_effect(prompt, timeout):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise KeyboardInterrupt
            return {"assistant_response": "ok"}

        mock_runner = _make_runner()
        mock_runner.run_prompt.side_effect = run_prompt_side_effect

        with patch("prompter.cli.input", return_value="R"):
            code = execution_loop([Prompt("Only", "body")], mock_runner, 60, output)

        assert code == 0
        assert mock_runner.run_prompt.call_count == 2

        report = json.loads(output.read_text())
        assert len(report) == 1
        assert report[0]["status"] == "success"

    def test_interrupt_next(self, tmp_path: Path) -> None:
        """INT-02: KeyboardInterrupt → 'N' → skip prompt, next continues (TC-11)."""
        output = tmp_path / "report.json"

        mock_runner = _make_runner(
            [KeyboardInterrupt, {"assistant_response": "ok"}]
        )

        with patch("prompter.cli.input", return_value="N"):
            code = execution_loop(TWO_PROMPTS, mock_runner, 60, output)

        assert code == 0

        report = json.loads(output.read_text())
        assert len(report) == 2
        assert report[0]["status"] == "skipped"
        assert report[1]["status"] == "success"

    def test_interrupt_exit(self, tmp_path: Path) -> None:
        """INT-03: KeyboardInterrupt → 'E' → stop, error entry in report (TC-12)."""
        output = tmp_path / "report.json"

        mock_runner = _make_runner([KeyboardInterrupt])

        with patch("prompter.cli.input", return_value="E"):
            code = execution_loop(TWO_PROMPTS, mock_runner, 60, output)

        assert code == 0

        report = json.loads(output.read_text())
        assert len(report) == 1
        assert report[0]["status"] == "error"
        assert report[0]["error"] == "Interrupted by user"

    def test_interrupt_invalid_then_repeat(self, tmp_path: Path) -> None:
        """INT-01: invalid input ignored, then 'R' accepted (TC-10)."""
        output = tmp_path / "report.json"
        call_count = 0

        def run_prompt_side_effect(prompt, timeout):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise KeyboardInterrupt
            return {"assistant_response": "ok"}

        mock_runner = _make_runner()
        mock_runner.run_prompt.side_effect = run_prompt_side_effect

        with patch("prompter.cli.input", side_effect=["X", "R"]):
            code = execution_loop([Prompt("Only", "body")], mock_runner, 60, output)

        assert code == 0
        assert mock_runner.run_prompt.call_count == 2

    def test_interrupt_next_first_prompt_new_session(self, tmp_path: Path) -> None:
        """INT-02: skip 1st prompt → 2nd still succeeds, exit code 0."""
        output = tmp_path / "report.json"

        mock_runner = _make_runner(
            [KeyboardInterrupt, {"assistant_response": "second ok"}]
        )

        with patch("prompter.cli.input", return_value="N"):
            code = execution_loop(TWO_PROMPTS, mock_runner, 60, output)

        assert code == 0

        report = json.loads(output.read_text())
        assert len(report) == 2
        assert report[0]["status"] == "skipped"
        assert report[1]["status"] == "success"


# ─── SIGTERM tests ─────────────────────────────────────────────────────────

class TestSigterm:
    """SIGTERM scenarios (INT-04)."""

    def test_sigterm_graceful_termination(self, tmp_path: Path) -> None:
        """INT-04: SigtermReceived → error entry, exit code 143 (TC-13)."""
        output = tmp_path / "report.json"

        mock_runner = _make_runner([SigtermReceived()])

        code = execution_loop(TWO_PROMPTS, mock_runner, 60, output)

        assert code == 143

        report = json.loads(output.read_text())
        assert len(report) == 1
        assert report[0]["status"] == "error"
        assert report[0]["error"] == "Terminated by SIGTERM"

    def test_interrupt_repeated_sigint(self, tmp_path: Path) -> None:
        """KeyboardInterrupt during input() → exit code 130, no report."""
        input_file = tmp_path / "prompts.txt"
        input_file.write_text("prompt body\n")
        output = tmp_path / "report.json"

        mock_runner = _make_runner([KeyboardInterrupt])

        with (
            patch("prompter.cli.prepare_prompts", return_value=TWO_PROMPTS),
            patch("prompter.cli.create_runner", return_value=mock_runner),
            patch("prompter.cli.find_config_dir", return_value=None),
            patch("prompter.cli.load_settings", return_value={}),
            patch("prompter.cli.setup_logging"),
            patch("prompter.cli.input", side_effect=KeyboardInterrupt),
        ):
            result = runner_cli.invoke(
                app, [str(input_file), "-o", str(output)]
            )

        assert result.exit_code == 130
        assert not output.exists()


# ─── Session & logging tests ─────────────────────────────────────────────

class TestSession:
    """Session-related scenarios (ORC-02, ORC-08, LOG-08)."""

    def test_session_id_logged(self, tmp_path: Path) -> None:
        """ORC-02: runner logs 'session: ...' before each prompt."""
        from prompter.runner.base import AssistantRunner

        class _StubRunner(AssistantRunner):
            supports_session = True

            def check_availability(self):
                pass

            def resume_hint(self):
                return None

            def _execute_prompt(self, prompt, timeout):
                return {"result": "ok"}, "sess_test"

        stub = _StubRunner({})

        with patch("prompter.runner.base.logger") as mock_base_logger:
            result, output = _invoke_main(tmp_path, stub, TWO_PROMPTS)

        assert result.exit_code == 0

        session_calls = [
            c for c in mock_base_logger.info.call_args_list
            if len(c.args) >= 1 and "session" in str(c.args[0])
        ]
        assert len(session_calls) == 2

    def test_session_restore_command_logged(self, tmp_path: Path) -> None:
        """LOG-08: resume_hint logged after report save."""
        mock_runner = _make_runner()
        mock_runner.resume_hint.return_value = (
            "To continue this session interactively, run: claude --resume sess_abc"
        )

        with patch("prompter.cli.logger") as mock_logger:
            result, output = _invoke_main(
                tmp_path, mock_runner, [Prompt("Only", "body")]
            )

        assert result.exit_code == 0
        info_messages = [
            str(c) for c in mock_logger.info.call_args_list
        ]
        assert any("claude --resume sess_abc" in m for m in info_messages)

    def test_session_restore_command_not_logged_without_session(
        self, tmp_path: Path
    ) -> None:
        """LOG-08: resume_hint not logged when None."""
        mock_runner = _make_runner(
            [SessionIntegrityError("No session_id received from first prompt")]
        )
        mock_runner.resume_hint.return_value = None

        with patch("prompter.cli.logger") as mock_logger:
            result, output = _invoke_main(
                tmp_path, mock_runner, [Prompt("Only", "body")]
            )

        assert result.exit_code == 1
        info_messages = " ".join(
            str(c) for c in mock_logger.info.call_args_list
        )
        assert "claude --resume" not in info_messages

    def test_fatal_error_session_integrity(self, tmp_path: Path) -> None:
        """ORC-08: SessionIntegrityError → exit 1, 1 error entry (TC-14)."""
        mock_runner = _make_runner(
            [SessionIntegrityError("No session_id received from first prompt")]
        )

        with patch("prompter.cli.logger") as mock_logger:
            result, output = _invoke_main(
                tmp_path, mock_runner, TWO_PROMPTS
            )

        assert result.exit_code == 1
        assert mock_runner.run_prompt.call_count == 1

        error_calls = [
            str(c) for c in mock_logger.error.call_args_list
        ]
        assert any("No session_id" in m for m in error_calls)

        report = json.loads(output.read_text())
        assert len(report) == 1
        assert report[0]["status"] == "error"
        assert "No session_id" in report[0]["error"]

    def test_session_integrity_lost_session_id(self, tmp_path: Path) -> None:
        """ORC-06: lost session_id on 2nd prompt → exit 1, 2 entries."""
        mock_runner = _make_runner([
            {"result": "ok"},
            SessionIntegrityError(
                "Session integrity error: no session_id received"
            ),
        ])

        with patch("prompter.cli.logger") as mock_logger:
            result, output = _invoke_main(
                tmp_path, mock_runner,
                [Prompt("P1", "b1"), Prompt("P2", "b2"), Prompt("P3", "b3")],
            )

        assert result.exit_code == 1
        assert mock_runner.run_prompt.call_count == 2

        error_calls = " ".join(str(c) for c in mock_logger.error.call_args_list)
        assert "no session_id received" in error_calls

        report = json.loads(output.read_text())
        assert len(report) == 2
        assert report[0]["status"] == "success"
        assert report[1]["status"] == "error"

    def test_session_integrity_changed_session_id(self, tmp_path: Path) -> None:
        """ORC-07: changed session_id → exit 1, 2 entries."""
        mock_runner = _make_runner([
            {"result": "ok"},
            SessionIntegrityError(
                "Session integrity error: session_id changed "
                "from 'sess_abc' to 'sess_xyz'"
            ),
        ])

        with patch("prompter.cli.logger") as mock_logger:
            result, output = _invoke_main(
                tmp_path, mock_runner,
                [Prompt("P1", "b1"), Prompt("P2", "b2"), Prompt("P3", "b3")],
            )

        assert result.exit_code == 1
        assert mock_runner.run_prompt.call_count == 2

        error_calls = " ".join(str(c) for c in mock_logger.error.call_args_list)
        assert "sess_abc" in error_calls
        assert "sess_xyz" in error_calls

        report = json.loads(output.read_text())
        assert len(report) == 2
        assert report[0]["status"] == "success"
        assert report[1]["status"] == "error"


# ─── Error-recovery tests ────────────────────────────────────────────────

class TestErrorRecovery:
    """ERR-01..ERR-09: errors and timeouts don't stop execution."""

    def test_error_and_timeout_do_not_stop_execution(
        self, tmp_path: Path
    ) -> None:
        """ERR-06/ERR-01: error and timeout → continue to next prompt."""
        mock_runner = _make_runner([
            {"result": "ok"},
            Exception("fail"),
            subprocess.TimeoutExpired("cmd", 60),
            {"result": "ok2"},
        ])

        with patch("prompter.cli.logger") as mock_logger:
            result, output = _invoke_main(
                tmp_path, mock_runner, FOUR_PROMPTS
            )

        assert result.exit_code == 0

        error_calls = [str(c) for c in mock_logger.error.call_args_list]
        assert len(error_calls) == 2

        report = json.loads(output.read_text())
        assert len(report) == 4
        assert report[0]["status"] == "success"
        assert report[1]["status"] == "error"
        assert "error" in report[1]
        assert report[2]["status"] == "timeout"
        assert "error" in report[2]
        assert report[3]["status"] == "success"


# ─── Availability tests ──────────────────────────────────────────────────

class TestAvailability:
    """ORC-09: assistant availability checks."""

    def test_assistant_not_available(self, tmp_path: Path) -> None:
        """ORC-09: check_availability raises → exit 1, run_prompt not called."""
        mock_runner = _make_runner()
        mock_runner.check_availability.side_effect = RuntimeError(
            "claude CLI not found in $PATH"
        )

        with patch("prompter.cli.logger") as mock_logger:
            result, output = _invoke_main(
                tmp_path, mock_runner, [Prompt("Only", "body")]
            )

        assert result.exit_code == 1
        mock_runner.run_prompt.assert_not_called()

        error_calls = " ".join(str(c) for c in mock_logger.error.call_args_list)
        assert "claude CLI not found" in error_calls

    def test_exception_before_execution_loop(self, tmp_path: Path) -> None:
        """ERR-10: prepare_prompts failure → exit 1, no traceback."""
        input_file = tmp_path / "prompts.txt"
        input_file.write_text("placeholder\n")
        output = tmp_path / "report.json"

        mock_runner = _make_runner()

        with (
            patch(
                "prompter.cli.prepare_prompts",
                side_effect=RuntimeError("parse failure"),
            ),
            patch("prompter.cli.create_runner", return_value=mock_runner),
            patch("prompter.cli.find_config_dir", return_value=None),
            patch("prompter.cli.load_settings", return_value={}),
            patch("prompter.cli.setup_logging"),
            patch("prompter.cli.logger") as mock_logger,
        ):
            result = runner_cli.invoke(app, [str(input_file), "-o", str(output)])

        assert result.exit_code == 1
        assert "Traceback" not in (result.output or "")
        mock_runner.run_prompt.assert_not_called()

        error_calls = " ".join(str(c) for c in mock_logger.error.call_args_list)
        assert "parse failure" in error_calls


# ─── Report tests ────────────────────────────────────────────────────────

class TestReport:
    """REP-01..REP-06: report structure and formatting."""

    def test_report_structure(self, tmp_path: Path) -> None:
        """REP-01..REP-06: all 4 statuses, correct fields and format."""
        mock_runner = _make_runner([
            {"result": "ok"},
            KeyboardInterrupt,
            Exception("some error"),
            subprocess.TimeoutExpired("cmd", 60),
        ])

        with (
            patch("prompter.cli.input", return_value="N"),
        ):
            result, output = _invoke_main(
                tmp_path, mock_runner, FOUR_PROMPTS
            )

        assert result.exit_code == 0

        report = json.loads(output.read_text())
        assert isinstance(report, list)
        assert len(report) == 4

        iso_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")
        valid_statuses = {"success", "skipped", "error", "timeout"}

        for entry in report:
            assert isinstance(entry["prompt"], str)
            assert "assistant_response" in entry
            assert iso_pattern.match(entry["timestamp"]), (
                f"Bad timestamp: {entry['timestamp']}"
            )
            assert entry["status"] in valid_statuses

        assert report[0]["status"] == "success"
        assert "error" not in report[0]

        assert report[1]["status"] == "skipped"
        assert "error" not in report[1]

        assert report[2]["status"] == "error"
        assert "error" in report[2]

        assert report[3]["status"] == "timeout"
        assert "error" in report[3]

    def test_report_overwrite_warning(self, tmp_path: Path) -> None:
        """REP-02: existing file → overwritten with warning."""
        output = tmp_path / "report.json"
        output.write_text('["old data"]')

        mock_runner = _make_runner()

        with patch("prompter.report.logger") as mock_report_logger:
            result, _ = _invoke_main(tmp_path, mock_runner, [Prompt("Only", "b")])

        assert result.exit_code == 0

        report = json.loads(output.read_text())
        assert len(report) == 1
        assert report[0]["status"] == "success"

        warning_calls = " ".join(
            str(c) for c in mock_report_logger.warning.call_args_list
        )
        assert "already exists" in warning_calls


# ─── DOC-03 / user messages ─────────────────────────────────────────────

class TestUserMessages:
    """DOC-03: user-facing messages in English (ASCII)."""

    def test_user_messages_english(self, tmp_path: Path) -> None:
        """DOC-03: print/input strings contain only ASCII (TC-15)."""
        output = tmp_path / "report.json"
        mock_runner = _make_runner([KeyboardInterrupt])

        captured_prints: list[str] = []
        captured_inputs: list[str] = []

        original_input = None

        def fake_input(prompt=""):
            captured_inputs.append(prompt)
            return "E"

        with (
            patch("prompter.cli.input", side_effect=fake_input),
            patch("builtins.print", side_effect=lambda *a, **kw: captured_prints.append(
                " ".join(str(x) for x in a)
            )),
        ):
            execution_loop([Prompt("Only", "body")], mock_runner, 60, output)

        cyrillic = re.compile(r"[\u0400-\u04FF]")
        for text in captured_prints + captured_inputs:
            assert not cyrillic.search(text), f"Cyrillic found: {text!r}"


# ─── Assistant selection tests ───────────────────────────────────────────

class TestAssistantSelection:
    """CLI-07: --assistant flag and settings priority."""

    def test_create_runner_via_main(self, tmp_path: Path) -> None:
        """CLI-07: default assistant is 'claude'."""
        input_file = tmp_path / "prompts.txt"
        input_file.write_text("placeholder\n")
        output = tmp_path / "report.json"
        mock_runner = _make_runner()

        with (
            patch("prompter.cli.prepare_prompts", return_value=[Prompt("P", "b")]),
            patch("prompter.cli.create_runner", return_value=mock_runner) as mock_create,
            patch("prompter.cli.find_config_dir", return_value=None),
            patch("prompter.cli.load_settings", return_value={}),
            patch("prompter.cli.setup_logging"),
        ):
            result = runner_cli.invoke(
                app, [str(input_file), "-o", str(output)]
            )

        assert result.exit_code == 0
        mock_create.assert_called_once()
        assert mock_create.call_args[0][0] == "claude"

    def test_unknown_assistant_exits_with_error(self, tmp_path: Path) -> None:
        """CLI-07: unknown assistant → exit 1."""
        input_file = tmp_path / "prompts.txt"
        input_file.write_text("placeholder\n")
        output = tmp_path / "report.json"

        with (
            patch("prompter.cli.prepare_prompts", return_value=[Prompt("P", "b")]),
            patch(
                "prompter.cli.create_runner",
                side_effect=ValueError("Unknown assistant: 'unknown'"),
            ),
            patch("prompter.cli.find_config_dir", return_value=None),
            patch("prompter.cli.load_settings", return_value={}),
            patch("prompter.cli.setup_logging"),
        ):
            result = runner_cli.invoke(
                app,
                [str(input_file), "-o", str(output), "--assistant", "unknown"],
            )

        assert result.exit_code == 1

    def test_assistant_flag_explicit(self, tmp_path: Path) -> None:
        """CLI-07: --assistant gemini → create_runner('gemini', ...)."""
        input_file = tmp_path / "prompts.txt"
        input_file.write_text("placeholder\n")
        output = tmp_path / "report.json"
        mock_runner = _make_runner()

        with (
            patch("prompter.cli.prepare_prompts", return_value=[Prompt("P", "b")]),
            patch("prompter.cli.create_runner", return_value=mock_runner) as mock_create,
            patch("prompter.cli.find_config_dir", return_value=None),
            patch("prompter.cli.load_settings", return_value={}),
            patch("prompter.cli.setup_logging"),
        ):
            result = runner_cli.invoke(
                app,
                [str(input_file), "-o", str(output), "--assistant", "gemini"],
            )

        assert result.exit_code == 0
        assert mock_create.call_args[0][0] == "gemini"

    def test_assistant_from_settings(self, tmp_path: Path) -> None:
        """CLI-07: settings.json assistant → used when no CLI flag."""
        input_file = tmp_path / "prompts.txt"
        input_file.write_text("placeholder\n")
        output = tmp_path / "report.json"
        mock_runner = _make_runner()

        with (
            patch("prompter.cli.prepare_prompts", return_value=[Prompt("P", "b")]),
            patch("prompter.cli.create_runner", return_value=mock_runner) as mock_create,
            patch("prompter.cli.find_config_dir", return_value=tmp_path),
            patch(
                "prompter.cli.load_settings",
                return_value={"assistant": "gemini"},
            ),
            patch("prompter.cli.setup_logging"),
        ):
            result = runner_cli.invoke(
                app, [str(input_file), "-o", str(output)]
            )

        assert result.exit_code == 0
        assert mock_create.call_args[0][0] == "gemini"

    def test_assistant_cli_overrides_settings(self, tmp_path: Path) -> None:
        """CLI-07: CLI flag overrides settings.json."""
        input_file = tmp_path / "prompts.txt"
        input_file.write_text("placeholder\n")
        output = tmp_path / "report.json"
        mock_runner = _make_runner()

        with (
            patch("prompter.cli.prepare_prompts", return_value=[Prompt("P", "b")]),
            patch("prompter.cli.create_runner", return_value=mock_runner) as mock_create,
            patch("prompter.cli.find_config_dir", return_value=None),
            patch(
                "prompter.cli.load_settings",
                return_value={"assistant": "gemini"},
            ),
            patch("prompter.cli.setup_logging"),
        ):
            result = runner_cli.invoke(
                app,
                [str(input_file), "-o", str(output), "--assistant", "claude"],
            )

        assert result.exit_code == 0
        assert mock_create.call_args[0][0] == "claude"
