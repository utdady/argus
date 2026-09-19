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

## V0 core (build these)

| Component | Role | Scope | Status | Detail |
|-----------|------|-------|--------|--------|
| **Client** | Ears/mouth/UI — text + push-to-talk, play TTS | Browser on laptop | planned | [BLUEPRINT](BLUEPRINT.md) |
| **API** | Door to the brain — REST (+ WebSocket later) | FastAPI on laptop | planned | [BLUEPRINT](BLUEPRINT.md) |
| **Orchestrator** | Control loop, state machine, tool loop | In-process Python | planned | [ORCHESTRATION](ORCHESTRATION.md) |
| **LLM provider** | Messages + tools → answer or tool calls | API behind interface | planned | [TECH_STACK](TECH_STACK.md) |
| **Tools** | Named capabilities (`get_time`, weather/search, remember/recall, open_app) | Registry + schemas | planned | [ORCHESTRATION](ORCHESTRATION.md) |
| **Permissions** | Gate tools by risk; confirm side effects | Code, not prompts | planned | [ORCHESTRATION](ORCHESTRATION.md) |
| **Memory** | Durable notes via remember/recall | Flat SQLite notes | planned | [ORCHESTRATION](ORCHESTRATION.md) |
| **Storage / audit** | Sessions, messages, tool audit log | SQLite | planned | [BLUEPRINT](BLUEPRINT.md) |
| **STT** | Audio → transcript | faster-whisper (local) | planned | [TECH_STACK](TECH_STACK.md) |
| **TTS** | Reply text → audio | Piper or hosted | planned | [TECH_STACK](TECH_STACK.md) |

---

## V0 optional

| Component | Role | Scope | Status | Detail |
|-----------|------|-------|--------|--------|
| **Speaker ID** | Soft “is this Addy?” match | One enrolled voice; soft gate for side effects | optional | [ORCHESTRATION](ORCHESTRATION.md) |

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

---

## How parts connect (one glance)

```text
Client → API → Orchestrator → LLM provider
                    ↓
           Permissions → Tools
                    ↓
           Memory ← Storage / audit
                    ↓
              STT / TTS
           (Speaker ID optional)
```

Full diagrams: [DIAGRAMS.md](DIAGRAMS.md).

---

## Code map (when scaffold lands)

Expected packages (not created yet):

| Component | Likely path |
|-----------|-------------|
| API | `apps/api/` or `argus/api/` |
| Orchestrator | `argus/orchestrator/` |
| Providers (STT/LLM/TTS) | `argus/providers/` |
| Tools | `argus/tools/` |
| Permissions | `argus/permissions/` |
| Memory / storage | `argus/storage/` |
| Client | `apps/web/` or `clients/web/` |

Update this table when the repo scaffold exists.
