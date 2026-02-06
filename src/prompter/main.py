"""Main CLI module for Prompter application."""

import importlib.metadata
import logging
from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional

import typer

from prompter.config import find_config_dir, load_settings, setup_logging
from prompter.io import PromptReader, SessionLogger
from prompter.runner import ClaudeRunner

logger = logging.getLogger(__name__)


def _version_callback(value: bool) -> None:
    """Show version and exit if --version flag is provided."""
    if value:
        try:
            version_str = importlib.metadata.version("prompter")
        except importlib.metadata.PackageNotFoundError:
            version_str = "unknown"
        typer.echo(f"Prompter version: {version_str}")
        raise typer.Exit()


app = typer.Typer(
    name="prompter",
    help="CLI utility for automating interaction with Claude Code CLI.",
)


@app.command()
def main(
    input_file: Annotated[
        Path,
        typer.Argument(
            help="Path to the file containing prompts (.txt, .md, or .json).",
            exists=True,
            readable=True,
        ),
    ],
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            help="Path to save the output report (JSON).",
        ),
    ] = Path("report.json"),
    verbose: Annotated[
        Optional[bool],
        typer.Option(
            "--verbose",
            "-v",
            help="Enable verbose output.",
        ),
    ] = None,
    app_name: Annotated[
        str,
        typer.Option(
            "--app-name",
            help="Application name for config directory.",
        ),
    ] = "prompter",
    config: Annotated[
        Optional[Path],
        typer.Option(
            "--config",
            "-c",
            help="Path to custom config directory.",
        ),
    ] = None,
    timeout: Annotated[
        Optional[int],
        typer.Option(
            "--timeout",
            "-t",
            help="Timeout in seconds for each prompt execution.",
        ),
    ] = None,
    version: Annotated[
        Optional[bool],
        typer.Option(
            "--version",
            help="Show version and exit.",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = None,
) -> None:
    """Execute prompts from a file using Claude Code CLI."""
    config_dir = find_config_dir(app_name, config)
    settings = load_settings(config_dir)

    effective_verbose = (
        verbose if verbose is not None else settings.get("verbose", False)
    )
    effective_timeout = (
        timeout if timeout is not None else settings.get("timeout", 2400)
    )

    setup_logging(config_dir, verbose=effective_verbose)

    logger.info("Starting Prompter")
    logger.debug("Config directory: %s", config_dir)
    logger.debug("Settings: %s", settings)

    runner = ClaudeRunner()
    reader = PromptReader()
    session_logger = SessionLogger()

    try:
        prompts = reader.read(input_file)
    except (FileNotFoundError, ValueError) as e:
        logger.error("Failed to read prompts: %s", e)
        raise typer.Exit(code=1)

    if not prompts:
        logger.warning("No prompts found in %s", input_file)
        raise typer.Exit(code=0)

    results: list[dict] = []
    total_prompts = len(prompts)
    i = 0

    while i < total_prompts:
        prompt = prompts[i]
        logger.info("Processing prompt %d/%d...", i + 1, total_prompts)

        try:
            result = runner.run_prompt(
                prompt, timeout=effective_timeout, verbose=effective_verbose
            )
            results.append({
                "prompt": prompt,
                "claude_response": result,
                "timestamp": datetime.now().isoformat(),
                "status": "success",
            })
            if effective_verbose:
                logger.debug("Prompt %d completed successfully", i + 1)
            i += 1

        except KeyboardInterrupt:
            typer.echo("\nInterrupted. (R)epeat, (N)ext or (E)xit? ", nl=False)
            choice = input().strip().upper()

            if choice == "R":
                logger.info("Repeating prompt %d", i + 1)
                continue
            elif choice == "N":
                logger.info("Skipping to next prompt")
                results.append({
                    "prompt": prompt,
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
            logger.error("Failed to process prompt: %s", e)
            results.append({
                "prompt": prompt,
                "claude_response": None,
                "timestamp": datetime.now().isoformat(),
                "status": "error",
                "error": str(e),
            })
            i += 1
            continue

    session_logger.save_report(results, output)
    logger.info("Processing complete. Report saved to %s", output)


if __name__ == "__main__":
    app()
