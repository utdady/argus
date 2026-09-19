# Blueprint

High-level architecture for Argus. Implementation details for the control loop live in [ORCHESTRATION.md](ORCHESTRATION.md).

## System shape

```
Clients (ears / mouths)          Brain (always one)
─────────────────────            ──────────────────
Laptop UI / mic                  Argus API + Orchestrator
Phone (later)               →    Providers (STT, LLM, TTS)
Room speaker (later)             Tools + Permissions
                                 Memory store
                                 Device registry (later)
```

## Layers

| Layer | Responsibility |
|-------|----------------|
| Clients | Capture audio/text, play TTS, show chat; register as a device |
| API | REST + WebSocket; auth; route events to orchestrator |
| Orchestrator | Conversation state, LLM turns, tool plans, confirms |
| Providers | STT / LLM / TTS behind interfaces (local or cloud) |
| Tools | Named capabilities with schemas and risk levels |
| Permissions | Who may run which tool; confirm when required |
| Memory | Notes and facts; later: household vs private scopes |
| Storage | SQLite first; Postgres when needed |

## Request lifecycle (target)

Every request should pass through:

1. Receive audio or text  
2. Identify device (V0: laptop only)  
3. Identify or verify user (V0: single user; soft speaker ID optional)  
4. Transcribe audio if needed  
5. Retrieve only permitted memory  
6. Ask LLM for answer or tool call  
7. Validate tool arguments  
8. Check permissions / confirmation  
9. Execute tool  
10. Generate response  
11. Return to originating endpoint  
12. Log safely  

The LLM never decides authorization.

## Deployment progression

| Stage | Where |
|-------|--------|
| Development / V0 | Existing Windows laptop / desktop |
| Always-on home | Dedicated PC or mini PC |
| Isolation | Linux + Docker Compose |
| Remote access | Secure tunnel / gateway to home brain |

Cloud should be an **optional gateway**, not the authority for private memory, home controls, or local secrets.

## V0 boundary

V0 runs entirely on one machine:

- One client (browser and/or local voice capture)
- One API + orchestrator process
- Local or API LLM behind `LLMProvider`
- Local STT (e.g. faster-whisper) + TTS (e.g. Piper or hosted)
- SQLite for notes and logs
- No device registry, Home Assistant, or multi-user hard auth yet

## Interfaces (provider contracts)

Providers stay swappable:

```text
SpeechToText.transcribe(audio) -> text
LLMProvider.respond(messages, tools) -> text | tool_calls
TextToSpeech.synthesize(text) -> audio
ToolExecutor.execute(name, args, context) -> result
```

See [TECH_STACK.md](TECH_STACK.md) for concrete choices.
