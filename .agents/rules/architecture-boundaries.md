# Rule: Architecture Boundaries

Applies to every code change under `src/app/`.

Source of truth: `.agents/project-context/architecture.md` and the established
`health` module.

## Mandatory

- Keep the dependency direction: `presentation -> application -> domain`.
  `infrastructure` implements `application` interfaces and may import `domain`.
- `domain` imports only the standard library and other `domain` files. Never
  SQLAlchemy, FastAPI, Pydantic, `application`, `infrastructure`, or
  `presentation`.
- `application` may import `core.exceptions` (shared error base) but never
  SQLAlchemy, FastAPI, `infrastructure`, `presentation`, or `core.config`. Use
  `Protocol` interfaces in `application/interfaces.py`.
- `infrastructure` never imports `presentation` or FastAPI.
- `presentation` imports `infrastructure` only inside
  `presentation/dependencies.py` (the composition root).
- Shared top-level `presentation/` handles cross-cutting HTTP concerns
  (exception handler, pagination); shared `infrastructure/importing/` is the
  bulk CSV adapter. Do not put business rules in either.
- Routers and use cases never receive an `AsyncSession`, run queries, or call
  `commit()`. The repository is the only database/transaction boundary.
- Use cases never import `get_settings`, read environment variables, or know
  HTTP status codes. Raise module-specific `AppError` subclasses instead.
- Business rules live in `domain` or the use case, never in routers or
  repositories.
- Every business module uses integer `Identity` primary keys, the shared
  `TimestampMixin`, and native Postgres enum types. Do not invent a second
  persistence convention.
- A new module follows the workflow encoded in
  `.agents/skills/new-module/SKILL.md`, including registration in `main.py`,
  `db/metadata.py`, tests, and documentation.
- Do not create empty abstractions "for the future"; add an abstraction when
  there is a real caller.

## Verify before finishing

- `rg "from (fastapi|sqlalchemy)" src/app/modules/*/application`
  returns nothing.
- `rg "AsyncSession|session\.commit|HTTPException" src/app/modules/*/presentation/router.py`
  returns nothing.
- New routers are included in `src/app/main.py`.
- New models are imported in `src/app/db/metadata.py`.
