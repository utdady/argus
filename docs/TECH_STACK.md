# Tech stack

Choices for V0 and what we explicitly defer. Prefer interfaces over lock-in.

## V0 choices (brain slice)

| Layer | Choice | Notes |
|-------|--------|--------|
| Language | Python 3.11+ | `pyproject.toml` package `argus` |
| Client | CLI (`python -m argus.cli`) | FastAPI / browser deferred |
| Orchestrator | In-process ReAct loop | No agent framework |
| LLM | Ollama via OpenAI-compatible `LLMProvider` | Default `qwen3:4b`; `base_url` swap for hosted |
| STT / TTS | Deferred | After text brain is solid |
| Voice UX | Deferred | Push-to-talk later |
| DB | SQLite + FTS5 | Notes, sessions, audit, pending confirms |
| Vector memory | Deferred | FTS first |
| Config | `.env` / `.env.example` | Secrets never committed |
| Packaging | venv + `pip install -e .` | Docker later |

## Interfaces (must stay)

```text
LLMProvider.complete(messages, tools) -> Message
# Later: SpeechToText, TextToSpeech, stream()
```

Swap local Ollama ↔ hosted OpenAI-compatible endpoint via `ARGUS_LLM_BASE_URL` only — **never** silent failover.

## Hardware (ASUS)

- ~8 GB system RAM + ~6 GB VRAM
- Default model class: **~4B** quantized; **8B** stretch eval only
- `ARGUS_NUM_CTX≈4096`

## Explicitly not this slice

| Item | Why defer |
|------|-----------|
| FastAPI / WebSocket | Prove loop in CLI first |
| Browser / phone clients | After API |
| Weather / web_search | Keep V0 offline |
| Real app launch | Dry-run confirm only |
| PostgreSQL / vectors | Premature |
| Home Assistant | After tool + permission loop |
| LAN Ollama exposure | No auth; use future API |
| Agent frameworks | Unnecessary for V0 |

## Later stack (target, not committed)

| Layer | Candidate |
|-------|-----------|
| API | FastAPI + WebSocket |
| DB | PostgreSQL (+ pgvector optional) |
| Deploy | Docker Compose on home server |
| Home | Home Assistant as a **tool adapter** |
| Remote | Secure tunnel; cloud as gateway only |
