# Tech stack

Choices for V0 and what we explicitly defer. Prefer interfaces over lock-in.

## V0 choices

| Layer | Choice | Notes |
|-------|--------|--------|
| Language | Python 3.11+ | Matches planned FastAPI / AI tooling |
| API | FastAPI | REST + WebSocket |
| Orchestrator | In-process Python module | Tool-calling loop; no heavy agent framework yet |
| LLM | API provider behind `LLMProvider` | e.g. OpenAI-compatible; local later |
| STT | faster-whisper (local) | Laptop GPU/CPU as available |
| TTS | Piper (local) or hosted API | Start with whatever is simplest to ship |
| Voice UX | Push-to-talk | Wake word deferred |
| Speaker ID | Optional soft match | One enrolled profile |
| DB | SQLite | Notes, sessions, audit; migrate later |
| Vector memory | Deferred | Keyword / simple search first |
| Client | Browser chat + mic | CLI optional |
| Config | `.env` + example file | Secrets never committed |
| Packaging | Plain venv first | Docker Compose when stabilizing |

## Interfaces (must stay)

```text
SpeechToText
LLMProvider
TextToSpeech
ToolExecutor
```

Swap local ↔ cloud without rewriting orchestration.

## Explicitly not V0

| Item | Why defer |
|------|-----------|
| PostgreSQL / pgvector / Qdrant | Premature until retrieval quality hurts |
| Home Assistant | After tool + permission loop works |
| Windows desktop agent | Separate process; post-V0 |
| Native iOS app | Web client first |
| Kubernetes / Proxmox / multi-VM | Ops theater for one laptop |
| Fully local LLM requirement | Nice later; API is fine for V0 reasoning |
| Voice cloning | Licensing + ML side quest |
| Hard multi-user auth | Soft speaker ID optional only |

## Later stack (target, not committed)

| Layer | Candidate |
|-------|-----------|
| DB | PostgreSQL (+ pgvector optional) |
| Deploy | Docker Compose on home server |
| Home | Home Assistant as a **tool adapter** |
| Remote | Secure tunnel; cloud as gateway only |
| Identity | User accounts + device tokens + optional speaker embeddings |

## Hardware note (dev)

Primary development host: existing Windows machine (e.g. gaming desktop / laptop). No dedicated home server required for V0.
