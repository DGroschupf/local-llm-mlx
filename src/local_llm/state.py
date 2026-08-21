from __future__ import annotations

import json
import time
from threading import Lock
from typing import Any

from local_llm.config import APP_DIR, LOG_DIR, STATE_FILE


state_lock = Lock()


def ensure_app_dirs() -> None:
    APP_DIR.mkdir(exist_ok=True)
    LOG_DIR.mkdir(exist_ok=True)


def load_state() -> dict[str, Any]:
    try:
        return json.loads(STATE_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(state: dict[str, Any]) -> None:
    ensure_app_dirs()
    STATE_FILE.write_text(json.dumps(state, indent=2))


def touch_state(state: dict[str, Any]) -> None:
    state["last_activity_at"] = time.time()
