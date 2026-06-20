# MCP mode — Claude calls dispatch as a native tool

`mcp_server.py` exposes the dispatcher as a **Model Context Protocol** server, so
Claude Code (or any MCP client) can call `dispatch` and `list_models` as **native
tools** — no skill + Bash hop. It's pure Python standard library: **no `pip install`**.

## Tools exposed

| Tool | What it does |
|------|--------------|
| `dispatch` | Run a job on the local model (generate → write → verify → retry) and return a JSON summary. Args: `task` (required), `role`, `workdir`, `max_retries`, `backend`, `model`, `dry_run`. |
| `list_models` | List installed models ranked for a `role`, with non-chat models excluded. |

## Register with Claude Code

**Option A — CLI:**
```bash
claude mcp add local-dispatch -- python /absolute/path/to/Claude-local-dispatch/mcp_server.py
```

**Option B — config file.** Copy `.mcp.json.example` to `.mcp.json` (project-local) or
merge into `~/.claude.json` (global), set the absolute path, and restart Claude Code:
```json
{
  "mcpServers": {
    "local-dispatch": {
      "command": "python",
      "args": ["/absolute/path/to/Claude-local-dispatch/mcp_server.py"]
    }
  }
}
```

After restart, verify with `/mcp` inside Claude Code — you should see `local-dispatch`
connected with two tools.

## Using it

Just ask Claude naturally — *"dispatch this to my local model"* — and it calls the
`dispatch` tool. Or be explicit about the role: *"use list_models to show my best
coding model, then dispatch the job."*

## Skill vs MCP — which to use?

| | Skill (`/local-dispatch`) | MCP (`dispatch` tool) |
|---|---|---|
| Setup | copy a folder | register a server + restart |
| Invocation | `/local-dispatch` then Bash | native tool call |
| Token overhead | reads skill + shells out | lower — direct tool call |
| Best for | quick start, no restart | the cleanest, lowest-overhead path |

They can coexist. The MCP tool is the recommended path once set up.

## Protocol notes (for contributors)

- Transport: **stdio**, newline-delimited JSON-RPC 2.0 (one JSON object per line).
- Handshake: `initialize` (echoes the client's `protocolVersion`, defaults to
  `2024-11-05`) → client sends `notifications/initialized` (no reply) → `tools/list`
  → `tools/call`.
- All logging goes to **stderr**; **stdout carries only JSON-RPC** (critical — any
  stray stdout print corrupts the stream).
- `tools/call` returns `{ content: [{type:"text", text: <json>}], isError: bool }`.
- Backend-down and tool exceptions are returned as `isError: true` results, never
  crash the server.
- Smoke test: `python tests/mcp_smoke_test.py` (drives the server over a pipe).
