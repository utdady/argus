# Orchestration

Source of truth for Argus’s control loop. Keep this accurate as the code evolves.

## Goal

Own the loop: **perceive → interpret → act → observe → remember → respond** — with permissions enforced outside the LLM.

## V0 loop

Prefer a **ReAct / tool-calling** loop. Add explicit plan-then-execute only when multi-step side effects need it.

```
User (text or push-to-talk audio)
    → STT (if audio)
    → Build context (user, device, session, allowed tools/memory)
    → LLM turn (answer or tool_calls)
    → For each tool: validate → permission → confirm? → execute
    → LLM turn with tool results (until done)
    → TTS (if voice session) + text reply
    → Persist session / memory writes
```

## State machine

| State | Meaning |
|-------|---------|
| `idle` | Waiting for input |
| `listening` | Capturing audio (push-to-talk) |
| `transcribing` | STT in progress |
| `thinking` | LLM turn |
| `awaiting_tool_confirm` | Side-effect gated on user yes/no |
| `executing_tool` | Running an approved tool |
| `speaking` | TTS playback |
| `responding` | Text reply delivered |
| `error` | Recover, apologize, or replan |

## Context object (every turn)

```text
user_id          # V0: single local user (e.g. "addy")
device_id        # V0: "laptop_01"
room             # optional; null in V0
session_id
channel          # "text" | "voice"
allowed_tools    # from permission matrix
allowed_memory   # V0: all local notes; later scoped
pending_confirm  # tool name + args + token, if any
speaker_match    # optional: confidence that voice == enrolled user
```

## Tools (V0 starter set — offline)

| Tool | Risk | Confirm? |
|------|------|----------|
| `get_time` | read | No |
| `remember` | write | No |
| `recall` | read | No |
| `open_application` | side_effect | Yes (allowlisted apps; **dry-run** only) |

**Deferred:** `get_weather`, `web_search` (keep brain offline until loop is proven).

**Not in V0:** unrestricted shell, email send, purchases, door locks, arbitrary file delete, real process launch.

## Permission model

Even with one user, every tool declares:

- `name`, input schema  
- `risk`: `read` | `write` | `side_effect`  
- `requires_confirm`: bool  
- `allowed_roles` (V0: `["owner"]`)  

Flow:

```
LLM requests tool
  → schema validate
  → permission check (code)
  → if requires_confirm → awaiting_tool_confirm
  → execute + audit log
  → return result to LLM
```

Authorization is never “the model said it was OK.”

## Memory (V0 → later)

**V0:** flat notes table (`remember` / `recall`), owned by the single user.

**Later scopes:**

| Scope | Examples |
|-------|----------|
| `household` | Shared lists, room names, family routines |
| `private:{user_id}` | Preferences, personal schedules |

Retrieval must filter by identity **before** context reaches the LLM.

## Voice extras (staging)

| Feature | This brain slice | Notes |
|---------|------------------|--------|
| STT + TTS | Deferred | After CLI brain |
| Push-to-talk | Deferred | — |
| Soft speaker ID | Deferred | — |
| Wake word | V0.5 | After PTT + tools are solid |

Speaker ID for one enrolled profile is binary: **match owner / unknown**. Do not treat it as strong auth for high-risk actions.

## Audit log

For every tool attempt, record: timestamp, user, device, tool, args summary, allow/deny/confirm, outcome. Needed for debugging and future household trust.

## Anti-goals for the orchestrator

- No unrestricted `run_shell` from the LLM  
- No “intent classifier” microservice in V0 (tool-calling is enough)  
- No multi-agent swarm until a single orchestrator is boringly reliable  
- No trusting the model to hide private memory  
