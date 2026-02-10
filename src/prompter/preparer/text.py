"""Text format handler (.txt, .md).

Handles plain text and Markdown files with separator-based splitting.
Supports escape sequences for literal separators.
"""

import re
from pathlib import Path

from . import register_format

# Separator pattern (INP-01, INP-04)
SEPARATOR = "---"


@register_format(".txt", ".md")
def parse_text(content: str, file_path: Path) -> list[str]:
    """Parse text/Markdown format prompts.

    Format:
    - Prompts separated by '---' on its own line
    - First block (before first separator) is metadata and is skipped (PRE-02)
    - Escape sequences: \\--- → literal ---, \\\\--- → literal \\--- (INC-03)
    - @include directives pass through unchanged; resolved by parent

    Args:
        content: File content as string
        file_path: Path to the file (for error messages)

    Returns:
        List of prompt strings
    """
    lines = content.splitlines()
    processed_lines: list[str] = []

    # Process escape sequences (INC-03)
    # First pass: handle separators on separate lines
    for line in lines:
        stripped_line = line.strip()
        if stripped_line == r"\---":
            # Single backslash escape on its own line: becomes literal ---
            processed_lines.append("---")
        elif stripped_line == r"\\---":
            # Double backslash escape on its own line: becomes literal \---
            processed_lines.append(r"\---")
        else:
            # For other lines, process escape sequences inline
            # Replace \--- with --- and \\--- with \---
            processed_line = line.replace(r"\\---", "\x00DOUBLE_ESC\x00")  # Temporary marker
            processed_line = processed_line.replace(r"\---", "---")
            processed_line = processed_line.replace("\x00DOUBLE_ESC\x00", r"\---")
            processed_lines.append(processed_line)

    # Rejoin content
    processed_content = "\n".join(processed_lines)

    # Split by separator (must be on its own line)
    # Need to handle both \n---\n and edge cases
    parts = []
    current_part = []
    for i, line in enumerate(processed_lines):
        if line.strip() == SEPARATOR:
            # Found separator on its own line
            parts.append("\n".join(current_part))
            current_part = []
        else:
            current_part.append(line)
    # Add last part
    if current_part or parts:  # If we had separators or have remaining content
        parts.append("\n".join(current_part))

    # If no separators found, entire file is one prompt
    if len(parts) == 1:
        stripped_content = processed_content.strip()
        # Return empty list if content is empty (INP-05)
        return [stripped_content] if stripped_content else []

    # First block is metadata, skip it (PRE-02)
    prompts = [part.strip() for part in parts[1:]]

    # Filter out empty prompts
    return [p for p in prompts if p]
