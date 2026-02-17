"""Handler for .json prompt files."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from ..models import Prompt
from . import register_format


@register_format(".json")
def handle_json(
    content: str,
    file_path: Path,
    resolve_include: Callable[[Path], list[Prompt]],
) -> list[Prompt]:
    """Parse .json files: array of {title, body} objects or {$ref} includes."""
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {file_path.name}: {e}") from e

    if not isinstance(data, list):
        raise ValueError(
            f"Expected a JSON array in {file_path.name}, "
            f"got {type(data).__name__}"
        )

    prompts: list[Prompt] = []

    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(
                f"Item {i} in {file_path.name} must be an object, "
                f"got {type(item).__name__}"
            )

        if "$ref" in item:
            ref = item["$ref"]
            if not isinstance(ref, str):
                raise ValueError(
                    f"Item {i} in {file_path.name}: "
                    f"'$ref' must be a string, got {type(ref).__name__}"
                )
            prompts.extend(resolve_include(Path(ref)))
        elif "title" in item and "body" in item:
            title = item["title"]
            body = item["body"]
            if not isinstance(title, str):
                raise ValueError(
                    f"Item {i} in {file_path.name}: "
                    f"'title' must be a string, got {type(title).__name__}"
                )
            if not isinstance(body, str):
                raise ValueError(
                    f"Item {i} in {file_path.name}: "
                    f"'body' must be a string, got {type(body).__name__}"
                )
            prompts.append(Prompt(title=title.strip(), body=body.strip()))
        else:
            raise ValueError(
                f'Item {i} in {file_path.name}: '
                f'object must have "title"+"body" or "$ref"'
            )

    return prompts
