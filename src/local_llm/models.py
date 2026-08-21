from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ModelProfile:
    name: str
    model: str
    role: str
    size_gb: float
    chat_kv_size: int
    max_tokens: int
    server_module: str = "mlx_lm.server"


MODELS: dict[str, ModelProfile] = {
    "qwen": ModelProfile(
        name="qwen",
        model="keXjos/Qwen3.8-9B-mlx-4Bit",
        role="Daily driver",
        size_gb=5.04,
        chat_kv_size=32768,
        max_tokens=2048,
    ),
    "devstral": ModelProfile(
        name="devstral",
        model="mlx-community/Devstral-Small-2-24B-Instruct-2512-OptiQ-4bit",
        role="Heavy coding mode",
        size_gb=15.4,
        chat_kv_size=16384,
        max_tokens=2048,
    ),
}


def model_payload() -> dict[str, dict[str, object]]:
    return {name: asdict(profile) for name, profile in MODELS.items()}
