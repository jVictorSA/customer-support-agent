# Architecture

This document is the committed canonical architecture contract. Keep it updated
when a boundary, transaction rule, or extension point changes.

## Evidence

- `src/customer_support_agent/modules/health/` — reference module for the
  four-layer structure, `Protocol` port and composition root.
- `src/customer_support_agent/db/session.py` — session-per-request and
  transaction ownership.
- `src/customer_support_agent/db/base.py` and
  `src/customer_support_agent/db/metadata.py` — declarative base, naming
  convention and Alembic model registration.
- `src/customer_support_agent/app.py` — router registration and lifespan.
- `tests/health/`, `tests/integration/test_database.py` — established test
  seams.
- `.agents/project-context/conventions.md` — confirmed intentional patterns
  evidenced by code.

## Module boundaries

- `domain` may import: standard library and other `domain` files only.
- `domain` must not import: SQLAlchemy, FastAPI, Pydantic, `application`,
  `infrastructure`, or `presentation`.
- `application` may import: standard library, `domain`, and its own
  `application` files.
- `application` must not import: SQLAlchemy, FastAPI, `infrastructure`, or
  `presentation`.
- `infrastructure` may import: `application`, `domain`, `db`, `core`, and
  third-party infrastructure libraries (for example SQLAlchemy).
- `infrastructure` must not import: `presentation` or FastAPI.
- `presentation` may import: `application`, `core`, FastAPI, and Pydantic.
- `presentation` must not import: `infrastructure` except in
  `presentation/dependencies.py`, which is the module composition root.
- `core` may import: standard library and Pydantic Settings. It must not import
  business modules.
- `db` may import: SQLAlchemy, `core`, and ORM models through
  `db/metadata.py` only. It must not import `presentation`.
- `app.py` may import: `presentation`, `db`, and `core`; it must not contain
  business rules.
- Business behavior belongs in: `domain` (pure rules/value objects) or the
  application use case; never in routers or repositories.
- Ports are `typing.Protocol` declarations in `application/ports.py`; use cases
  receive dependencies through the constructor and do not read settings
  directly. Evidence: `modules/health/application/ports.py`,
  `modules/health/application/check_database_health.py`.

## Persistence and state

- Transaction ownership: every public repository method opens
  `async with session.begin()`, including reads; the repository owns commit and
  rollback. Routers and use cases must not call `session.commit()` or receive
  an `AsyncSession`. Evidence: `db/session.py`,
  `modules/health/infrastructure/persistence/repository.py`.
- One `AsyncSession` per request, created and closed by `get_session`; the
  session factory uses `expire_on_commit=False` and `autoflush=False`.
  Evidence: `src/customer_support_agent/db/session.py`.
- Engine and session factory are lazy and `lru_cache`d; never create an engine
  at module import time. Evidence: `db/session.py`.
- Multi-write atomicity is expressed as one specific repository method; use
  cases do not coordinate multiple transactions.
- Repositories map ORM models to domain entities/DTOs and never return ORM
  models to use cases. Relationships needed after the transaction must be
  loaded inside it (`selectinload`/`joinedload`).
- Source of truth for the schema is Alembic. Migrations are applied manually,
  never automatically at API startup. Applied migrations are immutable; add a
  new migration instead. Evidence: `README.md` (Migrations),
  `alembic/env.py`, and the absence of migration execution in
  `src/customer_support_agent/app.py`.
- New ORM models must be imported in
  `src/customer_support_agent/db/metadata.py` so `--autogenerate` sees them.
- UTC is the storage/application timezone; local time conversion happens only
  at presentation. Timestamps must be timezone-aware. Evidence: `compose.yaml`
  (`TZ: UTC`) and `README.md` (architecture decisions).
- Open decisions (do not invent them silently): default primary-key strategy,
  `created_at`/`updated_at` mixin, error catalog/format, pagination/filters,
  authentication. Evidence: no such abstraction exists in `db/base.py`, no
  auth dependency is declared in `pyproject.toml`, and no error catalog module
  exists.

## Extension points

- Public-interface registration: create a module router in
  `modules/<module>/presentation/router.py` and include it in
  `src/customer_support_agent/app.py`.
- Dependency declaration: wire concrete repositories/use cases in
  `modules/<module>/presentation/dependencies.py` using FastAPI `Depends`;
  override these providers in tests via `app.dependency_overrides`. Evidence:
  `modules/health/presentation/dependencies.py`.
- Settings: add fields to `Settings` in `core/config.py`; never read
  environment variables inside use cases or repositories.
- Metadata: register models in `db/metadata.py`.
- Observability convention: `logging.getLogger(__name__)`; never `print`;
  error details in HTTP responses only when `APP_ENV=development`.
- New module workflow: use the `new-module` skill
  (`.agents/skills/new-module/SKILL.md`), which encodes the full checklist from
  package creation to tests, migration, registration and documentation.
