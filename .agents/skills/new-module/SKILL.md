---
name: new-module
description: >-
  Scaffolds a new business module following this repository's four-layer Clean
  Architecture (domain, application, infrastructure, presentation), including
  ports, use cases, SQLAlchemy models/repository, Pydantic schemas, router,
  dependency wiring, registration, tests, and Alembic migration. Use when the
  user asks to create a new module, feature module, entity, use case, endpoint,
  or to implement one of the business domains (products, orders, customers,
  promotions, categories).
---

# New Business Module

Create one module under `src/customer_support_agent/modules/<module>/` that
follows the established `health` pattern. Do not add business logic to routers,
repositories, or `app.py`.

Canonical contract: `.agents/project-context/architecture.md`,
`.agents/project-context/domain.md`, and the established `health` module.

## Guardrails

- Read `.agents/project-context/architecture.md`,
  `.agents/project-context/conventions.md`, and
  `.agents/project-context/domain.md` before writing code.
- Ask before choosing the primary-key strategy or timestamp mixin if the
  repository still has no decision. Do not silently invent one.
- Keep `domain` framework-free, `application` free of SQLAlchemy/FastAPI, and
  `presentation` free of `infrastructure` outside `dependencies.py`.
- Do not add a model without registering it in `db/metadata.py`.
- Do not add an endpoint without registering its router in `app.py`.
- Do not run migrations against a non-test database. Do not edit applied
  migrations.
- Do not introduce lint/type-check/CI config in this workflow.

## Workflow

Track progress:

```
New Module Progress:
- [ ] 1. Confirm scope, entities, and open decisions
- [ ] 2. Create the four-layer package
- [ ] 3. Model domain entities/value objects
- [ ] 4. Declare application ports
- [ ] 5. Implement the use case
- [ ] 6. Implement ORM model and repository
- [ ] 7. Register metadata and schemas
- [ ] 8. Implement router and dependencies
- [ ] 9. Register the router in app.py
- [ ] 10. Add unit and integration tests
- [ ] 11. Create and review the migration
- [ ] 12. Update documentation and validate
```

### 1. Confirm scope

Identify the module name (singular, snake_case), the entities/value objects, the
use cases, and which domain tables from `.agents/project-context/domain.md`
apply.
Record open decisions for the user instead of guessing.

### 2. Create the package

```text
src/customer_support_agent/modules/<module>/
├── __init__.py
├── domain/__init__.py
├── application/__init__.py
├── application/ports.py
├── application/<action>.py
├── infrastructure/__init__.py
├── infrastructure/persistence/__init__.py
├── infrastructure/persistence/models.py
├── infrastructure/persistence/repository.py
├── presentation/__init__.py
├── presentation/router.py
├── presentation/dependencies.py
└── presentation/schemas.py
```

Only create `domain` files when a real rule/value object exists; an empty
`domain/__init__.py` is acceptable, as in `modules/health/`.

### 3. Domain

- Pure Python only: stdlib and other `domain` files.
- No SQLAlchemy, FastAPI, Pydantic, settings, sessions, or I/O.
- Use dataclasses/enums/value objects; raise domain exceptions only when a rule
  needs to signal failure.

### 4. Ports

Declare repository/service contracts with `typing.Protocol` in
`application/ports.py`, mirroring `modules/health/application/ports.py`:

```python
from typing import Protocol

from customer_support_agent.modules.<module>.domain.<entity> import <Entity>


class <Entity>Repository(Protocol):
    async def get_by_id(self, entity_id: int) -> <Entity> | None: ...
```

### 5. Use case

```python
from dataclasses import dataclass

from customer_support_agent.modules.<module>.application.ports import (
    <Entity>Repository,
)


@dataclass(frozen=True, slots=True)
class <ActionResult>:
    ...


class <Action>UseCase:
    def __init__(self, repository: <Entity>Repository) -> None:
        self._repository = repository

    async def execute(self, ...) -> <ActionResult>:
        ...
```

Receive configuration explicitly through the constructor; never call
`get_settings()` or import FastAPI/SQLAlchemy here.

### 6. ORM model and repository

- Model in `infrastructure/persistence/models.py`, inheriting `Base` from
  `customer_support_agent.db.base`.
- Add `to_domain()`/`from_domain()` mapping as needed; never return ORM models
  upward.
- Every public repository method opens one transaction:

```python
class SqlAlchemy<Entity>Repository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, entity_id: int) -> <Entity> | None:
        async with self._session.begin():
            model = await self._session.get(<Entity>Model, entity_id)
            return model.to_domain() if model is not None else None
```

- Load relationships inside the transaction (`selectinload`/`joinedload`).
- No business decisions in the repository.

### 7. Metadata and schemas

- Import the new model in `src/customer_support_agent/db/metadata.py`.
- Add request/response models in `presentation/schemas.py`, separate from both
  ORM models and domain entities. Include `from_domain` mapping where useful.

### 8. Router and dependencies

- Thin router: validate input, call the use case, map the result/exception to a
  status code. Declare `response_model` and correct status codes.
- Wire concrete implementations only in `presentation/dependencies.py`, using
  `Depends(get_session)` and provider functions that tests can override.
- Never expose internal error detail outside `APP_ENV=development`.

### 9. Register the router

Edit `src/customer_support_agent/app.py` and include the module router next to
`health_router`.

### 10. Tests

- Unit test the use case with a fake implementing the `Protocol`.
- API test with `TestClient` and `app.dependency_overrides` (see
  `tests/health/test_health_db.py`).
- Repository/query behavior that fakes cannot guarantee: add an opt-in
  integration test under `tests/integration/` using the test database.
- Run `uv run pytest`; run the integration command when the repository/query
  changed.

### 11. Migration

Use the `db-migration` skill. Never run `alembic upgrade head` at API startup.

### 12. Documentation and validation

- Update `README.md` if a new endpoint/variable/decision is user-visible.
- Update `README.md` and the affected `.agents/project-context/` document when
  a module boundary, decision, or convention changes.
- Confirm: `uv run pytest` passes, the integration test passes if applicable,
  the router is registered, the model is in `db/metadata.py`, and the migration
  was reviewed.
