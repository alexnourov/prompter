"""Prompter - Automated Claude CLI interaction tool.

This package provides a command-line interface for executing prompts
through Claude CLI in an automated, sequential manner with session
management and comprehensive reporting.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("prompter")
except PackageNotFoundError:
    # Package not installed - use fallback version
    __version__ = "0.0.0"

__all__ = ["__version__"]
