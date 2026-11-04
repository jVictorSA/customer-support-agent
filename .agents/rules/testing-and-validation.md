# Rule: Testing and Validation

Source of truth: `.agents/project-context/validation.md`.

## Standard gate

```bash
uv run pytest
```

Run it after every code change. The verified baseline is `36 passed, 3 skipped`;
the skipped tests are the opt-in Postgres integration tests.

## Mandatory

- Test behavior and contracts, not private implementation details.
- Unit tests must not access the database. Use fakes implementing the
  `Protocol` interfaces and override FastAPI dependencies with
  `app.dependency_overrides`.
- Repository/query behavior that cannot be guaranteed by a fake needs an
  opt-in integration test using `customer_support_agent_test`, never the
  development database:

  ```bash
  docker compose up -d db
  RUN_INTEGRATION_TESTS=1 POSTGRES_DB=customer_support_agent_test \
    uv run pytest -m integration
  ```

  The integration fixture applies `alembic upgrade head` to the dedicated test
  database automatically when `RUN_INTEGRATION_TESTS=1`.

- Add or update tests with the change; do not leave a new public behavior
  untested.
- For API changes, exercise the route through `TestClient` and assert status
  code plus payload shape.
- For configuration changes, update `tests/test_config.py` and keep
  `.env.example`, `deploy/.env.hml`, and `deploy/.env.prod` consistent.
- For migrations, review generated SQL and verify `upgrade`/`downgrade` inside
  the API container.
- For CSV import changes, run the parser unit tests and the importer integration
  test; verify `uv run import-csv <dir> --truncate` after `alembic upgrade head`.
- Do not claim lint, formatting, type-check, or CI checks passed: none are
  configured. Do not add them as if they already exist; propose them separately.

## Pre-commit

- Stage only intentional changes.
- Run `uv run pytest`; run the integration command when repositories, queries,
  models, or migrations changed.
- Update `README.md` and the affected `.agents/project-context/` document when
  the change adds a variable, endpoint, module boundary, or architectural
  decision.
