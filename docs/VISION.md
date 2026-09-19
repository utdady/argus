# Vision

Argus is a **personal AI operating system for the household** — not only a voice chatbot.

One AI that can hear you, talk back, remember things, use the internet, control devices, and (later) distinguish household members — whether you speak from a phone, laptop, or a speaker in another room.

## North star

```
Household AI
└── Argus Core (one central brain)
    ├── Orchestrator — reasoning, conversation, planning
    ├── Memory — personal + shared
    ├── Tools — web, PC, home
    ├── Permissions — identity + access
    ├── Voice — STT + TTS
    └── Device endpoints — phone, Windows, house speakers
```



## Key principle

> The devices are the ears and mouths. The server is the brain.

You should not need a full LLM and Whisper stack on every device.

## What “done” looks like (long term)

- Always-on home brain (dedicated machine or mini PC)
- Multiple endpoints with room context
- Shared household memory vs private per-person memory
- Strict tool permissions (weather ≠ unlock door)
- Optional secure remote access (cloud as gateway, not authority)



## What V0 deliberately is not

V0 is a **single-user laptop proof of the orchestrator** — text + voice I/O, tools with permissions, simple memory. House-wide audio, multi-user identity, and cloud gateways come after that loop is reliable.

