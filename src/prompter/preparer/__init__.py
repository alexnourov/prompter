"""Prompt preparation subsystem.

This module provides the public API for loading and preparing prompts from various
file formats (.txt, .md, .json, .adoc). It handles:
- Format-specific parsing via registered handlers
- Recursive include directives (@include: <path>)
- Encoding detection and validation
- Circular dependency detection
"""

import logging
import re
from pathlib import Path
from typing import Callable

import charset_normalizer

logger = logging.getLogger(__name__)

# Include directive pattern (INC-01)
INCLUDE_MARKER = re.compile(r'^@include:\s+(.+)$')
MAX_INCLUDE_DEPTH = 10

# Registry of format handlers
_handlers: dict[str, Callable[[str, Path], list[str]]] = {}


def register_format(*extensions: str) -> Callable:
    """Decorator to register a handler for specified file extensions.

    Args:
        *extensions: File extensions to associate with the handler (e.g., ".txt", ".md")

    Returns:
        Decorator function that registers the handler
    """

    def decorator(func: Callable[[str, Path], list[str]]) -> Callable[[str, Path], list[str]]:
        for ext in extensions:
            _handlers[ext.lower()] = func
        return func

    return decorator


def prepare_prompts(file_path: Path, source_encoding: str | None = None) -> list[str]:
    """Load and prepare prompts from a file.

    Public API entry point. Resolves includes recursively and returns
    a flat list of prompts ready for execution.

    Args:
        file_path: Path to the prompts file
        source_encoding: Optional explicit encoding (INP-03)

    Returns:
        List of prepared prompt strings

    Raises:
        ValueError: If file format is unsupported, encoding invalid, or includes are malformed
    """
    return _resolve_recursive(file_path, seen=set(), depth=0, source_encoding=source_encoding)


def _resolve_recursive(
    file_path: Path, seen: set[Path], depth: int, source_encoding: str | None = None
) -> list[str]:
    """Recursively resolve a prompts file with include directives.

    Args:
        file_path: Path to the file to process
        seen: Set of already-visited absolute paths (for cycle detection)
        depth: Current recursion depth
        source_encoding: Optional explicit encoding

    Returns:
        List of prompts with all includes resolved

    Raises:
        ValueError: On excessive depth, circular dependency, unsupported format, or encoding error
    """
    # Check recursion depth (INC-02)
    if depth > MAX_INCLUDE_DEPTH:
        raise ValueError(
            f"Include depth exceeds maximum ({MAX_INCLUDE_DEPTH}). "
            f"Check for deeply nested or circular includes."
        )

    # Resolve absolute path and check for cycles (INC-02)
    abs_path = file_path.resolve()
    if abs_path in seen:
        raise ValueError(f"Circular include detected: {abs_path}")

    # Add to seen set
    seen.add(abs_path)

    try:
        # Determine file extension
        extension = abs_path.suffix.lower()
        if extension not in _handlers:
            raise ValueError(
                f"Unsupported file format: {extension}. "
                f"Supported formats: {', '.join(sorted(_handlers.keys()))}"
            )

        # Read file content with encoding handling (INP-03, ERR-10)
        if source_encoding is not None:
            try:
                content = abs_path.read_text(encoding=source_encoding)
            except UnicodeDecodeError as e:
                raise ValueError(
                    f"Failed to decode {abs_path} with encoding '{source_encoding}': {e}"
                ) from e
        else:
            # Auto-detect encoding
            raw = abs_path.read_bytes()
            detected = charset_normalizer.from_bytes(raw).best()
            if detected is None:
                raise ValueError(
                    f"Could not detect text encoding for {abs_path}. "
                    f"File may be binary or use an unsupported encoding."
                )
            content = str(detected)

        # Call registered handler
        handler = _handlers[extension]
        prompts = handler(content, abs_path)

        # Process include directives (INC-01)
        result: list[str] = []
        for prompt in prompts:
            match = INCLUDE_MARKER.match(prompt.strip())
            if match:
                include_path_str = match.group(1).strip()
                # Resolve relative to current file's directory
                include_path = (abs_path.parent / include_path_str).resolve()
                # Recursive call with incremented depth
                nested_prompts = _resolve_recursive(
                    include_path, seen, depth + 1, source_encoding=source_encoding
                )
                result.extend(nested_prompts)
            else:
                result.append(prompt)

        # Logging (PRE-04)
        logger.info(f"Loaded {len(prompts)} prompt(s) from {abs_path.name}")
        for i, prompt in enumerate(prompts, start=1):
            logger.debug(f"Prompt {i} from {abs_path.name}:\n{prompt}")

        return result

    finally:
        # Remove from seen to support diamond dependencies (A→B→D, A→C→D)
        seen.discard(abs_path)


# Import handlers to trigger @register_format decorators
from . import adoc, json_fmt, text  # noqa: E402, F401
