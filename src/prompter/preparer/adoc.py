"""Handler for .adoc (AsciiDoc) prompt files."""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

from ..models import Prompt
from . import _first_sentence, register_format

# Thematic break: ''' on its own line, surrounded by blank lines (or start/end of text)
_THEMATIC_BREAK_RE = re.compile(r"(?m)^\s*\n\s*'''\s*\n\s*")

# AsciiDoc heading: =, ==, ===, etc.
_HEADING_RE = re.compile(r"^(=+)\s+(.+)$", re.MULTILINE)

# Anchor: [[...]]
_ANCHOR_RE = re.compile(r"^\[\[.+?\]\]\s*$", re.MULTILINE)

# Include directive: include::path[attrs]
_INCLUDE_RE = re.compile(r"^include::(.+?)\[.*?\]\s*$", re.MULTILINE)

# Lines to strip during markup cleanup
_ADMONITION_BLOCK_RE = re.compile(r"^====\s*$")
_ADMONITION_LABEL_RE = re.compile(r"^\[(NOTE|TIP|WARNING|IMPORTANT|CAUTION)\]\s*$")
_SOURCE_BLOCK_RE = re.compile(r"^\[source.*?\]\s*$")
_CODE_FENCE_RE = re.compile(r"^----\s*$")
_COMMENT_RE = re.compile(r"^//\s")


@register_format(".adoc")
def handle_adoc(
    content: str,
    file_path: Path,
    resolve_include: Callable[[Path], list[Prompt]],
) -> list[Prompt]:
    """Parse .adoc files: split by thematic breaks, clean markup, resolve includes."""
    blocks = _THEMATIC_BREAK_RE.split(content)

    # If thematic breaks found, skip the first block (metadata, PRE-02)
    if len(blocks) > 1:
        blocks = blocks[1:]

    prompts: list[Prompt] = []

    for block in blocks:
        stripped = block.strip()
        if not stripped:
            continue

        # PRE-05: Extract title BEFORE markup cleanup
        title, body_without_heading = _extract_heading(stripped)

        # PRE-03: Clean markup from body
        cleaned = _clean_markup(body_without_heading if title else stripped)

        # INC-04: Check if the cleaned body is solely an include directive
        include_match = _INCLUDE_RE.fullmatch(cleaned.strip())
        if include_match:
            inc_path = include_match.group(1)
            prompts.extend(resolve_include(Path(inc_path)))
            continue

        if not cleaned.strip():
            continue

        if not title:
            title = _first_sentence(cleaned)

        prompts.append(Prompt(title=title, body=cleaned.strip()))

    return prompts


def _extract_heading(text: str) -> tuple[str | None, str]:
    """Extract AsciiDoc heading, skipping anchors and blank lines.

    Returns (title, body_without_heading_line) or (None, original_text).
    """
    lines = text.split("\n")
    heading_idx = None

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if _ANCHOR_RE.match(stripped):
            continue
        # First non-blank, non-anchor line — check if it's a heading
        heading_match = _HEADING_RE.match(stripped)
        if heading_match:
            heading_idx = i
        break

    if heading_idx is not None:
        title = _HEADING_RE.match(lines[heading_idx].strip()).group(2).strip()
        remaining_lines = lines[:heading_idx] + lines[heading_idx + 1:]
        return title, "\n".join(remaining_lines)

    return None, text


def _clean_markup(text: str) -> str:
    """Remove AsciiDoc structural markup while preserving content (PRE-03).

    Removes: anchors, headings, [source,...], ----, [NOTE]/====, // comments.
    Preserves: text, code block contents, lists, bold/italic, inline code.
    """
    lines = text.split("\n")
    result: list[str] = []
    in_code_block = False

    for line in lines:
        stripped = line.strip()

        # Toggle code block state on ----
        if _CODE_FENCE_RE.match(stripped):
            in_code_block = not in_code_block
            continue

        # Inside code blocks — preserve everything
        if in_code_block:
            result.append(line)
            continue

        # Outside code blocks — remove structural markup
        if _ANCHOR_RE.match(stripped):
            continue
        if _HEADING_RE.match(stripped):
            continue
        if _SOURCE_BLOCK_RE.match(stripped):
            continue
        if _ADMONITION_BLOCK_RE.match(stripped):
            continue
        if _ADMONITION_LABEL_RE.match(stripped):
            continue
        if _COMMENT_RE.match(stripped):
            continue

        result.append(line)

    return "\n".join(result)
