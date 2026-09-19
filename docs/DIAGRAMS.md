# Diagrams

Mermaid diagrams for Argus. Edit here; render in GitHub / VS Code / Cursor preview.

## 1. System context (target)

```mermaid
flowchart TB
  subgraph clients [Clients — ears and mouths]
    Laptop[Laptop UI / mic]
    Phone[Phone — later]
    Speaker[Room speaker — later]
  end

  subgraph brain [Argus brain]
    API[API + WebSocket]
    Orch[Orchestrator]
    Perm[Permissions]
    Mem[Memory]
    Tools[Tool registry]
    STT[STT provider]
    LLM[LLM provider]
    TTS[TTS provider]
  end

  Laptop --> API
  Phone --> API
  Speaker --> API
  API --> Orch
  Orch --> STT
  Orch --> LLM
  Orch --> TTS
  Orch --> Perm
  Orch --> Mem
  Orch --> Tools
```

## 2. V0 laptop slice

```mermaid
flowchart LR
  UI[Browser / PTT] --> API[FastAPI]
  API --> Orch[Orchestrator]
  Orch --> LLM[LLM API]
  Orch --> STT[faster-whisper]
  Orch --> TTS[TTS]
  Orch --> DB[(SQLite)]
  Orch --> T[Tools]
```

## 3. Request lifecycle

```mermaid
sequenceDiagram
  participant U as User
  participant C as Client
  participant O as Orchestrator
  participant L as LLM
  participant P as Permissions
  participant T as Tool

  U->>C: Text or PTT audio
  C->>O: Request + device/session
  opt Voice
    O->>O: STT transcribe
  end
  O->>O: Load permitted memory
  O->>L: Messages + tool schemas
  L-->>O: Answer or tool_call
  alt Tool call
    O->>P: Check risk / confirm
    P-->>O: allow | confirm | deny
    opt Needs confirm
      O->>U: Confirm?
      U-->>O: Yes / No
    end
    O->>T: Execute
    T-->>O: Result
    O->>L: Tool result
    L-->>O: Final answer
  end
  O->>C: Text (+ TTS audio)
  C->>U: Reply
```

## 4. Permission flow

```mermaid
flowchart TD
  A[LLM tool_call] --> B{Schema valid?}
  B -->|No| Z[Return error to LLM]
  B -->|Yes| C{Permission allow?}
  C -->|No| D[Deny + audit]
  C -->|Yes| E{requires_confirm?}
  E -->|No| F[Execute + audit]
  E -->|Yes| G[awaiting_tool_confirm]
  G --> H{User confirms?}
  H -->|No| I[Cancel + audit]
  H -->|Yes| F
  F --> J[Result to LLM]
```

## 5. Memory scopes (target model)

```mermaid
flowchart TB
  Q[Retrieval query] --> ID[Authenticated user_id]
  ID --> F[Filter in code]
  F --> H[household memories]
  F --> P[private:user_id only]
  H --> CTX[Context for LLM]
  P --> CTX
```

V0 uses a single-user notes store; this diagram is the intended end state so we do not paint ourselves into a corner.

## 6. Orchestrator states

```mermaid
stateDiagram-v2
  [*] --> idle
  idle --> listening: PTT start
  idle --> thinking: text input
  listening --> transcribing: PTT end
  transcribing --> thinking: transcript ready
  thinking --> awaiting_tool_confirm: side_effect tool
  thinking --> executing_tool: allowed tool
  thinking --> responding: final text
  thinking --> speaking: voice session
  awaiting_tool_confirm --> executing_tool: confirmed
  awaiting_tool_confirm --> responding: rejected
  executing_tool --> thinking: tool result
  responding --> idle
  speaking --> idle
  thinking --> error: failure
  error --> idle: recovered
```
