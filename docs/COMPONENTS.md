# Components

Living ledger of every major part of Argus — what it does, when it ships, and where the detail lives.

Update **Status** when a part starts or finishes; keep **Scope** honest so V0 stays small.

## Status legend

| Status | Meaning |
|--------|---------|
| `planned` | Designed in docs; no code yet |
| `in progress` | Being built |
| `done` | Works end-to-end for its V0/V* scope |
| `deferred` | Intentionally later |
| `optional` | Nice for V0; not required to call V0 done |

---

## V0 core (brain slice)

| Component | Role | Scope | Status | Detail |
|-----------|------|-------|--------|--------|
| **Client** | Text REPL | `python -m argus.cli` | done | [README](../README.md) |
| **API** | Door to the brain | FastAPI | deferred | After CLI brain |
| **Orchestrator** | ReAct loop, confirm pause/resume | `argus/orchestrator/` | done | [ORCHESTRATION](ORCHESTRATION.md) |
| **LLM provider** | OpenAI-compatible → Ollama | `argus/providers/` | done | [TECH_STACK](TECH_STACK.md) |
| **Tools** | `get_time`, `remember`, `recall`, `open_application` dry-run | `argus/tools/` | done | [ORCHESTRATION](ORCHESTRATION.md) |
| **Permissions** | allow / confirm / deny in code | `argus/permissions/` | done | [ORCHESTRATION](ORCHESTRATION.md) |
| **Memory** | Notes + FTS5 via remember/recall | SQLite | done | [ORCHESTRATION](ORCHESTRATION.md) |
| **Storage / audit** | Sessions, messages, audit, pending confirms | `argus/storage/` | done | [BLUEPRINT](BLUEPRINT.md) |
| **Evals** | JSONL cases + pass rate / latency | `evals/` | done | [TECH_STACK](TECH_STACK.md) |
| **STT** | Audio → transcript | faster-whisper | deferred | After text brain |
| **TTS** | Reply text → audio | Piper or hosted | deferred | After text brain |

---

## V0 optional

| Component | Role | Scope | Status | Detail |
|-----------|------|-------|--------|--------|
| **Speaker ID** | Soft “is this Addy?” match | One enrolled voice | deferred | [ORCHESTRATION](ORCHESTRATION.md) |

---

## Near-term (after V0)

| Component | Role | Scope | Status | Detail |
|-----------|------|-------|--------|--------|
| **Wake word** | Always-listen trigger → same path as PTT | Local detector | deferred (V0.5) | [ROADMAP](ROADMAP.md) |
| **Device id on requests** | Tag every call with endpoint identity | Even single laptop | deferred (V1) | [ROADMAP](ROADMAP.md) |
| **Client auth tokens** | Local clients prove identity | Tokens for API | deferred (V1) | [ROADMAP](ROADMAP.md) |
| **Docker Compose** | Package the brain | Optional packaging | deferred (V1) | [TECH_STACK](TECH_STACK.md) |

---

## Later (household OS)

| Component | Role | Scope | Status | Detail |
|-----------|------|-------|--------|--------|
| **Users & roles** | Multi-member identity | Accounts + roles | deferred (V2) | [ROADMAP](ROADMAP.md) |
| **Memory scopes** | `household` vs `private:{user}` filtered in code | Retrieval policy | deferred (V2) | [ORCHESTRATION](ORCHESTRATION.md) |
| **Home Assistant adapter** | Lights/sensors as tools | Tool only, not a second brain | deferred (V3) | [ROADMAP](ROADMAP.md) |
| **Windows agent** | Approved PC actions on a machine | Separate local process | deferred (V3) | [BLUEPRINT](BLUEPRINT.md) |
| **Device registry** | Rooms, capabilities, online status | Multi-endpoint | deferred (V4) | [BLUEPRINT](BLUEPRINT.md) |
| **Phone client** | Mobile ears/mouth | Web first | deferred (V4) | [ROADMAP](ROADMAP.md) |
| **Room satellites** | Mic/speaker endpoints | Custom or Pi-class | deferred (V4) | [VISION](VISION.md) |
| **Remote gateway** | Secure access to home brain | Tunnel; cloud not authority | deferred (V5) | [BLUEPRINT](BLUEPRINT.md) |

---

## Not in scope (until justified)

| Item | Why |
|------|-----|
| Unrestricted shell from the LLM | Bypasses the tool/permission model |
| Celebrity / unlicensed voice cloning | Legal + ML side quest |
| Kubernetes / multi-VM sprawl | Ops overhead before a working V0 |
| Vector DB as day-one memory | Keyword notes first |
| Intent-classifier microservice | Tool-calling is enough for V0 |
| Silent cloud LLM failover | Privacy; hosted is explicit config only |

---

## How parts connect (V0)

```text
CLI → Orchestrator → LLM provider (Ollama)
            ↓
   Permissions → Tools
            ↓
   Memory ← Storage / audit / pending confirm
```

Full diagrams: [DIAGRAMS.md](DIAGRAMS.md).

---

## Code map

| Component | Path |
|-----------|------|
| CLI | `argus/cli.py` |
| Orchestrator | `argus/orchestrator/` |
| LLM provider | `argus/providers/` |
| Tools | `argus/tools/` |
| Permissions | `argus/permissions/` |
| Storage | `argus/storage/` |
| Evals | `evals/` |
| API / web client | not yet |
