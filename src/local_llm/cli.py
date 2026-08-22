from __future__ import annotations

import argparse
import json

from local_llm.config import DEFAULT_IDLE_SECONDS, DEFAULT_UI_REFRESH_SECONDS
from local_llm.downloads import delete_repo, scan_downloaded
from local_llm.models import MODELS, model_payload
from local_llm.processes import is_pid_alive
from local_llm.state import load_state
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
    sub.add_parser(
        "models", help="List configured model profiles and their download status."
    )

    rm_parser = sub.add_parser(
        "rm", help="Delete the cached weights for a configured model."
    )
    rm_parser.add_argument("model", choices=MODELS)

    cache_parser = sub.add_parser(
        "cache", help="Inspect and clean up the local Hugging Face model cache."
    )
    cache_sub = cache_parser.add_subparsers(dest="cache_command", required=True)
    cache_sub.add_parser("list", help="List every model cached on disk.")
    cache_rm_parser = cache_sub.add_parser(
        "rm", help="Delete a cached repo by Hugging Face repo id, downloaded or not."
    )
    cache_rm_parser.add_argument("repo_id")

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
    elif args.command == "rm":
        profile = MODELS[args.model]
        _guard_active_repo(profile.model, f"model {args.model!r}")
        try:
            freed = delete_repo(profile.model)
        except KeyError:
            print(f"{args.model} ({profile.model}) is not downloaded.")
            return
        print(f"Deleted {args.model} ({profile.model}), freed {freed / 1e9:.2f} GB.")
    elif args.command == "cache":
        if args.cache_command == "list":
            _print_cache_list()
        elif args.cache_command == "rm":
            _guard_active_repo(args.repo_id, f"repo {args.repo_id!r}")
            try:
                freed = delete_repo(args.repo_id)
            except KeyError as exc:
                print(str(exc))
                return
            print(f"Deleted {args.repo_id}, freed {freed / 1e9:.2f} GB.")
    elif args.command == "ui":
        run_ui(
            host=args.host,
            port=args.port,
            server_port=args.server_port,
            idle_seconds=args.idle_seconds,
            refresh_seconds=args.refresh_seconds,
        )


def _guard_active_repo(repo_id: str, label: str) -> None:
    state = load_state()
    if is_pid_alive(state.get("pid")) and state.get("model") == repo_id:
        raise SystemExit(
            f"Refusing to delete {label}: it is the active model. "
            "Run `local-llm stop` first."
        )


def _print_cache_list() -> None:
    registered_by_repo = {profile.model: name for name, profile in MODELS.items()}
    cache = scan_downloaded()
    if not cache:
        print("No models cached on disk.")
        return
    for repo_id, cached in sorted(cache.items(), key=lambda kv: -kv[1].size_bytes):
        label = registered_by_repo.get(repo_id)
        tag = f" [{label}]" if label else ""
        print(f"{repo_id}{tag}  {cached.size_bytes / 1e9:.2f} GB")
