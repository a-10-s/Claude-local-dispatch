#!/usr/bin/env python3
"""
local-dispatch — Delegate coding jobs to a LOCAL LLM (Ollama / LM Studio).

The whole generate -> write -> verify -> retry loop runs on YOUR machine,
talking to your local model. Only a short final summary is meant to be
surfaced back to Claude (or you), so the expensive tokens stay local.

Usage:
    python dispatch.py "build a FastAPI todo API with tests"
    python dispatch.py --task-file job.md --workdir ./out
    python dispatch.py --dry-run "refactor utils.py"      # no files written

Exit code 0 = job verified/done, 1 = gave up after retries.
The last line of stdout is always a JSON summary (machine-readable).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error

# --------------------------------------------------------------------------- #
# Backend auto-detection
# --------------------------------------------------------------------------- #
# Both Ollama and LM Studio expose an OpenAI-compatible /v1/chat/completions.
BACKENDS = [
    {
        "name": "LM Studio",
        "base": "http://localhost:1234/v1",
        "probe": "http://localhost:1234/v1/models",
    },
    {
        "name": "Ollama",
        "base": "http://localhost:11434/v1",
        "probe": "http://localhost:11434/v1/models",
    },
]


def _http_json(url: str, payload: dict | None = None, timeout: int = 600) -> dict:
    """Minimal POST/GET JSON helper (stdlib only, no deps to install)."""
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers,
                                 method="POST" if data else "GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


# --------------------------------------------------------------------------- #
# Model selection — rank the user's INSTALLED models for the task at hand.
# Roles let Claude (or you) say "this is a coding job" and get the best local
# coder, without hard-coding a model name that may not be installed.
# --------------------------------------------------------------------------- #
import re

# Models that must never be used for chat/codegen.
EXCLUDE_HINTS = ("embed", "embedding", "rerank", "reranker", "whisper", "tts", "clip")

ROLE_HINTS = {
    "coding":    ("coder", "code", "codestral", "deepseek-coder", "starcoder", "codellama"),
    "reasoning": ("reasoning", "thinking", "-r1", "deepseek-r1", "qwq", "reasoner", "think"),
    "general":   (),
}


def parse_params(model_id: str) -> float:
    """Best-effort parameter count (in billions) parsed from the model id."""
    # Prefer total params like '30b', '14b'; ignore tiny active-param 'a3b' tags.
    matches = re.findall(r"(\d+(?:\.\d+)?)\s*b\b", model_id.lower())
    nums = [float(m) for m in matches]
    # Drop obvious MoE active-param tags (a3b/a4b) which appear after a dash.
    big = [n for n in nums if n >= 1]
    return max(big) if big else 0.0


def score_model(model_id: str, role: str) -> float:
    """Higher = better fit for the role. Negative = disqualified."""
    mid = model_id.lower()
    if any(h in mid for h in EXCLUDE_HINTS):
        return -1.0
    score = parse_params(mid)  # size as the baseline (bigger ~ more capable)
    for hint in ROLE_HINTS.get(role, ()):
        if hint in mid:
            score += 100  # strong boost for role match
            break
    # Penalize experimental/merged frankenmodels so clean, purpose-built models
    # win close calls (more predictable for an automated verify loop).
    if any(t in mid for t in ("uncensored", "heretic", "abliterated", "neo", "imatrix")):
        score -= 18
    return score


def rank_models(models: list[str], role: str) -> list[tuple[str, float]]:
    ranked = sorted(((m, score_model(m, role)) for m in models),
                    key=lambda x: x[1], reverse=True)
    return [(m, s) for m, s in ranked if s >= 0]


def select_model(backend: dict, role: str, explicit: str | None) -> str:
    if explicit:
        return explicit
    ranked = rank_models(backend.get("models", []), role)
    if ranked:
        return ranked[0][0]
    return backend["models"][0] if backend.get("models") else "local-model"


def detect_backend(preferred: str | None = None) -> dict:
    """Return the first reachable backend, or raise if none are up."""
    order = BACKENDS
    if preferred:
        order = sorted(BACKENDS, key=lambda b: preferred.lower() not in b["name"].lower())
    for b in order:
        try:
            models = _http_json(b["probe"], timeout=3)
            ids = [m.get("id") for m in models.get("data", [])]
            b = dict(b)
            b["models"] = ids
            return b
        except Exception:
            continue
    raise SystemExit(
        "No local LLM backend reachable.\n"
        "  - Start Ollama (ollama serve) or LM Studio (enable the local server).\n"
        "  - Checked: localhost:1234 (LM Studio), localhost:11434 (Ollama)."
    )


# --------------------------------------------------------------------------- #
# The protocol: we force the local model to answer in strict JSON so the
# loop is fully automatable. No fragile markdown parsing.
# --------------------------------------------------------------------------- #
SYSTEM_PROMPT = """\
You are a coding worker. You complete the user's task by emitting files and an \
optional shell command to verify your work.

Respond with ONE JSON object and nothing else. Schema:
{
  "reasoning": "<brief plan, <=2 sentences>",
  "files": [{"path": "relative/path.py", "content": "<full file content>"}],
  "verify": "<shell command to prove it works, or null>",
  "done": <true if the task is fully complete, else false>,
  "notes": "<what you did / what's left>"
}

Rules:
- Always return COMPLETE file contents, never diffs or ellipses.
- Prefer a verify command that exits non-zero on failure (tests, build, lint).
- If a previous attempt failed, the failure output is provided; FIX it.
- Keep going until done=true and verify passes.
"""


def chat(backend: dict, model: str, messages: list[dict], temperature: float) -> str:
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "stream": False,
    }
    resp = _http_json(backend["base"] + "/chat/completions", payload)
    return resp["choices"][0]["message"]["content"]


def parse_model_json(text: str) -> dict:
    """Extract the JSON object even if the model wraps it in prose/fences."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("Model did not return JSON.")
    return json.loads(text[start:end + 1])


def write_files(files: list[dict], workdir: str, dry_run: bool) -> list[str]:
    written = []
    for f in files:
        path = os.path.normpath(os.path.join(workdir, f["path"]))
        if not path.startswith(os.path.normpath(workdir)):
            raise ValueError(f"Refusing path-escape: {f['path']}")
        written.append(path)
        if dry_run:
            continue
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(f["content"])
    return written


def run_verify(cmd: str, workdir: str, timeout: int) -> tuple[bool, str]:
    try:
        proc = subprocess.run(cmd, shell=True, cwd=workdir, timeout=timeout,
                              capture_output=True, text=True)
        out = (proc.stdout + proc.stderr)[-4000:]
        return proc.returncode == 0, out
    except subprocess.TimeoutExpired:
        return False, f"verify timed out after {timeout}s"


# --------------------------------------------------------------------------- #
# Main loop
# --------------------------------------------------------------------------- #
def dispatch(task: str, args) -> dict:
    backend = detect_backend(args.backend)
    model = select_model(backend, args.role, args.model)
    log = lambda m: print(f"[dispatch] {m}", file=sys.stderr, flush=True)

    log(f"backend = {backend['name']}  role = {args.role}  model = {model}")
    os.makedirs(args.workdir, exist_ok=True)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": task},
    ]

    history = []
    for attempt in range(1, args.max_retries + 1):
        log(f"attempt {attempt}/{args.max_retries} — asking local model...")
        t0 = time.time()
        raw = chat(backend, model, messages, args.temperature)
        try:
            step = parse_model_json(raw)
        except Exception as e:
            log(f"bad JSON ({e}); nudging model.")
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user",
                             "content": "That was not valid JSON. Re-send ONLY the JSON object."})
            continue

        files = step.get("files", []) or []
        written = write_files(files, args.workdir, args.dry_run)
        log(f"wrote {len(written)} file(s) in {time.time()-t0:.1f}s — {step.get('notes','')[:80]}")

        verify_cmd = step.get("verify")
        verify_ok, verify_out = True, ""
        if verify_cmd and not args.dry_run:
            log(f"verify: {verify_cmd}")
            verify_ok, verify_out = run_verify(verify_cmd, args.workdir, args.verify_timeout)
            log("verify PASSED" if verify_ok else "verify FAILED")

        history.append({
            "attempt": attempt, "files": [f["path"] for f in files],
            "verify": verify_cmd, "verify_ok": verify_ok,
        })

        if step.get("done") and verify_ok:
            return {"status": "done", "attempts": attempt, "model": model,
                    "backend": backend["name"], "files": [f["path"] for f in files],
                    "notes": step.get("notes", ""), "history": history}

        # Feed the failure / incompleteness back for the next attempt.
        feedback = []
        if not verify_ok:
            feedback.append(f"verify command FAILED. Output:\n{verify_out}")
        if not step.get("done"):
            feedback.append("Task not marked done. Continue.")
        messages.append({"role": "assistant", "content": raw})
        messages.append({"role": "user", "content": "\n".join(feedback)})

    return {"status": "gave_up", "attempts": args.max_retries, "model": model,
            "backend": backend["name"], "notes": "Max retries reached.",
            "history": history}


def main():
    p = argparse.ArgumentParser(description="Delegate a coding job to a local LLM.")
    p.add_argument("task", nargs="?", help="The job description.")
    p.add_argument("--task-file", help="Read the job description from a file.")
    p.add_argument("--workdir", default="./dispatch-out", help="Where files are written.")
    p.add_argument("--backend", help="Prefer 'ollama' or 'lmstudio' (else auto-detect).")
    p.add_argument("--model", help="Force a specific model id (overrides --role ranking).")
    p.add_argument("--role", default="coding", choices=["coding", "reasoning", "general"],
                   help="Task type; picks the best-ranked installed model (default: coding).")
    p.add_argument("--list-models", action="store_true",
                   help="List installed models ranked for --role, then exit.")
    p.add_argument("--max-retries", type=int, default=4)
    p.add_argument("--verify-timeout", type=int, default=120)
    p.add_argument("--temperature", type=float, default=0.2)
    p.add_argument("--dry-run", action="store_true", help="Don't write files or run verify.")
    args = p.parse_args()

    if args.list_models:
        backend = detect_backend(args.backend)
        print(f"Backend: {backend['name']}   (ranked for role='{args.role}')\n")
        ranked = rank_models(backend.get("models", []), args.role)
        for i, (m, s) in enumerate(ranked):
            mark = "  <- best" if i == 0 else ""
            print(f"  {s:6.1f}  {m}{mark}")
        excluded = [m for m in backend.get("models", []) if score_model(m, args.role) < 0]
        if excluded:
            print("\n  excluded (non-chat):", ", ".join(excluded))
        sys.exit(0)

    task = args.task
    if args.task_file:
        with open(args.task_file, encoding="utf-8") as fh:
            task = fh.read()
    if not task:
        p.error("Provide a task string or --task-file.")

    result = dispatch(task, args)
    # Last stdout line is always the JSON summary (what Claude/you reviews).
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["status"] == "done" else 1)


if __name__ == "__main__":
    main()
