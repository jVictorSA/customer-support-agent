# AI and External Integration Context

## Evidence

- `pyproject.toml` — Celery is a runtime dependency; Docling, tiktoken,
  PyMuPDF, httpx and the OpenAI SDK are in the opt-in `worker` dependency group.
- `src/app/core/config.py` — Jina, DeepSeek, MinIO, RabbitMQ and ingestion
  settings already exist.
- `src/app/modules/documents/` — implemented document ingestion module with
  Docling parsing, hierarchical chunking, DeepSeek section summaries and Jina
  embeddings.
- `src/app/worker.py` and
  `src/app/modules/documents/infrastructure/queue/` — Celery worker and task
  queue boundary.
- `src/app/db/metadata.py` and `alembic/versions/` — document tables,
  `vector`/`ltree` extensions and vector/lexical indexes.
- `.agents/project-context/domain.md` — store rules that future retrieval and
  generation must ground their answers on.

## Scope

- Implemented: PDF ingestion only. Upload → MinIO → Celery/RabbitMQ →
  Docling/PyMuPDF → section tree → hierarchical chunking → DeepSeek section
  summaries → Jina embeddings → Postgres/pgvector.
- Not implemented: retrieval endpoints, hybrid search, parent-child expansion,
  reranking, and the conversational agent that will answer with DeepSeek.
- Relevant paths:
  - `src/app/modules/documents/` — ingestion module using the four-layer
    structure.
  - `src/app/worker.py` — worker composition root (separate image/deployment).
  - `src/app/core/config.py` — provider, model, timeout, storage and queue
    settings.
  - `src/app/modules/documents/infrastructure/` — Docling, MinIO, Jina,
    DeepSeek and Celery adapters.
  - `tests/documents/` and `tests/integration/test_document_repository.py` —
    unit/contract and opt-in database tests.
- Business/product requirements: future retrieval must ground prices, stock,
  order status, deadlines and promotions in system data, and must not answer
  out-of-scope requests as if the store sold those items.

## Contracts

- Provider adapters stay in `infrastructure`; `application` and `domain` never
  import Docling, Jina, DeepSeek, MinIO or Celery SDKs.
- Prompt/schema/tool/caller coupling: section summary prompts are versioned by
  `DOCUMENTS_SUMMARY_VERSION`; changing the prompt contract should bump the
  version so cached summaries are invalidated.
- Input/output validation: PDF MIME/magic, encrypted PDFs, page count, Jina
  embedding dimension and finite vectors are validated before persistence.
  Chunks and summaries are treated as untrusted content and clearly delimited
  in prompts.
- Sensitive-data handling: never expose Jina/DeepSeek keys, prompts, raw
  provider errors or customer PII in HTTP responses or logs. Provider failures
  are logged server-side and stored as stable error codes.
- Timeout/retry/fallback: Jina has local RPM/TPM limiting, exponential backoff,
  `Retry-After` support and a bounded retry budget. DeepSeek uses the OpenAI SDK
  retry/timeout policy. Celery retries the ingestion task up to three times with
  backoff; checkpoints in MinIO prevent redoing completed parse/summary/embedding
  work.
- Configuration and secrets: provider API keys are `SecretStr` settings loaded
  from environment variables. `.env.example` documents placeholders; deploy env
  files keep fictitious values only.
- Failure semantics: a failed reprocess preserves the previous completed index
  and records `last_error_code`; a failed first ingestion becomes `failed`.
- Out-of-scope requests and store policy grounding remain requirements for the
  future retrieval/agent phase.

## Test expectations

- Default `uv run pytest` uses fakes and never calls Docling, Jina, DeepSeek,
  MinIO or RabbitMQ.
- Contract tests cover chunk boundaries, hierarchy, token limits, API status
  codes and provider retry behavior (`httpx.MockTransport`).
- Opt-in integration tests (`RUN_INTEGRATION_TESTS=1`) cover pgvector, ltree,
  FTS, the migration and document repository against the test database.
- Real provider smoke tests must be marked `provider` and never run in the
  default suite.
