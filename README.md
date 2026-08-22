# local-llm

Small MLX runner for the two-model setup in
`Lokales Coding-Setup auf dem M5 MacBook Air 24 GB – MLX + Qwen3.8-9B + Devstral Small 2.md`.

It gives you an `ollama`-like command surface for:

- Qwen3.8-9B 4-bit as the daily driver
- Devstral Small 2 24B OptiQ 4-bit as heavy coding mode
- Qwen 3 14B, Gemma 4 12B, and Ministral 3 14B as protocol-model candidates
- one active model server at a time
- idle unloading
- a local dashboard for starting/stopping models and watching memory pressure
  - agent mode through `mlx-optiq` for Qwen, Devstral, Qwen 3 14B, and Ministral 3 14B

## Project Structure

```text
src/local_llm/
  __init__.py          package entrypoint only
  cli.py               command line interface
  config.py            paths and defaults
  memory.py            macOS memory/swap telemetry
  models.py            Qwen and Devstral profiles
  processes.py         PID/RSS/CPU helpers
  state.py             persisted runtime state
  status.py            status payload builder
  supervisor.py        model server lifecycle and idle unloading
  ui/
    server.py          small local HTTP server
    static/
      index.html       dashboard markup
      app.css          dashboard styling
      app.js           dashboard behavior
```

## Setup

This project uses [uv](https://docs.astral.sh/uv/) for fast dependency management. If you don't have it installed yet:

```bash
brew install uv
```

Sync the dependencies (this creates a `.venv` and installs the required `mlx-lm` and `mlx-optiq` packages):

```bash
uv sync
```

The model weights will be downloaded automatically from Hugging Face the first time you run a model.

## Commands

List configured models:

```bash
uv run local-llm models
```

Run interactive terminal chat:

```bash
uv run local-llm run qwen
uv run local-llm run devstral
```

Start a supervised OpenAI-compatible MLX server:

```bash
uv run local-llm serve qwen
uv run local-llm serve devstral
```

Start Devstral in agent mode with `mlx-optiq`:

```bash
uv run local-llm serve devstral --backend agent
```

Qwen can also be started through the agent backend:

```bash
uv run local-llm serve qwen --backend agent
```

The supervised server uses `127.0.0.1:8080` by default and unloads after 15 minutes
of inactivity. It also watches process CPU time, so active generation should refresh
the idle timer even when a client calls `mlx_lm.server` directly.

In agent mode, `optiq serve` also receives an `--idle-timeout` value so it can
release the model internally after being idle.

List models with their local disk status (downloaded or not, size on disk):

```bash
uv run local-llm models
```

Manage the local Hugging Face cache — list every cached repo (including ones not
in the profile list) or delete one to free disk space:

```bash
uv run local-llm cache list
uv run local-llm cache rm mlx-community/gemma-4-12B-it-4bit
```

Delete the cached weights for a configured model by name:

```bash
uv run local-llm rm gemma4-12b
```

Both `rm` and `cache rm` refuse to delete the currently active model server's
weights — run `uv run local-llm stop` first.

Check status:

```bash
uv run local-llm status
```

Stop the active server:

```bash
uv run local-llm stop
```

## Dashboard

Start the local UI:

```bash
uv run local-llm ui
```

Open:

```text
http://127.0.0.1:5177
```

The dashboard refreshes every 1 second by default. To make it quieter:

```bash
uv run local-llm ui --refresh-seconds 120
```

The dashboard can:

- start Qwen
- start Qwen Agent through `mlx-optiq`
- start Devstral
- start Devstral Agent through `mlx-optiq`
- stop the active server
- show active PID/model/log path
- show memory pressure, available memory, swap usage, and process RSS
- estimate whether each model currently looks comfortable, tight, or risky
- send browser-chat prompts through the running local server
- copy a Claude Code command for the local Devstral agent server
- show which models are already downloaded, with size on disk
- delete cached model weights you no longer need, right from the dashboard

The current UI is dependency-free static HTML/CSS/JS served by the Python CLI.
It is intentionally split into separate files so a React/Vite frontend can later
replace `ui/static/` while keeping the same backend endpoints:
`/api/status`, `/api/start/{model}`, `/api/start/{model}:agent`, `/api/stop`,
`/api/config`, and `/api/chat`.

## Model Profiles

| Name | Model | Mode | Chat KV | Max Output |
|---|---|---:|---:|---:|
| `qwen` | `keXjos/Qwen3.8-9B-mlx-4Bit` | daily driver | 32768 | 2048 |
| `devstral` | `mlx-community/Devstral-Small-2-24B-Instruct-2512-OptiQ-4bit` | heavy coding | 16384 | 2048 |
| `qwen3-14b` | `mlx-community/Qwen3-14B-4bit` | protocol candidate | 24576 | 2048 |
| `gemma4-12b` | `mlx-community/gemma-4-12B-it-4bit` | protocol candidate | 24576 | 2048 |
| `ministral3-14b` | `mlx-community/Ministral-3-14B-Instruct-2512-4bit` | protocol candidate | 24576 | 2048 |

`qwen3-14b` and `ministral3-14b` have confirmed tool-calling support and can run
with `--backend agent`. `gemma4-12b` currently fails to load at all (`ValueError:
Received 11 parameters not in model: vision_embedder.*`) — the mlx-community 4-bit
quant ships Gemma 4's vision tower weights, and mlx-lm 0.31.3 (the latest release
as of 2026-08-22) doesn't have a model class for them yet. Both `mlx` and `agent`
backends hit the same load path, so this isn't just an agent-mode gap — chat mode
is broken too, for either backend. Revisit once mlx-lm ships Gemma 4 support.

`mlx_lm.chat` supports `--max-kv-size`, so the terminal chat command uses the
profile-specific KV sizes. The installed `mlx_lm.server` does not expose that flag,
so the server command only passes supported server flags.

## Claude Code With Devstral Agent Mode

Start the local Anthropic-compatible server:

```bash
uv run local-llm serve devstral --backend agent
```

Then go to the project where Claude Code should work and paste:

```bash
ANTHROPIC_BASE_URL="http://127.0.0.1:8080" ANTHROPIC_AUTH_TOKEN="sk-optiq-local" ANTHROPIC_CUSTOM_MODEL_OPTION="mlx-community/Devstral-Small-2-24B-Instruct-2512-OptiQ-4bit" ANTHROPIC_CUSTOM_MODEL_OPTION_NAME="Devstral Local" claude --model "mlx-community/Devstral-Small-2-24B-Instruct-2512-OptiQ-4bit"
```

The dashboard shows this command in the Claude Code panel and has a copy button.

`ANTHROPIC_BASE_URL` points Claude Code at the local Anthropic-compatible gateway.
`ANTHROPIC_CUSTOM_MODEL_OPTION` makes the Devstral model selectable as a custom
model name.

## Continue / OpenAI-Compatible Clients

When a model is served, point the client at:

```text
http://127.0.0.1:8080/v1
```

Use the exact model id from the profile, for example:

```text
keXjos/Qwen3.8-9B-mlx-4Bit
```

or:

```text
mlx-community/Devstral-Small-2-24B-Instruct-2512-OptiQ-4bit
```

For Continue, open its `config.yaml` and add:

```yaml
name: Local MLX
version: 1.0.0
schema: v1

models:
  - name: Qwen Local
    provider: openai
    model: keXjos/Qwen3.8-9B-mlx-4Bit
    apiBase: http://127.0.0.1:8080/v1
    apiKey: sk-optiq-local
    roles:
      - chat
      - edit
      - apply

  - name: Devstral Local
    provider: openai
    model: mlx-community/Devstral-Small-2-24B-Instruct-2512-OptiQ-4bit
    apiBase: http://127.0.0.1:8080/v1
    apiKey: sk-optiq-local
    roles:
      - chat
      - edit
      - apply
    capabilities:
      - tool_use
```

Use `uv run local-llm serve qwen` before selecting Qwen in Continue, or
`uv run local-llm serve devstral --backend agent` before selecting Devstral.

## Notes

The memory view uses macOS commands such as `vm_stat`, `sysctl`, and `ps`. It is a
practical fit warning, not a perfect VRAM profiler: Apple Silicon uses unified
memory, so the important signals are memory pressure, swap, and the model process
RSS together.
