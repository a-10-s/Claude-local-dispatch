---
name: local-dispatch
description: Delegate a coding/text job to the user's LOCAL LLM (Ollama or LM Studio) instead of doing it yourself. The local model runs the full generate→write→verify→retry loop on the user's machine; you only review the final JSON summary. Use when the user wants to save Claude tokens by offloading bulk work to local compute, or explicitly says "/local-dispatch" or "dispatch this locally".
---

# local-dispatch

Your job is to **hand work off to the user's local model and only check the result** — NOT to do the work yourself. This keeps expensive generation tokens on the user's machine.

## Step 1 — classify the task, pick a role

Decide the task type and pass it as `--role`:
- `--role coding` — writing/refactoring code, scaffolding, tests (default).
- `--role reasoning` — logic, math, planning, analysis-heavy prose.
- `--role general` — everything else.

The dispatcher ranks the user's **installed** models for that role and picks the best one automatically. Do NOT hard-code a model name unless the user asks for a specific one (then pass `--model <id>`).

Tip: run `python dispatch.py --list-models --role coding` first if you want to see/announce which local model will be used.

## Step 2 — dispatch the job (do NOT write the code yourself)

```bash
python ~/.claude/skills/local-dispatch/dispatch.py "<the user's task>" --role <role> --workdir <target dir>
```

Useful flags:
- `--backend ollama|lmstudio` — force a backend (default: auto-detect both).
- `--model <id>` — force a specific local model (overrides ranking).
- `--dry-run` — preview without writing files.
- `--max-retries N` — local fix-up loops before giving up (default 4).

## Step 3 — review the result (this is where you spend tokens, sparingly)

- The dispatcher prints a **JSON summary** as its last stdout line and writes files into `--workdir`.
- If `status == "done"`: briefly review the produced files for correctness, then report to the user.
- If `status == "gave_up"`: read `history` to see what failed. Distinguish a real code bug from an environment issue (e.g. a missing test dependency — that's not the model's fault). Only take over yourself if the local model genuinely cannot do it, and tell the user you're stepping in (it costs tokens).

## Token discipline (important)

- Do **not** read the full intermediate model chatter — only the final summary + the files you must verify.
- Do **not** silently redo the whole task in your own context unless the local run failed.
- If the task is tiny or needs your judgment more than raw generation, say so — dispatching isn't always worth it.
