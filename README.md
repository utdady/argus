# Argus

Personal household AI — one central brain, many devices.

**Current focus:** planning docs and V0 orchestration design. Application code comes next.

## Status


| Phase                   | State       |
| ----------------------- | ----------- |
| Docs / architecture     | In progress |
| V0 — laptop core        | Not started |
| V0.5 — wake word        | Deferred    |
| House-wide / multi-user | Later       |


See [docs/ROADMAP.md](docs/ROADMAP.md) for milestones.

## Docs


| Doc                                    | What it covers                   |
| -------------------------------------- | -------------------------------- |
| [COMPONENTS](docs/COMPONENTS.md)       | Parts ledger — status of every module |
| [VISION](docs/VISION.md)               | Endgame: household AI OS         |
| [BLUEPRINT](docs/BLUEPRINT.md)         | System architecture              |
| [ORCHESTRATION](docs/ORCHESTRATION.md) | Control loop, tools, permissions |
| [TECH_STACK](docs/TECH_STACK.md)       | Chosen stack and deferrals       |
| [ROADMAP](docs/ROADMAP.md)             | Phased milestones                |
| [DIAGRAMS](docs/DIAGRAMS.md)           | Mermaid system / flow diagrams   |




## Principles

1. **Devices are ears and mouths. The server is the brain.**
2. **Permissions and memory access are enforced in code**, not by prompting the LLM.
3. **Start on one laptop.** Scale to rooms and household members later.
4. **Providers are swappable** (STT / LLM / TTS) behind thin interfaces.



## V0 success criteria

On your laptop you can:

1. Chat (text) and get a tool-backed answer
2. Speak (push-to-talk) → STT → Argus → TTS
3. `remember` / `recall` notes
4. Tools respect risk levels (auto vs confirm)



## Quick start (code)

Application scaffold is not in the repo yet. After V0 code lands, this section will cover install and run steps.