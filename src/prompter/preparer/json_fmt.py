"""JSON format handler (.json).

Handles JSON array format with string prompts and $ref include directives.
"""

import json
from pathlib import Path
from typing import Any

from . import register_format


@register_format(".json")
def parse_json(content: str, file_path: Path) -> list[str]:
    """Parse JSON format prompts.

    Format:
    - Root must be an array
    - Elements can be:
      - Strings (direct prompts)
      - Objects with "$ref" key (include directives) (INC-05)
    - $ref value must be a string path

    Args:
        content: File content as string
        file_path: Path to the file (for error messages)

    Returns:
        List of prompts (strings and @include: directives)

    Raises:
        ValueError: If format is invalid
    """
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {file_path}: {e}") from e

    # Must be an array (INP-02)
    if not isinstance(data, list):
        raise ValueError(f"JSON root must be an array in {file_path}, got {type(data).__name__}")

    prompts: list[str] = []

    for i, item in enumerate(data):
        # Handle $ref objects (INC-05)
        if isinstance(item, dict):
            if "$ref" in item:
                ref_value = item["$ref"]
                if not isinstance(ref_value, str):
                    raise ValueError(
                        f"$ref value must be a string in {file_path} at index {i}, "
                        f"got {type(ref_value).__name__}"
                    )
                # Convert to internal include marker
                prompts.append(f"@include: {ref_value}")
            else:
                raise ValueError(
                    f"Invalid object in {file_path} at index {i}: "
                    f"expected {{\"$ref\": \"path\"}}, got {item}"
                )
        # Handle string prompts
        elif isinstance(item, str):
            prompts.append(item)
        # Reject other types (INP-06)
        else:
            raise ValueError(
                f"Invalid element type in {file_path} at index {i}: "
                f"expected string or {{\"$ref\": \"path\"}}, got {type(item).__name__}"
            )

    return prompts
