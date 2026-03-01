# NexFlow Backend

> **AI-Powered Workflow Manager** — multi-agent orchestration with OAuth integrations.

NexFlow is a production-ready FastAPI backend that lets users interact with their connected apps (GitHub, Gmail, Google Calendar, Google Drive, Google Photos, LinkedIn) through a conversational AI interface. A LangGraph supervisor agent orchestrates tool calls via a pluggable MCP (Model Context Protocol) registry.

---

## Table of Contents

- [Features](#features)
- [Architecture Overview](#architecture-overview)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Local Development](#local-development)
  - [Environment Variables](#environment-variables)
- [API Reference](#api-reference)
  - [Auth](#auth)
  - [Chat](#chat)
  - [Integrations](#integrations)
  - [Health](#health)
- [Agent & MCP System](#agent--mcp-system)
- [Database & Migrations](#database--migrations)
- [Testing](#testing)
- [Deployment](#deployment)
  - [Docker](#docker)
  - [CI/CD Pipeline](#cicd-pipeline)
  - [Render](#render)
- [Rate Limits](#rate-limits)
- [Contributing](#contributing)

---

## Features

- **Conversational AI** — streaming SSE chat powered by OpenAI or OpenRouter (Claude, GPT, etc.)
- **LangGraph Supervisor Agent** — multi-step reasoning loop with tool call support and configurable iteration limits
- **MCP Tool Registry** — pluggable adapter system; each OAuth integration exposes callable tools to the agent
- **OAuth Integrations** — connect GitHub, Google (Gmail, Calendar, Drive, Photos), and LinkedIn per-user
- **JWT Auth** — access + refresh token flow with bcrypt-hashed passwords; token revocation via Redis
- **Async PostgreSQL** — SQLAlchemy 2 async + asyncpg with Alembic migrations
- **Redis** — refresh-token blocklist and rate limiting
- **Structured Logging** — `structlog` with correlation IDs per request
- **Production Middleware** — CORS, global error handling, per-route rate limiters
- **Readiness Probe** — checks DB, Redis, and LLM client liveness
- **CI/CD** — GitHub Actions → GHCR image push → Render deploy

---

## Architecture Overview

```
Client (Frontend)
    │  HTTP / SSE
    ▼
FastAPI (main.py)
    ├── Middleware: CORS · ErrorHandler · CorrelationId
    ├── /api/v1/auth         → AuthService (JWT + bcrypt)
    ├── /api/v1/chat         → ChatService → LangGraph Supervisor Agent
    │                                             └── MCP Tool Registry
    ├── /api/v1/integrations → IntegrationService (OAuth 2.0 flows)
    └── /api/v1/health       → DB / Redis / LLM probes

LangGraph Agent Loop
    supervisor_node ──(tool calls?)──► tool_executor_node
         ▲                                     │
         └─────────────────────────────────────┘
                (iterates up to MAX_TOOL_CALLS_PER_TURN)

MCP Registry
    ├── github adapter       (repos, issues, PRs, gists, …)
    ├── gmail adapter        (send, list, read, …)
    ├── google_calendar      (events CRUD)
    ├── google_drive         (files list/upload/download)
    ├── google_photos        (albums, media)
    └── linkedin adapter     (profile, posts, connections)
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | FastAPI 0.115+ |
| Language | Python 3.12 |
| AI / Agents | LangGraph 0.2+, LangChain-Core, LangChain-OpenAI |
| LLM Providers | OpenAI, OpenRouter (configurable) |
| Database | PostgreSQL 16 via SQLAlchemy 2 async + asyncpg |
| Migrations | Alembic |
| Cache / Queue | Redis 7 via redis-py (hiredis) |
| Auth | python-jose (JWT HS256), passlib + bcrypt, Fernet |
| OAuth | Authlib |
| HTTP Client | httpx |
| Logging | structlog |
| Testing | pytest, pytest-asyncio |
| Containerisation | Docker (multi-stage, python:3.12-slim) |
| CI/CD | GitHub Actions → GHCR → Render |

---

## Project Structure

```
backend/
├── main.py                    # App factory, lifespan (startup/shutdown)
├── requirements.txt
├── Dockerfile                 # Multi-stage build
├── docker-compose.yml         # Local Postgres + Redis
├── alembic.ini
├── alembic/                   # Migration scripts
├── render.yaml                # Render deployment config
├── .env.example               # Environment variable template
│
├── app/
│   ├── config.py              # Pydantic Settings (all env vars)
│   ├── database.py            # Async SQLAlchemy engine + session
│   ├── redis.py               # Shared Redis client
│   ├── dependencies.py        # FastAPI dependency injection helpers
│   │
│   ├── routers/
│   │   ├── auth.py            # /api/v1/auth
│   │   ├── chat.py            # /api/v1/chat
│   │   ├── integrations.py    # /api/v1/integrations
│   │   └── health.py          # /api/v1/health
│   │
│   ├── services/
│   │   ├── auth_service.py    # Register, login, refresh, logout
│   │   ├── chat_service.py    # Conversation/message CRUD + agent dispatch
│   │   ├── integration_service.py  # OAuth flow orchestration
│   │   └── llm_client.py      # LLM abstraction (OpenAI / OpenRouter)
│   │
│   ├── agents/
│   │   └── supervisor.py      # LangGraph StateGraph (supervisor + tool_executor)
│   │
│   ├── mcp/
│   │   ├── base.py            # BaseMCPTool abstract class
│   │   ├── registry.py        # Global tool registry (init + lookup)
│   │   └── adapters/
│   │       ├── github.py
│   │       ├── gmail.py
│   │       ├── google_calendar.py
│   │       ├── google_drive.py
│   │       ├── google_photos.py
│   │       └── linkedin.py
│   │
│   ├── models/                # SQLAlchemy ORM models
│   │   ├── user.py
│   │   ├── conversation.py
│   │   ├── message.py
│   │   ├── agent_session.py
│   │   ├── tool_execution.py
│   │   ├── integration.py
│   │   └── oauth_connection.py
│   │
│   ├── schemas/               # Pydantic request/response schemas
│   │   ├── auth.py
│   │   ├── chat.py
│   │   ├── integration.py
│   │   └── common.py
│   │
│   ├── middleware/
│   │   ├── cors.py            # CORS origins from ALLOWED_ORIGINS env
│   │   ├── error_handler.py   # Global exception → JSON error response
│   │   └── rate_limiter.py    # Redis-backed per-route rate limiters
│   │
│   └── utils/
│       ├── logger.py          # structlog setup + get_logger helper
│       └── correlation.py     # CorrelationId middleware
│
└── tests/
    ├── conftest.py
    ├── test_config.py
    ├── test_dependencies.py
    ├── test_mcp_registry.py
    ├── test_middleware.py
    ├── test_routers.py
    ├── test_schemas.py
    ├── test_service_auth.py
    ├── test_service_chat.py
    ├── test_service_integration.py
    └── test_utils_crypto.py
```

---

## Getting Started

### Prerequisites

- Python 3.12+
- Docker & Docker Compose
- An OpenAI **or** OpenRouter API key
- (Optional) OAuth app credentials for GitHub / Google / LinkedIn

### Local Development

```bash
# 1. Clone the repo
git clone https://github.com/MuditGarg007/nexflow-backend.git
cd nexflow-backend

# 2. Start infrastructure (Postgres + Redis)
docker compose up -d

# 3. Create and activate virtual environment
python -m venv venv
source venv/bin/activate    # Windows: venv\Scripts\activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Configure environment
cp .env.example .env
# Edit .env and fill in your keys (see Environment Variables section)

# 6. Run database migrations
alembic upgrade head

# 7. Start the dev server
uvicorn main:app --reload --port 8000
```

The API is now available at `http://localhost:8000`.  
Interactive docs: `http://localhost:8000/docs`

---

### Environment Variables

Copy `.env.example` to `.env` and populate the values:

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | ✅ | PostgreSQL async DSN (`postgresql+asyncpg://...`) |
| `REDIS_URL` | ✅ | Redis DSN (`redis://localhost:6379/0`) |
| `SECRET_KEY` | ✅ | JWT signing secret (64-char random string) |
| `FERNET_KEY` | ✅ | Fernet key for encrypting OAuth tokens — generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `OPENAI_API_KEY` | ✅* | OpenAI API key (if `LLM_PROVIDER=openai`) |
| `OPENROUTER_API_KEY` | ✅* | OpenRouter API key (if `LLM_PROVIDER=openrouter`) |
| `LLM_PROVIDER` | | `openai` (default) or `openrouter` |
| `DEFAULT_MODEL` | | OpenAI model name, default `gpt-5-mini` |
| `OPENROUTER_DEFAULT_MODEL` | | OpenRouter model, default `anthropic/claude-3.5-sonnet` |
| `GITHUB_CLIENT_ID` | | GitHub OAuth App Client ID |
| `GITHUB_CLIENT_SECRET` | | GitHub OAuth App Client Secret |
| `GOOGLE_CLIENT_ID` | | Google OAuth 2.0 Client ID |
| `GOOGLE_CLIENT_SECRET` | | Google OAuth 2.0 Client Secret |
| `LINKEDIN_CLIENT_ID` | | LinkedIn OAuth App Client ID |
| `LINKEDIN_CLIENT_SECRET` | | LinkedIn OAuth App Client Secret |
| `FRONTEND_URL` | | Frontend origin, used for OAuth redirects (default `http://localhost:3000`) |
| `ALLOWED_ORIGINS` | | Comma-separated CORS origins |
| `ENVIRONMENT` | | `development` or `production` |
| `LOG_LEVEL` | | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | | JWT access token TTL (default `15`) |
| `REFRESH_TOKEN_EXPIRE_DAYS` | | JWT refresh token TTL (default `7`) |
| `RATE_LIMIT_CHAT` | | Chat requests per minute per user (default `30`) |
| `RATE_LIMIT_AUTH` | | Auth requests per minute per IP (default `5`) |
| `RATE_LIMIT_TOOLS` | | Tool calls per minute per user (default `60`) |
| `MAX_TOOL_CALLS_PER_TURN` | | Agent tool call iteration cap (default `5`) |

*At least one LLM provider key is required.

---

## API Reference

Base URL: `http://localhost:8000/api/v1`  
Full interactive docs: `/docs` (Swagger UI) · `/redoc`

### Auth

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/auth/register` | None | Register a new user |
| `POST` | `/auth/login` | None | Login and receive access + refresh tokens |
| `POST` | `/auth/refresh` | None | Exchange refresh token for new token pair |
| `POST` | `/auth/logout` | Bearer | Revoke refresh token |
| `GET` | `/auth/me` | Bearer | Get current user profile |

**Register / Login request bodies:**
```json
// POST /auth/register
{ "email": "user@example.com", "password": "secret", "display_name": "Alice" }

// POST /auth/login
{ "email": "user@example.com", "password": "secret" }

// POST /auth/refresh | /auth/logout
{ "refresh_token": "<token>" }
```

**Token response:**
```json
{ "access_token": "...", "refresh_token": "...", "token_type": "bearer" }
```

---

### Chat

All chat endpoints require `Authorization: Bearer <access_token>`.

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/chat/conversations` | List all user conversations |
| `POST` | `/chat/conversations` | Create a new conversation |
| `GET` | `/chat/conversations/{id}` | Get conversation with full message history |
| `DELETE` | `/chat/conversations/{id}` | Delete a conversation |
| `POST` | `/chat/conversations/{id}/messages` | Send a message — responds as **SSE stream** |

**SSE Event Stream** (`POST /chat/conversations/{id}/messages`):

```
event: thinking
data: "Planning to call 2 tool(s)"

event: tool_call
data: {"tool": "github_list_repos", "status": "executing"}

event: tool_result
data: {"tool": "github_list_repos", "result": {...}}

event: response
data: "Here are your repositories: ..."
```

---

### Integrations

All endpoints require `Authorization: Bearer <access_token>`.

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/integrations/` | List all available integrations (with `is_connected` flag) |
| `GET` | `/integrations/connected` | List integrations the current user has connected |
| `GET` | `/integrations/{id}/oauth/authorize` | Get OAuth authorization URL to connect an integration |
| `GET` | `/integrations/{id}/oauth/callback` | OAuth callback handler (redirect from provider) |
| `DELETE` | `/integrations/{id}/disconnect` | Disconnect an integration |
| `GET` | `/integrations/{id}/tools` | List available MCP tools for an integration |

**Supported integration IDs:** `github` · `gmail` · `google_calendar` · `google_drive` · `google_photos` · `linkedin`

---

### Health

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `GET` | `/health` | None | Liveness probe — returns `{"status": "ok"}` |
| `GET` | `/health/ready` | None | Readiness probe — checks DB, Redis, and LLM client |

**Readiness response:**
```json
{
  "status": "ok",
  "database": "ok",
  "redis": "ok",
  "llm": "ok"
}
```

---

## Agent & MCP System

### LangGraph Supervisor

The agent runs as a compiled `StateGraph` with two nodes:

```
supervisor_node
    │  decision: call tools OR respond
    ▼
tool_executor_node  ──►  supervisor_node  (loop)
    │
    └─► END  (when final_response is set or max_iterations reached)
```

**Agent state fields:**

| Field | Description |
|---|---|
| `messages` | Full conversation history (LangChain message types) |
| `user_id` | Owning user — used for OAuth token lookup |
| `connected_integration_ids` | Only tools from connected integrations are injected |
| `iteration_count` | Tracks loop iterations |
| `max_iterations` | Configurable cap (default from `MAX_TOOL_CALLS_PER_TURN`) |
| `final_response` | Set when the agent decides to respond without tool calls |
| `events` | List of SSE event dicts emitted to the client |

### MCP Tool Registry

Each integration exposes tools via a `BaseMCPTool` subclass. Tools are auto-registered at app startup in `init_registry()`. Only tools whose `status == "stable"` are sent to the LLM by default.

**GitHub tools (examples):** `github_list_repos`, `github_create_issue`, `github_list_pull_requests`, `github_create_gist`  
**Gmail tools:** `gmail_list_messages`, `gmail_send_email`, `gmail_read_message`  
**Google Calendar tools:** `google_calendar_list_events`, `google_calendar_create_event`  
**Google Drive tools:** `google_drive_list_files`, `google_drive_upload_file`  
**Google Photos tools:** `google_photos_list_albums`, `google_photos_list_media`  
**LinkedIn tools:** `linkedin_get_profile`, `linkedin_create_post`

---

## Database & Migrations

The app uses async SQLAlchemy 2 with PostgreSQL. Migration files live in `alembic/`.

```bash
# Create a new migration
alembic revision --autogenerate -m "description"

# Apply all pending migrations
alembic upgrade head

# Downgrade one step
alembic downgrade -1
```

**ORM Models:**

| Model | Table | Description |
|---|---|---|
| `User` | `users` | Core user account |
| `Conversation` | `conversations` | Chat sessions |
| `Message` | `messages` | Individual chat messages with role + tool_calls |
| `AgentSession` | `agent_sessions` | Per-turn agent execution metadata |
| `ToolExecution` | `tool_executions` | Audit log of individual tool calls |
| `Integration` | `integrations` | Catalog of available integrations |
| `OAuthConnection` | `oauth_connections` | Per-user OAuth token storage (Fernet-encrypted) |

---

## Testing

Tests use `pytest` with `pytest-asyncio`.

```bash
# Run all tests
pytest -v

# Run a specific test file
pytest tests/test_service_auth.py -v

# Run with coverage (if pytest-cov is installed)
pytest --cov=app --cov-report=term-missing
```

**Test modules:**

| File | Coverage area |
|---|---|
| `test_config.py` | Settings loading |
| `test_dependencies.py` | FastAPI dependency injection |
| `test_mcp_registry.py` | MCP tool registration + lookup |
| `test_middleware.py` | CORS, error handler, rate limiter |
| `test_routers.py` | HTTP endpoint integration |
| `test_schemas.py` | Pydantic schema validation |
| `test_service_auth.py` | AuthService (register, login, refresh, logout) |
| `test_service_chat.py` | ChatService (conversation management, agent dispatch) |
| `test_service_integration.py` | IntegrationService (OAuth flows, connect/disconnect) |
| `test_utils_crypto.py` | Fernet encryption helpers |

---

## Deployment

### Docker

```bash
# Build the image locally
docker build -t nexflow-backend .

# Run the container
docker run -p 8000:8000 --env-file .env nexflow-backend
```

The Dockerfile uses a two-stage build (`python:3.12-slim`) to keep the final image lean.

### CI/CD Pipeline

The GitHub Actions workflow (`.github/workflows/ci.yml`) runs on every push to `main`:

1. **Test job** — installs dependencies and runs `pytest -v`
2. **Build & push job** (runs only if tests pass) — logs into GHCR and pushes tagged image:
   - `ghcr.io/<owner>/nexflow-backend:latest`
   - `ghcr.io/<owner>/nexflow-backend:<git-sha>`

### Render

`render.yaml` defines a web service that pulls the latest image from GHCR. All secrets are injected as environment variables (not committed to the repo):

| Variable | Source |
|---|---|
| `DATABASE_URL` | Render environment (manual) |
| `REDIS_URL` | Render environment (manual) |
| `SECRET_KEY` | Render environment (manual) |
| `FERNET_KEY` | Render environment (manual) |
| `OPENAI_API_KEY` | Render environment (manual) |
| `FRONTEND_URL` | Render environment (manual) |
| `ALLOWED_ORIGINS` | Render environment (manual) |
| `ENVIRONMENT` | `production` (hardcoded in render.yaml) |
| `LOG_LEVEL` | `INFO` (hardcoded in render.yaml) |

---

## Rate Limits

Rate limiting is Redis-backed and applied per-route:

| Scope | Default | Env Variable |
|---|---|---|
| Auth endpoints (`/auth/register`, `/auth/login`) | 5 req/min | `RATE_LIMIT_AUTH` |
| Chat send message | 30 req/min | `RATE_LIMIT_CHAT` |
| Tool calls | 60 req/min | `RATE_LIMIT_TOOLS` |

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes and add tests
4. Run `pytest -v` and ensure all tests pass
5. Open a pull request against `main`

Please follow the existing code style (no unnecessary comments, type hints on all public functions).
