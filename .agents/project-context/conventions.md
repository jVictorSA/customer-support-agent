# Known Intentional Conventions

Record only patterns confirmed by documentation or established code. Each entry
must state why it is expected and the evidence source.

- **Four-layer module directories** — every business module is split into
  `domain`, `application`, `infrastructure`, and `presentation` so dependency
  direction stays explicit and the module is testable without a database.
  Evidence: `src/customer_support_agent/modules/health/` and
  `.agents/project-context/architecture.md`.
- **`Protocol` ports instead of concrete repository types** — use cases depend
  on structural interfaces, enabling fakes and keeping `application` free of
  SQLAlchemy. Evidence: `modules/health/application/ports.py`,
  `modules/health/application/check_database_health.py`.
- **Repository-owned transactions on every public method** — `session.begin()`
  in reads and writes returns the connection to the pool and centralizes
  commit/rollback; it is not an oversight that reads open a transaction.
  Evidence: `db/session.py`,
  `modules/health/infrastructure/persistence/repository.py`.
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
- **Health module as the reference** — it is intentionally small and
  demonstrates the intended structure for future modules. Evidence:
  `src/customer_support_agent/modules/health/` and the project README.
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
  Evidence: `app.py`, `db/session.py`,
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
  calls in `src/customer_support_agent/app.py`.
- **`db/metadata.py` is the only `db` file importing module models** — it is the
  metadata composition root for Alembic autogenerate. Evidence:
  `src/customer_support_agent/db/metadata.py`.

## Not yet conventions

The following are open decisions and must not be treated as established rules:
default primary-key strategy, timestamp mixin, error catalog/format,
pagination/filters, authentication/authorization, and lint/format/type-check/CI
tooling. Evidence: no such abstraction or dependency exists in `db/base.py`,
`pyproject.toml`, or `src/customer_support_agent/`.
