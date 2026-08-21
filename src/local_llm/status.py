from __future__ import annotations

from typing import Any

from local_llm.memory import build_fit_status, build_memory_status
from local_llm.models import MODELS, model_payload
from local_llm.processes import is_pid_alive
from local_llm.state import load_state, save_state


def build_status() -> dict[str, Any]:
    state = load_state()
    active = is_pid_alive(state.get("pid"))

    if not active and state:
        save_state({})
        state = {}

    memory = build_memory_status(state.get("pid") if active else None)
    fit = build_fit_status(memory, state.get("model_name"))

    return {
        "active": active,
        "state": state if active else {},
        "memory": memory,
        "fit": fit,
        "models": model_payload(),
        "commands": _commands(),
    }


def _commands() -> dict[str, dict[str, str]]:
    commands = {}
    for name, profile in MODELS.items():
        values = {
            "chat": f"uv run local-llm run {name}",
            "serve": f"uv run local-llm serve {name}",
        }
        if profile.supports_agent:
            values["serve_agent"] = f"uv run local-llm serve {name} --backend agent"
            values["claude"] = _claude_command(profile.model, profile.name.title())
        commands[name] = values
    return commands


def _claude_command(model: str, display_name: str) -> str:
    return (
        'ANTHROPIC_BASE_URL="http://127.0.0.1:8080" '
        'ANTHROPIC_AUTH_TOKEN="sk-optiq-local" '
        f'ANTHROPIC_CUSTOM_MODEL_OPTION="{model}" '
        f'ANTHROPIC_CUSTOM_MODEL_OPTION_NAME="{display_name} Local" '
        f'claude --model "{model}"'
    )
