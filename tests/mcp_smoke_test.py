#!/usr/bin/env python3
"""Smoke test: drive mcp_server.py over stdio with a scripted JSON-RPC client.

Verifies the MCP handshake and a real tools/call against the running backend.
Run from the repo root:  python tests/mcp_smoke_test.py
Exit 0 = all checks passed.
"""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

REQUESTS = [
    {"jsonrpc": "2.0", "id": 1, "method": "initialize",
     "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                "clientInfo": {"name": "smoke", "version": "0"}}},
    {"jsonrpc": "2.0", "method": "notifications/initialized"},  # notification
    {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
     "params": {"name": "list_models", "arguments": {"role": "coding"}}},
]


def main() -> int:
    proc = subprocess.Popen(
        [sys.executable, os.path.join(ROOT, "mcp_server.py")],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, cwd=ROOT,
    )
    payload = "".join(json.dumps(r) + "\n" for r in REQUESTS)
    out, err = proc.communicate(payload, timeout=60)

    responses = [json.loads(l) for l in out.splitlines() if l.strip()]
    by_id = {r.get("id"): r for r in responses}

    ok = True

    def check(name, cond):
        nonlocal ok
        print(("PASS" if cond else "FAIL"), "-", name)
        ok = ok and cond

    # initialize
    init = by_id.get(1, {})
    check("initialize returns serverInfo",
          init.get("result", {}).get("serverInfo", {}).get("name") == "local-dispatch")
    check("initialize echoes protocolVersion",
          init.get("result", {}).get("protocolVersion") == "2024-11-05")

    # notification produced NO response with that shape (we sent 4 msgs, expect 3 responses)
    check("notification got no reply (3 responses for 3 requests)", len(responses) == 3)

    # tools/list
    tl = by_id.get(2, {}).get("result", {}).get("tools", [])
    names = {t["name"] for t in tl}
    check("tools/list exposes dispatch + list_models", {"dispatch", "list_models"} <= names)
    check("dispatch tool has inputSchema with 'task' required",
          "task" in (next(t for t in tl if t["name"] == "dispatch")["inputSchema"]["required"]))

    # tools/call list_models
    call = by_id.get(3, {}).get("result", {})
    check("tools/call returns content array", isinstance(call.get("content"), list))
    if call.get("content"):
        data = json.loads(call["content"][0]["text"])
        check("list_models returned a backend + ranking",
              "backend" in data and "ranked" in data)
        print("   backend:", data.get("backend"), "| best:", data.get("best"))

    print("\nstderr from server:")
    print("  " + "\n  ".join(err.strip().splitlines()[:5]))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
