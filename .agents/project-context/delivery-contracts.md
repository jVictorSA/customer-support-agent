# Delivery Contracts

## Evidence

- `README.md` — documented endpoints, status codes, error exposure and
  environment variables.
- `src/customer_support_agent/app.py` — registered routes and lifespan.
- `src/customer_support_agent/modules/health/presentation/router.py`,
  `schemas.py` — response contract and error exposure.
- `src/customer_support_agent/core/config.py` — configuration fields and
  development-mode flag.
- `.env.example`, `deploy/.env.hml`, `deploy/.env.prod`, `compose.yaml`,
  `compose.override.yaml`, `compose.prod.yaml`, `Dockerfile`, `.dockerignore` —
  configuration and deployment behavior.
- `.agents/project-context/architecture.md` — layering and persistence gates
  that back these delivery contracts.

## Public interfaces and authorization

- Interface registration and path conventions: module routers live in
  `modules/<module>/presentation/router.py` with an `APIRouter` prefix and tags,
  and are included in `app.py`. Current routes: `GET /` (API name/version/status),
  `GET /health` (liveness), `GET /health/db` (database readiness).
- Authentication, authorization, and ownership gates: none implemented.
  Do not assume an auth layer exists; introducing authentication is an open
  decision (no auth dependency is declared in `pyproject.toml` and no auth
  provider exists in the codebase).
- Response contract:
  - Every route declares an explicit `response_model`; never return ORM models.
  - Status codes must reflect the real result. `/health/db` returns `200` when
    the database is reachable and `503` with `status="degraded"` and
    `database="down"` when it is not.
  - Internal error detail (`detail`) is exposed only when
    `APP_ENV=development`; `hml`/`prod` responses omit it and the full error is
    logged server-side.
  - Business failures are signaled by the use case and translated to HTTP in
    presentation; use cases must not import `HTTPException`.
  - No stack trace, SQL, credentials, or internal paths in HTTP responses.
- Language: API payloads and messages are in English; user-facing store content
  may follow the store policy material.

## Configuration and deployment

- Configuration source: `Settings` in `core/config.py`, loaded from environment
  variables with optional local `.env`. `APP_ENV` selects `development`, `hml`,
  or `prod`. `.env.example` must document every development variable; keep it
  in sync with `Settings`.
- Database configuration: `POSTGRES_*` variables build the async URL;
  `DATABASE_URL` is an optional full override for managed Postgres. `POSTGRES_HOST`
  is `localhost` in the local `.env` and Compose overrides it to `db` inside
  containers.
- Secret handling: `.env` is not versioned; `deploy/.env.hml` and
  `deploy/.env.prod` contain fictitious values only. Real credentials must come
  from a secret manager/CI environment, never Git or the image.
- Deployment/runtime constraints:
  - `compose.yaml` is the base; `compose.override.yaml` is development (bind
    mount, hot reload, published DB port); `compose.prod.yaml` is hml/prod
    (immutable image, restart policy, no published DB port).
  - The API waits for a healthy database before starting, but the startup probe
    tolerates failure and starts in degraded mode; `/health/db` then returns 503.
  - Alembic migrations are manual and never run at startup.
  - The production image runs as a non-root user; `deploy/` and `.env*` are
    excluded from the Docker context.

## Compatibility review

Before completing API, persistence, configuration, or deployment changes, map:

- OpenAPI contract: new/changed route paths, request/response schemas, status
  codes, and error payload shape.
- Database contract: ORM model changes, `db/metadata.py` registration,
  migration `upgrade`/`downgrade`, and whether existing data needs backfill.
- Configuration contract: new/renamed environment variables in `Settings`,
  `.env.example`, `deploy/.env.hml`, `deploy/.env.prod`, and Compose files.
- Runtime contract: `/health`, `/health/db`, startup behavior, Docker image
  user and non-root assumptions, and ports.
- Documentation contract: update `README.md` and the affected
  `.agents/project-context/` document when a variable, endpoint, module
  boundary, or architectural decision changes.
