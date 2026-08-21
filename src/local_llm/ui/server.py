from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Any

from local_llm.config import (
    DEFAULT_IDLE_SECONDS,
    DEFAULT_SUPERVISOR_TICK_SECONDS,
    DEFAULT_UI_REFRESH_SECONDS,
)
from local_llm.models import MODELS, model_payload
from local_llm.processes import is_pid_alive
from local_llm.state import load_state, save_state, state_lock
from local_llm.status import build_status
from local_llm.supervisor import (
    idle_monitor_loop,
    mark_activity,
    start_server,
    stop_server,
)

STATIC_DIR = Path(__file__).parent / "static"
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
}


def run_ui(
    host: str = "127.0.0.1",
    port: int = 5177,
    server_port: int = 8080,
    idle_seconds: int = DEFAULT_IDLE_SECONDS,
    refresh_seconds: int = DEFAULT_UI_REFRESH_SECONDS,
    monitor_tick_seconds: int = DEFAULT_SUPERVISOR_TICK_SECONDS,
) -> None:
    server = ThreadingHTTPServer(
        (host, port),
        _make_handler(
            server_port=server_port,
            idle_seconds=idle_seconds,
            refresh_seconds=refresh_seconds,
        ),
    )
    monitor = Thread(
        target=idle_monitor_loop, args=(monitor_tick_seconds,), daemon=True
    )
    monitor.start()

    url = f"http://{host}:{port}"
    print(f"local-llm UI: {url}")
    print("Open that URL in your browser. Press Ctrl+C to stop the dashboard.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
    finally:
        server.server_close()


def _make_handler(
    server_port: int,
    idle_seconds: int,
    refresh_seconds: int,
) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/" or self.path.startswith("/?"):
                self._send_static("index.html")
            elif self.path == "/app.css":
                self._send_static("app.css")
            elif self.path == "/app.js":
                self._send_static("app.js")
            elif self.path == "/api/config":
                self._send_json({"refresh_seconds": refresh_seconds})
            elif self.path == "/api/status":
                self._send_json(build_status())
            elif self.path == "/api/models":
                self._send_json(model_payload())
            else:
                self.send_error(404)

        def do_POST(self) -> None:
            if self.path.startswith("/api/start/"):
                model_name, backend = self._start_target()
                profile = MODELS.get(model_name)
                if profile is None:
                    self.send_error(404, "Unknown model")
                    return

                try:
                    state = start_server(
                        profile,
                        port=server_port,
                        idle_seconds=idle_seconds,
                        backend=backend,
                    )
                except ValueError as exc:
                    self.send_error(400, str(exc))
                    return
                self._send_json({"ok": True, "state": state})
            elif self.path == "/api/stop":
                self._send_json({"ok": True, "stopped": stop_server()})
            elif self.path == "/api/shutdown":
                stop_server()
                self._send_json({"ok": True})
                Thread(target=self.server.shutdown, daemon=True).start()
            elif self.path == "/api/touch":
                mark_activity()
                self._send_json({"ok": True})
            elif self.path == "/api/chat":
                self._handle_chat()
            else:
                self.send_error(404)

        def _handle_chat(self) -> None:
            state = load_state()
            if not is_pid_alive(state.get("pid")):
                self.send_error(409, "No model server is running")
                return

            profile = MODELS.get(state.get("model_name"))
            if profile is None:
                self.send_error(409, "Active model is not configured")
                return

            body = self._read_json()
            prompt = str(body.get("prompt", "")).strip()
            if not prompt:
                self.send_error(400, "Missing prompt")
                return

            with state_lock:
                fresh_state = load_state()
                if is_pid_alive(fresh_state.get("pid")):
                    fresh_state["last_activity_at"] = time.time()
                    save_state(fresh_state)

            payload = {
                "model": state.get("model"),
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": profile.max_tokens,
                "temperature": 0,
                "stream": True,
            }
            url = f"http://{state.get('host', '127.0.0.1')}:{state.get('port', 8080)}/v1/chat/completions"

            try:
                request = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=600) as response:
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Cache-Control", "no-cache")
                    self.end_headers()

                    while True:
                        line = response.readline()
                        if not line:
                            break
                        self.wfile.write(line)
                        self.wfile.flush()
            except urllib.error.URLError as exc:
                self.send_error(502, f"Model server is not ready: {exc}")
                return

        def _read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            if length == 0:
                return {}
            return json.loads(self.rfile.read(length).decode("utf-8"))

        def _start_target(self) -> tuple[str, str]:
            target = self.path.rsplit("/", 1)[-1]
            if ":" not in target:
                return target, "mlx"
            model_name, backend = target.split(":", 1)
            return model_name, backend

        def _send_static(self, filename: str) -> None:
            path = STATIC_DIR / filename
            try:
                encoded = path.read_bytes()
            except FileNotFoundError:
                self.send_error(404)
                return

            self.send_response(200)
            self.send_header(
                "Content-Type",
                CONTENT_TYPES.get(path.suffix, "application/octet-stream"),
            )
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def _send_json(self, payload: Any) -> None:
            encoded = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, format: str, *args: Any) -> None:
            return

    return Handler
