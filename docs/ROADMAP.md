# Roadmap

Checkboxes update when something works end-to-end — not when a file is created.

## Docs (now)

- [x] README + vision / blueprint / orchestration / stack / roadmap / diagrams / components
- [x] Keep docs in sync as V0 brain code lands

## V0 — Laptop brain (CLI + Ollama)

Single user. Local host. Text orchestrator + permissions. Offline tools.

- [x] Project scaffold (orchestrator, providers, tools, storage)
- [x] Text CLI → LLM → reply
- [x] Tool registry + schema validation
- [x] Permission checks (`read` / `write` / `side_effect` + confirm)
- [x] Audit log for tool attempts
- [x] Tools: `get_time`, `remember`, `recall`, `open_application` (dry-run + confirm)
- [x] SQLite notes (FTS5) + session history
- [x] Eval harness (`evals/`)
- [x] Local FastAPI API (`/api/chat`, `/api/confirm`)
- [x] Browser client
- [ ] STT / TTS (push-to-talk)
- [ ] Soft speaker ID
- [x] Provider interfaces for LLM (STT/TTS later)

**Brain-slice done when:** CLI tool loop works against Ollama; pytest green; evals runnable.

**Full V0 done when:** weather/search (optional), remember/recall, confirmed side-effect, and push-to-talk voice also work.

## V0.5 — Wake word

- [ ] Local wake-word detector
- [ ] Listening UX (false-trigger handling)
- [ ] Same orchestrator path as PTT after wake

## V1 — Central API habits

Still one brain; cleaner multi-client readiness.

- [ ] Stable WebSocket protocol for clients
- [ ] Device id on every request (even if only laptop)
- [ ] Auth tokens for local clients
- [ ] Docker Compose optional packaging

## V2 — Memory scopes + identity

- [ ] Users table + roles
- [ ] `household` vs `private:{user_id}` memory filtering in code
- [ ] Harder speaker ID experiments
- [ ] Memory delete + audit

## V3 — Home + PC agents

- [ ] Home Assistant tool adapter (lights / sensors first)
- [ ] Windows agent for approved local actions
- [ ] Room-aware defaults when device registry exists

## V4 — House-wide endpoints

- [ ] Device registry (room, capabilities, online status)
- [ ] Phone web client
- [ ] Room mic/speaker satellites
- [ ] Response routing back to originating device

## V5 — Remote access

- [ ] Secure tunnel / gateway to home brain
- [ ] Cloud never owns private memory or home secrets
- [ ] Offline / local fallback behavior

## Explicit non-goals (until justified)

- Unrestricted shell from the LLM  
- Door unlock / purchases without strong confirmation  
- Kubernetes, multi-VM sprawl, Neo4j-by-default  
- Cloning a copyrighted celebrity voice  
