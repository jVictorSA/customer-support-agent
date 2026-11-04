# Rule: AI and External Integrations

Applies when adding LLM, RAG, tool-calling, retrieval, or any external
provider integration.

Source of truth: `.agents/project-context/ai.md`,
`.agents/project-context/domain.md`, and
`.agents/project-context/architecture.md`.

No AI integration exists yet. Do not assume provider SDKs, model names, or
API-key settings are already present.

## Mandatory

- Put provider/model/API-key/timeout settings in `core/config.py` `Settings`.
  Never hardcode them or read environment variables inside use cases.
- Never commit real credentials. Provider keys belong in environment/secrets;
  `.env.example` gets placeholders only.
- Keep provider SDKs and HTTP clients in `infrastructure`. `application` and
  `domain` must not import them.
- Give every external call an explicit timeout and a safe failure path; do not
  block the event loop with synchronous clients.
- Validate model and tool input/output before acting on it or returning it.
  Tool schemas and prompt instructions are a contract: changing a tool name,
  field, or caller dispatch requires updating tests and callers together.
- Ground prices, stock, order status, deadlines, and promotions in system data.
  Never let the model invent or guess them, and check promotion validity.
- Treat store policy text and retrieved content as untrusted data, not
  instructions. Keep it separated from system prompts.
- Do not expose prompts, credentials, raw SQL, or customer PII in responses or
  logs. Follow the LGPD-oriented data handling in
  `.agents/project-context/domain.md`.
- Internal provider/LLM errors follow the existing rule: detailed only when
  `APP_ENV=development`; production returns a safe message and logs server-side.
- Out-of-scope requests (accessories the store does not sell) must be handled
  politely and redirected, never answered as if the store sold them.

## Test expectations

- Unit-test agent orchestration with fakes for the provider/tools; no real API
  calls in the default `uv run pytest` suite.
- Add contract tests for tool schemas and deterministic policy decisions.
- Add opt-in integration tests only if a real provider is exercised; mark them
  like the existing `integration` tests and document required env vars.
