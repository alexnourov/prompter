"""AsciiDoc format handler (.adoc).

Handles AsciiDoc files with metadata stripping and markup cleaning.
Two-stage pipeline: separator-based splitting + markup removal.
"""

import re
from pathlib import Path

from . import register_format

# Thematic break separator (INP-01a)
SEPARATOR = "'''"

# Include directive pattern (INC-04)
INCLUDE_PATTERN = re.compile(r'^include::(.+?)\[.*?\]\s*$')


@register_format(".adoc")
def parse_adoc(content: str, file_path: Path) -> list[str]:
    """Parse AsciiDoc format prompts.

    Two-stage processing:
    1. Split by ''' separator, skip first block (metadata) (PRE-02)
    2. Clean AsciiDoc markup from each prompt (PRE-03)
    3. Convert include:: directives to @include: markers (INC-04)

    Args:
        content: File content as string
        file_path: Path to the file (for error messages)

    Returns:
        List of cleaned prompt strings
    """
    # Stage 1: Split by thematic breaks (PRE-02)
    parts = content.split(f"\n{SEPARATOR}\n")

    # If no separators, entire file is one prompt
    if len(parts) == 1:
        prompts = [content]
    else:
        # Skip first block (metadata)
        prompts = parts[1:]

    # Stage 2: Clean markup and handle includes (PRE-03, INC-04)
    cleaned_prompts: list[str] = []

    for prompt in prompts:
        cleaned = _clean_markup(prompt.strip())

        # Check if cleaned prompt is an include directive
        include_match = INCLUDE_PATTERN.match(cleaned.strip())
        if include_match:
            include_path = include_match.group(1).strip()
            cleaned_prompts.append(f"@include: {include_path}")
        else:
            if cleaned:  # Skip empty prompts
                cleaned_prompts.append(cleaned)

    return cleaned_prompts


def _clean_markup(text: str) -> str:
    """Remove AsciiDoc markup while preserving content.

    Removes:
    - Anchors [[...]]
    - Section headers (==, ===, etc.)
    - Source block markers [source,...] and delimiters (----)
    - Admonitions ([NOTE], ====)
    - Comments (// ...)

    Preserves:
    - Text content
    - Code block content
    - Lists
    - Bold/italic (*text*, _text_)
    - Inline code (`code`)

    Args:
        text: Raw AsciiDoc text

    Returns:
        Cleaned text with markup removed
    """
    lines = text.splitlines()
    result_lines: list[str] = []
    in_code_block = False
    in_admonition = False

    for line in lines:
        stripped = line.strip()

        # Toggle code block state
        if stripped == "----":
            in_code_block = not in_code_block
            continue  # Skip delimiter line

        # Toggle admonition block state
        if stripped == "====":
            in_admonition = not in_admonition
            continue

        # Inside code block or admonition: preserve content as-is
        if in_code_block or in_admonition:
            result_lines.append(line)
            continue

        # Remove anchors [[...]]
        line = re.sub(r'\[\[.*?\]\]', '', line)

        # Remove section headers (== Title, === Subtitle, etc.)
        if re.match(r'^=+\s+', stripped):
            continue

        # Remove source block attributes [source,...]
        if re.match(r'^\[source,.*?\]$', stripped):
            continue

        # Remove admonition markers [NOTE], [WARNING], etc.
        if re.match(r'^\[(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]$', stripped):
            continue

        # Remove comments (// ...)
        if stripped.startswith('//'):
            continue

        # Keep all other lines
        if line.strip():  # Skip completely empty lines
            result_lines.append(line)

    # Join and clean up excessive whitespace
    result = '\n'.join(result_lines)
    # Collapse multiple blank lines into single blank line
    result = re.sub(r'\n\s*\n\s*\n+', '\n\n', result)

    return result.strip()
