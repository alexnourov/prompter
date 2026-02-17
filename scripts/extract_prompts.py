#!/usr/bin/env python3
"""Extract prompts from PROMPTS.adoc (tagged region) and convert to .md.

Usage:
    python extract_prompts.py specs/PROMPTS.adoc               # stdout
    python extract_prompts.py specs/PROMPTS.adoc specs/PROMPTS.md  # file
"""

import re
import sys
from pathlib import Path


def extract_tagged_region(text: str, tag: str = "prompts") -> str:
    pattern = rf"//\s*tag::{tag}\[\]\s*\n(.*?)//\s*end::{tag}\[\]"
    match = re.search(pattern, text, re.DOTALL)
    if not match:
        raise ValueError(f"Tagged region '{tag}' not found in input")
    return match.group(1)


def convert_prompt(text: str) -> str:
    lines = text.split("\n")
    result: list[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # AsciiDoc comment lines (// ...)
        if re.match(r"^//\s", line):
            i += 1
            continue

        # Anchor lines: [[something]]
        if re.match(r"^\[\[.*\]\]$", line):
            i += 1
            continue

        # Attribute lines: [cols=...], [start=N], [options=...]
        if re.match(r"^\[(cols|start|options)=", line):
            i += 1
            continue

        # Source blocks: [source,lang] or [source]
        source_match = re.match(r"^\[source(?:,(\w+))?\]$", line)
        if source_match:
            lang = source_match.group(1) or ""
            i += 1
            if i < len(lines) and lines[i].strip() == "----":
                result.append(f"```{lang}")
                i += 1
                while i < len(lines) and lines[i].strip() != "----":
                    content_line = lines[i]
                    if content_line.strip() == "---":
                        content_line = "\\---"
                    result.append(content_line)
                    i += 1
                result.append("```")
                if i < len(lines):
                    i += 1  # skip closing ----
                continue
            continue

        # Stray ---- outside source blocks
        if line.strip() == "----":
            i += 1
            continue

        # Headers: == → ##, === → ###, etc.
        header_match = re.match(r"^(={2,5})\s+(.+)$", line)
        if header_match:
            level = len(header_match.group(1))
            title = header_match.group(2)
            result.append(f"{'#' * level} {title}")
            i += 1
            continue

        # Continuation marker: standalone +
        if line.strip() == "+":
            i += 1
            continue

        # Cross-references: xref:FILE#anchor[text] → text
        line = re.sub(r"xref:[^\[]+\[([^\]]+)\]", r"\1", line)

        # Internal refs with display text: <<anchor,text>> → text
        line = re.sub(r"<<[^,>]+,([^>]+)>>", r"\1", line)

        # Bare internal refs: <<prompt-NN>> → промпт NN
        line = re.sub(
            r"<<prompt-(\d+)>>",
            lambda m: f"промпт {int(m.group(1))}",
            line,
        )

        # Other bare refs: <<anchor>> → anchor
        line = re.sub(r"<<([^>]+)>>", r"\1", line)

        # Ordered list: . item → 1. item, .. item → indented
        ol_match = re.match(r"^(\.{1,3})\s+(.*)$", line)
        if ol_match:
            dots = len(ol_match.group(1))
            indent = "  " * (dots - 1)
            rest = ol_match.group(2)
            line = f"{indent}1. {rest}"

        # Unordered sub-items: ** item → indented * item
        if re.match(r"^\*\*\s", line):
            line = "  *" + line[2:]

        # Escape standalone --- in content
        if line.strip() == "---":
            line = "\\---"

        result.append(line)
        i += 1

    return "\n".join(result)


def main() -> None:
    if len(sys.argv) < 2:
        print(
            f"Usage: {sys.argv[0]} PROMPTS.adoc [output.md]",
            file=sys.stderr,
        )
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else None

    text = input_path.read_text(encoding="utf-8")
    tagged = extract_tagged_region(text)

    # Protect ''' inside source blocks (---- ... ----) before splitting
    placeholder = "\x00THEMATIC_BREAK\x00"

    def protect_source_blocks(text: str) -> str:
        def replace_in_block(m: re.Match) -> str:
            return m.group(0).replace("'''", placeholder)
        return re.sub(r"^----\n.*?^----", replace_in_block, text, flags=re.MULTILINE | re.DOTALL)

    protected = protect_source_blocks(tagged)

    # Split by AsciiDoc thematic break '''
    prompts_raw = re.split(r"^'{3}$", protected, flags=re.MULTILINE)

    # Restore placeholders
    prompts_raw = [p.replace(placeholder, "'''") for p in prompts_raw]

    # Strip comments, then filter empty chunks
    def strip_comments(chunk: str) -> str:
        lines = [l for l in chunk.split("\n") if not re.match(r"^//\s", l)]
        return "\n".join(lines).strip()

    prompts = [strip_comments(p) for p in prompts_raw]
    prompts = [p for p in prompts if p]

    converted = [convert_prompt(p) for p in prompts]
    output = "\n\n---\n\n".join(converted) + "\n"

    if output_path:
        output_path.write_text(output, encoding="utf-8")
        print(
            f"Extracted {len(converted)} prompts → {output_path}",
            file=sys.stderr,
        )
    else:
        sys.stdout.write(output)


if __name__ == "__main__":
    main()
