<div align="center">

# 🪄 Claude-Local-Dispatch

### Make Claude Code delegate the work to your **local LLM** — and only pay tokens to review the result.

**Save Claude / Anthropic API tokens by offloading coding jobs to [Ollama](https://ollama.com) or [LM Studio](https://lmstudio.ai) running on your own GPU.**

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![Zero dependencies](https://img.shields.io/badge/dependencies-0-brightgreen.svg)](#requirements)
[![Works with Claude Code](https://img.shields.io/badge/Claude%20Code-skill-8A2BE2.svg)](https://docs.claude.com/en/docs/claude-code)
[![Ollama](https://img.shields.io/badge/Ollama-supported-black.svg)](https://ollama.com)
[![LM Studio](https://img.shields.io/badge/LM%20Studio-supported-black.svg)](https://lmstudio.ai)

</div>

---

> **TL;DR** — `Claude-Local-Dispatch` is a tiny (single-file, zero-dependency) Python tool **plus a Claude Code skill** that lets **Claude act as the orchestrator and reviewer** while your **local model does all the heavy generation**. The full *generate → write files → run tests → fix → repeat* loop runs **on your machine**, talking to your local model. Claude only ever sees a short JSON summary — so the expensive tokens stay local and your bill drops.

```
You:  /local-dispatch "build a FastAPI todo API with pytest tests"
        │
Claude ─┤  picks the best LOCAL coding model you have installed
        │  runs dispatch.py  ──►  your GPU loops until tests pass
        │
        ▼
Claude reviews ONE short summary  ✅  (a few tokens, not thousands)
```

## Table of Contents
- [Why this exists](#-why-this-exists)
- [How it saves tokens](#-how-it-actually-saves-tokens)
- [Features](#-features)
- [Requirements](#-requirements)
- [Install](#-install)
- [Usage](#-usage)
- [Smart model selection](#-smart-model-selection)
- [MCP mode (native tool)](#-mcp-mode--claude-calls-it-as-a-native-tool)
- [How it works](#-how-it-works-architecture)
- [Honest limitations](#-honest-limitations)
- [Roadmap](#-roadmap--ideas)
- [FAQ](#-faq)
- [Contributing](#-contributing)
- [License](#-license)

---

## 💡 Why this exists

[Claude Code](https://docs.claude.com/en/docs/claude-code) is brilliant at **planning, judgment, and catching bugs** — but every token costs money. Meanwhile, a 7B–70B model on your own GPU (via **Ollama** or **LM Studio**) is **free to run** and increasingly capable at routine code generation.

`Claude-Local-Dispatch` splits the work along exactly that line:

| Phase | Who does it | Token cost |
|-------|-------------|-----------:|
| Understand the request, choose the approach | **Claude** | small |
| Generate the bulk code, iterate on test failures | **Your local LLM** | **$0** |
| Review the final result, catch real bugs | **Claude** | small |

The result: Claude becomes a **token-efficient orchestrator** of your own hardware.

## 🔑 How it *actually* saves tokens

The naive idea — "Claude calls my local model for each step" — **does not** save much, because every intermediate result re-enters Claude's context and costs input tokens.

The trick this tool uses: **the entire iterative loop runs inside a local Python process talking to `localhost`.** Every draft, every failed test, every fix-up happens *without Claude in the loop*. None of that noise touches Claude's context. Claude spends tokens only on:

1. Reading the small skill file (once), and
2. Reviewing the final **JSON summary** + the handful of files it needs to verify.

> Keep the summary small → savings are real. Let the noise leak back into Claude → savings vanish. The design enforces the former.

## ✨ Features

- 🔌 **Auto-detects** both Ollama (`:11434`) and LM Studio (`:1234`) — no config to start.
- 🧠 **Smart model selection** — ranks *your installed models* by task role (`coding` / `reasoning` / `general`) and picks the best fit. Embedding/non-chat models are automatically excluded.
- ♻️ **Self-correcting loop** — writes files, runs your verify command (tests/build/lint), feeds failures back to the local model, and retries.
- 📦 **Zero dependencies** — pure Python standard library. No `pip install`. Single file.
- 🧩 **Claude Code skill included** — type `/local-dispatch "<job>"` and Claude orchestrates.
- 🛠️ **Native MCP server** — expose `dispatch` + `list_models` as native Claude tools (still **zero dependencies** — MCP over stdio, no SDK).
- 🖥️ **Works standalone too** — use it as a plain CLI with no Claude at all.
- 🔒 **Path-escape guard** — generated files can't be written outside your `--workdir`.
- 💰 **Token-savings report** — every run reports how many tokens ran locally and an estimate of the Claude cost avoided (uses the model's real `usage` counts when available).
- 📊 **Machine-readable output** — the last stdout line is always a JSON summary; exit `0` = done, `1` = gave up.

## 📋 Requirements

- **Python 3.8+** (standard library only — nothing to install)
- One running local backend:
  - **[Ollama](https://ollama.com)** → `ollama serve` (listens on `:11434`)
  - **[LM Studio](https://lmstudio.ai)** → enable the local server (listens on `:1234`)
- A capable model loaded. Great picks: `qwen2.5-coder`, `qwen3-coder`, `deepseek-coder-v2`, `codestral`.

## 📥 Install

```bash
# 1. Clone
git clone https://github.com/a-10-s/Claude-local-dispatch ~/Claude-local-dispatch

# 2. Install the Claude Code skill (so you can type /local-dispatch)
cp -r ~/Claude-local-dispatch/skills/local-dispatch ~/.claude/skills/

# 3. (the skill bundles dispatch.py + config.json, so it's self-contained)
```

Now in Claude Code:

```
/local-dispatch "write a Python rate-limiter with tests"
```

## 🚀 Usage

### Via Claude Code (recommended)
```
/local-dispatch "refactor utils.py for readability and add docstrings"
```
Claude classifies the task, picks your best local model, runs the loop, and reviews the result.

### Standalone CLI (no Claude needed)
```bash
# Auto-detect backend, auto-pick best coding model
python dispatch.py "write a function to parse ISO timestamps, with tests" --workdir ./out

# See which model will be used for a role
python dispatch.py --list-models --role coding

# Force a backend and/or model
python dispatch.py "scaffold a CLI" --backend ollama --model qwen2.5-coder:7b

# Reasoning-heavy task → picks your best reasoning model
python dispatch.py "analyze this algorithm's complexity" --role reasoning --workdir ./out

# Preview without writing files
python dispatch.py "build a todo API" --dry-run
```

### Flags
| Flag | Default | Description |
|------|---------|-------------|
| `--role` | `coding` | `coding` \| `reasoning` \| `general` — picks the best-ranked installed model |
| `--model` | auto | Force a specific model id (overrides ranking) |
| `--backend` | auto | Prefer `ollama` or `lmstudio` |
| `--workdir` | `./dispatch-out` | Where generated files are written |
| `--max-retries` | `4` | Local fix-up loops before giving up |
| `--verify-timeout` | `120` | Seconds allowed for the verify command |
| `--temperature` | `0.2` | Sampling temperature |
| `--price-in` / `--price-out` | `3` / `15` | Claude $/Mtok used for the savings estimate |
| `--dry-run` | off | Don't write files or run verify |
| `--list-models` | — | List installed models ranked for `--role`, then exit |

## 🧠 Smart model selection

You asked the obvious question: *which* local model gets the job?

**Answer: auto-ranked by role, with override.** The tool scores every model you have installed:
- **Role match** (e.g. `coder`/`code`/`codestral` for coding) → big boost
- **Parameter size** → baseline (bigger ≈ more capable)
- **Embedding / non-chat models** → excluded entirely
- **Experimental frankenmerges** (`uncensored`, `heretic`, …) → slight penalty so clean, purpose-built models win close calls

Example on a real machine:
```
$ python dispatch.py --list-models --role coding
   130.0  qwen/qwen3-coder-30b          <- best
   122.0  mistralai/codestral-22b-v0.1
   114.0  qwen2.5-coder-14b-instruct-128k
   ...
   excluded (non-chat): text-embedding-nomic-embed-text-v1.5
```

Claude (or you) just says *“this is a coding job”* and the right local model is chosen automatically. Override anytime with `--model`.

## 🛠 MCP mode — Claude calls it as a native tool

Prefer the lowest-overhead path? Run the included **MCP server** and Claude calls
`dispatch` / `list_models` as **native tools** — no skill + Bash hop. Still pure
standard library, **no `pip install`**.

```bash
# Register with Claude Code (CLI)
claude mcp add local-dispatch -- python /absolute/path/to/Claude-local-dispatch/mcp_server.py
```

Or copy [`.mcp.json.example`](.mcp.json.example) → `.mcp.json`, set the path, restart
Claude Code, and check `/mcp`. Then just say *"dispatch this to my local model"*.

| Tool | Args | Returns |
|------|------|---------|
| `dispatch` | `task` (req), `role`, `workdir`, `max_retries`, `backend`, `model`, `dry_run` | JSON summary (`status`, files, history) |
| `list_models` | `role`, `backend` | ranked installed models for the role |

Full guide: [docs/MCP.md](docs/MCP.md). Skill vs MCP comparison included.

## 💰 Token-savings report

Every dispatch returns a `report` showing how much work stayed off Claude's bill:

```jsonc
"report": {
  "local_prompt_tokens": 230,
  "local_completion_tokens": 185,
  "local_total_tokens": 415,
  "estimated_token_counts": false,        // false = real usage from the backend
  "est_claude_cost_avoided_usd": 0.0035,  // estimate at the configured rate
  "price_basis": { "input_per_mtok": 3.0, "output_per_mtok": 15.0 }
}
```

- Uses the model's **real `usage` counts** when the backend reports them (LM Studio and
  most Ollama builds do); falls back to a `chars/4` estimate otherwise (flagged).
- The dollar figure is an **estimate** of what those tokens *would* have cost on Claude —
  they actually ran locally for **$0** of API spend. Tune the basis to your model/plan:
  ```bash
  python dispatch.py "<job>" --price-in 15 --price-out 75   # e.g. Opus-class rates
  ```
- Small jobs save pennies; a long multi-retry job that would have chewed through Claude's
  context is where it adds up.

## 🏗 How it works (architecture)

```
 ┌─────────────┐   /local-dispatch   ┌──────────────────────────┐
 │  Claude     │ ──────────────────► │  dispatch.py (your PC)    │
 │  Code       │                     │                          │
 │ (orchestr-  │                     │  1. detect backend       │
 │  ator +     │   short JSON        │  2. rank + pick model    │
 │  reviewer)  │ ◄────────────────── │  3. ask local model      │ ◄─┐
 └─────────────┘   summary only      │  4. write files          │   │ loop
                                     │  5. run verify (tests)   │   │ stays
                                     │  6. feed failures back ──┼───┘ LOCAL
                                     └───────────┬──────────────┘
                                                 │ OpenAI-compatible API
                                          ┌──────▼───────┐
                                          │ Ollama / LM  │
                                          │ Studio (GPU) │
                                          └──────────────┘
```

The local model is forced to answer in **strict JSON** (`files`, `verify`, `done`, `notes`) so the loop is fully automatable — no fragile markdown parsing. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for details.

## ⚠️ Honest limitations

- **Your local model is the ceiling.** Weak models fail the verify loop often, and then Claude gets pulled in to fix things (= tokens). Use a strong coding model.
- **Not magic.** For tasks that need judgment more than raw generation, just use Claude directly — the skill will tell you so.
- **Environment matters.** A verify command can fail for reasons unrelated to the code (e.g. a missing test dependency). The skill teaches Claude to distinguish a real bug from an environment issue.
- **Prior art.** Tools like [`aider`](https://github.com/Aider-AI/aider), [Cline](https://github.com/cline/cline), and [Continue](https://github.com/continuedev/continue) already run local-model coding loops. **What's new here is the Claude-Code-skill packaging** — Claude as the orchestrator/reviewer that *delegates* to local compute to cut tokens.

## 🗺 Roadmap / ideas

Contributions welcome on any of these — they turn this from a neat trick into a **serious token optimizer**:

- [x] ~~**MCP server mode** — expose dispatch as a native Claude tool (no Bash hop).~~ ✅ shipped — see [docs/MCP.md](docs/MCP.md)
- [x] ~~**Token-savings report** — estimate tokens (and $) saved per dispatch.~~ ✅ shipped — every run includes a `report`.
- [ ] **Context injection** — pass existing project files to the local model for refactors.
- [ ] **Task decomposition** — split a big job into sub-jobs, each dispatched separately.
- [ ] **Ollama auto-pull** — fetch a recommended model if none suitable is installed.
- [ ] **Result cache** — skip re-running identical jobs.
- [ ] **Multi-model voting** — run 2 local models, let Claude pick the better output.
- [ ] **Per-language verify presets** — auto-pick `pytest` / `npm test` / `cargo test`.

## ❓ FAQ

**Does this remove Claude from the loop entirely?**
No — and that's the point. Claude plans and reviews (where it's worth the tokens); your local model generates (where it's free). You can also use `dispatch.py` fully standalone with no Claude.

**Will it work with my models?**
If your backend exposes an OpenAI-compatible `/v1/chat/completions` (Ollama and LM Studio both do), yes. Run `--list-models` to see what gets picked.

**Is my code sent to the cloud?**
The local loop talks only to `localhost`. Only the final summary (and files you ask Claude to review) ever reach Claude.

**Why JSON output from the model?**
So the loop is deterministic and automatable. Strict JSON beats parsing markdown for files and commands.

## 🤝 Contributing

PRs welcome! See [CONTRIBUTING.md](CONTRIBUTING.md). Good first issues: the roadmap items above, more backends, and verify-command presets.

## 📄 License

[MIT](LICENSE) — use it, fork it, share it freely.

---

<div align="center">

**Keywords:** Claude Code local LLM · save Claude tokens · Anthropic token optimizer · Ollama Claude Code · LM Studio Claude Code · offload to local model · self-hosted AI coding agent · reduce Claude API cost · local model orchestration · qwen coder · deepseek coder · codestral · free AI coding · GPU LLM agent

⭐ **If this saves you tokens, star the repo so others find it.**

</div>
