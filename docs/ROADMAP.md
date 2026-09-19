# Roadmap

Checkboxes update when something works end-to-end — not when a file is created.

## Docs (now)

- [x] README + vision / blueprint / orchestration / stack / roadmap / diagrams
- [ ] Keep docs in sync as V0 code lands

## V0 — Laptop core

Single user. One machine. Orchestrator + permissions + voice I/O.

- [ ] Project scaffold (API, orchestrator package, providers, tools, storage)
- [ ] Text chat → LLM → reply
- [ ] Tool registry + schema validation
- [ ] Permission checks (`read` / `write` / `side_effect` + confirm)
- [ ] Audit log for tool attempts
- [ ] Tools: `get_time`, `get_weather` or `web_search`, `remember`, `recall`
- [ ] Tool: `open_application` (allowlist + confirm)
- [ ] SQLite notes + session history
- [ ] Browser client (text)
- [ ] STT (faster-whisper) + TTS via push-to-talk
- [ ] Soft speaker ID (enroll Addy; log confidence; optional soft gate)
- [ ] Provider interfaces for STT / LLM / TTS

**V0 done when:** weather/search, remember/recall, and at least one confirmed side-effect tool work over text and push-to-talk voice.

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
