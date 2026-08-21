from __future__ import annotations

import argparse
import json

from local_llm.config import DEFAULT_IDLE_SECONDS, DEFAULT_UI_REFRESH_SECONDS
from local_llm.models import MODELS, model_payload
from local_llm.status import build_status
from local_llm.supervisor import run_chat, start_server, stop_server, supervise_foreground
from local_llm.ui.server import run_ui


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="local-llm",
        description="Small MLX local LLM runner for Qwen and Devstral.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run", help="Start an interactive mlx_lm.chat session.")
    run_parser.add_argument("model", choices=MODELS)

    serve_parser = sub.add_parser("serve", help="Start one supervised MLX server.")
    serve_parser.add_argument("model", choices=MODELS)
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8080)
    serve_parser.add_argument("--idle-seconds", type=int, default=DEFAULT_IDLE_SECONDS)
    serve_parser.add_argument(
        "--backend",
        choices=("mlx", "agent"),
        default="mlx",
        help="Use mlx_lm.server or Devstral's optiq agent server.",
    )

    sub.add_parser("stop", help="Stop the active model server.")
    sub.add_parser("status", help="Show active model and memory status.")
    sub.add_parser("models", help="List configured model profiles.")

    ui_parser = sub.add_parser("ui", help="Start the local browser dashboard.")
    ui_parser.add_argument("--host", default="127.0.0.1")
    ui_parser.add_argument("--port", type=int, default=5177)
    ui_parser.add_argument("--server-port", type=int, default=8080)
    ui_parser.add_argument("--idle-seconds", type=int, default=DEFAULT_IDLE_SECONDS)
    ui_parser.add_argument("--refresh-seconds", type=int, default=DEFAULT_UI_REFRESH_SECONDS)

    args = parser.parse_args()

    if args.command == "run":
        run_chat(MODELS[args.model])
    elif args.command == "serve":
        start_server(
            MODELS[args.model],
            args.host,
            args.port,
            args.idle_seconds,
            backend=args.backend,
        )
        print(json.dumps(build_status(), indent=2))
        supervise_foreground()
    elif args.command == "stop":
        stopped = stop_server()
        print("Stopped active model server." if stopped else "No active model server.")
    elif args.command == "status":
        print(json.dumps(build_status(), indent=2))
    elif args.command == "models":
        print(json.dumps(model_payload(), indent=2))
    elif args.command == "ui":
        run_ui(
            host=args.host,
            port=args.port,
            server_port=args.server_port,
            idle_seconds=args.idle_seconds,
            refresh_seconds=args.refresh_seconds,
        )
