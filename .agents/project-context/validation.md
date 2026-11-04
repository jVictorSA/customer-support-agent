# Validation

## Evidence

- `pyproject.toml` — pytest configuration, `asyncio_mode = "auto"`, integration
  marker and dev dependencies.
- `tests/` — unit/contract tests per module, parser tests and opt-in
  integration tests for repositories and the CSV importer.
- `README.md` — documented commands.
- `.env.example`, `compose.yaml`, `docker/postgres/init/01-create-test-db.sh` —
  database test setup.
- `.agents/project-context/architecture.md` — persistence and migration gates
  referenced by the targeted checks.

## Standard checks

```bash
uv run pytest
```

Verified on 2026-11-04: `36 passed, 3 skipped` (the skipped tests are the
opt-in Postgres integration tests). This is the only automated quality gate
currently configured.

## Targeted checks

- Application/domain/use-case change: `uv run pytest` and add or update a
  focused unit test using a fake `Protocol` implementation. Evidence:
  `tests/categories/test_categories.py`, `tests/products/test_products.py`.
- HTTP/presentation change: `uv run pytest` and exercise the route through
  `fastapi.testclient.TestClient` with `app.dependency_overrides` for use-case
  dependencies. Evidence: `tests/conftest.py`, `tests/<module>/`.
- Persistence/repository or database change: run the opt-in integration tests
  against the dedicated test database:

  ```bash
  docker compose up -d db
  RUN_INTEGRATION_TESTS=1 \
  POSTGRES_DB=customer_support_agent_test \
  uv run pytest -m integration
  ```

  Never point integration tests at the development database. The test database
  is created by `docker/postgres/init/01-create-test-db.sh` on first volume
  initialization, and the integration fixture applies `alembic upgrade head` to
  it automatically when `RUN_INTEGRATION_TESTS=1`.
- CSV import change: run the parser unit tests and, when the database is
  available, the opt-in importer integration test. The command itself is:

  ```bash
  uv run import-csv <directory> --truncate
  # or inside the API container:
  docker compose exec api import-csv <directory> --truncate
  ```

  The importer must run after `alembic upgrade head` and must not run at API
  startup.
- Migration change: review the generated SQL, then apply/verify inside the API
  container:

  ```bash
  docker compose exec api alembic current
  docker compose exec api alembic upgrade head
  docker compose exec api alembic downgrade -1
  ```

  `alembic revision --autogenerate` is a generation step, not validation; the
  generated migration must be reviewed before applying.
- Configuration change: add/update a unit test in `tests/test_config.py` when
  URL building or defaults change, and verify `.env.example` plus both deploy
  env files remain consistent.
- Container/deployment change: `docker compose config` for syntax, then build
  and exercise `/health` and `/health/db`; do not run migrations automatically
  on startup.

## Limitations

- No linter, formatter, type checker, or CI is configured: `pyproject.toml`
  declares no such dependency or config, and no CI/format config files exist.
  Do not claim these checks ran.
- The initial Alembic migration now exists; schema changes must still be
  reviewed and applied manually, never at API startup.
- Integration tests are opt-in (`RUN_INTEGRATION_TESTS=1`) and require a
  running Postgres with the migration applied; local `uv run pytest` does not
  exercise the database.
- Unit tests use FastAPI `TestClient` and dependency overrides; no external
  service or LLM provider test harness exists.
- Python 3.12 is required; `uv` manages the environment and lockfile.

## Pre-commit handoff

- Stage only intentional changes. Run `uv run pytest` before committing; run
  the integration command when the change touches repositories, queries,
  models, or migrations.
- `pre-commit-review` reviews the staged index only, writes a report to
  `docs/reviews/`, and must not modify code or git state.
- When a change adds a variable, endpoint, module boundary, or architectural
  decision, update `README.md` and the affected `.agents/project-context/`
  document in the same delivery.
