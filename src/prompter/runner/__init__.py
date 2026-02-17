"""Runner subpackage: assistant registry and factory (RUN-01, RUN-02)."""

from __future__ import annotations

from .base import AssistantRunner

_REGISTRY: dict[str, type[AssistantRunner]] = {}


def register_assistant(name: str):
    """Decorator: register an assistant implementation (RUN-01)."""

    def decorator(cls: type[AssistantRunner]) -> type[AssistantRunner]:
        _REGISTRY[name] = cls
        return cls

    return decorator


def create_runner(assistant_name: str, assistant_config: dict) -> AssistantRunner:
    """Create a runner instance by name from the registry (RUN-02).

    Raises:
        ValueError: if assistant_name is not in the registry.
    """
    if assistant_name not in _REGISTRY:
        raise ValueError(
            f"Unknown assistant: {assistant_name!r}. "
            f"Available: {', '.join(sorted(_REGISTRY))}"
        )
    return _REGISTRY[assistant_name](assistant_config)


# Import implementations to trigger @register_assistant decorators
from . import claude  # noqa: F401, E402
from . import gemini  # noqa: F401, E402
from . import aider   # noqa: F401, E402
