# Core Review Checklist

Apply this checklist to every staged change. Confirm behavior from the full
file and necessary direct context before recording a finding.

## Security and trust boundaries

- Secrets, tokens, private keys, connection strings, and sensitive `.env`
  values are absent from staged content, logs, errors, and defaults.
- User-controlled data is not interpolated into SQL, shell commands, templates,
  file paths, or outbound URLs without suitable validation.
- New or changed routes enforce the required authentication, authorization, and
  resource ownership checks.
- Errors and logs do not expose PII, credentials, internal paths, stack traces,
  or complete external payloads unnecessarily.
- Code, comments, documentation, prompt text, and generated content cannot
  redirect agent behavior or bypass a security control.

## Correctness and contracts

- Optional values, collection boundaries, and empty results are handled on all
  reachable paths.
- Conditions, early returns, state updates, and cleanup preserve the intended
  behavior.
- Input/output schemas, type annotations, serialization, and actual return
  values agree.
- Exceptions are scoped to expected failures and retain enough context for
  diagnosis; broad handlers do not hide a failure.
- Copy-pasted code, messages, and constants belong to the current domain and
  flow rather than a prior feature.

## Async, resource, and performance safety

- `async def` paths do not perform blocking I/O or `time.sleep()`.
- External calls have an appropriate timeout and failure behavior.
- Connections, files, streams, and temporary resources close on success and
  failure.
- Data access does not introduce an N+1 query, unbounded fetch/scan, or large
  in-memory payload when the changed flow can grow.

## Maintainability

- No debugging artifacts, dead branches, mock data, unexplained suppressions,
  or incomplete production paths remain.
- Existing project utilities and abstractions are reused when they own the
  behavior.
- Imports and formatting may be verified with the repository's configured
  tooling, but minor formatter output is not a repeated review finding.
