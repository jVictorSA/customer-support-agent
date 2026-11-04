# Known Intentional Conventions

Record only patterns confirmed by documentation or established code. Each entry
must state why it is expected and the evidence source.

- **Four-layer module directories** — every business module is split into
  `domain`, `application`, `infrastructure`, and `presentation` so dependency
  direction stays explicit and the module is testable without a database.
  Evidence: `src/app/modules/health/` and
  `.agents/project-context/architecture.md`.
- **`Protocol` interfaces instead of concrete repository types** — use cases
  depend on structural interfaces, enabling fakes and keeping `application`
  free of SQLAlchemy. Evidence:
  `modules/health/application/interfaces.py`,
  `modules/health/application/check_database_health.py`.
- **Repository-owned transactions on every public method** — `session.begin()`
  in reads and writes returns the connection to the pool and centralizes
  commit/rollback; it is not an oversight that reads open a transaction.
  Evidence: `db/session.py`,
  `modules/health/infrastructure/repository.py`.
- **Composition root in `presentation/dependencies.py`** — this is the only
  presentation file allowed to import `infrastructure`; other presentation
  files import only `application`. Evidence:
  `modules/health/presentation/dependencies.py`,
  `.agents/project-context/architecture.md`.
- **Lazy cached engine, session factory and settings** — `lru_cache` avoids
  import-time side effects and lets tests clear caches; global mutable state
  is otherwise avoided. Evidence: `core/config.py`, `db/session.py`,
  `tests/integration/test_database.py`.
- **Frozen slotted result dataclasses** — use cases return small immutable
  application results instead of leaking framework objects. Evidence:
  `modules/health/application/check_database_health.py`
  (`DatabaseHealthResult`).
- **Health module as the smallest reference** — it demonstrates the minimal
  structure; `categories`, `products`, `customers`, `orders` and `promotions`
  show the full CRUD/pagination pattern. Evidence:
  `src/app/modules/` and the project README.
- **Development-only error detail** — `/health/db` exposes a `detail` field only
  when `APP_ENV=development`; `hml`/`prod` omit it. Evidence:
  `modules/health/presentation/router.py`, `core/config.py`.
- **English code, Portuguese documentation** — identifiers, docstrings and code
  comments are English; README and project docs are Portuguese; API payloads are
  English. Evidence: source files versus `README.md`.
- **UTC everywhere in storage/application** — local `America/Sao_Paulo`
  conversion belongs to presentation/formatting only. Evidence: `compose.yaml`
  (`TZ: UTC`) and `README.md` (architecture decisions).
- **`logging`, never `print`** — server-side diagnostics use module loggers.
  Evidence: `main.py`, `db/session.py`,
  `modules/health/...`.
- **Tests override FastAPI dependencies** — contract tests replace providers via
  `app.dependency_overrides` and use realistic fakes rather than hitting the
  database. Evidence: `tests/conftest.py`, `tests/health/test_health_db.py`.
- **Integration tests are opt-in via a marker** — `pytest.mark.integration` plus
  `RUN_INTEGRATION_TESTS=1` keeps the default suite fast and database-free.
  Evidence: `pyproject.toml`, `tests/integration/test_database.py`.
- **Migrations are explicit and immutable** — no startup migration, no editing
  applied revisions; a schema change is a new reviewed migration. Evidence:
  `README.md` (Migrations), `alembic/env.py`, and the absence of migration
  calls in `src/app/main.py`.
- **`db/metadata.py` is the only `db` file importing module models** — it is the
  metadata composition root for Alembic autogenerate. Evidence:
  `src/app/db/metadata.py`.
- **Integer identity primary keys** — every root table has an `Identity()` PK
  named after the entity (`category_id`, `product_id`, etc.); `order_items`
  uses the composite key `(order_id, product_id)`. This matches the source data
  and keeps foreign keys explicit. Evidence: module persistence models and the
  initial migration.
- **`TimestampMixin` on every model** — `created_at`/`updated_at` are
  timezone-aware and database-defaulted; importer updates preserve
  `created_at`. Evidence: `db/base.py`, module models.
- **Native Postgres enums backed by `StrEnum`** — `product_status`,
  `order_status` and `payment_method` are real database types, and
  `values_callable` stores the member values. Evidence: module models and the
  initial migration.
- **`Numeric` + `Decimal` internally, `float` at the API boundary** — money never
  uses binary floats in the domain or database. Evidence: `ProductModel`,
  `OrderModel`, `ProductResponse`, `OrderSummaryResponse`.
- **Module-specific exceptions under `core.exceptions`** — use cases raise
  `NotFoundError` subclasses with a stable `code`; a single handler in
  `presentation/exception_handlers.py` renders `{code, message}`. Evidence:
  `core/exceptions.py`, `presentation/exception_handlers.py`,
  `modules/*/application/exceptions.py`.
- **Paginated list envelope** — every list route uses `PaginationParams` and
  `Page[T]` with `items`, `total`, `page`, `page_size`; repositories return
  `(items, total)`. Evidence: `presentation/pagination.py`, module routers.
- **Orders are one aggregate** — `OrderItem` is loaded and updated through the
  order repository; item writes are never coordinated by a use case. Evidence:
  `modules/orders/infrastructure/repository.py`.
- **Bulk data enters through the CSV importer** — `import-csv` is the only
  supported bulk path, runs outside startup and uses one transaction. Evidence:
  `infrastructure/importing/csv_importer.py`, `cli/import_csv.py`.
- **GET-only operational API; ingestion is the exception** — business modules
  expose list/detail routes; only `/documents` has upload/update/delete routes
  because ingestion is an operator workflow. Evidence: module routers.
- **Integer PK + public UUID for documents** — document/section/chunk tables
  keep the project's `Identity()` PK convention and expose a separate
  `public_id` UUID in the API. Evidence: document models and schemas.
- **Worker has its own image and composition root** — Celery/Docling/Tesseract
  live in the worker image (`worker-runtime`/`worker-dev`), and
  `src/app/worker.py` builds adapters per task with its own async engine.
  Evidence: `Dockerfile`, `compose.yaml`, `src/app/worker.py`.
- **Ingestion checkpoints live in object storage** — parse, summary and
  embedding batches are cached under `cache/{sha256}/...` keyed by checksum and
  version so provider transient failures do not discard completed work.
  Evidence: `application/checkpoints.py`, MinIO storage adapter.

## Not yet conventions

The following are open decisions and must not be treated as established rules:
authentication/authorization, write endpoints, the full error catalog beyond
404/409/400, and lint/format/type-check/CI tooling. Evidence: no auth
dependency is declared in `pyproject.toml`, routers only declare GET routes, and
no lint/CI configuration exists.
