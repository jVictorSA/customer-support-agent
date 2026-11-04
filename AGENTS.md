# AGENTS.md

Project guidance for OpenCode and other coding agents. Keep this file short;
detailed contracts live in `.agents/project-context/`.

## Start here

1. Read `.agents/project-context/PROJECT.md` for any non-trivial task. It is
   the routing map for the other context files.
2. Always load `.agents/project-context/conventions.md` before reporting a
   project-specific issue.
3. For architecture, persistence, or new-module work, read
   `.agents/project-context/architecture.md`.
4. For routes, schemas, configuration, deploy, or migrations, read
   `.agents/project-context/delivery-contracts.md`.
5. For LLM/RAG/tool-calling work, read `.agents/project-context/ai.md`.
6. For business entities, use cases, store rules, or the planned data model,
   read `.agents/project-context/domain.md`.
7. Before validating or committing, read `.agents/project-context/validation.md`.

The always-on rules are in `.agents/rules/` and are loaded automatically. They
are mandatory.

## What this project is

A Python 3.12 FastAPI backend for a customer-support agent for a musical
instrument store. Postgres 17.11, SQLAlchemy 2.x async (`asyncpg`), Alembic,
`pydantic-settings`, `uv`, Docker Compose, pytest/pytest-asyncio. The business
AI integration is not implemented yet; the current `health` module is the
reference Clean Architecture pattern.

## Architecture in one line

`presentation -> application -> domain`; `infrastructure` implements
`application` ports. Routers never touch the database; repositories own all
transactions and commit; use cases depend on `Protocol` ports.

## Commands

```bash
# Unit/contract tests (default gate)
uv run pytest

# Local API + Postgres
docker compose up --build -d
docker compose logs -f api
# API: http://127.0.0.1:8000, docs: http://127.0.0.1:8000/docs

# Integration tests (dedicated test DB, opt-in)
docker compose up -d db
RUN_INTEGRATION_TESTS=1 POSTGRES_DB=customer_support_agent_test \
  uv run pytest -m integration

# Migrations (inside the API container; never at startup)
docker compose exec api alembic current
docker compose exec api alembic revision --autogenerate -m "create products"
docker compose exec api alembic upgrade head
docker compose exec api alembic downgrade -1
```

There is no lint, formatter, type checker, or CI configured. Do not claim they
ran and do not introduce them as if they already existed; propose that
separately.

## Working conventions

- Code identifiers, docstrings, and comments in English. README and project
  docs in Portuguese. API payloads and messages in English.
- Type every public function. Prefer `collections.abc` types and absolute
  imports from `app`. No wildcard imports.
- Use `logging.getLogger(__name__)`, never `print`.
- Configure through `Settings`/environment variables; never hardcode hosts,
  ports, credentials, URLs, model names, or API keys.
- Async only for I/O; never block the event loop.
- Store and process timestamps in UTC; convert to `America/Sao_Paulo` only in
  presentation.
- Do not expose stack traces, SQL, credentials, prompts, or customer PII in
  HTTP responses. Internal detail only when `APP_ENV=development`.
- Do not invent open decisions: primary-key strategy, timestamp mixin, error
  catalog/format, pagination/filters, authentication, and lint/CI tooling are
  still open (no such abstraction or dependency exists in `db/base.py`,
  `pyproject.toml`, or `src/customer_support_agent/`).

## Workflows and skills

- New business module: use the `new-module` skill; it encodes the full
  workflow from package creation to tests, migration and registration.
- Schema change: use the `db-migration` skill; review autogenerate SQL and
  never edit an applied migration.
- Before committing: use the `pre-commit-review` skill on staged changes.
- PR description: use the `pr-description` skill.
- Project context refresh: use the `project-context-setup` skill.

## Definition of done

- Behavior is covered by tests and `uv run pytest` passes.
- Integration tests were run for repository/query/migration changes.
- New endpoints are registered in `src/app/main.py`; new models are registered in
  `db/metadata.py`; new settings are documented in `.env.example` and both
  deploy env files.
- `README.md` and the affected `.agents/project-context/` document are updated
  when a public interface, variable, module boundary, or architectural decision
  changes.
- No secrets, generated migrations left unreviewed, or debug artifacts are
  committed.
