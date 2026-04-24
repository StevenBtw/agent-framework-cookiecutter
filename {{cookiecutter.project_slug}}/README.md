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
# Run unit tests (fast, mocked dependencies)
uv run pytest

# Run LLM evaluation tests (calls real model, requires config)
uv sync --group evals
uv run pytest -m evals

# Lint
uv run ruff check .

# Format
uv run ruff format .

# Type check
uv run ty check
```

### Evaluation

The project includes an evaluation harness in `tests/evals/` for testing LLM
output quality.  Eval tests are excluded from the normal test run (they call the
real model) — use `pytest -m evals` to include them.

**Default backend: Azure AI Evaluation** — LLM-as-judge metrics for relevance,
coherence, groundedness and fluency (1-5 scale).

**Eval dataset:** `tests/evals/datasets/eval_cases.jsonl` — add your test
scenarios as JSONL entries and version them alongside your code.

**Extensible:** The `BaseEvaluator` protocol in `tests/evals/base.py` lets you
swap in alternative backends:

| Backend | Install | Docs |
|---|---|---|
| Azure AI Evaluation (default) | `uv sync --group evals` | [learn.microsoft.com](https://learn.microsoft.com/en-us/azure/ai-foundry/evaluation/) |
| DeepEval | `pip install deepeval` | [docs.confident-ai.com](https://docs.confident-ai.com/) |
| LangSmith | `pip install langsmith` | [docs.smith.langchain.com](https://docs.smith.langchain.com/) |
| promptfoo | `npx promptfoo@latest` | [promptfoo.dev](https://www.promptfoo.dev/) |

See `tests/evals/__init__.py` for integration examples.

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
                      Orchestrator
                            |
         +---------+--------+---------+----------+
         |         |                  |          |
  Conversation  Middleware      HITL Handoff   Logging
    History      Pipeline       State          + Tracing
         |         |
         |   +-----+------+
         |   |            |
         | Context     Tool
         | Providers   Filters
         |   |            |
         | +--+--+   +----+------+
         | |     |   |           |
         |Memory Know AuditLog HumanApproval
         |Prov.  Prov. Filter    Filter
         |
   ConversationalAgent
   (receives full message list)
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

### Utilities (`utils/`)

| Module | Purpose |
|---|---|
| `tracing.py` | Request/correlation IDs via `contextvars`. `X-Correlation-ID` header propagation. |
| `logging.py` | Structured logging (JSON or human-readable). Auto-injects request IDs. Wired to `AuditLogFilter`. |
| `errors.py` | `AgentError` → `ToolError` → `ToolHTTPError`, `RateLimitError`. `format_error_for_llm()` for safe messages. |
| `schemas.py` | Shared Pydantic models for REST, WebSocket and tool results. |
| `rate_limiting.py` | Token-bucket rate limiter on chat endpoints. Configurable via `RATE_LIMIT_RPM` / `RATE_LIMIT_BURST`. |
| `history.py` | In-memory conversation history per session. Configurable via `MAX_TURNS`. |

### Conversation History

The orchestrator maintains per-session conversation history so the LLM sees prior turns. History is loaded before each call, passed as a message list to the agent, and the new turn is appended after. Streaming responses are fully captured (not stored as placeholders). Configure `MAX_TURNS` in `.env` to control the window size.
{% if cookiecutter.governance_level != "none" %}
## Governance

This project integrates the [Microsoft Agent Governance Toolkit](https://github.com/microsoft/agent-governance-toolkit) at the **{{ cookiecutter.governance_level }}** tier.

| Tier     | What runs                                                                     |
|----------|-------------------------------------------------------------------------------|
| minimal  | `PolicyToolFilter` — every tool call is evaluated against `policies.yaml`     |
| standard | minimal + `PolicyInputProvider` / `PolicyOutputProvider` around the LLM call  |
| full     | standard + tool/policy events forwarded to the AGT compliance log             |

Edit `policies.yaml` (at the project root) to add, remove, or reorder rules. The format follows AGT's `PolicyDocument` schema; see the toolkit README for the full reference.

Set `AGT_ENABLED=false` in `.env` to bypass all policy checks (dev only).
{% endif %}
