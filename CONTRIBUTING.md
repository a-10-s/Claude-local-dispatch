# Contributing to Claude-Local-Dispatch

Thanks for helping make Claude a leaner, cheaper orchestrator! 🎉

## Ground rules
- Keep `dispatch.py` **dependency-free** (Python standard library only). The zero-install promise is a core feature.
- Keep the **final summary small** — anything that bloats what Claude reads defeats the token-saving purpose.
- Match the existing code style (type hints, short helpers, comments that explain *why*).

## Dev setup
```bash
git clone https://github.com/a-10-s/Claude-local-dispatch
cd Claude-local-dispatch
# start Ollama (ollama serve) or LM Studio's local server, load a coding model
python dispatch.py --list-models --role coding      # sanity check
python dispatch.py "write fizzbuzz with a test" --dry-run
```

## Good first issues
See the **Roadmap** in the [README](README.md#-roadmap--ideas). High-value picks:
- Token-savings report (`--report`)
- MCP server mode (expose dispatch as a native Claude tool)
- Verify-command presets per language (`pytest` / `npm test` / `cargo test`)
- Context injection for refactor tasks

## Submitting a PR
1. Fork & branch (`feat/<thing>` or `fix/<thing>`).
2. Test against **both** Ollama and LM Studio if you touch backend code.
3. Update the README/docs if behavior changes.
4. Open the PR with a clear description and, ideally, a before/after of tokens or behavior.

## Reporting bugs
Open an issue with: your backend (Ollama/LM Studio), model id, the command you ran, and the JSON summary / error.
