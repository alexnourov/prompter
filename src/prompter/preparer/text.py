"""Handler for .txt and .md prompt files."""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

from ..models import Prompt
from . import _first_sentence, register_format

_SEPARATOR = "---"
_INCLUDE_RE = re.compile(r"^@include:\s*(.+)$", re.MULTILINE)
_HEADING_RE = re.compile(r"^#+\s+(.+)$", re.MULTILINE)


def _split_blocks(content: str) -> list[str]:
    """Split content by '---' separators, handling escape sequences.

    \\--- → literal '---'
    \\\\--- → literal '\\---'
    """
    # Temporarily replace escaped sequences
    placeholder_double = "\x00DOUBLE_ESCAPE\x00"
    placeholder_single = "\x00SINGLE_ESCAPE\x00"

    text = content.replace("\\\\---", placeholder_double)
    text = text.replace("\\---", placeholder_single)

    blocks = re.split(r"^---$", text, flags=re.MULTILINE)

    # Restore escape sequences
    restored = []
    for block in blocks:
        block = block.replace(placeholder_single, "---")
        block = block.replace(placeholder_double, "\\---")
        restored.append(block)

    return restored


@register_format(".txt", ".md")
def handle_text(
    content: str,
    file_path: Path,
    resolve_include: Callable[[Path], list[Prompt]],
) -> list[Prompt]:
    """Parse .txt/.md files: split by '---', resolve @include directives."""
    blocks = _split_blocks(content)
    is_md = file_path.suffix.lower() == ".md"

    # If separators found, skip the first block (metadata, PRE-02)
    if len(blocks) > 1:
        blocks = blocks[1:]

    prompts: list[Prompt] = []

    for block in blocks:
        stripped = block.strip()
        if not stripped:
            continue

        # Check for @include directives
        include_match = _INCLUDE_RE.search(stripped)
        if include_match:
            # Process all @include directives in this block
            remaining = stripped
            parts = _INCLUDE_RE.split(remaining)
            # parts: [before, path, after, path, ...]
            i = 0
            while i < len(parts):
                text_part = parts[i].strip()
                if text_part:
                    prompts.append(_make_prompt(text_part, is_md))
                i += 1
                if i < len(parts):
                    inc_path = parts[i].strip()
                    prompts.extend(resolve_include(Path(inc_path)))
                    i += 1
            continue

        prompts.append(_make_prompt(stripped, is_md))

    return prompts


def _make_prompt(text: str, is_md: bool) -> Prompt:
    """Create a Prompt from a text block, extracting title per format rules."""
    if is_md:
        heading_match = _HEADING_RE.match(text)
        if heading_match:
            title = heading_match.group(1).strip()
            body = text[heading_match.end():].strip()
            return Prompt(title=_first_sentence(title), body=body)

    return Prompt(title=_first_sentence(text), body=text)
