# {{ cookiecutter.project_name }}

{{ cookiecutter.description }}

## Quick Start

### Prerequisites

- Python {{ cookiecutter.python_version }}+
- [uv](https://docs.astral.sh/uv/)
- [prek](https://github.com/j178/prek) (optional, for pre-commit hooks)

### Setup

```bash
# Install dependencies
uv sync

# Copy environment variables
cp .env.example .env
# Edit .env with your configuration

# Install pre-commit hooks
prek install
```

### Running

{% if cookiecutter.interface in ["cli", "both"] -%}
#### CLI Chat

```bash
uv run {{ cookiecutter.project_slug }}
```
{%- endif %}

{% if cookiecutter.interface in ["fastapi", "both"] -%}
#### API Server

```bash
uv run {{ cookiecutter.project_slug }}-server
```

The server exposes:

| Endpoint | Protocol | Purpose |
|---|---|---|
| `POST /chat` | HTTP | Non-streaming chat |
| `POST /chat/stream` | SSE | Server-Sent Events streaming |
| `WS /ws/chat` | WebSocket | Customer-facing full-duplex chat |
| `WS /ws/operator` | WebSocket | Operator console (HITL) |
| `POST /webhooks/async-result` | HTTP | Inbound webhook for async operation callbacks |
| `GET /health` | HTTP | Health check |
{%- endif %}

#### Docker

```bash
docker compose up --build
```

### Development

```bash
# Run tests
uv run pytest

# Lint
uv run ruff check .

# Format
uv run ruff format .

# Type check
uv run ty check
```

## Architecture

```
Customer (Web UI)                    Operator (Dashboard)
      |                                     |
      | WebSocket /ws/chat                  | WebSocket /ws/operator
      v                                     v
+----------------------------------------------------------+
|                     FastAPI Server                        |
|                                                          |
|  Authorization: Bearer <JWT>  --> auth.py resolves       |
|                                   UserIdentity (Entra ID |
|                                   or custom OIDC)        |
|                                                          |
|  POST /webhooks/async-result  <-- external system calls  |
|                                   back when async ops    |
|                                   complete               |
+---------------------------+------------------------------+
                            |
                    ConversationalAgent
                            |
              +-------------+-------------+
              |                           |
     Middleware Pipeline           HITL Handoff State
              |                    (per-session tracking)
    +---------+---------+
    |                   |
  Context            Tool
  Providers          Filters
    |                   |
  +--+--+         +-----+-------+
  |     |         |             |
Memory Knowledge  AuditLog  HumanApproval
Provider Provider  Filter     Filter
```

### Middleware Pipeline

Inspired by the [Microsoft Agent Framework](https://github.com/microsoft/agent-framework)
context-provider pattern:

- **Context Providers** run `before_run()` / `after_run()` hooks linearly:
  - `MemoryContextProvider` — recalls relevant memories, stores interactions
  - `KnowledgeContextProvider` — retrieves relevant documents (RAG)

- **Tool Filters** run `before_tool()` / `after_tool()` hooks around every tool call:
  - `AuditLogFilter` — logs all tool invocations for compliance
  - `HumanApprovalFilter` — blocks sensitive tools until an operator approves

### Tools (three categories)

| Category | Pattern | Examples |
|---|---|---|
| **Async** (fire-and-forget) | HTTP 201/202, result via webhook | `send_quote_for_approval`, `request_document_generation` |
| **Data** (synchronous CRUD) | GET/POST/PUT, immediate response | `get_entity`, `update_preferences` |
| **Logic** (computation) | POST, immediate result | `calculate_quotation`, `fuzzy_search` |

### Human-in-the-Loop (HITL)

Two modes supported:

1. **Pause-and-consult** — The AI agent calls a sensitive tool. The `HumanApprovalFilter`
   sends an approval request to the operator WebSocket. The operator approves or denies.
   The customer sees `approval_pending` / `approval_result` events.

2. **Full handoff** — The operator takes over the conversation entirely. The customer
   sees `transferred_to_human` and subsequent `human_message` events. When done, the
   operator sends `resume_agent` and the customer sees `agent_resumed`.

### WebSocket Protocol

**Customer events** (`/ws/chat`):

| Direction | Type | Payload |
|---|---|---|
| Client -> Server | `message` | `{message, user_id, session_id}` |
| Server -> Client | `token` | `{data: "..."}` streaming token |
| Server -> Client | `done` | Response complete |
| Server -> Client | `error` | `{data: "..."}` |
| Server -> Client | `transferred_to_human` | HITL: human took over |
| Server -> Client | `human_message` | `{data: "..."}` from operator |
| Server -> Client | `agent_resumed` | AI agent is back |
| Server -> Client | `approval_pending` | `{request: {...}}` |
| Server -> Client | `approval_result` | `{approved: bool}` |
| Server -> Client | `async_result` | `{data: {...}}` webhook result |

**Operator events** (`/ws/operator`):

| Direction | Type | Payload |
|---|---|---|
| Server -> Client | `approval_request` | Tool call needing approval |
| Server -> Client | `conversation_update` | Live transcript |
| Server -> Client | `handoff_message` | Customer msg during handoff |
| Server -> Client | `async_result` | Webhook result notification |
| Client -> Server | `approval_response` | `{request_id, approved}` |
| Client -> Server | `operator_message` | `{session_id, message}` |
| Client -> Server | `takeover` | `{session_id}` full handoff |
| Client -> Server | `resume_agent` | `{session_id}` hand back to AI |

### Key Components

- **Agent**: Conversational agent with middleware pipeline
- **Memory**: {{ cookiecutter.memory_provider }} for long-term memory (isolated per user)
- **Knowledge**: RAG stub (implement your own retrieval pipeline)
- **Model**: {% if cookiecutter.model_provider == "azure_ai_foundry" %}Azure OpenAI (Responses API with DefaultAzureCredential){% else %}Custom provider via pydantic-ai{% endif %}
- **Inbound Auth**: JWT validation (Entra ID or custom OIDC) for user identity and memory isolation
- **Outbound Auth**: {% if cookiecutter.auth_method == "bearer_token" %}Bearer token{% else %}Azure Managed Identity{% endif %} for service-to-service calls
