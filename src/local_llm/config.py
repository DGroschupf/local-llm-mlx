from __future__ import annotations

from pathlib import Path


APP_DIR = Path.cwd() / ".local-llm"
STATE_FILE = APP_DIR / "state.json"
LOG_DIR = APP_DIR / "logs"

DEFAULT_IDLE_SECONDS = 15 * 60
DEFAULT_SUPERVISOR_TICK_SECONDS = 15
DEFAULT_UI_REFRESH_SECONDS = 3
