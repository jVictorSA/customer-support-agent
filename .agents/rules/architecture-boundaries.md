# Rule: Architecture Boundaries

Applies to every code change under `src/customer_support_agent/`.

Source of truth: `.agents/project-context/architecture.md` and the established
`health` module.

## Mandatory

- Keep the dependency direction: `presentation -> application -> domain`.
  `infrastructure` implements `application` ports and may import `domain`.
- `domain` imports only the standard library and other `domain` files. Never
  SQLAlchemy, FastAPI, Pydantic, `application`, `infrastructure`, or
  `presentation`.
- `application` never imports SQLAlchemy, FastAPI, `infrastructure`, or
  `presentation`. Use `Protocol` ports in `application/ports.py`.
- `infrastructure` never imports `presentation` or FastAPI.
- `presentation` imports `infrastructure` only inside
  `presentation/dependencies.py` (the composition root).
- Routers and use cases never receive an `AsyncSession`, run queries, or call
  `commit()`. The repository is the only database/transaction boundary.
- Use cases never import `get_settings`, read environment variables, or know
  HTTP status codes. Pass explicit dependencies/configuration through the
  constructor.
- Business rules live in `domain` or the use case, never in routers or
  repositories.
- A new module follows the workflow encoded in
  `.agents/skills/new-module/SKILL.md`, including registration in `app.py`,
  `db/metadata.py`, tests, and documentation.
- Do not create empty abstractions "for the future"; add an abstraction when
  there is a real caller.

## Verify before finishing

- `rg "from (fastapi|sqlalchemy)" src/customer_support_agent/modules/*/application`
  returns nothing.
- `rg "AsyncSession|session\.commit|HTTPException" src/customer_support_agent/modules/*/presentation/router.py`
  returns nothing.
- New routers are included in `src/customer_support_agent/app.py`.
