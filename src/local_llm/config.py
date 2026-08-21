from __future__ import annotations

from pathlib import Path

APP_DIR = Path.cwd() / ".local-llm"
STATE_FILE = APP_DIR / "state.json"
LOG_DIR = APP_DIR / "logs"

DEFAULT_IDLE_SECONDS = 60 * 60  # 1 hour
DEFAULT_SUPERVISOR_TICK_SECONDS = 15
DEFAULT_UI_REFRESH_SECONDS = 1
LOCAL_AUTH_TOKEN = "sk-optiq-local"
