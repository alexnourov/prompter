"""CLI application for Prompter.

This module implements the main command-line interface and execution loop
for automated Claude CLI interactions.
"""

import logging
import shutil
import signal
from datetime import datetime
from pathlib import Path
from subprocess import TimeoutExpired

import typer

from .config import find_config_dir, load_settings, merge_config
from .log import setup_logging
from .models import PromptResult, SigtermReceived
from .preparer import prepare_prompts
from .report import save_report
from .runner import run_prompt

logger = logging.getLogger(__name__)

# Typer application instance (CLI-03)
app = typer.Typer()


def _sigterm_handler(signum: int, frame) -> None:
    """Signal handler for SIGTERM (INT-04).

    Raises SigtermReceived exception to trigger graceful shutdown.
    """
    raise SigtermReceived()


def _version_callback(value: bool) -> None:
    """Eager callback for --version flag (CLI-02).

    Executed before validation of required arguments,
    allowing `prompter --version` without input_file.

    Args:
        value: True if --version was provided

    Raises:
        typer.Exit: Always exits after printing version
    """
    if value:
        from . import __version__

        print(__version__)
        raise typer.Exit()


def _now_iso() -> str:
    """Get current timestamp in ISO 8601 format.

    Format: YYYY-MM-DDTHH:MM:SS (REP-04)
    - No microseconds
    - No timezone

    Returns:
        ISO 8601 timestamp string
    """
    return datetime.now().replace(microsecond=0).isoformat()


def execution_loop(
    prompts: list[str],
    output_path: Path,
    timeout: int,
) -> int:
    """Execute prompts sequentially through Claude CLI.

    Main execution loop implementing the orchestration logic (ORC-01..ORC-08).
    Handles:
    - Session management (ORC-02, ORC-03, ORC-04)
    - Error handling (ERR-01, ERR-06)
    - Signal handling (INT-01..INT-04)
    - Result collection and report generation (REP-01, REP-02)

    Args:
        prompts: List of prompts to execute
        output_path: Path where to save the report
        timeout: Timeout in seconds for each prompt

    Returns:
        Exit code: 0 for success, 1 for fatal error, 143 for SIGTERM (ERR-11)

    Interactive prompts (INT-01, INT-02, INT-03):
    - On KeyboardInterrupt (Ctrl+C):
      - (R)epeat: retry current prompt
      - (N)ext: skip current prompt, mark as "skipped"
      - (E)xit: stop execution, mark current as "error"
    """
    # Handle empty prompts list (INP-05)
    if not prompts:
        logger.warning("No prompts found in input file")
        save_report([], output_path)
        return 0

    results: list[PromptResult] = []
    session_id: str | None = None
    exit_code = 0  # ERR-11: default to success
    i = 0

    while i < len(prompts):
        prompt = prompts[i]
        logger.info(f"session: {session_id or 'new'}")  # ORC-02

        try:
            # Execute prompt (EXE-01..12)
            result_obj, new_session_id = run_prompt(prompt, session_id, timeout)

            # Check session integrity (ORC-03, ORC-04)
            if session_id is None and new_session_id is None:
                # First prompt didn't establish session (ORC-03)
                logger.error("No session_id received")
                results.append(
                    PromptResult(
                        prompt, result_obj, _now_iso(), "error", error="No session_id received"
                    )
                )
                exit_code = 1  # ERR-11: fatal error
                break

            if session_id is not None:
                # Subsequent prompts must maintain session (ORC-04)
                if new_session_id is None:
                    logger.error(f"No session_id in response for prompt {i + 1}")
                    results.append(
                        PromptResult(
                            prompt,
                            result_obj,
                            _now_iso(),
                            "error",
                            error="Session integrity error: no session_id received",
                        )
                    )
                    exit_code = 1  # ERR-11: fatal error
                    break

                if new_session_id != session_id:
                    logger.error(
                        f"session_id changed: expected {session_id}, got {new_session_id}"
                    )
                    results.append(
                        PromptResult(
                            prompt,
                            result_obj,
                            _now_iso(),
                            "error",
                            error=f"Session integrity error: session_id changed from {session_id} to {new_session_id}",
                        )
                    )
                    exit_code = 1  # ERR-11: fatal error
                    break

            # Update session and record success
            session_id = new_session_id
            results.append(PromptResult(prompt, result_obj, _now_iso(), "success"))
            i += 1

        except TimeoutExpired:
            # Timeout handling (ERR-01)
            # Note: run_prompt already killed the process
            logger.error(f"Timeout on prompt {i + 1}")
            results.append(
                PromptResult(
                    prompt, None, _now_iso(), "timeout", error=f"Timeout after {timeout}s"
                )
            )
            i += 1

        except KeyboardInterrupt:
            # Interactive interruption (INT-01, INT-02, INT-03)
            while True:
                choice = input("(R)epeat / (N)ext / (E)xit? ").strip().upper()
                if choice in ("R", "N", "E"):
                    break

            if choice == "R":
                # Repeat: don't increment i
                continue
            elif choice == "N":
                # Next: skip current prompt
                results.append(PromptResult(prompt, None, _now_iso(), "skipped"))
                i += 1
            elif choice == "E":
                # Exit: stop execution
                results.append(
                    PromptResult(
                        prompt, None, _now_iso(), "error", error="Interrupted by user"
                    )
                )
                break

        except SigtermReceived:
            # SIGTERM handling (INT-04)
            logger.error("SIGTERM received, terminating")
            results.append(
                PromptResult(prompt, None, _now_iso(), "error", error="Terminated by SIGTERM")
            )
            exit_code = 143  # Standard exit code for SIGTERM
            break

        except Exception as e:
            # Generic error handling (ERR-06)
            logger.error(f"Error on prompt {i + 1}: {e}")
            results.append(PromptResult(prompt, None, _now_iso(), "error", error=str(e)))
            i += 1

    # Save report (REP-01, REP-02)
    try:
        save_report(results, output_path)
    except SigtermReceived:
        # Handle SIGTERM during report save
        logger.error("SIGTERM received during report save")
        save_report(results, output_path)  # Retry save
        exit_code = 143 if exit_code == 0 else exit_code

    # Log session resumption command (LOG-08)
    if session_id is not None:
        logger.info(f"To continue this session interactively, run: claude --resume {session_id}")

    return exit_code  # ERR-11


@app.command()
def main(
    input_file: Path = typer.Argument(..., exists=True, help="Path to prompts file"),
    output: Path | None = typer.Option(None, "-o", "--output", help="Output report path"),
    verbose: bool | None = typer.Option(None, "-v", "--verbose", help="Enable verbose logging"),
    app_name: str = typer.Option("prompter", "--app-name", help="Application name for config"),
    config: Path | None = typer.Option(None, "-c", "--config", help="Config directory path"),
    timeout: int | None = typer.Option(
        None, "-t", "--timeout", min=10, help="Timeout per prompt in seconds"
    ),
    source_encoding: str | None = typer.Option(
        None, "--source-encoding", help="Source file encoding (default: auto-detect)"
    ),
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True, help="Show version"
    ),
) -> None:
    """Prompter - Automated Claude CLI interaction tool.

    Execute prompts from INPUT_FILE sequentially through Claude CLI,
    maintaining session context and generating execution reports.

    Requirements:
    - CLI-01: Typer-based CLI
    - CLI-02: --version flag (eager callback)
    - CLI-03: Mandatory Typer usage
    - CLI-04: Positional input_file argument
    - CLI-05: Optional parameters with defaults
    - CFG-01: Configuration system integration
    - ERR-10: Graceful error handling
    - INT-04: SIGTERM handling
    - ORC-09: Claude CLI availability check
    """
    try:
        # Register SIGTERM handler (INT-04)
        signal.signal(signal.SIGTERM, _sigterm_handler)

        # Configuration setup (CFG-01, CFG-02, CFG-07)
        config_dir = find_config_dir(app_name, config)

        # Load settings from settings.json if config_dir exists
        settings = load_settings(config_dir) if config_dir is not None else {}

        # Define defaults
        defaults = {
            "output": "report.json",
            "verbose": False,
            "timeout": 2400,
            "source_encoding": None,  # None = auto-detect (INP-03)
        }

        # Build CLI args dict (only non-None values are considered "explicitly provided")
        cli_args = {
            "output": str(output) if output is not None else None,
            "verbose": verbose,
            "timeout": timeout,
            "source_encoding": source_encoding,
        }

        # Merge configuration (CFG-07)
        effective = merge_config(cli_args, settings, defaults)

        # Convert output to Path after merge
        effective["output"] = Path(effective["output"])

        # Setup logging (LOG-01)
        setup_logging(config_dir, effective["verbose"])

        logger.info("Prompter started")
        logger.debug(f"Configuration: {effective}")

        # Check for claude CLI (ORC-09)
        if shutil.which("claude") is None:
            logger.error("claude CLI not found in $PATH")
            raise typer.Exit(code=1)

        # Parse prompts (PRE-01, INP-01..06)
        logger.info(f"Loading prompts from {input_file}")
        prompts = prepare_prompts(input_file, effective["source_encoding"])
        logger.info(f"Loaded {len(prompts)} prompt(s)")

        # Execute main loop (ORC-01..08)
        exit_code = execution_loop(prompts, effective["output"], effective["timeout"])

        # Exit with code from execution_loop (ERR-11)
        if exit_code != 0:
            raise typer.Exit(code=exit_code)

    except typer.Exit:
        # Re-raise typer.Exit as-is (from execution_loop or other sources)
        raise

    except SigtermReceived:
        # SIGTERM outside execution_loop (INT-04)
        logger.error("SIGTERM received, exiting")
        raise typer.Exit(code=143)

    except KeyboardInterrupt:
        # SIGINT (Ctrl+C) outside execution_loop (ERR-10, ERR-11)
        logger.error("Interrupted by user (Ctrl+C), exiting")
        raise typer.Exit(code=130)

    except Exception as e:
        # Generic error handling (ERR-10)
        logger.error(f"Fatal error: {e}", exc_info=True)
        raise typer.Exit(code=1)
