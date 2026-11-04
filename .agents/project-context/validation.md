# Validation

## Evidence

- `pyproject.toml` — pytest configuration, `asyncio_mode = "auto"`, integration
  marker and dev dependencies.
- `tests/` — unit/contract tests and opt-in integration test.
- `README.md` — documented commands.
- `.env.example`, `compose.yaml`, `docker/postgres/init/01-create-test-db.sh` —
  database test setup.
- `.agents/project-context/architecture.md` — persistence and migration gates
  referenced by the targeted checks.

## Standard checks

```bash
uv run pytest
```

Verified on 2026-11-04: `10 passed, 1 skipped` (the skipped test is the opt-in
integration test). This is the only automated quality gate currently
configured.

## Targeted checks

- Application/domain/use-case change: `uv run pytest` and add or update a
  focused unit test using a fake `Protocol` implementation. Evidence:
  `tests/health/test_check_database_health.py`.
- HTTP/presentation change: `uv run pytest` and exercise the route through
  `fastapi.testclient.TestClient` with `app.dependency_overrides` for use-case
  dependencies. Evidence: `tests/conftest.py`, `tests/health/test_health_db.py`.
- Persistence/repository or database change: run the opt-in integration test
  against the dedicated test database:

  ```bash
  docker compose up -d db
  RUN_INTEGRATION_TESTS=1 \
  POSTGRES_DB=customer_support_agent_test \
  uv run pytest -m integration
  ```

  Never point integration tests at the development database. The test database
  is created by `docker/postgres/init/01-create-test-db.sh` on first volume
  initialization.
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
- There is no initial Alembic migration and `alembic/versions/` contains only
  `.gitkeep`; schema changes require creating the migration first.
- Integration tests are opt-in (`RUN_INTEGRATION_TESTS=1`) and require a
  running Postgres; local `uv run pytest` does not exercise the database.
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
