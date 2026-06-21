# Advanced features

These six features extend the core dispatcher. Each lives in its own
standard-library module next to `dispatch.py` and is wired into the CLI (and,
through `dispatch.py`, the MCP `dispatch` tool). They degrade gracefully: if a
module is missing, the flag becomes a no-op and the core loop still runs.

> **Meta note:** features #3–#8 were implemented **by a local model** (`qwen3-coder-30b`
> via LM Studio) using this very tool — `local-dispatch` building `local-dispatch`.
> Each module was generated with a self-test verify command and reviewed before integration.

## #3 Context injection — `--context`
`context.py` reads existing files and formats them into the prompt so the model can
**edit/refactor** instead of only creating new files.

```bash
python dispatch.py "add a farewell() function to greet.py" --context "greet.py" --workdir ./src
```
- Accepts comma-separated files/globs, resolved relative to `--workdir` first.
- Paths are relabeled relative to the workdir so edited files land in place (no dir doubling).
- Total context is capped (default 24k chars) with a truncation note.

## #4 Task decomposition — `--decompose`
`decompose.py` asks the local model to split a big task into ordered sub-tasks
(`id`, `title`, `description`, `depends_on`), then dispatches each in turn.

```bash
python dispatch.py "build a small FastAPI todo service with tests" --decompose --workdir ./app
```
Returns a combined summary: `status` (`done`/`partial`), the `plan`, and per-sub-task `results`.

## #5 Verify presets — `--auto-verify`
`presets.py` auto-detects a verify command when the model supplies none:
`pytest` (Python), `npm test` (Node), `cargo test` (Rust), `go test ./...` (Go).

```bash
python dispatch.py "write a module and tests" --auto-verify --workdir ./pkg
```

## #6 Result cache — `--cache`
`cache.py` stores successful results keyed by a sha256 of `(task, model, role)` under
`.dispatch-cache/`. An identical re-run returns instantly with `"cached": true` and **0 new tokens**.

```bash
python dispatch.py "scaffold a CLI" --cache --workdir ./out   # 2nd run is instant
```

## #7 Multi-model voting — `--vote`
`voting.py` runs the task across several models, scores each candidate with a judge
model, and picks the best **model** to run the full dispatch with.

```bash
python dispatch.py "tricky algorithm" --vote "qwen3-coder-30b,codestral-22b-v0.1" --workdir ./out
```

## #8 Ollama auto-pull — `--pull-if-missing`
`pull.py` checks `ollama` for the chosen model and runs `ollama pull <model>` if it's
absent (Ollama backend only). No-op on LM Studio.

```bash
python dispatch.py "write fizzbuzz" --backend ollama --pull-if-missing --workdir ./out
```

## Combining
Flags compose, e.g. cache + auto-verify + context:
```bash
python dispatch.py "refactor utils.py for readability" \
  --context "utils.py" --auto-verify --cache --workdir ./src
```
