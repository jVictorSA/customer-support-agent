# Architecture

This document is the committed canonical architecture contract. Keep it updated
when a boundary, transaction rule, or extension point changes.

## Evidence

- `src/app/modules/health/` — original reference module for
  the four-layer structure, `Protocol` port and composition root.
- `src/app/modules/{categories,products,customers,orders,promotions}/`
  — implemented business modules with the same layering.
- `src/app/core/exceptions.py` and
  `src/app/presentation/` — shared exception base, global
  error handler and pagination contract.
- `src/app/infrastructure/importing/` and
  `src/app/cli/` — CSV import adapter and command entrypoint.
- `src/app/db/session.py` — session-per-request and
  transaction ownership.
- `src/app/db/base.py` and
  `src/app/db/metadata.py` — declarative base, naming
  convention and Alembic model registration.
- `src/app/main.py` — router registration and lifespan.
- `tests/health/`, `tests/integration/test_database.py` — established test
  seams.
- `.agents/project-context/conventions.md` — confirmed intentional patterns
  evidenced by code.

## Module boundaries

- `domain` may import: standard library and other `domain` files only.
- `domain` must not import: SQLAlchemy, FastAPI, Pydantic, `application`,
  `infrastructure`, or `presentation`.
- `application` may import: standard library, `domain`, its own `application`
  files, and `core.exceptions` (shared error base only).
- `application` must not import: SQLAlchemy, FastAPI, `infrastructure`,
  `presentation`, or `core.config`.
- `infrastructure` may import: `application`, `domain`, `db`, `core`, and
  third-party infrastructure libraries (for example SQLAlchemy).
- `infrastructure` must not import: `presentation` or FastAPI.
- `presentation` may import: `application`, `core`, FastAPI, and Pydantic.
- `presentation` must not import: `infrastructure` except in
  `presentation/dependencies.py`, which is the module composition root.
- `core` may import: standard library, Pydantic/Pydantic Settings and no
  business modules. `core.exceptions` is framework-agnostic.
- `db` may import: SQLAlchemy, `core`, and ORM models through
  `db/metadata.py` only. It must not import `presentation`.
- Shared `presentation/` (top-level) contains cross-cutting HTTP concerns:
  exception handlers and the pagination envelope. It may import `core` and
  FastAPI/Pydantic, and is imported by module routers.
- Shared `infrastructure/importing/` is a cross-module adapter for bulk CSV
  loading; it may import ORM models and `db.session`. `cli/` is a thin command
  entrypoint over that adapter.
- `main.py` may import: `presentation`, `db`, and `core`; it must not contain
  business rules.
- Business behavior belongs in: `domain` (pure rules/value objects) or the
  application use case; never in routers or repositories.
- Interfaces are `typing.Protocol` declarations in
  `application/interfaces.py`; use cases receive dependencies through the
  constructor and do not read settings directly. Evidence:
  `modules/health/application/interfaces.py`,
  `modules/health/application/check_database_health.py`.

## Persistence and state

- Transaction ownership: every public repository method opens
  `async with session.begin()`, including reads; the repository owns commit and
  rollback. Routers and use cases must not call `session.commit()` or receive
  an `AsyncSession`. Evidence: `db/session.py`,
  `modules/health/infrastructure/repository.py`.
- One `AsyncSession` per request, created and closed by `get_session`; the
  session factory uses `expire_on_commit=False` and `autoflush=False`.
  Evidence: `src/app/db/session.py`.
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
  `src/app/main.py`.
- Primary keys are integer `Identity()` columns named after the entity
  (`category_id`, `product_id`, etc.). `order_items` uses the composite key
  `(order_id, product_id)`. Evidence: module `infrastructure/models.py`
  and the initial Alembic migration.
- Every table uses the `TimestampMixin` from `db/base.py` (`created_at` and
  `updated_at`, timezone-aware, server default `now()`).
- Money uses `Numeric(12, 2)` and `Decimal` in domain/repository; response
  schemas expose `float`.
- Enums are native Postgres types (`product_status`, `order_status`,
  `payment_method`) backed by Python `StrEnum` values. Changing values requires
  an explicit `ALTER TYPE` migration.
- New ORM models must be imported in
  `src/app/db/metadata.py` so `--autogenerate` sees them.
- UTC is the storage/application timezone; local time conversion happens only
  at presentation. Timestamps must be timezone-aware. Evidence: `compose.yaml`
  (`TZ: UTC`) and `README.md` (architecture decisions).
- List endpoints use `page`/`page_size` (default 20, max 100) and return
  `{items, total, page, page_size}`. Evidence:
  `src/app/presentation/pagination.py`.
- Expected application errors use `AppError` subclasses in `core.exceptions` and
  module-specific exceptions in `application/exceptions.py`. The handler in
  `presentation/exception_handlers.py` returns `{code, message}` with 404 for
  `NotFoundError`, 409 for `ConflictError` and 400 otherwise.
- The CSV importer is the only bulk-loading path. It runs outside startup, in a
  single transaction, upserts by primary key, preserves `created_at` on updates
  and resets integer sequences after loading explicit IDs. Evidence:
  `infrastructure/importing/csv_importer.py`, `cli/import_csv.py`.
- Open decisions (do not invent them silently): authentication/authorization,
  lint/format/type-check/CI tooling, and the full error catalog beyond 404/409/400.

## Extension points

- Public-interface registration: create a module router in
  `modules/<module>/presentation/router.py` and include it in
  `src/app/main.py`.
- Dependency declaration: wire concrete repositories/use cases in
  `modules/<module>/presentation/dependencies.py` using FastAPI `Depends`;
  override these providers in tests via `app.dependency_overrides`. Evidence:
  `modules/health/presentation/dependencies.py`.
- Settings: add fields to `Settings` in `core/config.py`; never read
  environment variables inside use cases or repositories.
- Metadata: register models in `db/metadata.py`.
- Error handling: raise an `AppError` subclass from the use case; register the
  global handler once in `main.py` via `register_exception_handlers`.
- Pagination: use `PaginationParams` and `Page[T]` from
  `presentation/pagination.py`; repositories return `(items, total)`.
- Bulk data: use the `import-csv` command; do not import CSVs at API startup.
- Observability convention: `logging.getLogger(__name__)`; never `print`;
  error details in HTTP responses only when `APP_ENV=development`.
- New module workflow: use the `new-module` skill
  (`.agents/skills/new-module/SKILL.md`), which encodes the full checklist from
  package creation to tests, migration, registration and documentation.
