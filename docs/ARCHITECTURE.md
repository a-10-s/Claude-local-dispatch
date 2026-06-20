# Architecture

`Claude-Local-Dispatch` is intentionally small: one Python file, the standard
library, and a Claude Code skill that tells Claude to use it. This document
explains the moving parts and the design decisions behind them.

## The token-saving principle

The expensive part of an LLM coding session is the **iteration**: drafts, failed
tests, fix-ups, re-runs. If each of those round-trips through Claude's context,
you pay input tokens for all of it.

Claude-Local-Dispatch keeps that entire loop **inside a local process** talking to
`localhost`. Claude is invoked exactly twice per job:

1. **Before** — to classify the task and launch the dispatcher.
2. **After** — to review a compact JSON summary plus any files worth checking.

Everything between those two points is free local compute.

## Components

| File | Role |
|------|------|
| `dispatch.py` | The worker: detect backend → rank/pick model → loop (generate, write, verify, retry) → emit JSON summary. |
| `config.json` | Defaults and role/exclude hint lists (documentation + future config loading). |
| `skills/local-dispatch/SKILL.md` | Teaches Claude Code *how to delegate and review* instead of doing the work itself. |
| `mcp_server.py` | Optional MCP server (stdio, pure stdlib) exposing `dispatch` + `list_models` as native Claude tools. Reuses `dispatch.py`. See [MCP.md](MCP.md). |

## The loop

```
detect_backend()        # GET /v1/models on :1234 (LM Studio) and :11434 (Ollama)
   │
select_model()          # rank installed models for the role; exclude embeddings
   │
for attempt in 1..max_retries:
   chat()               # POST /v1/chat/completions, force strict-JSON reply
   parse_model_json()   # tolerate fences/prose, extract the JSON object
   write_files()        # path-escape guarded write into --workdir
   run_verify()         # run the model's verify command (tests/build/lint)
   if done and verify_ok: return {status: "done", ...}
   else: append failure output to the conversation and retry
return {status: "gave_up", ...}
```

## The model protocol

The local model is instructed (via the system prompt) to reply with **one JSON
object only**:

```json
{
  "reasoning": "brief plan",
  "files": [{"path": "rel/path.py", "content": "full file"}],
  "verify": "python -m pytest -q",
  "done": true,
  "notes": "what I did / what's left"
}
```

Why JSON instead of parsing markdown code fences?
- **Deterministic** — no guessing which fence is which file.
- **Self-verifying** — the model supplies the command that proves its own work.
- **Automatable** — the loop can act on `done` / `verify` without human help.

`parse_model_json()` is forgiving: it strips ``` fences and extracts the outermost
`{...}` so a chatty model still works.

## Model ranking

`score_model(model_id, role)`:
- Baseline = parameter count parsed from the id (`30b` → 30).
- `+100` if the id contains a role hint (`coder`, `codestral`, `reasoning`, …).
- `-18` for experimental merges (`uncensored`, `heretic`, `imatrix`, …) so clean,
  purpose-built models win close calls (more predictable for an automated loop).
- `< 0` (disqualified) for non-chat models (`embed`, `rerank`, `tts`, …).

`select_model()` returns the explicit `--model` if given, else the top-ranked model
for the role, else the first available.

## Safety

- **Path-escape guard**: `write_files()` normalizes each path and refuses anything
  that resolves outside `--workdir`.
- **Verify timeout**: the verify subprocess is killed after `--verify-timeout` seconds.
- **No cloud egress from the loop**: the worker talks only to your local backend.

## Extending

- **New backend**: add an entry to `BACKENDS` with a `base` and `probe` URL.
- **New role**: add hints to `ROLE_HINTS`.
- **MCP mode** (shipped): `mcp_server.py` wraps `dispatch()` in a stdio JSON-RPC MCP
  server so Claude calls it as a native tool instead of via the skill + Bash. Pure
  stdlib — no SDK. See [MCP.md](MCP.md).
