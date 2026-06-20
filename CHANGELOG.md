# Changelog

All notable changes to this project are documented here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

## [0.1.0] — initial release
### Added
- `dispatch.py` — zero-dependency CLI that delegates coding jobs to a local LLM.
- Auto-detection of **Ollama** (`:11434`) and **LM Studio** (`:1234`) backends.
- Self-correcting loop: generate → write files → run verify command → retry on failure.
- Strict-JSON model protocol (`files`, `verify`, `done`, `notes`).
- **Smart model selection**: role-based ranking (`coding` / `reasoning` / `general`),
  embedding/non-chat exclusion, experimental-merge penalty. `--list-models` to inspect.
- Path-escape guard and verify timeout for safety.
- **Claude Code skill** (`/local-dispatch`) so Claude orchestrates and reviews instead
  of doing the work itself.
- Docs: README (SEO), ARCHITECTURE, CONTRIBUTING, LICENSE (MIT), config.json.
