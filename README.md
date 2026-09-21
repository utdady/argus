# Argus

Personal household AI — one central brain, many devices.

**Current focus:** V0 brain on a local laptop (CLI + browser + Ollama + tools + permissions). Voice comes later.

## Status

| Phase | State |
|-------|--------|
| Docs / architecture | Done (living docs) |
| V0 — laptop brain (CLI) | In progress |
| V0.5 — wake word | Deferred |
| House-wide / multi-user | Later |

See [docs/ROADMAP.md](docs/ROADMAP.md) and [docs/COMPONENTS.md](docs/COMPONENTS.md).

## Docs

| Doc | What it covers |
|-----|----------------|
| [COMPONENTS](docs/COMPONENTS.md) | Parts ledger — status of every module |
| [VISION](docs/VISION.md) | Endgame: household AI OS |
| [BLUEPRINT](docs/BLUEPRINT.md) | System architecture |
| [ORCHESTRATION](docs/ORCHESTRATION.md) | Control loop, tools, permissions |
| [TECH_STACK](docs/TECH_STACK.md) | Chosen stack and deferrals |
| [ROADMAP](docs/ROADMAP.md) | Phased milestones |
| [DIAGRAMS](docs/DIAGRAMS.md) | Mermaid system / flow diagrams |

## Principles

1. **Devices are ears and mouths. The server is the brain.**
2. **Permissions and memory access are enforced in code**, not by prompting the LLM.
3. **Start on one machine.** Scale to rooms and household members later.
4. **Providers are swappable** (STT / LLM / TTS) behind thin interfaces.
5. **No silent cloud failover.** Hosted LLM is an explicit `.env` change only.

## Quick start (V0 brain)

### Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com) installed locally
- A small local model (default intent: `qwen3:4b` — use whatever 3–4B tag you pull)

```bash
ollama pull qwen3:4b
```

If that tag is unavailable, pull another ~4B model and set `ARGUS_MODEL` accordingly.

### Install

```bash
cd argus
python -m venv .venv
# Windows:
.venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env
```

### Chat CLI

```bash
python -m argus.cli
```

Commands inside the REPL:

- normal text → orchestrator turn
- `/confirm yes` or `/confirm no` when a side-effect tool is pending
- `/quit`

### Browser chat (local API)

```bash
python -m argus.api
# or: argus-serve
```

Open [http://127.0.0.1:8787](http://127.0.0.1:8787). Same orchestrator as the CLI (sessions, tools, `/api/confirm` for side-effects). Bound to localhost only.

### Tests (no LLM required)


```bash
pytest
```

### Evals (requires Ollama)

```bash
python -m evals.run_evals
python -m evals.run_evals --model qwen3:4b --limit 10
```

## Running on a modest GPU laptop

Hardware target: **8 GB system RAM + ~6 GB VRAM**.

- Prefer a **~4B** quantized model; treat **8B** as a stretch eval only.
- Keep `ARGUS_NUM_CTX=4096` (or lower) so the context cache does not thrash VRAM.
- Close heavy apps; load **one** Ollama model at a time.
- Expect slow tokens — that is normal on this box.
- Run everything locally for V0. Do not expose Ollama on the LAN (no auth). The local FastAPI app (`python -m argus.api`) is bound to 127.0.0.1.
- Hosted OpenAI-compatible endpoints work via `ARGUS_LLM_BASE_URL`, but only as an **explicit** config change (useful as an eval baseline), never as automatic failover.

## V0 success criteria (this slice)

1. Text CLI chat with tool-backed answers  
2. `remember` / `recall` via SQLite FTS5  
3. `open_application` dry-run requires confirmation  
4. Tool attempts are audited  
5. `pytest` passes; eval harness reports pass rate / latency  

Voice (STT/TTS) is **not** part of this slice. Browser chat over local FastAPI is included.
