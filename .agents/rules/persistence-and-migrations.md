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
- ORM models live in `modules/<module>/infrastructure/models.py`;
  domain entities never inherit from `Base`.
- Register every new ORM model in
  `src/app/db/metadata.py`.
- Use the existing `Base` naming convention; do not hand-write constraint names
  that the convention would generate.
- Migrations are manual: never run `alembic upgrade head` during API startup.
- Never edit an already applied migration; create a new one. One migration
  represents one logical schema change.
- Always review `--autogenerate` output before applying it.
- Store and process timestamps in UTC with timezone-aware values; convert to
  local time only at presentation.
- Use integer `Identity()` primary keys named after the entity, the shared
  `TimestampMixin`, `Numeric(12,2)` + `Decimal` for money, and native Postgres
  enums backed by `StrEnum`. Do not invent a second convention.
- `order_items` is part of the `orders` aggregate: use the composite key
  `(order_id, product_id)` and update items through the order repository.
- Bulk CSV loading is the one cross-model exception: `CsvImporter` owns a single
  transaction and upserts by primary key. Do not use it at API startup.

## Canonical commands

```bash
docker compose exec api alembic current
docker compose exec api alembic revision --autogenerate -m "create products"
docker compose exec api alembic upgrade head
docker compose exec api alembic downgrade -1
```

Bulk import (after `upgrade head`, never at startup):

```bash
uv run import-csv data/ --truncate
# or
docker compose exec api import-csv data/ --truncate
```

Run repository/query integration checks with the dedicated test database:

```bash
docker compose up -d db
RUN_INTEGRATION_TESTS=1 POSTGRES_DB=customer_support_agent_test \
  uv run pytest -m integration
```
