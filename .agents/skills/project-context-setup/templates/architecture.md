# Architecture

## Evidence

- `<path and concise reason>`

## Module boundaries

- `<layer/area>` may import: `<facts>`.
- `<layer/area>` must not import: `<facts>`.
- Business behavior belongs in: `<facts>`.

## Persistence and state

- Transaction ownership: `<facts>`.
- Cache/queue/source-of-truth behavior: `<facts>`.
- New model or schema registration: `<facts>`.

## Extension points

- Public-interface registration: `<facts>`.
- Dependency declaration: `<facts>`.
- Observability convention: `<facts>`.
