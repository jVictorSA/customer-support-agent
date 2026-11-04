# Rule: Persistence and Migrations

Applies to ORM models, repositories, SQLAlchemy sessions, and Alembic changes.

Source of truth: `.agents/project-context/architecture.md`,
`.agents/project-context/conventions.md`, and
`.agents/skills/db-migration/SKILL.md`.

## Mandatory

- Every public repository method opens its own transaction with
  `async with self._session.begin()`, including reads.
- Never call `session.commit()` outside a repository transaction; never nest a
  transaction inside another repository method.
- One public method equals one transaction. For multi-write atomicity, add a
  dedicated repository method instead of coordinating transactions in a use
  case.
- Repositories map ORM models to domain entities/DTOs; never return ORM models
  to use cases. Load required relationships inside the transaction.
- Repositories contain no business decisions.
- ORM models live in `modules/<module>/infrastructure/persistence/models.py`;
  domain entities never inherit from `Base`.
- Register every new ORM model in
  `src/customer_support_agent/db/metadata.py`.
- Use the existing `Base` naming convention; do not hand-write constraint names
  that the convention would generate.
- Migrations are manual: never run `alembic upgrade head` during API startup.
- Never edit an already applied migration; create a new one. One migration
  represents one logical schema change.
- Always review `--autogenerate` output before applying it.
- Store and process timestamps in UTC with timezone-aware values; convert to
  local time only at presentation.
- Do not invent a primary-key strategy or timestamp mixin. These are open
  decisions (no such abstraction exists in `db/base.py`); ask before the first
  entity if the user has not chosen one.

## Canonical commands

```bash
docker compose exec api alembic current
docker compose exec api alembic revision --autogenerate -m "create products"
docker compose exec api alembic upgrade head
docker compose exec api alembic downgrade -1
```

Run repository/query integration checks with the dedicated test database:

```bash
docker compose up -d db
RUN_INTEGRATION_TESTS=1 POSTGRES_DB=customer_support_agent_test \
  uv run pytest -m integration
```
