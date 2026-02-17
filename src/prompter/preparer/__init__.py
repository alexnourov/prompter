"""Prompt preparation: registry, recursive resolution, and public API."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

import charset_normalizer

from ..models import Prompt

logger = logging.getLogger(__name__)

MAX_INCLUDE_DEPTH = 10

_handlers: dict[str, Callable[[str, Path, Callable[[Path], list[Prompt]]], list[Prompt]]] = {}


def register_format(*extensions: str) -> Callable:
    """Decorator: register a handler for the given file extensions."""

    def decorator(func: Callable[[str, Path, Callable[[Path], list[Prompt]]], list[Prompt]]) -> Callable:
        for ext in extensions:
            _handlers[ext] = func
        return func

    return decorator


def prepare_prompts(file_path: Path, source_encoding: str | None = None) -> list[Prompt]:
    """Public API: read prompts from a file, resolving includes recursively."""
    return _resolve_recursive(file_path, seen=set(), depth=0, source_encoding=source_encoding)


def _resolve_recursive(
    file_path: Path,
    seen: set[Path],
    depth: int,
    source_encoding: str | None = None,
) -> list[Prompt]:
    """Recursively read a file, resolving include directives via callback."""
    if depth > MAX_INCLUDE_DEPTH:
        raise ValueError(
            f"Maximum include depth ({MAX_INCLUDE_DEPTH}) exceeded: {file_path}"
        )

    resolved = file_path.resolve()

    if resolved in seen:
        raise ValueError(f"Circular include detected: {resolved}")

    seen.add(resolved)

    ext = file_path.suffix.lower()
    if ext not in _handlers:
        raise ValueError(f"Unsupported file format: '{ext}'")

    try:
        text = _read_file(resolved, source_encoding)

        def resolve_include(inc_path: Path) -> list[Prompt]:
            abs_path = (resolved.parent / inc_path).resolve()
            return _resolve_recursive(
                abs_path, seen, depth + 1, source_encoding=source_encoding
            )

        handler = _handlers[ext]
        prompts = handler(text, file_path, resolve_include)

        logger.info("Prepared %d prompt(s) from %s", len(prompts), file_path.name)
        for p in prompts:
            logger.debug("  Prompt: %s", p.title)

        return prompts
    finally:
        seen.discard(resolved)


def _read_file(resolved: Path, source_encoding: str | None) -> str:
    """Read file content with explicit or auto-detected encoding."""
    if source_encoding is not None:
        try:
            return resolved.read_text(encoding=source_encoding)
        except UnicodeDecodeError as e:
            raise ValueError(
                f"Cannot decode {resolved.name} with encoding "
                f"'{source_encoding}': {e}"
            ) from e

    raw = resolved.read_bytes()
    detected = charset_normalizer.from_bytes(raw).best()
    if detected is None:
        raise ValueError(
            f"Cannot detect encoding for {resolved.name}: "
            f"file may be binary or use an unknown encoding"
        )
    return str(detected)


def _first_sentence(text: str, max_len: int = 80) -> str:
    """Extract the first sentence from text, up to max_len characters (PRE-05)."""
    first_line = text.strip().split("\n", 1)[0].strip()

    # Look for sentence boundary: ". " or "." at end of line
    dot_space = first_line.find(". ")
    dot_end = len(first_line) - 1 if first_line.endswith(".") else -1

    # Pick the earliest sentence boundary
    positions = [p for p in (dot_space, dot_end) if p >= 0]
    if positions:
        sentence = first_line[: min(positions) + 1]
        if len(sentence) <= max_len:
            return sentence

    if len(first_line) <= max_len:
        return first_line

    return first_line[: max_len - 1] + "\u2026"


# Import handler modules to trigger @register_format decorators
from . import text as _text  # noqa: E402, F401
from . import json_fmt as _json_fmt  # noqa: E402, F401
from . import adoc as _adoc  # noqa: E402, F401
