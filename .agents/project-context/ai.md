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

- Implemented: PDF ingestion and the conversational agent. Ingestion runs
  upload → MinIO → Celery/RabbitMQ → Docling/PyMuPDF → section tree →
  hierarchical chunking → DeepSeek summaries → Jina embeddings →
  Postgres/pgvector. Chat runs API enqueue → `agent-worker` → intent agent →
  ReAct orchestrator → hybrid retrieval / deterministic data tools / complaint
  tool → response writer → grounding validation → persisted messages, traces
  and optional signed webhook.
- Implemented: Text-to-SQL as an opt-in ReAct tool for catalog/stock/promotions
  and the authenticated customer's own orders. It uses a static semantic
  catalog, deterministic metric templates, SQLGlot validation, a dedicated
  read-only role and Postgres RLS.
- Not implemented: reranking, semantic memory over past messages, historical
  summarization and operator resolution of complaints.
- Relevant paths:
  - `src/app/modules/agent/` — ReAct loop, tools, prompts, traces and webhook
    delivery.
  - `src/app/modules/text_to_sql/` — semantic catalog, metric templates,
    generation/validation/execution pipeline and SQL status contracts.
  - `src/app/modules/documents/` — ingestion and hybrid retrieval SQL.
  - `src/app/agent_worker.py` — chat worker composition root.
  - `src/app/modules/{auth,conversations,messages,complaints}/` — JWT,
    persistence and ownership boundaries.
  - `src/app/core/config.py` — provider, model, timeout, retrieval, auth and
    webhook settings.
  - `tests/agent/` and `tests/integration/test_conversation_flow.py` —
    orchestration fakes and opt-in database tests.
- Business/product requirements: prices, stock, order status, deadlines,
  promotion validity, opening hours, payment options, shipping estimates and
  return eligibility come from deterministic tools, never from the model.
  Out-of-scope accessory requests are redirected.

## Contracts

- Provider adapters stay in `infrastructure`; `application` and `domain` never
  import Docling, Jina, DeepSeek, MinIO, Celery or PyJWT SDKs.
- Chat tool schemas and prompts are a contract: `search_store_knowledge`,
  `search_catalog`, `get_product_details`, `list_my_orders`,
  `get_order_status`, `get_store_status`, `check_return_eligibility`,
  `calculate_payment_options`, `estimate_shipping`, `register_complaint` and
  the opt-in `text_to_sql`.
  Changing a tool name/field requires updating prompts, tests and traces.
- `text_to_sql` only receives a `question`; the customer scope is server-derived.
  It returns `answered`, `clarification_required`, `unsupported` or
  `unavailable` as structured data. SQL is never sent to the writer or customer;
  it is persisted in `agent_steps` together with the result rows.
- Tools never accept `customer_id`; the server-derived `CustomerScope` filters
  orders and complaints. Other customers' records are unreachable by contract.
- Structured outputs are JSON objects validated in `application`; a repair call
  is attempted before failing a step. The writer output is validated by a
  deterministic grounding check (citations, required data tool, currency
  values) with one repair attempt and a safe fallback.
- The orchestrator prompt is explicitly ReAct: each iteration must expose a
  `Thought`, then at most one native tool call (Action), then consume the tool
  result (Observation) before the next Thought. It finishes with
  `Thought + Final Answer`, a handoff note for the writer.
- Out-of-scope is broader than accessories: the intent agent returns
  `out_of_scope_type` in `accessory`, `benign_off_topic`, `harmful_or_illegal`
  or `other`. Harmful/illegal requests are refused deterministically before the
  orchestrator or writer runs; benign off-topic requests are redirected by the
  writer. Prompt injection and retrieved content remain untrusted data.
- Every LLM call, tool call and validation is persisted in `agent_runs` /
  `agent_steps` (prompts, outputs, tool args/results, token usage, latency and
  error code). Trace writes are best-effort and never block delivery.
- Webhook payloads are versioned and signed with HMAC-SHA256 over
  `timestamp.body`; delivery status and attempts live on the assistant message.
- Chat turns are idempotent: one in-flight user message per conversation and
  `client_message_id` uniqueness. Celery redelivery cannot process a claimed
  message twice; stale processing is reclaimable.
- Ingestion still validates PDF MIME/magic, encrypted PDFs, page count, Jina
  embedding dimension/finite vectors, uses MinIO checkpoints and retries
  provider calls with bounded backoff.
- Provider failures are logged server-side and stored as stable error codes;
  HTTP responses never include prompts, SQL, credentials or raw provider errors.

## Test expectations

- Default `uv run pytest` uses fakes and never calls Docling, Jina, DeepSeek,
  MinIO or RabbitMQ.
- Contract tests cover chunk boundaries, hierarchy, token limits, API status
  codes and provider retry behavior (`httpx.MockTransport`).
- Opt-in integration tests (`RUN_INTEGRATION_TESTS=1`) cover pgvector, ltree,
  FTS, the migration and document repository against the test database.
- Text-to-SQL unit tests use a scripted fake SQL chat model and executor; they
  cover policy rejection, one technical repair, metric templates and status
  mapping. Integration tests cover RLS, read-only writes and catalog drift.
- Real provider smoke tests must be marked `provider` and never run in the
  default suite; the Text-to-SQL evaluation dataset is also `provider` and uses
  the test database.
