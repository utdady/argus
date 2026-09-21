# Tech stack

Choices for V0 and what we explicitly defer. Prefer interfaces over lock-in.

## V0 choices (brain slice)

| Layer | Choice | Notes |
|-------|--------|--------|
| Language | Python 3.11+ | `pyproject.toml` package `argus` |
| Client | CLI + browser (`argus/static`) | Local only on 127.0.0.1 |
| API | FastAPI REST (`python -m argus.api`) | Chat + confirm; WebSocket later |
| Orchestrator | In-process ReAct loop | No agent framework |
| LLM | Ollama via OpenAI-compatible `LLMProvider` | Default `qwen3:4b`; `base_url` swap for hosted |
| STT | faster-whisper `tiny` on CPU | Optional `[voice]`; keeps GPU for Ollama |
| TTS | edge-tts British neural (default) / SAPI fallback | `en-GB-RyanNeural` butler-like; needs network |
| Voice UX | Browser hold-to-talk | `/api/voice` multipart |
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


## Context window note

`OpenAICompatProvider` sends `extra_body.options.num_ctx`. Confirm in Ollama that the loaded model actually uses 4096; some `/v1` paths ignore `options`. Hosted OpenAI-compatible endpoints may reject the field — strip it when `base_url` is not local.

## Hardware (modest local GPU)

- ~8 GB system RAM + ~6 GB VRAM
- Default model class: **~4B** quantized; **8B** stretch eval only
- `ARGUS_NUM_CTX≈4096`

## Explicitly not this slice

| Item | Why defer |
|------|-----------|
| WebSocket streaming | REST is enough for V0 chat |
| Phone clients | After laptop browser |
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
