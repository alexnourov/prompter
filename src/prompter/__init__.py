"""Prompter — batch prompt execution for AI assistants."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("prompter")
except PackageNotFoundError:
    __version__ = "0.0.0"
