"""Main CLI module for Prompter application."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional

import typer

from prompter.config import find_config_dir, load_settings, setup_logging
from prompter.io import PromptReader, SessionLogger
from prompter.runner import ClaudeRunner

app = typer.Typer(
    name="prompter",
    help="CLI utility for automating interactions with Claude Code CLI.",
    add_completion=False,
)

logger = logging.getLogger(__name__)


@app.command()
def main(
    input_file: Annotated[
        Path,
        typer.Argument(
            help="Path to the prompts file (.txt, .md, or .json)",
            exists=True,
            readable=True,
        ),
    ],
    output: Annotated[
        Path,
        typer.Option(
            "--output", "-o",
            help="Path to save the JSON report",
        ),
    ] = Path("report.json"),
    verbose: Annotated[
        Optional[bool],
        typer.Option(
            "--verbose", "-v",
            help="Enable verbose output",
        ),
    ] = None,
    app_name: Annotated[
        str,
        typer.Option(
            "--app-name",
            help="Application name for config directory",
        ),
    ] = "prompter",
    config: Annotated[
        Optional[Path],
        typer.Option(
            "--config", "-c",
            help="Path to config directory",
        ),
    ] = None,
    timeout: Annotated[
        Optional[int],
        typer.Option(
            "--timeout", "-t",
            help="Timeout in seconds for each prompt",
        ),
    ] = None,
) -> None:
    """Execute prompts from a file using Claude Code CLI."""
    config_dir = find_config_dir(app_name, config)
    settings = load_settings(config_dir)

    effective_verbose = verbose if verbose is not None else settings.get("verbose", False)
    effective_timeout = timeout if timeout is not None else settings.get("timeout", 2400)

    setup_logging(config_dir, verbose=effective_verbose)

    logger.info("Starting Prompter")
    logger.debug("Config directory: %s", config_dir)
    logger.debug("Effective timeout: %d", effective_timeout)

    reader = PromptReader()
    runner = ClaudeRunner()
    session_logger = SessionLogger()

    try:
        prompts = reader.read(input_file)
    except (FileNotFoundError, ValueError) as e:
        logger.error("Failed to read prompts: %s", e)
        raise typer.Exit(code=1)

    if not prompts:
        logger.warning("No prompts found in %s", input_file)
        raise typer.Exit(code=0)

    logger.info("Loaded %d prompts from %s", len(prompts), input_file)

    report: list[dict] = []
    total_prompts = len(prompts)
    i = 0

    while i < total_prompts:
        prompt_text = prompts[i]
        logger.info("Processing prompt %d/%d...", i + 1, total_prompts)

        try:
            result = runner.run_prompt(
                prompt_text,
                timeout=effective_timeout,
                verbose=effective_verbose,
            )

            report.append({
                "prompt": prompt_text,
                "claude_response": result,
                "timestamp": datetime.now().isoformat(),
                "status": "success",
            })

            if effective_verbose:
                logger.debug("Prompt %d completed successfully", i + 1)

            i += 1

        except KeyboardInterrupt:
            logger.warning("Prompt %d interrupted by user", i + 1)
            choice = _ask_interrupt_choice()

            if choice == "r":
                logger.info("Repeating prompt %d", i + 1)
                continue
            elif choice == "n":
                logger.info("Skipping to next prompt")
                report.append({
                    "prompt": prompt_text,
                    "claude_response": None,
                    "timestamp": datetime.now().isoformat(),
                    "status": "skipped",
                })
                i += 1
                continue
            else:
                logger.info("Exiting by user request")
                break

        except Exception as e:
            logger.error("Failed to process prompt %d: %s", i + 1, e)
            report.append({
                "prompt": prompt_text,
                "claude_response": None,
                "timestamp": datetime.now().isoformat(),
                "status": "error",
                "error": str(e),
            })
            i += 1
            continue

    session_logger.save_report(report, output)
    logger.info("Processing complete. Report saved to %s", output)


def _ask_interrupt_choice() -> str:
    """Ask user what to do after interrupt.

    Returns:
        User choice: 'r' for repeat, 'n' for next, 'e' for exit.
    """
    try:
        choice = input("\nInterrupted. (R)epeat, (N)ext or (E)xit? ").strip().lower()
        if choice in ("r", "repeat"):
            return "r"
        elif choice in ("n", "next"):
            return "n"
        else:
            return "e"
    except (EOFError, KeyboardInterrupt):
        return "e"
