from __future__ import annotations

import os
import subprocess
from typing import Any


def is_pid_alive(pid: Any) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def process_rss_gb(pid: int | None) -> float | None:
    if not pid:
        return None
    try:
        output = subprocess.check_output(["ps", "-o", "rss=", "-p", str(pid)], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    if not output:
        return None
    return int(output) / 1024**2


def process_cpu_seconds(pid: int | None) -> int | None:
    if not pid:
        return None
    try:
        output = subprocess.check_output(["ps", "-o", "time=", "-p", str(pid)], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    if not output:
        return None
    parts = output.split(":")
    try:
        if len(parts) == 3:
            hours, minutes, seconds = parts
            return int(hours) * 3600 + int(minutes) * 60 + int(seconds)
        if len(parts) == 2:
            minutes, seconds = parts
            return int(minutes) * 60 + int(seconds)
    except ValueError:
        return None
    return None
