# Delivery Contracts

## Evidence

- `README.md` — documented endpoints, status codes, error exposure and
  environment variables.
- `src/app/main.py` — registered routes and lifespan.
- `src/app/modules/*/presentation/router.py`, `schemas.py` —
  business response contracts.
- `src/app/presentation/exception_handlers.py` and
  `pagination.py` — shared error and pagination contracts.
- `src/app/infrastructure/importing/csv_importer.py` and
  `cli/import_csv.py` — bulk data contract.
- `src/app/modules/health/presentation/router.py`,
  `schemas.py` — health response contract and error exposure.
- `src/app/core/config.py` — configuration fields and
  development-mode flag.
- `.env.example`, `deploy/.env.hml`, `deploy/.env.prod`, `compose.yaml`,
  `compose.override.yaml`, `compose.prod.yaml`, `Dockerfile`, `.dockerignore` —
  configuration and deployment behavior.
- `.agents/project-context/architecture.md` — layering and persistence gates
  that back these delivery contracts.

## Public interfaces and authorization

- Interface registration and path conventions: module routers live in
  `modules/<module>/presentation/router.py` with an `APIRouter` prefix and tags,
  and are included in `main.py`. Current routes: `GET /` (API name/version/status),
  `GET /health` (liveness), `GET /health/db` (database readiness), plus
  `GET /categories`, `/products`, `/customers`, `/orders`, `/promotions` with
  `/{id}` detail routes, plus the `/documents` ingestion surface:
  `POST /documents`, `GET /documents`, `GET /documents/{public_id}`,
  `GET /documents/{public_id}/sections`,
  `GET /documents/{public_id}/chunks`, `PATCH /documents/{public_id}`,
  `DELETE /documents/{public_id}`, `POST /documents/{public_id}/restore` and
  `POST /documents/{public_id}/reprocess`. Business routes other than document
  ingestion remain GET-only.
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
    presentation; use cases must not import `HTTPException`. The shared handler
    returns `{code, message}` using `AppError.status_code`: 404 for
    `NotFoundError`, 409 for `ConflictError`, 413/415/422/503 for document
    ingestion errors and 400 for other `AppError` subclasses.
  - Every list route uses `page`/`page_size` (default 20, max 100) and returns
    `{items, total, page, page_size}`. Detail routes return the entity schema;
    `GET /orders/{order_id}` additionally includes `items`.
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
- Document ingestion configuration: `DOCUMENTS_*` for limits/chunking/OCR,
  `MINIO_*`, `RABBITMQ_*`/`CELERY_*`, `JINA_*` and `DEEPSEEK_*`. Jina/DeepSeek
  keys are `SecretStr` and must be present only in the runtime environment.
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
  - Bulk data is loaded with `import-csv <directory>` (or
    `docker compose exec api import-csv <directory>`), never at startup. `data/`
    is ignored by Git; the importer upserts by primary key and resets sequences.
  - Compose adds `rabbitmq`, `minio`, `minio-init` and `worker`. The worker
    uses the separate `worker-runtime`/`worker-dev` image targets, runs
    `--concurrency=1`, and scales independently from the API.
  - `db` uses `pgvector/pgvector:pg17`; the migration enables `vector` and
    `ltree`.
  - The production image runs as a non-root user; `deploy/` and `.env*` are
    excluded from the Docker context.
  - Document write routes have no authentication yet; restrict network exposure
    until the auth layer is implemented.

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
