from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from typing import Any

from local_llm.config import DEFAULT_IDLE_SECONDS, DEFAULT_SUPERVISOR_TICK_SECONDS, LOG_DIR
from local_llm.models import ModelProfile
from local_llm.processes import is_pid_alive, process_cpu_seconds
from local_llm.state import ensure_app_dirs, load_state, save_state, state_lock, touch_state


def run_chat(profile: ModelProfile) -> None:
    cmd = [
        sys.executable,
        "-m",
        "mlx_lm.chat",
        "--model",
        profile.model,
        "--max-kv-size",
        str(profile.chat_kv_size),
        "--max-tokens",
        str(profile.max_tokens),
    ]
    os.execvp(cmd[0], cmd)


def start_server(
    profile: ModelProfile,
    host: str = "127.0.0.1",
    port: int = 8080,
    idle_seconds: int = DEFAULT_IDLE_SECONDS,
    backend: str = "mlx",
) -> dict[str, Any]:
    if backend == "agent" and not profile.supports_agent:
        raise ValueError(f"{profile.name} does not have an agent backend configured")

    with state_lock:
        state = load_state()
        if is_pid_alive(state.get("pid")):
            same_model = (
                state.get("model_name") == profile.name
                and state.get("port") == port
                and state.get("backend") == backend
            )
            if same_model:
                touch_state(state)
                save_state(state)
                return state
            _stop_server_locked(state)

        ensure_app_dirs()
        log_path = LOG_DIR / f"{profile.name}-{int(time.time())}.log"
        log_file = log_path.open("ab")
        cmd = _server_command(profile, host, port, idle_seconds, backend)
        process = subprocess.Popen(
            cmd,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

        state = {
            "pid": process.pid,
            "model_name": profile.name,
            "model": profile.model,
            "backend": backend,
            "host": host,
            "port": port,
            "started_at": time.time(),
            "last_activity_at": time.time(),
            "last_cpu_seconds": process_cpu_seconds(process.pid),
            "idle_seconds": idle_seconds,
            "log_path": str(log_path),
            "cmd": cmd,
        }
        save_state(state)
        return state


def _server_command(
    profile: ModelProfile,
    host: str,
    port: int,
    idle_seconds: int,
    backend: str,
) -> list[str]:
    if backend == "agent":
        return [
            "optiq",
            "serve",
            "--model",
            profile.model,
            "--host",
            host,
            "--port",
            str(port),
            "--max-tokens",
            str(profile.max_tokens),
            "--idle-timeout",
            str(idle_seconds),
            "--max-concurrent",
            "1",
        ]

    return [
        sys.executable,
        "-m",
        profile.server_module,
        "--model",
        profile.model,
        "--host",
        host,
        "--port",
        str(port),
        "--max-tokens",
        str(profile.max_tokens),
        "--prompt-cache-bytes",
        str(profile.server_cache_bytes),
    ]


def stop_server() -> bool:
    with state_lock:
        state = load_state()
        stopped = _stop_server_locked(state)
        save_state({})
    return stopped


def supervise_foreground(tick_seconds: int = DEFAULT_SUPERVISOR_TICK_SECONDS) -> None:
    print("Supervisor active. Press Ctrl+C to stop the model server.")
    try:
        while True:
            idle_monitor_tick()
            state = load_state()
            if not is_pid_alive(state.get("pid")):
                print("Model server is no longer running.")
                return
            time.sleep(tick_seconds)
    except KeyboardInterrupt:
        print("\nStopping model server.")
        stopped = stop_server()
        print("Stopped active model server." if stopped else "No active model server.")


def idle_monitor_loop(tick_seconds: int = DEFAULT_SUPERVISOR_TICK_SECONDS) -> None:
    while True:
        idle_monitor_tick()
        time.sleep(tick_seconds)


def idle_monitor_tick() -> None:
    with state_lock:
        state = load_state()
        pid = state.get("pid")

        if is_pid_alive(pid):
            _refresh_activity_from_cpu(state, pid)
            idle_seconds = int(state.get("idle_seconds", DEFAULT_IDLE_SECONDS))
            idle_for = time.time() - float(state.get("last_activity_at", time.time()))
            if idle_for >= idle_seconds:
                _stop_server_locked(state)
                save_state({})
        elif state:
            save_state({})


def mark_activity() -> None:
    with state_lock:
        state = load_state()
        if is_pid_alive(state.get("pid")):
            touch_state(state)
            save_state(state)


def _refresh_activity_from_cpu(state: dict[str, Any], pid: int) -> None:
    cpu_seconds = process_cpu_seconds(pid)
    last_cpu_seconds = state.get("last_cpu_seconds")
    if cpu_seconds is None or last_cpu_seconds is None:
        return
    if cpu_seconds > last_cpu_seconds:
        state["last_cpu_seconds"] = cpu_seconds
        touch_state(state)
        save_state(state)


def _stop_server_locked(state: dict[str, Any]) -> bool:
    pid = state.get("pid")
    if not is_pid_alive(pid):
        return False

    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        return False
    except PermissionError:
        os.kill(pid, signal.SIGTERM)

    deadline = time.time() + 8
    while time.time() < deadline:
        if not is_pid_alive(pid):
            return True
        time.sleep(0.2)

    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except PermissionError:
        os.kill(pid, signal.SIGKILL)
    return True
