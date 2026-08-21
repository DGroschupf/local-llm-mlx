from __future__ import annotations

import subprocess
from typing import Any

from local_llm.models import MODELS
from local_llm.processes import process_rss_gb


def build_memory_status(pid: int | None) -> dict[str, Any]:
    total_gb = _run_float(["sysctl", "-n", "hw.memsize"], divisor=1024**3)
    vm = _parse_vm_stat()
    swap = _parse_swap_usage()
    process_gb = process_rss_gb(pid) if pid else None

    used_gb = None
    available_gb = None
    pressure = "unknown"

    if total_gb is not None and vm:
        free_pages = (
            vm.get("Pages free", 0)
            + vm.get("Pages inactive", 0)
            + vm.get("Pages speculative", 0)
        )
        page_size = vm.get("page_size", 16384)
        available_gb = free_pages * page_size / 1024**3
        used_gb = total_gb - available_gb

        if available_gb < 2:
            pressure = "red"
        elif available_gb < 5:
            pressure = "yellow"
        else:
            pressure = "green"

    return {
        "total_gb": _round(total_gb),
        "used_gb": _round(used_gb),
        "available_gb": _round(available_gb),
        "swap_used_gb": _round(swap.get("used_gb", 0)),
        "process_rss_gb": _round(process_gb),
        "pressure": pressure,
    }


def build_fit_status(memory: dict[str, Any], active_model: str | None) -> dict[str, Any]:
    available_gb = memory.get("available_gb")
    pressure = memory.get("pressure", "unknown")
    result: dict[str, Any] = {"active_model": active_model, "models": {}}

    for name, profile in MODELS.items():
        needed = profile.size_gb + 4.0
        if available_gb is None:
            level = "unknown"
            message = "Memory availability could not be read."
        elif pressure == "red":
            level = "risky"
            message = "Available memory is critically low."
        elif available_gb < needed:
            level = "tight"
            message = f"Estimated headroom below {needed:.1f} GB."
        else:
            level = "comfortable"
            message = "Estimated headroom looks okay."

        result["models"][name] = {
            "level": level,
            "message": message,
            "estimated_needed_gb": round(needed, 1),
        }

    return result


def _parse_vm_stat() -> dict[str, int]:
    try:
        output = subprocess.check_output(["vm_stat"], text=True)
    except (OSError, subprocess.CalledProcessError):
        return {}

    result: dict[str, int] = {}
    for line in output.splitlines():
        if "page size of" in line:
            for part in line.split():
                if part.isdigit():
                    result["page_size"] = int(part)
                    break
        elif ":" in line:
            key, value = line.split(":", 1)
            result[key] = int(value.strip().strip(".").replace(".", ""))
    return result


def _parse_swap_usage() -> dict[str, float]:
    try:
        output = subprocess.check_output(["sysctl", "-n", "vm.swapusage"], text=True)
    except (OSError, subprocess.CalledProcessError):
        return {"used_gb": 0.0}

    parts = output.replace(",", "").split()
    for index, part in enumerate(parts):
        if part == "used" and index + 2 < len(parts):
            return {"used_gb": _parse_size_to_gb(parts[index + 2])}
    return {"used_gb": 0.0}


def _parse_size_to_gb(value: str) -> float:
    number = ""
    unit = ""
    for char in value:
        if char.isdigit() or char == ".":
            number += char
        else:
            unit += char
    if not number:
        return 0.0
    return _to_gb(float(number), unit or "G")


def _to_gb(value: float, unit: str) -> float:
    unit = unit.upper().rstrip(".")
    if unit.startswith("M"):
        return value / 1024
    if unit.startswith("K"):
        return value / 1024**2
    if unit.startswith("T"):
        return value * 1024
    return value


def _run_float(cmd: list[str], divisor: int = 1) -> float | None:
    try:
        output = subprocess.check_output(cmd, text=True).strip()
        return float(output) / divisor
    except (OSError, subprocess.CalledProcessError, ValueError):
        return None


def _round(value: float | None) -> float | None:
    return round(value, 2) if value is not None else None
