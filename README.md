# Microsoft Agent Framework Cookiecutter

A [cookiecutter](https://github.com/cookiecutter/cookiecutter) template for building conversational AI agents on top of the [Microsoft Agent Framework](https://github.com/microsoft/agent-framework/). It gives you a working project skeleton with long-term memory, knowledge retrieval, external service tooling and your choice of model provider; all wired together and ready to run.

## Why this template?

Standing up a conversational AI backend involves a surprising amount of plumbing. You need a model provider, a memory layer so the agent actually remembers past conversations, some form of knowledge retrieval so it can ground its answers in real data and a set of tools so it can interact with the outside world. Then you still have to choose an interface (CLI? HTTP? WebSocket?), set up configuration management, wire in auth, add linting and type checking and write your first tests.

This template handles all of that scaffolding for you. You run one command, answer a few questions and get a project that is ready for `uv sync && uv run pytest`. The idea is to let you skip the boilerplate and jump straight into the interesting parts: your agent's personality, your domain knowledge and your business logic integrations.

## What is included

### Core agent

The generated project creates a `ConversationalAgent` class that ties together memory recall, knowledge search and tool invocation into a single `chat()` or `chat_stream()` method. Depending on your model provider choice, it uses either the Azure OpenAI Responses API (via the `openai` SDK with `DefaultAzureCredential`) or [pydantic-ai](https://ai.pydantic.dev/) for any OpenAI-compatible endpoint.

### Long-term memory

Every conversation is ephemeral unless you give the agent memory. The template lets you pick one of three providers at generation time:

| Provider | Why you might choose it |
| --- | --- |
| **azure-foundry** | [Azure AI Foundry Memory Stores](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/memory-usage), the managed memory solution built into the Foundry Agent Service. It handles memory extraction, consolidation and retrieval for you; memories are scoped per user and partitioned automatically. Requires an Azure Foundry project with chat and embedding model deployments. The natural choice if you are already on Azure and want a fully managed, production-ready memory layer with no additional infrastructure to operate. |
| **grafeo-memory** | Fully embedded, self-contained memory built on [GrafeoDB](https://github.com/GrafeoDB/grafeo). No servers, no Docker, no external vector stores; just a single `.db` file and an LLM. It extracts facts and entities from conversations, stores them as a graph with native vector search and reconciles new information against existing memories automatically. Less mature than the other options but zero infrastructure overhead, which makes it ideal for local development, edge deployments or situations where you do not want to depend on external services. |
| **mem0** | The most battle-tested option. [Mem0](https://github.com/mem0ai/mem0) is a full memory platform with automatic fact extraction, multi-level memory (user, session, agent) and adaptive personalization. The tradeoff is infrastructure: self-hosted mem0 requires a vector store (Qdrant, Chroma, etc.), optionally a graph database(Grafeo, Neo4j, Kuzu), a backing database and an LLM for memory processing. There is also a managed hosted option if you prefer not to run that yourself. Choose this when you need production-grade memory at scale and are comfortable with the operational overhead. |

The generated code includes a `MemoryProvider` class with `store()`, `recall()` and `get_all()` methods. Whichever provider you pick, the interface is the same; only the implementation differs. All three providers isolate memories per user: Azure Foundry uses its native scoping, grafeo-memory creates a separate `.db` file per user under a configurable directory and mem0 filters by `user_id` server-side.

### Knowledge retrieval (RAG)

The template generates a `KnowledgeProvider` stub with `search()` and `ingest()` methods. This is intentionally left as a skeleton because RAG pipelines are highly domain-specific: your choice of vector store, chunking strategy, embedding model and reranking approach will depend entirely on your data and your latency requirements. The stub gives you the interface contract so the agent knows how to call it; you fill in the implementation.

### Model provider

You get to choose between two approaches:

- **Azure AI Foundry**: uses `AsyncAzureOpenAI` from the `openai` SDK with `DefaultAzureCredential` and the OpenAI Responses API. This is the path of least resistance if you are deploying on Azure and want managed model hosting.
- **pydantic-ai custom**: uses [pydantic-ai](https://ai.pydantic.dev/) to connect to any OpenAI-compatible API endpoint. This is the flexible option; point it at a self-hosted model, a third-party provider or anything else that speaks the OpenAI protocol.

### Tools

Agents are only as useful as the actions they can take. The template includes three tool patterns that cover the most common integration scenarios:

| Tool | Pattern | Example use cases |
| --- | --- | --- |
| `async_api` | Fire-and-forget; sends a request and gets back an HTTP 201 with a correlation ID | Starting a BPM workflow, submitting a batch job, sending a notification |
| `data_service` | Synchronous CRUD; GET, POST and PUT on entity resources | Looking up customer details, creating an order, updating account info |
| `logic_service` | Synchronous request-response; POST inputs, receive computed results | Calling a pricing engine, running a risk assessment, evaluating eligibility rules |

Why these three? Because most enterprise service landscapes boil down to these patterns. You have systems that accept work asynchronously (BPM engines, message queues, notification services), systems that store and retrieve data (CRMs, ERPs, master data services) and systems that compute things on demand (calculation engines, rules engines, scoring models). Rather than creating a single generic "call any API" tool, the template gives each pattern its own module with appropriate defaults. This makes the agent's tool descriptions clearer to the LLM and makes your code easier to navigate.

All three share a common `ServiceClient` base that handles httpx async connections, timeouts and authentication. Each service gets its own base URL, API key and timeout in the configuration; this keeps things cleanly separated when your agent talks to multiple backends.

### Interface layer

The `interface` choice controls how users interact with your agent:

- **CLI**: a terminal-based chat REPL with streaming output. Great for development, testing and quick demos.
- **FastAPI**: an HTTP server with three endpoints. `POST /chat` for simple request-response, `POST /chat/stream` for Server-Sent Events (token-by-token streaming) and `WS /ws/chat` for full-duplex WebSocket communication. The SSE endpoint is the simplest path to a streaming chat UI; the WebSocket endpoint is what you want for richer interactions like typing indicators, mid-response cancellation or future voice integration.
- **Both**: generates both the CLI and the FastAPI server. This is the default and usually the right choice; you get the CLI for local development and the server for production.

Why SSE and WebSocket instead of just one? They serve different needs. SSE is unidirectional (server to client) and works over plain HTTP, which means it plays nicely with load balancers, CDNs and proxies without any special configuration. It is what OpenAI, Anthropic and most LLM APIs use for streaming. WebSocket is bidirectional and persistent, which you need if the client should be able to cancel a response mid-stream, send typing indicators or eventually pipe in audio from a voice interface. Having both means the frontend team can pick whichever fits their use case.

### Configuration

All settings flow through [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) with `.env` file support. If you configure an Azure Key Vault URL, secrets are loaded from Key Vault automatically using `DefaultAzureCredential`. The generated `.env.example` documents every configuration variable so you know exactly what to fill in.

Why pydantic-settings instead of plain `os.getenv()`? Because it gives you validation, type coercion and documentation in one place. If someone sets a timeout to `"fast"` instead of a number, they get a clear error at startup rather than a mysterious crash at runtime. And because it inherits from Pydantic's `BaseModel`, your IDE gets full autocomplete on all settings.

### Authentication

There are two layers of authentication in the generated project.

**Inbound (user identity)**: The FastAPI server validates JWT tokens from the `Authorization: Bearer <token>` header to identify callers. Two identity providers are supported out of the box:

- **Entra ID** (Azure AD): extracts the `oid` claim as the user identifier.
- **Custom OIDC**: validates tokens from any OpenID Connect provider and extracts the `sub` claim.

When a valid token is present the user gets an authenticated identity and their own isolated memory partition. Anonymous callers get a transient session-scoped ID so their memories do not persist across sessions. The auth module also supports composite user identifiers like `prospect:abc123` or `customer:21-390hkjfw` which are common in multi-tenant systems.

Set `AUTH_ENABLED=false` (the default) to skip token validation during local development.

**Outbound (service credentials)**: Two options for how your agent authenticates to external services:

- **Bearer token**: API keys loaded from config or Key Vault. Simple and works everywhere.
- **Azure Managed Identity**: uses `DefaultAzureCredential` for service-to-service auth. No secrets to manage; Azure handles the token lifecycle. This is the recommended approach for production Azure deployments.

### Evaluation

The template includes an evaluation harness for testing LLM output quality beyond unit tests. The default backend is [Azure AI Evaluation](https://learn.microsoft.com/en-us/azure/ai-foundry/evaluation/) which provides LLM-as-judge metrics for relevance, coherence, groundedness and fluency on a 1-5 scale. Eval tests live in `tests/evals/` and are excluded from the normal test run; use `pytest -m evals` to include them.

The harness is built on an extensible `BaseEvaluator` protocol so you can plug in alternative backends without changing your test cases:

| Backend | Install | Best for |
| --- | --- | --- |
| **Azure AI Evaluation** (default) | `uv sync --group evals` | Azure-native projects, integrates with Foundry portal |
| **[DeepEval](https://docs.confident-ai.com/)** | `uv add deepeval` | pytest-native metrics (GEval, Faithfulness), optional cloud dashboard |
| **[LangSmith](https://docs.smith.langchain.com/)** | `uv add langsmith` | Tracing + evals with annotation queues for human review. Works without LangChain |
| **[promptfoo](https://www.promptfoo.dev/)** | `npx promptfoo@latest` | YAML-based prompt regression testing with built-in web UI |

The eval dataset is a JSONL file (`tests/evals/datasets/eval_cases.jsonl`) so you can version your test scenarios alongside your code and run them in CI.

### Developer tooling

The template sets up a modern Python development workflow. Every tool was chosen for a specific reason:

- **[uv](https://docs.astral.sh/uv/)** for package management. It is dramatically faster than pip and handles virtual environments, dependency resolution and lockfiles in one tool. No more juggling pip, pip-tools and virtualenv separately.
- **[ruff](https://docs.astral.sh/ruff/)** for linting and formatting. It replaces flake8, isort, black and dozens of other tools with a single, extremely fast Rust-based binary. One config section in `pyproject.toml` instead of five separate config files.
- **[ty](https://github.com/astral-sh/ty)** for type checking. From the same team as ruff; designed to be fast and compatible with the modern Python type system.
- **[prek](https://github.com/j178/prek)** for pre-commit hooks. A Rust-based reimagining of pre-commit that is faster and ships as a single binary with no dependencies. It is fully compatible with existing `.pre-commit-config.yaml` files.
- **pytest** with `pytest-asyncio` and `pytest-httpx` for testing. The generated tests mock the memory, knowledge and model layers so they run without any external services.
- **Docker** with a Dockerfile that uses uv for dependency installation and a `docker-compose.yml` for one-command deployment.

### Utilities

The generated project includes a `utils/` package with lightweight, barebones implementations of cross-cutting concerns. These are starting points, not production libraries; replace them as your needs grow.

| Module | What it does |
| --- | --- |
| `tracing.py` | Per-request `request_id` and `correlation_id` via `contextvars`. The FastAPI server reads `X-Correlation-ID` from inbound headers and sets `X-Request-ID` on responses. |
| `logging.py` | Structured logging with two formatters: JSON lines for production log aggregators and a human-readable format for local development. Both automatically include request/correlation IDs. The `AuditLogFilter` is wired to a real logger by default. |
| `errors.py` | Typed exception hierarchy (`AgentError` → `ToolError` → `ToolHTTPError`, `RateLimitError`). Includes `format_error_for_llm()` which produces a safe message the LLM can relay without leaking internals, and `format_error_response()` for structured API error bodies. |
| `schemas.py` | Shared Pydantic models for REST requests/responses and WebSocket message types. Keeps data contracts in one place so interfaces and tests can import them without circular dependencies. |
| `rate_limiting.py` | In-memory token-bucket rate limiter with per-key tracking. Wired as a FastAPI dependency on the chat endpoints. For multi-worker deployments, swap for a Redis-backed implementation. |
| `history.py` | In-memory conversation history keyed by `(user_id, session_id)`. Bounded by `MAX_TURNS` (configurable via `.env`). The orchestrator loads history before each LLM call and appends the new turn after, so the model sees the full conversation context. |

### Conversation history

Every call to `orchestrator.chat()` or `chat_stream()` now includes conversation history. The orchestrator loads prior turns for the session, passes them as a message list to the agent (not just a single prompt string), and stores the new turn after the response completes. For streaming, tokens are accumulated so the real response text is stored in both memory and history (not a placeholder).

History is in-memory and bounded by `MAX_TURNS`. It does not persist across server restarts. For production, replace `ConversationHistory` with a Redis or database-backed implementation.

## Requirements

- Python 3.14+
- [cookiecutter](https://github.com/cookiecutter/cookiecutter) (or [cruft](https://github.com/cruft/cruft) if you want template updates)
- [uv](https://docs.astral.sh/uv/) (for the generated project)

## Usage

### Generate a project

From a local clone:

```bash
cookiecutter path/to/agent-framework-cookiecutter
```

From GitHub:

```bash
cookiecutter gh:StevenBtw/agent-framework-cookiecutter
```

You will be prompted for:

| Variable | Description | Default |
| --- | --- | --- |
| `project_name` | Human-readable project name | My Agent |
| `project_slug` | Directory and package distribution name | my-agent |
| `package_name` | Python import name | my_agent |
| `author` | Your name | Your Name |
| `author_email` | Your email | `you@example.com` |
| `description` | Short project description | A conversational AI agent |
| `python_version` | Minimum Python version | 3.14 |
| `memory_provider` | azure-foundry, grafeo-memory or mem0 | azure-foundry |
| `model_provider` | azure_ai_foundry or pydantic_ai_custom | azure_ai_foundry |
| `interface` | both, cli or fastapi | both |
| `auth_method` | bearer_token or managed_identity | bearer_token |

### Set up the generated project

```bash
cd my-agent
cp .env.example .env
# Fill in your configuration values in .env

uv sync
prek install
```

### Run

```bash
# Interactive CLI chat
uv run my-agent

# API server
uv run my-agent-server

# Docker
docker compose up --build

# Tests
uv run pytest

# Linting and formatting
uv run ruff check .
uv run ruff format .
uv run ty check
```

## Generated project structure

```text
my-agent/
├── pyproject.toml
├── .python-version
├── .pre-commit-config.yaml
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── README.md
├── src/
│   └── my_agent/
│       ├── __init__.py
│       ├── orchestrator.py           # Wires agents + middleware + HITL state
│       ├── middleware.py             # Context providers, tool filters, pipeline
│       ├── config.py                 # pydantic-settings + Azure Key Vault
│       ├── auth.py                   # Inbound JWT auth (Entra ID / custom OIDC)
│       ├── agents/
│       │   ├── __init__.py
│       │   └── conversational.py     # Agent definition: model, tools, persona
│       ├── interfaces/
│       │   ├── __init__.py
│       │   ├── cli.py                # Terminal REPL (if cli or both)
│       │   └── server.py             # FastAPI + SSE + WS + operator WS + webhooks
│       ├── memory/
│       │   ├── __init__.py
│       │   └── provider.py           # Your chosen memory implementation
│       ├── knowledge/
│       │   ├── __init__.py
│       │   └── provider.py           # RAG stub; implement your retrieval pipeline
│       ├── providers/
│       │   ├── __init__.py
│       │   └── model.py              # Azure AI Foundry or pydantic-ai custom
│       ├── utils/
│       │   ├── __init__.py
│       │   ├── tracing.py            # Request/correlation ID context vars
│       │   ├── logging.py            # Structured logging (JSON + dev formatters)
│       │   ├── errors.py             # Typed exception hierarchy + LLM-safe formatting
│       │   ├── schemas.py            # Shared Pydantic models (requests, responses, WS)
│       │   ├── rate_limiting.py      # Token-bucket rate limiter
│       │   └── history.py            # In-memory conversation history (per-session)
│       └── tools/
│           ├── __init__.py
│           ├── base.py               # Shared httpx async client with auth
│           ├── async_api.py          # Fire-and-forget operations (HTTP 201)
│           ├── data_service.py       # CRUD operations (GET/POST/PUT)
│           └── logic_service.py      # Request-response computations
└── tests/
    ├── __init__.py
    ├── conftest.py                   # Shared fixtures with mocked dependencies
    ├── test_agent.py                 # Orchestrator integration tests
    ├── test_middleware.py            # Middleware unit tests
    ├── test_tracing.py              # Request context propagation tests
    ├── test_logging.py              # Structured logging tests
    ├── test_errors.py               # Error hierarchy + formatting tests
    ├── test_rate_limiting.py        # Token bucket tests
    ├── test_history.py              # Conversation history tests
    └── evals/
        ├── __init__.py              # Eval framework docs + extension points
        ├── base.py                  # BaseEvaluator protocol, EvalCase, EvalResult
        ├── azure_evaluators.py      # Azure AI Evaluation backend (default)
        ├── conftest.py              # Eval fixtures and evaluator suite
        ├── test_response_quality.py # Eval tests (pytest -m evals)
        └── datasets/
            └── eval_cases.jsonl     # Versioned eval scenarios
```

### Why this layout

The codebase separates three concerns that change for different reasons.

**What the agent is** lives in `agents/`: Each agent module defines a model provider, a tool registry and a system prompt. The template starts with a single `conversational.py` agent because that is all most projects need at the beginning. When you eventually need a second agent (a triage bot, a specialist, a supervisor) you add a file here and import it in the orchestrator. Nothing else moves.

**How agents run** lives in `orchestrator.py` and `middleware.py`: The orchestrator is the composition root: it creates agents, wires up the middleware pipeline (memory recall, knowledge retrieval, audit logging, human approval) and manages HITL handoff state. The middleware module defines the building blocks themselves. These two files are kept separate because `middleware.py` contains reusable abstractions (base classes, filter implementations, the pipeline runner) while `orchestrator.py` contains wiring decisions specific to your application. You will add new filters and context providers to middleware fairly often; you will rarely change how the orchestrator assembles them.

**How users connect** lives in `interfaces/`: The CLI and FastAPI server both import from the orchestrator and nothing else. They don't know about agents, middleware or tools directly. This means you can swap or extend interfaces without touching business logic and you can test the orchestrator without spinning up a server.

Everything else (memory, knowledge, providers, tools, config) is infrastructure that the layers above consume through clean interfaces.

## Extending the generated project

### Adding a new agent

Create a new file in `agents/` with a class that exposes `run()`, `run_stream()` and a `tools` property. Import it in `orchestrator.py` and decide how it participates: does it replace the conversational agent, run alongside it or get called conditionally? The orchestrator is where that decision lives.

### Adding a new tool

Create a new file in `tools/`, define your async function and add it to `tools/__init__.py`. Then register it in your agent's `TOOL_REGISTRY` dict in `agents/conversational.py`. The `ServiceClient` base class in `tools/base.py` handles HTTP concerns; your tool function just needs to call the right endpoint and return the result. If the new service needs its own base URL and credentials, add a new settings class in `config.py` following the pattern of `AsyncApiSettings`.

### Adding middleware

To add a new context provider, subclass `ContextProvider` in `middleware.py` and override `before_run()` and/or `after_run()`. To add a new tool filter, subclass `ToolFilter` and override `before_tool()` and/or `after_tool()`. Then wire it into the pipeline in `orchestrator.py`.

### Implementing knowledge retrieval

Open `knowledge/provider.py` and fill in the `search()` and `ingest()` methods with your retrieval logic. The `KnowledgeResult` dataclass is already defined; return a list of those from your search implementation. The agent calls `search()` before every response to ground its answers in your data, so keep the latency low.

### Switching memory providers

The memory provider is baked in at generation time. If you need to switch later, replace the contents of `memory/provider.py` with the implementation for your new provider. The interface (`store`, `recall`, `get_all`) stays the same so nothing else in the codebase needs to change.

### Adding WebSocket features

The WebSocket endpoint in `interfaces/server.py` follows a simple JSON protocol. The customer WebSocket sends JSON with a `message` field; the server responds with `token`, `done` or `error` typed messages. The operator WebSocket handles approval requests, live transcripts and handoff commands. To add features like typing indicators or presence, define new message types and handle them in the appropriate WebSocket handler.

## License

MIT
