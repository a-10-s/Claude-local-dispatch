#!/usr/bin/env python3
"""
local-dispatch MCP server — expose the local-LLM dispatcher as NATIVE Claude tools.

Instead of going through a skill + Bash hop, Claude (or any MCP client) calls the
`dispatch` and `list_models` tools directly. The heavy generate->write->verify->retry
loop still runs entirely on your machine against Ollama / LM Studio; Claude only
receives the compact JSON summary.

Transport: stdio, newline-delimited JSON-RPC 2.0 (the MCP stdio convention).
Dependencies: NONE — Python standard library only (no `pip install mcp` needed).

Register with Claude Code (one of):
  claude mcp add local-dispatch -- python /path/to/mcp_server.py
or add to ~/.claude.json / .mcp.json:
  { "mcpServers": { "local-dispatch": {
      "command": "python", "args": ["/path/to/mcp_server.py"] } } }
"""
from __future__ import annotations

import json
import sys
from types import SimpleNamespace

# Reuse the dispatcher logic. mcp_server.py sits next to dispatch.py.
import dispatch as D

SERVER_NAME = "local-dispatch"
SERVER_VERSION = "0.1.0"
DEFAULT_PROTOCOL = "2024-11-05"

# --------------------------------------------------------------------------- #
# Tool schemas
# --------------------------------------------------------------------------- #
ROLE_ENUM = ["coding", "reasoning", "general"]

TOOLS = [
    {
        "name": "dispatch",
        "description": (
            "Delegate a coding/text job to the user's LOCAL LLM (Ollama or LM Studio) "
            "and only return a short summary. The full generate->write files->run "
            "verify->retry loop runs locally; use this instead of writing the code "
            "yourself when the goal is to save tokens. Returns a JSON summary with "
            "status ('done'|'gave_up'), the files written, and attempt history."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {"type": "string",
                         "description": "The job description for the local model."},
                "role": {"type": "string", "enum": ROLE_ENUM, "default": "coding",
                         "description": "Task type; selects the best-ranked installed model."},
                "workdir": {"type": "string", "default": "./dispatch-out",
                            "description": "Directory where generated files are written."},
                "max_retries": {"type": "integer", "default": 4,
                                "description": "Local fix-up loops before giving up."},
                "backend": {"type": "string",
                            "description": "Prefer 'ollama' or 'lmstudio' (else auto-detect)."},
                "model": {"type": "string",
                          "description": "Force a specific model id (overrides role ranking)."},
                "dry_run": {"type": "boolean", "default": False,
                            "description": "Preview without writing files or running verify."},
            },
            "required": ["task"],
        },
    },
    {
        "name": "list_models",
        "description": (
            "List the local models installed on the detected backend, ranked for a "
            "given role (coding/reasoning/general). Non-chat models (embeddings, etc.) "
            "are excluded. Use to announce which local model a dispatch will pick."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "role": {"type": "string", "enum": ROLE_ENUM, "default": "coding"},
                "backend": {"type": "string",
                            "description": "Prefer 'ollama' or 'lmstudio' (else auto-detect)."},
            },
        },
    },
]


# --------------------------------------------------------------------------- #
# Tool implementations
# --------------------------------------------------------------------------- #
def tool_dispatch(arguments: dict) -> dict:
    args = SimpleNamespace(
        role=arguments.get("role", "coding"),
        model=arguments.get("model"),
        backend=arguments.get("backend"),
        workdir=arguments.get("workdir", "./dispatch-out"),
        max_retries=int(arguments.get("max_retries", 4)),
        verify_timeout=int(arguments.get("verify_timeout", 120)),
        temperature=float(arguments.get("temperature", 0.2)),
        dry_run=bool(arguments.get("dry_run", False)),
    )
    task = arguments.get("task")
    if not task:
        raise ValueError("'task' is required.")
    return D.dispatch(task, args)


def tool_list_models(arguments: dict) -> dict:
    role = arguments.get("role", "coding")
    backend = D.detect_backend(arguments.get("backend"))
    ranked = D.rank_models(backend.get("models", []), role)
    excluded = [m for m in backend.get("models", []) if D.score_model(m, role) < 0]
    return {
        "backend": backend["name"],
        "role": role,
        "best": ranked[0][0] if ranked else None,
        "ranked": [{"model": m, "score": s} for m, s in ranked],
        "excluded": excluded,
    }


TOOL_IMPLS = {"dispatch": tool_dispatch, "list_models": tool_list_models}


# --------------------------------------------------------------------------- #
# JSON-RPC / MCP plumbing (stdio, newline-delimited)
# --------------------------------------------------------------------------- #
def log(msg: str) -> None:
    print(f"[mcp:{SERVER_NAME}] {msg}", file=sys.stderr, flush=True)


def send(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def result_msg(req_id, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def error_msg(req_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def handle(req: dict):
    """Return a response dict, or None for notifications (no reply)."""
    method = req.get("method")
    req_id = req.get("id")
    params = req.get("params") or {}

    if method == "initialize":
        proto = params.get("protocolVersion", DEFAULT_PROTOCOL)
        return result_msg(req_id, {
            "protocolVersion": proto,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        })

    if method in ("notifications/initialized", "initialized"):
        return None  # notification, no response

    if method == "ping":
        return result_msg(req_id, {})

    if method == "tools/list":
        return result_msg(req_id, {"tools": TOOLS})

    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        impl = TOOL_IMPLS.get(name)
        if impl is None:
            return error_msg(req_id, -32602, f"Unknown tool: {name}")
        try:
            log(f"tools/call {name} {json.dumps(arguments)[:120]}")
            payload = impl(arguments)
            text = json.dumps(payload, indent=2)
            return result_msg(req_id, {
                "content": [{"type": "text", "text": text}],
                "isError": False,
            })
        except SystemExit as e:  # detect_backend raises this when no backend is up
            return result_msg(req_id, {
                "content": [{"type": "text", "text": str(e)}],
                "isError": True,
            })
        except Exception as e:  # noqa: BLE001 — surface any tool error to the client
            return result_msg(req_id, {
                "content": [{"type": "text", "text": f"{type(e).__name__}: {e}"}],
                "isError": True,
            })

    # Unknown method
    if req_id is not None:
        return error_msg(req_id, -32601, f"Method not found: {method}")
    return None


def main() -> None:
    log(f"started (stdio). version {SERVER_VERSION}")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            send(error_msg(None, -32700, "Parse error"))
            continue
        try:
            resp = handle(req)
        except Exception as e:  # noqa: BLE001
            resp = error_msg(req.get("id"), -32603, f"Internal error: {e}")
        if resp is not None:
            send(resp)
    log("stdin closed; exiting.")


if __name__ == "__main__":
    main()
