from __future__ import annotations

from dataclasses import asdict, dataclass

from local_llm.downloads import scan_downloaded

_GIB = 1024**3


@dataclass(frozen=True)
class ModelProfile:
    name: str
    model: str
    role: str
    size_gb: float
    chat_kv_size: int
    max_tokens: int
    server_cache_bytes: int = 4 * _GIB
    server_module: str = "mlx_lm.server"
    supports_agent: bool = False


MODELS: dict[str, ModelProfile] = {
    "qwen": ModelProfile(
        name="qwen",
        model="keXjos/Qwen3.8-9B-mlx-4Bit",
        role="Daily driver",
        size_gb=5.04,
        chat_kv_size=32768,
        max_tokens=2048,
        server_cache_bytes=8 * _GIB,
        supports_agent=True,
    ),
    "devstral": ModelProfile(
        name="devstral",
        model="mlx-community/Devstral-Small-2-24B-Instruct-2512-OptiQ-4bit",
        role="Heavy coding mode",
        size_gb=15.4,
        chat_kv_size=16384,
        max_tokens=2048,
        server_cache_bytes=2 * _GIB,
        supports_agent=True,
    ),
    "qwen3-14b": ModelProfile(
        name="qwen3-14b",
        model="mlx-community/Qwen3-14B-4bit",
        role="Protocol candidate — best tested tool-calling reliability",
        size_gb=8.31,
        chat_kv_size=24576,
        max_tokens=2048,
        supports_agent=True,
    ),
    "gemma4-12b": ModelProfile(
        name="gemma4-12b",
        model="mlx-community/gemma-4-12B-it-4bit",
        role="Broken — fails to load on mlx-lm 0.31.3 (vision_embedder weight mismatch)",
        size_gb=6.74,
        chat_kv_size=24576,
        max_tokens=2048,
        supports_agent=False,
    ),
    "ministral3-14b": ModelProfile(
        name="ministral3-14b",
        model="mlx-community/Ministral-3-14B-Instruct-2512-4bit",
        role="Protocol candidate — native tool-calling, separate reasoning checkpoint",
        size_gb=8.42,
        chat_kv_size=24576,
        max_tokens=2048,
        supports_agent=True,
    ),
}


def model_payload() -> dict[str, dict[str, object]]:
    cache = scan_downloaded()
    payload: dict[str, dict[str, object]] = {}
    for name, profile in MODELS.items():
        data = asdict(profile)
        cached = cache.get(profile.model)
        data["downloaded"] = cached is not None
        data["size_on_disk_gb"] = (
            round(cached.size_bytes / 1e9, 2) if cached else None
        )
        payload[name] = data
    return payload
