# Project Review Context

## Evidence

- Committed project context: `.agents/project-context/architecture.md`
  (canonical layer/persistence contract), `domain.md` (business scope and
  planned data model), `conventions.md`, `delivery-contracts.md`,
  `validation.md`, and `ai.md`.
- Repository documentation: `README.md` (setup, endpoints, decisions).
- Tooling/dependencies: `pyproject.toml`, `uv.lock`, `Dockerfile`, `compose.yaml`,
  `compose.override.yaml`, `compose.prod.yaml`, `alembic.ini`, `alembic/env.py`,
  `.env.example`, `deploy/.env.hml`, `deploy/.env.prod`.
- Established implementation examples:
  `src/customer_support_agent/modules/health/` (reference Clean Architecture
  module), `src/customer_support_agent/core/config.py`,
  `src/customer_support_agent/db/` (base, metadata, session),
  `tests/health/`, `tests/integration/test_database.py`.

## Project map

- Runtime and framework: Python `>=3.12`; FastAPI with `fastapi[standard]`;
  `uv` for environment and lockfile; Uvicorn in production; Docker Compose for
  local/dev/hml/prod (`pyproject.toml`, `Dockerfile`, `compose*.yaml`).
- Persistence/state: Postgres 17.11; SQLAlchemy 2.x async with `asyncpg`;
  one `AsyncSession` per request; repositories own transactions; Alembic async
  migrations with the same `Settings` as the application
  (`src/customer_support_agent/db/session.py`, `alembic/env.py`,
  `src/customer_support_agent/modules/health/infrastructure/persistence/repository.py`).
- Configuration: `pydantic-settings` `Settings` in
  `src/customer_support_agent/core/config.py`; environment variables are the
  source of truth, `.env` is local convenience only.
- Main code areas:
  - `src/customer_support_agent/app.py` — FastAPI app, lifespan, router
    registration.
  - `src/customer_support_agent/core/` — application settings.
  - `src/customer_support_agent/db/` — declarative base, Alembic metadata,
    engine/session factory/startup probe.
  - `src/customer_support_agent/modules/<module>/` — `domain`,
    `application`, `infrastructure`, `presentation`.
  - `tests/` — unit/contract tests plus opt-in integration tests.
  - `alembic/versions/` — migration scripts.
- Domain data: the business scope, store rules and planned data model are
  summarized in `.agents/project-context/domain.md`. They are not implemented
  as entities/models yet (`src/customer_support_agent/db/metadata.py` imports no
  module models and `alembic/versions/` has no migration).
- AI integration: planned by the product scope in
  `.agents/project-context/domain.md` but not implemented; no LLM/RAG provider
  dependency or provider configuration exists in `pyproject.toml` or
  `core/config.py` at the time of this profile.

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
  changing the planned data model.
- Always read `.agents/project-context/conventions.md` before reporting a
  project-specific finding.
- Read `.agents/project-context/validation.md` for the verified commands and
  known tooling gaps.
