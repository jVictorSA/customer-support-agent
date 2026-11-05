# Project Review Context

## Evidence

- Committed project context: `.agents/project-context/architecture.md`
  (canonical layer/persistence contract), `domain.md` (business scope and
  data model), `conventions.md`, `delivery-contracts.md`,
  `validation.md`, and `ai.md`.
- Repository documentation: `README.md` (setup, endpoints, decisions).
- Tooling/dependencies: `pyproject.toml`, `uv.lock`, `Dockerfile`, `compose.yaml`,
  `compose.override.yaml`, `compose.prod.yaml`, `alembic.ini`, `alembic/env.py`,
  `.env.example`, `deploy/.env.hml`, `deploy/.env.prod`.
- Established implementation examples:
  `src/app/modules/health/` (reference Clean Architecture
  module), `src/app/core/config.py`,
  `src/app/db/` (base, metadata, session),
  `tests/health/`, `tests/integration/test_database.py`.

## Project map

- Runtime and framework: Python `>=3.12`; FastAPI with `fastapi[standard]`;
  `uv` for environment and lockfile; Uvicorn in production; Docker Compose for
  local/dev/hml/prod (`pyproject.toml`, `Dockerfile`, `compose*.yaml`).
- Persistence/state: Postgres 17.11; SQLAlchemy 2.x async with `asyncpg`;
  one `AsyncSession` per request; repositories own transactions; integer
  `Identity` PKs, `TimestampMixin`, native Postgres enums and `Numeric(12,2)`
  money; Alembic async migrations with the same `Settings` as the application
  (`src/app/db/`, `alembic/env.py`).
- Configuration: `pydantic-settings` `Settings` in
  `src/app/core/config.py`; environment variables are the
  source of truth, `.env` is local convenience only.
- Main code areas:
  - `src/app/main.py` — FastAPI app, lifespan, router
    registration.
  - `src/app/core/` — application settings and shared
    exception base (`exceptions.py`).
  - `src/app/db/` — declarative base, timestamp mixin,
    Alembic metadata, engine/session factory/startup probe.
  - `src/app/presentation/` — global error handler and
    pagination envelope.
  - `src/app/modules/<module>/` — `domain`,
    `application`, `infrastructure`, `presentation`.
  - `src/app/modules/documents/` — PDF ingestion, hierarchy/chunking,
    DeepSeek summaries and Jina embeddings; `src/app/worker.py` is the Celery
    composition root.
  - `src/app/modules/{auth,conversations,messages,complaints,agent}/` —
    JWT authentication, conversation persistence, complaints, hybrid retrieval,
    ReAct orchestration, deterministic tools and durable agent traces;
    `src/app/agent_worker.py` is the chat worker composition root.
  - `src/app/infrastructure/importing/` and `cli/` — CSV
    importer and `import-csv` command.
  - `tests/` — unit/contract tests plus opt-in integration tests.
  - `alembic/versions/` — migration scripts (initial migration included).
- Domain data: the business scope, store rules and data model are summarized in
  `.agents/project-context/domain.md`. The six tables and the
  `categories/products/customers/orders/promotions` modules are implemented with
  GET-only routes; the conversation flow adds `conversations`, `messages`,
  `complaints`, `agent_runs` and `agent_steps`.
- AI integration: document ingestion and the conversational agent are
  implemented (Docling, DeepSeek summaries/agents, Jina embeddings, MinIO,
  Celery/RabbitMQ, pgvector). Retrieval is hybrid pgvector + Portuguese FTS with
  RRF and parent-child expansion. Text-to-SQL, reranking and semantic memory are
  not implemented. Provider configuration lives in `core/config.py`.

## Context selection

- Read `.agents/project-context/architecture.md` when: adding or changing
  modules, layers, imports, repositories, transactions, ORM models, migrations,
  dependency wiring, or router registration.
- Read `.agents/project-context/delivery-contracts.md` when: changing API
  routes/schemas/status codes, error exposure, configuration variables,
  Compose/deploy files, secrets, or schema compatibility.
- Read `.agents/project-context/ai.md` when: touching LLM/RAG/tool-calling code,
  provider settings, prompts, customer data handling, or external integration
  boundaries, or omit if the change has no AI/external-integration surface.
- Read `.agents/project-context/domain.md` when: modeling business entities,
  implementing use cases, writing prompts/tools that depend on store rules, or
  changing the data model.
- Always read `.agents/project-context/conventions.md` before reporting a
  project-specific finding.
- Read `.agents/project-context/validation.md` for the verified commands and
  known tooling gaps.
