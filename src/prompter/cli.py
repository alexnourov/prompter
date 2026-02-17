"""CLI module: Typer app, execution loop, helpers (CLI-01..CLI-07, ORC-01, INT-01..INT-04, ERR-01..ERR-11)."""

from __future__ import annotations

import logging
import signal
from datetime import datetime
from pathlib import Path
from subprocess import TimeoutExpired
from typing import Optional

import typer

from .config import find_config_dir, load_settings, merge_config
from .log import setup_logging
from .models import Prompt, PromptResult, SessionIntegrityError, SigtermReceived
from .preparer import prepare_prompts
from .report import save_report
from .runner import create_runner
from .runner.base import AssistantRunner

logger = logging.getLogger(__name__)

app = typer.Typer()


# ─── Helpers ──────────────────────────────────────────────────────────────

def _now_iso() -> str:
    """Current time in ISO 8601: YYYY-MM-DDTHH:MM:SS (REP-04).

    No microseconds, no timezone.
    """
    return datetime.now().replace(microsecond=0).isoformat()


def _sigterm_handler(signum, frame):
    """SIGTERM signal handler (INT-04)."""
    raise SigtermReceived()


def _version_callback(value: bool) -> None:
    """Eager callback for --version (CLI-02).

    Executes before mandatory argument validation,
    allowing ``prompter --version`` without input_file.
    """
    if value:
        from prompter import __version__

        print(__version__)
        raise typer.Exit()


# ─── Execution loop ──────────────────────────────────────────────────────

def execution_loop(
    prompts: list[Prompt],
    runner: AssistantRunner,
    timeout: int,
    output_path: Path,
) -> int:
    """Execute prompts sequentially and save report (ORC-01).

    Returns:
        Exit code: 0 = success, 1 = fatal error, 143 = SIGTERM (ERR-11).
    """
    if not prompts:  # INP-05
        logger.warning("No prompts found in input file")
        save_report([], output_path)
        return 0

    results: list[PromptResult] = []
    exit_code = 0  # ERR-11
    i = 0

    while i < len(prompts):
        p = prompts[i]

        try:
            result_obj = runner.run_prompt(p.body, timeout)
            results.append(
                PromptResult(p.body, p.title, result_obj, _now_iso(), "success")
            )
            i += 1

        except SessionIntegrityError as e:  # ORC-08
            logger.error(str(e))
            results.append(
                PromptResult(
                    p.body, p.title, None, _now_iso(), "error", error=str(e)
                )
            )
            exit_code = 1
            break

        except TimeoutExpired:  # ERR-01
            logger.error("Timeout on prompt %d", i + 1)
            results.append(
                PromptResult(
                    p.body, p.title, None, _now_iso(), "timeout",
                    error=f"Timeout after {timeout}s",
                )
            )
            i += 1

        except KeyboardInterrupt:  # INT-01, INT-02, INT-03
            while True:
                choice = input("(R)epeat / (N)ext / (E)xit? ").strip().upper()
                if choice in ("R", "N", "E"):
                    break
            if choice == "R":
                continue  # same i
            elif choice == "N":
                results.append(
                    PromptResult(
                        p.body, p.title, None, _now_iso(), "skipped"
                    )
                )
                i += 1
            elif choice == "E":
                results.append(
                    PromptResult(
                        p.body, p.title, None, _now_iso(), "error",
                        error="Interrupted by user",
                    )
                )
                break

        except SigtermReceived:  # INT-04
            logger.error("SIGTERM received, terminating")
            results.append(
                PromptResult(
                    p.body, p.title, None, _now_iso(), "error",
                    error="Terminated by SIGTERM",
                )
            )
            exit_code = 143
            break

        except Exception as e:  # ERR-06
            logger.error("Error on prompt %d: %s", i + 1, e)
            results.append(
                PromptResult(
                    p.body, p.title, None, _now_iso(), "error", error=str(e)
                )
            )
            i += 1

    # REP-01, REP-02
    try:
        save_report(results, output_path)
    except SigtermReceived:
        logger.error("SIGTERM received during report save")
        save_report(results, output_path)
        exit_code = 143 if exit_code == 0 else exit_code

    # LOG-08: resume hint
    hint = runner.resume_hint()
    if hint:
        logger.info(hint)

    return exit_code


# ─── Main command ─────────────────────────────────────────────────────────

@app.command()
def main(
    input_file: Path = typer.Argument(exists=True),
    output: Optional[Path] = typer.Option(None, "-o", "--output"),
    verbose: Optional[bool] = typer.Option(None, "-v", "--verbose"),
    app_name: str = typer.Option("prompter", "--app-name"),
    config: Optional[Path] = typer.Option(None, "-c", "--config"),
    timeout: Optional[int] = typer.Option(None, "--timeout", "-t", min=10),
    source_encoding: Optional[str] = typer.Option(None, "--source-encoding"),
    assistant: Optional[str] = typer.Option(None, "--assistant"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True
    ),
) -> None:
    """Prompter — batch prompt execution for AI assistants (CLI-01)."""
    try:
        # INT-04: register SIGTERM handler
        signal.signal(signal.SIGTERM, _sigterm_handler)

        # CFG-01..CFG-05: locate config directory
        config_dir = find_config_dir(app_name, config)

        # CFG-06: load settings
        settings = load_settings(config_dir) if config_dir is not None else {}

        # CFG-07: merge configuration
        cli_args = {
            "output": str(output) if output is not None else None,
            "verbose": verbose,
            "timeout": timeout,
            "source_encoding": source_encoding,
            "assistant": assistant,
        }
        defaults = {
            "output": "report.json",
            "verbose": False,
            "timeout": 2400,
            "source_encoding": None,
            "assistant": "claude",
        }
        effective = merge_config(cli_args, settings, defaults)
        effective["output"] = Path(effective["output"])

        # LOG-01..LOG-06: setup logging
        setup_logging(config_dir, effective["verbose"])

        # INP-01..INP-06, PRE-01..PRE-05: parse prompts
        prompts = prepare_prompts(input_file, effective["source_encoding"])

        # CLI-06: dry-run mode
        if dry_run:
            for idx, p in enumerate(prompts, 1):
                print(f"{idx}. {p.title}")
            raise typer.Exit(code=0)

        # RUN-02, ORC-09: create runner and check availability
        assistant_name = effective["assistant"]
        assistant_config = settings.get(assistant_name, {})
        runner = create_runner(assistant_name, assistant_config)

        try:
            runner.check_availability()
        except RuntimeError as e:
            logger.error(str(e))
            raise typer.Exit(code=1)

        # ORC-01: execution loop
        exit_code = execution_loop(
            prompts, runner, effective["timeout"], effective["output"]
        )
        if exit_code != 0:
            raise typer.Exit(code=exit_code)

    except typer.Exit:
        raise
    except SystemExit:
        raise
    except SigtermReceived:  # INT-04: SIGTERM outside execution_loop
        raise typer.Exit(code=143)
    except KeyboardInterrupt:  # ERR-10, ERR-11
        raise typer.Exit(code=130)
    except Exception as e:  # ERR-10
        logger.error("Fatal error: %s", e)
        raise typer.Exit(code=1)
