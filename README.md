# Customer Support Agent

API de agente de atendimento ao cliente para uma loja de instrumentos musicais.

O projeto está em desenvolvimento. A API conecta em um Postgres 17 com
`pgvector`/`ltree` via SQLAlchemy async, as migrations são gerenciadas pelo
Alembic, o endpoint `/health/db` verifica a conexão, o módulo de documentos
implementa a ingestão de PDFs com armazenamento, processamento assíncrono e
embeddings, e o fluxo de atendimento conversacional já implementa login JWT,
conversas, mensagens, reclamações, processamento assíncrono via Celery e o
agente ReAct com tools de RAG, catálogo, pedidos e reclamações.

## Sumário

- [Stack](#stack)
- [Requisitos](#requisitos)
- [Configuração do ambiente](#configuração-do-ambiente)
- [Como executar](#como-executar)
- [Text-to-SQL](#text-to-sql)
- [Migrations](#migrations)
- [Importação de dados](#importação-de-dados)
- [Ingestão de documentos](#ingestão-de-documentos)
- [Atendimento conversacional](#atendimento-conversacional)
- [Perguntas de exemplo](#perguntas-de-exemplo)
- [Testes](#testes)
- [Endpoints](#endpoints)
- [Ambientes de hml/prod](#ambientes-de-hmlprod)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Codificação com agentes de IA](#codificação-com-agentes-de-ia)
- [Decisões de arquitetura](#decisões-de-arquitetura)
- [O que eu faria com mais tempo](#o-que-eu-faria-com-mais-tempo)
- [Limitações conhecidas](#limitações-conhecidas)

## Stack

- [Python 3.12+](https://www.python.org/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [Postgres 17 + pgvector + ltree](https://www.postgresql.org/)
- [SQLAlchemy 2.x async + asyncpg](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Alembic](https://alembic.sqlalchemy.org/)
- [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [MinIO](https://min.io/) para armazenamento dos PDFs e checkpoints
- [RabbitMQ](https://www.rabbitmq.com/) + [Celery](https://docs.celeryq.dev/) para processamento assíncrono
- [Docling](https://docling-project.github.io/docling/) para extração estrutural de PDF
- [Jina AI](https://jina.ai/embeddings/) para embeddings e [DeepSeek](https://api-docs.deepseek.com/) para resumos de seção e agentes
- [PyJWT](https://pyjwt.readthedocs.io/) para autenticação
- [uv](https://docs.astral.sh/uv/) para gerenciamento do ambiente e dependências
- [Docker Compose](https://docs.docker.com/compose/) para Postgres, MinIO, RabbitMQ, API e worker
- [pytest](https://docs.pytest.org/) + [pytest-asyncio](https://pytest-asyncio.readthedocs.io/) para testes

## Requisitos

- Docker e Docker Compose
- Python 3.12 ou superior e uv (para rodar comandos fora do container)

## Configuração do ambiente

Crie o arquivo de variáveis de desenvolvimento:

```bash
cp .env.example .env
```

As principais variáveis são:

| Variável | Descrição | Padrão dev |
| --- | --- | --- |
| `APP_ENV` | Ambiente da aplicação (`development`, `hml`, `prod`) | `development` |
| `POSTGRES_USER` | Usuário do Postgres | `app` |
| `POSTGRES_PASSWORD` | Senha do Postgres | `app` |
| `POSTGRES_DB` | Banco principal | `customer_support_agent` |
| `POSTGRES_HOST` | Host do banco | `localhost` |
| `POSTGRES_PORT` | Porta interna do banco | `5432` |
| `POSTGRES_HOST_PORT` | Porta publicada no host (dev) | `5432` |
| `POSTGRES_VOLUME_NAME` | Nome do volume persistente | `customer_support_agent_postgres_data` |
| `API_PORT` | Porta publicada da API | `8000` |
| `DB_POOL_SIZE` | Tamanho do pool | `5` |
| `DB_MAX_OVERFLOW` | Overflow do pool | `10` |
| `DB_POOL_RECYCLE` | Reciclagem de conexões (segundos) | `1800` |
| `DB_CONNECT_TIMEOUT` | Timeout de conexão (segundos) | `5` |
| `DB_HEALTHCHECK_TIMEOUT` | Timeout do `/health/db` (segundos) | `3` |
| `DB_STARTUP_CHECK_ENABLED` | Tenta conectar no startup | `true` |
| `DB_STARTUP_MAX_RETRIES` | Tentativas no startup | `10` |
| `DB_STARTUP_RETRY_DELAY` | Intervalo entre tentativas (segundos) | `1.0` |
| `DATABASE_URL` | URL completa opcional; sobrescreve as variáveis `POSTGRES_*` | vazio |
| `DOCUMENTS_MAX_UPLOAD_MB` | Tamanho máximo do PDF enviado | `50` |
| `DOCUMENTS_MAX_PAGES` | Número máximo de páginas | `500` |
| `DOCUMENTS_STORAGE_BUCKET` | Bucket do MinIO | `rag-documents` |
| `DOCUMENTS_OCR_ENABLED` | Liga o OCR do Docling (Tesseract) | `false` |
| `DOCUMENTS_CHUNK_*` | Alvo, máximo, mínimo e overlap de tokens | `800/1000/150/60` |
| `MINIO_ENDPOINT` | Endpoint S3 do MinIO | `localhost:9000` |
| `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` | Credenciais do MinIO | `minioadmin` |
| `RABBITMQ_*` | Credenciais/host/porta do RabbitMQ | `app/app/localhost/5672` |
| `CELERY_BROKER_URL` | URL AMQP completa opcional | vazio |
| `JINA_API_KEY` | Chave da API de embeddings | vazio |
| `JINA_EMBEDDING_MODEL` | Modelo de embedding | `jina-embeddings-v5-text-small` |
| `JINA_EMBEDDING_DIMENSIONS` | Dimensão do vetor (fixa no schema) | `1024` |
| `DEEPSEEK_API_KEY` | Chave da API DeepSeek | vazio |
| `DEEPSEEK_MODEL` | Modelo usado para resumos e agentes | `deepseek-flash` |
| `AUTH_JWT_SECRET` | Segredo HS256 dos tokens | valor de desenvolvimento |
| `AUTH_ACCESS_TOKEN_EXPIRE_MINUTES` | Validade do access token | `15` |
| `AUTH_REFRESH_TOKEN_EXPIRE_DAYS` | Validade do refresh token | `7` |
| `AGENT_MAX_ITERATIONS` | Limite do loop ReAct | `6` |
| `AGENT_HISTORY_MAX_MESSAGES` | Mensagens de contexto | `20` |
| `AGENT_HISTORY_MAX_TOKENS` | Orçamento de tokens do histórico | `6000` |
| `AGENT_*_MODEL` | Override de modelo por agente (vazio usa `DEEPSEEK_MODEL`) | vazio |
| `AGENT_TEXT_TO_SQL_ENABLED` | Habilita a tool de text-to-SQL | `false` |
| `TEXT_TO_SQL_DB_USER` | Role read-only usado pelo executor SQL | `text_to_sql_reader` |
| `TEXT_TO_SQL_DB_PASSWORD` | Senha do role read-only | valor de desenvolvimento |
| `TEXT_TO_SQL_DATABASE_URL` | URL completa opcional do banco read-only | vazio |
| `TEXT_TO_SQL_MODEL` | Modelo do rewriter/gerador SQL (vazio usa `DEEPSEEK_MODEL`) | vazio |
| `TEXT_TO_SQL_*` | Tentativas, linhas, timeout e limites de complexidade | `2/50/5000/4/30` |
| `RETRIEVAL_*` | Top-k vetorial/lexical, RRF, contexto | `20/20/60/8/6000` |
| `CONVERSATION_WEBHOOK_SECRET` | Segredo HMAC dos webhooks | valor de desenvolvimento |
| `CONVERSATION_WEBHOOK_MAX_RETRIES` | Retries de entrega do webhook | `5` |
| `CONVERSATION_WEBHOOK_ALLOW_PRIVATE_HOSTS` | Permite localhost/rede privada (dev) | `true` em dev |

O `.env` usa `POSTGRES_HOST=localhost` para permitir rodar a API e comandos
Alembic direto no host. No container, o Compose sobrescreve
`POSTGRES_HOST=db`.

## Como executar

Subir API, Postgres, MinIO, RabbitMQ e worker em desenvolvimento:

```bash
docker compose up --build -d
docker compose logs -f api
docker compose logs -f worker
docker compose logs -f agent-worker
```

A API ficará disponível em `http://127.0.0.1:8000`, com documentação em
`http://127.0.0.1:8000/docs`. O console do MinIO fica em
`http://127.0.0.1:9001` e o management do RabbitMQ em
`http://127.0.0.1:15672`.

O código é montado dentro do container com hot reload. O Postgres fica exposto
em `localhost:5432` para inspeção com clientes SQL. O worker roda em uma imagem
própria (`worker-dev`/`worker-runtime`) porque carrega Docling, modelos de layout
e Tesseract, e pode escalar independentemente da API. O `agent-worker` usa uma
imagem leve (`agent-dev`/`agent-runtime`), sem Docling, e consome apenas a fila
`conversations.process`.

Para parar:

```bash
docker compose down
```

Para apagar também o volume do banco:

```bash
docker compose down -v
```

Também é possível rodar a API no host, desde que o Postgres esteja no ar:

```bash
uv sync
uv run fastapi dev
```

## Text-to-SQL

A tool `text_to_sql` responde perguntas analíticas e consultas complexas sobre
catálogo, estoque, promoções e os pedidos do próprio cliente. Ela só é exposta
quando `AGENT_TEXT_TO_SQL_ENABLED=true` e a conexão read-only está configurada.

O fluxo é:

```text
pergunta + histórico
  -> rewriter SQL (pergunta autônoma)
  -> gerador (métrica determinística ou SELECT livre)
  -> validação com SQLGlot
  -> executor read-only (RLS + statement_timeout + LIMIT)
  -> resposta estruturada + resumo
  -> orquestrador/redator/grounding
```

Segurança:

- role dedicado `text_to_sql_reader`, sem escrita;
- RLS em `orders` e `order_items`, limitada por
  `current_setting('app.customer_id')`;
- allowlist de tabelas/colunas; `customers`, tabelas internas, PII, DDL/DML e
  funções perigosas são bloqueados;
- `SELECT *`, `CROSS JOIN`, CTEs recursivas e consultas acima dos limites são
  recusados;
- o SQL bruto fica apenas em `agent_steps`, nunca na resposta ao cliente.

O role é criado pelo script `docker/postgres/init/02-create-text-to-sql-role.sh`
em volumes novos. Para um banco já existente, crie o role antes de aplicar a
migration de RLS:

```bash
docker compose exec db psql -U app -d customer_support_agent \
  -c "CREATE ROLE text_to_sql_reader LOGIN PASSWORD 'troque-esta-senha';" \
  -c "GRANT CONNECT ON DATABASE customer_support_agent TO text_to_sql_reader;"
docker compose exec api alembic upgrade head
```

Não altere `TEXT_TO_SQL_DB_USER` sem ajustar os `GRANT`s da migration.

## Migrations

O Alembic está configurado para usar a mesma `Settings` da aplicação, com engine
async. A migration inicial cria as tabelas `categories`, `products`,
`customers`, `orders`, `order_items` e `promotions`, com enums nativos do
Postgres, índices, checks e colunas de auditoria. A migration de documentos cria
`documents`, `document_sections` e `document_chunks`, habilita as extensões
`vector` e `ltree` e adiciona índices HNSW, GiST e GIN. A migration de conversa
cria `conversations`, `messages`, `complaints`, `agent_runs` e `agent_steps`,
com enums, FKs, índice único parcial de idempotência e índices de consulta. A
migration de Text-to-SQL habilita RLS em `orders`/`order_items` e concede
`SELECT` ao role `text_to_sql_reader`; o role precisa existir antes dela.

Comandos canônicos, executados dentro do container da API:

```bash
# ver revisão atual
docker compose exec api alembic current

# criar uma migration a partir dos models
docker compose exec api alembic revision --autogenerate -m "create products"

# aplicar migrations
docker compose exec api alembic upgrade head

# reverter uma migration
docker compose exec api alembic downgrade -1
```

Os models ORM de cada módulo devem ser importados em
`src/app/db/metadata.py` para que o `--autogenerate` os
encontre.

As migrations não rodam automaticamente no startup da API. Isso evita corrida
entre réplicas e mantém o deploy explícito.

## Importação de dados

Os dados operacionais podem ser carregados por CSVs, sem endpoint de upload e
sem rodar no startup. O comando aceita um diretório com seis arquivos:
`categories.csv`, `products.csv`, `customers.csv`, `orders.csv`,
`order_items.csv` e `promotions.csv`.

```bash
# aplicar a migration antes da primeira carga
docker compose exec api alembic upgrade head

# importar/atualizar (idempotente, upsert por PK)
uv run import-csv data/

# recarregar do zero
uv run import-csv data/ --truncate
```

Os cabeçalhos devem corresponder às colunas do modelo. `specs` é um objeto JSON,
datas usam ISO-8601 e booleanos aceitam `true/false` ou `0/1`. Os CSVs não são
versionados; `data/` está no `.gitignore`. A importação inteira roda em uma
transação e ajusta as sequences após inserir IDs explícitos.

## Ingestão de documentos

O pipeline aceita apenas PDF e é assíncrono:

```text
POST /documents
  -> valida PDF/tamanho/páginas e calcula SHA-256 em streaming
  -> MinIO: sources/{sha256}.pdf
  -> documents (pending) + task no RabbitMQ
  -> worker: Docling -> árvore de seções -> chunks -> resumos DeepSeek
             -> embeddings Jina -> Postgres/pgvector
```

Comportamento principal:

- reenvio do mesmo conteúdo retorna `409` (deduplicação por SHA-256);
- `DELETE /documents/{public_id}` é soft-delete e `POST /restore` desfaz;
- `POST /documents/{public_id}/reprocess` refaz a ingestão usando o PDF já
  armazenado;
- checkpoints de parse, resumos e embeddings ficam em
  `cache/{sha256}/...` no MinIO, então uma intermitência de provedor não perde
  o processamento já feito;
- em falha de reprocessamento, o índice anterior é preservado;
- OCR é opcional (`DOCUMENTS_OCR_ENABLED=true`, Tesseract `por+eng`);
- não há autenticação nesta fase; os endpoints de escrita devem ficar restritos
  à rede interna até a camada de auth ser implementada.

Exemplo com `curl`:

```bash
curl -X POST http://127.0.0.1:8000/documents \
  -F "file=@politicas.pdf" \
  -F "name=Políticas da loja"

curl http://127.0.0.1:8000/documents
curl http://127.0.0.1:8000/documents/{public_id}/sections
curl http://127.0.0.1:8000/documents/{public_id}/chunks
```

O worker usa `--concurrency=1` por padrão. A Jina é chamada com rate limit local
(100 RPM / 100k TPM), retries com backoff e `Retry-After`; o Celery também
reprocessa a task até 3 vezes com backoff.

## Atendimento conversacional

O fluxo é assíncrono e separado da ingestão de documentos:

```text
POST /auth/login (e-mail + telefone)
  -> access token (15 min) + refresh token (7 dias)
POST /conversations
POST /conversations/{public_id}/messages  -> 202 Accepted
  -> messages (queued) + task conversations.process no RabbitMQ
agent-worker:
  -> claim atômico da mensagem
  -> intent agent (JSON estruturado)
  -> orquestrador ReAct (máx. AGENT_MAX_ITERATIONS)
       -> search_store_knowledge (RAG híbrido + rewriter)
       -> search_catalog / get_product_details
       -> list_my_orders / get_order_status (escopo do cliente)
       -> text_to_sql (métricas e consultas complexas, se habilitado)
       -> register_complaint
  -> response writer + validação de grounding
  -> messages (assistant) + agent_runs/agent_steps
  -> conversations.deliver_webhook (HMAC-SHA256, retries)
```

Características principais:

- **isolamento por cliente**: o token identifica o `customer_id`; as tools de
  pedido não aceitam `customer_id` e sempre filtram pelo cliente autenticado;
- **uma mensagem em processamento por conversa**: um novo POST retorna `409`;
- **idempotência**: `client_message_id` único por conversa;
- **polling**: `GET /conversations/{public_id}/messages?after_message_id=...`;
- **reclamações**: no máximo uma reclamação aberta por conversa; a conversa
  continua ativa e recebe `awaiting_human=true`;
- **agente ReAct explícito**: o orquestrador opera em
  `Thought -> Action -> Observation -> Thought`, com no máximo uma tool por
  iteração e uma `Final Answer` de handoff para o response writer;
- **out-of-scope amplo**: acessórios, piadas, receitas, assuntos gerais e
  pedidos perigosos/ilegais são classificados como fora do escopo. Pedidos
  perigosos são recusados deterministicamente antes de qualquer tool ou writer;
- **grounding**: preços/estoque/status precisam vir de tool; citações inválidas
  disparam reparo e, em último caso, fallback seguro;
- **Text-to-SQL**: consultas agregadas e buscas complexas usam um pipeline
  separado, com catálogo semântico, validação SQLGlot, role read-only e RLS por
  cliente; o SQL bruto não é enviado ao redator nem ao cliente;
- **traces**: todas as chamadas de LLM, tools e validações são persistidas em
  `agent_runs`/`agent_steps`, incluindo prompts, resultados, tokens e latência;
- **sem autenticação nas rotas antigas**: `/customers` e `/orders` continuam
  abertas nesta fase; apenas o fluxo conversacional e `/complaints` usam JWT.

### Teste rápido no Swagger

1. Faça login em `POST /auth/login` com um cliente carregado por `import-csv`.
2. Clique em **Authorize** e informe o `access_token`.
3. Crie uma conversa em `POST /conversations`.
4. Envie uma mensagem em `POST /conversations/{public_id}/messages` com
   `webhook_url=http://api:8000/dev/webhooks/conversation` (Docker) ou
   `http://127.0.0.1:8000/dev/webhooks/conversation` (API no host).
5. Acompanhe a resposta em `GET /conversations/{public_id}/messages` e o status
   de entrega no campo `delivery_status`.

O receiver de desenvolvimento existe apenas com `APP_ENV=development`, valida a
assinatura HMAC e não persiste o payload. Para usar `http://127.0.0.1:8000` no
host, mantenha `CONVERSATION_WEBHOOK_ALLOW_PRIVATE_HOSTS=true` no `.env`.

## Perguntas de exemplo

As conversas completas estão em
[`docs/examples/conversas.md`](docs/examples/conversas.md). As perguntas abaixo
cobrem os principais cenários de atendimento e ajudam a validar a escolha de
tools e políticas:

| Cenário | Pergunta de exemplo | Consulta esperada |
| --- | --- | --- |
| Catálogo | Quais opções de violões disponíveis custando até R$ 1000? | `search_catalog` |
| Preço e estoque | Quanto custa o Takamine GD20 e tem em estoque? | `search_catalog`/`get_product_details` |
| Informações da loja | Qual o endereço da loja? | `search_store_knowledge` |
| Horário | Qual o horário de funcionamento? Vocês estão abertos agora? | `search_store_knowledge` + status de expediente |
| Pedido | Qual o status e o rastreamento do meu pedido? | `list_my_orders`/`get_order_status` |
| Devolução | Me arrependi da minha compra, posso devolver meu pedido? | `search_store_knowledge` + elegibilidade de devolução |
| Pagamento | Quanto fica o Yamaha C40 em 12x? Tem desconto no PIX? | `search_store_knowledge` + cálculo de pagamento |
| Frete | Qual o frete para o CEP 79000-000? | `search_store_knowledge` + cálculo de frete |
| Promoção | A promoção do Yamaha C40 ainda está válida? | `search_store_knowledge`/catálogo com validade |
| Reclamação | Meu pedido atrasou e quero registrar uma reclamação. | `register_complaint` |
| Fora do escopo | Vocês vendem cordas de violão e palhetas? | redirecionamento de acessório |
| Fora do escopo | Me passa uma receita de bolo? | redirecionamento de assunto geral |

As perguntas de horário, validade de promoção, elegibilidade de devolução e
cálculo de pagamento/frete também estão listadas em
[`docs/examples/conversas.md`](docs/examples/conversas.md). As validações
determinísticas desses cenários fazem parte das melhorias planejadas; os
exemplos documentam o comportamento esperado do agente.

## Testes

Testes unitários e de contrato:

```bash
uv run pytest
```

Teste de integração opcional contra o Postgres do Compose:

```bash
docker compose up -d db
RUN_INTEGRATION_TESTS=1 \
POSTGRES_DB=customer_support_agent_test \
uv run pytest -m integration
```

O banco `customer_support_agent_test` é criado automaticamente pelo script em
`docker/postgres/init/` na primeira inicialização do volume. O fixture de
integração aplica `alembic upgrade head` nesse banco automaticamente antes dos
testes; não é preciso migrar manualmente. O fixture também garante o role
`text_to_sql_reader` para os testes de RLS.

Teste opcional de qualidade do Text-to-SQL com provider real:

```bash
RUN_INTEGRATION_TESTS=1 DEEPSEEK_API_KEY=... \
POSTGRES_DB=customer_support_agent_test \
uv run pytest -m provider
```

## Endpoints

| Método | Rota         | Descrição |
| --- | --- | --- |
| `GET` | `/` | Nome, versão e status da API |
| `GET` | `/health` | Liveness da API |
| `GET` | `/health/db` | Readiness do banco (`SELECT 1`) |
| `POST` | `/auth/login` | Login com `email` + `phone`; retorna access/refresh tokens |
| `POST` | `/auth/refresh` | Troca refresh token por novo access token |
| `GET` | `/auth/me` | Perfil do cliente autenticado |
| `POST` | `/conversations` | Cria conversa para o cliente autenticado |
| `GET` | `/conversations` | Lista paginada das conversas do cliente |
| `GET` | `/conversations/{public_id}` | Detalhe da conversa |
| `POST` | `/conversations/{public_id}/messages` | Enfileira mensagem (`202`) |
| `GET` | `/conversations/{public_id}/messages` | Mensagens paginadas; `after_message_id` |
| `GET` | `/complaints` | Lista paginada das reclamações do cliente |
| `GET` | `/complaints/{public_id}` | Detalhe da reclamação |
| `POST` | `/dev/webhooks/conversation` | Receiver dev de webhook (somente development) |
| `GET` | `/categories` | Lista paginada de categorias |
| `GET` | `/categories/{category_id}` | Detalhe da categoria |
| `GET` | `/products` | Lista paginada; filtros `category_id`, `status`, `name`, `max_price` |
| `GET` | `/products/{product_id}` | Detalhe do produto |
| `GET` | `/customers` | Lista paginada; filtros `city`, `name` |
| `GET` | `/customers/{customer_id}` | Detalhe do cliente |
| `GET` | `/orders` | Lista paginada; filtros `customer_id`, `status` |
| `GET` | `/orders/{order_id}` | Detalhe do pedido com itens |
| `GET` | `/promotions` | Lista paginada; filtros `product_id`, `is_active` |
| `GET` | `/promotions/{promotion_id}` | Detalhe da promoção |
| `POST` | `/documents` | Upload de PDF (`multipart`, campo `file`); `202` |
| `GET` | `/documents` | Lista paginada; filtros `status`, `is_enabled`, `include_deleted` |
| `GET` | `/documents/{public_id}` | Detalhe e contagens do documento |
| `GET` | `/documents/{public_id}/sections` | Seções hierárquicas paginadas |
| `GET` | `/documents/{public_id}/chunks` | Chunks paginados; filtro `section_public_id` |
| `PATCH` | `/documents/{public_id}` | Nome, metadados e `is_enabled` |
| `DELETE` | `/documents/{public_id}` | Soft-delete |
| `POST` | `/documents/{public_id}/restore` | Restaura documento soft-deleted |
| `POST` | `/documents/{public_id}/reprocess` | Reenfileira a ingestão |

### Paginação e erros

As listas usam `page` (padrão `1`) e `page_size` (padrão `20`, máximo `100`) e
retornam:

```json
{
  "items": [],
  "total": 0,
  "page": 1,
  "page_size": 20
}
```

Recursos inexistentes retornam o status adequado e um corpo estável:

```json
{
  "code": "product_not_found",
  "message": "Product 999 not found"
}
```

### `GET /health/db`

Banco disponível:

```json
{
  "status": "ok",
  "database": "up"
}
```

Banco indisponível (HTTP 503):

```json
{
  "status": "degraded",
  "database": "down"
}
```

Quando `APP_ENV=development`, a resposta de falha também inclui um campo
`detail` com a causa. Em `hml`/`prod` o detalhe não é exposto; o erro completo
vai para o log.

## Ambientes de hml/prod

Os arquivos `deploy/.env.hml` e `deploy/.env.prod` são versionados apenas com
valores fictícios. Substitua as credenciais antes de qualquer deploy real.

Para subir hml ou prod:

```bash
ENV_FILE=deploy/.env.hml \
docker compose --env-file deploy/.env.hml \
  -f compose.yaml -f compose.prod.yaml up -d --build
```

```bash
ENV_FILE=deploy/.env.prod \
docker compose --env-file deploy/.env.prod \
  -f compose.yaml -f compose.prod.yaml up -d --build
```

Em produção, o Postgres não publica porta no host; ele é acessível apenas pela
rede interna do Compose. A aplicação aceita `DATABASE_URL` para apontar para um
Postgres gerenciado, caso necessário.

## Estrutura do projeto

```text
.
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
├── deploy/
│   ├── .env.hml
│   └── .env.prod
├── docker/
│   └── postgres/init/        # banco de testes e role read-only
├── .agents/
│   ├── project-context/      # perfil do projeto para agentes
│   ├── rules/                # regras sempre carregadas
│   └── skills/               # fluxos reutilizáveis
├── src/
│   └── app/
│       ├── main.py           # aplicação FastAPI e lifespan
│       ├── worker.py         # worker de ingestão de documentos
│       ├── agent_worker.py   # worker do agente conversacional
│       ├── core/
│       │   ├── config.py     # Settings da aplicação
│       │   └── exceptions.py # AppError e bases de erro
│       ├── db/
│       │   ├── base.py       # Base declarativa + naming convention
│       │   ├── metadata.py   # metadata para o Alembic
│       │   └── session.py    # engine, session factory e startup probe
│       ├── presentation/
│       │   ├── exception_handlers.py  # handler global de erros
│       │   └── pagination.py          # Page[T] e parâmetros de paginação
│       ├── infrastructure/importing/  # importador CSV
│       ├── cli/import_csv.py          # comando import-csv
│       └── modules/
│           ├── health/
│           ├── auth/
│           ├── conversations/
│           ├── messages/
│           ├── complaints/
│           ├── agent/
│           ├── text_to_sql/
│           ├── categories/
│           ├── products/
│           ├── customers/
│           ├── orders/
│           └── promotions/
├── tests/
│   ├── categories/
│   ├── products/
│   ├── customers/
│   ├── orders/
│   ├── promotions/
│   ├── agent/
│   ├── text_to_sql/
│   ├── importing/
│   └── integration/
├── AGENTS.md
├── opencode.json
├── alembic.ini
├── compose.yaml
├── compose.override.yaml
├── compose.prod.yaml
├── Dockerfile
├── pyproject.toml
└── uv.lock
```

## Codificação com agentes de IA

O desenvolvimento deste repositório usa o [OpenCode](https://opencode.ai/) como
assistente de código. A configuração é versionada para que o mesmo contexto
valha para qualquer pessoa ou ferramenta que trabalhe no projeto:

- `AGENTS.md`: instruções permanentes, comandos, convenções e definição de
  pronto.
- `.agents/rules/`: regras sempre carregadas sobre fronteiras de arquitetura,
  persistência/migrations, integrações de IA e validação.
- `.agents/project-context/`: perfil versionado do projeto, derivado do código,
  do README e do escopo de negócio registrado em `domain.md`. `PROJECT.md`
  funciona como mapa de leitura dos demais arquivos.
- `.agents/skills/`: fluxos reutilizáveis para configurar/atualizar o contexto
  (`project-context-setup`), criar módulos de negócio (`new-module`), criar e
  revisar migrations (`db-migration`), revisar o staged antes do commit
  (`pre-commit-review`) e gerar descrições de PR (`pr-description`).

O fluxo usado é: carregar o contexto e as regras antes de implementar; usar as
skills para scaffolding e migrations; rodar `uv run pytest`; revisar o staged
com `pre-commit-review`; e registrar decisões de arquitetura em
`.agents/project-context/architecture.md`.
Nenhum assistente de codificação roda em produção — o agente de atendimento ao
cliente é o produto, não o assistente de codificação.

## Decisões de arquitetura

- **SQLAlchemy async + asyncpg** para não bloquear o event loop em chamadas de
  banco, alinhado ao uso futuro de LLMs e I/O externo.
- **Sessão por request** e **transação por método público de repository**. Todo
  método do repository usa `session.begin()`, inclusive leituras, para devolver
  a conexão ao pool imediatamente. O commit fica no repository; use cases não
  tocam em sessão.
- **Engine e session factory lazy com cache**, evitando efeitos colaterais no
  import e facilitando testes.
- **`expire_on_commit=False`** para evitar lazy loads implícitos após commit em
  contexto async.
- **Alembic async** lendo a mesma `Settings`, com imports explícitos em
  `db/metadata.py` para autogenerate determinístico.
- **Base declarativa com naming convention** para nomes previsíveis de
  constraints e índices.
- **Módulos em Clean Architecture**: `domain`, `application`, `infrastructure`
  e `presentation`. O módulo `health` é a menor referência; os módulos de
  negócio mostram o padrão completo.
- **PKs inteiras com `Identity` e `TimestampMixin`** em todas as tabelas;
  `order_items` usa PK composta e pertence ao agregado `orders`.
- **Dinheiro em `Numeric(12,2)` + `Decimal`**, com `float` apenas na resposta
  JSON; enums de status/pagamento são tipos nativos do Postgres.
- **Listas paginadas** com `page`/`page_size` e envelope `items/total/page/
  page_size`; erros de aplicação retornam `{code, message}`.
- **Importação CSV idempotente** via `import-csv`, em uma transação, com upsert
  por PK e reset de sequences; nunca roda no startup.
- **Startup com retries limitados e modo degradado**: se o banco não responder,
  a API sobe, loga o problema e `/health/db` retorna 503.
- **UTC** no banco e na aplicação. A conversão para `America/Sao_Paulo` deve
  acontecer apenas na apresentação.
- **JWT stateless** com access token de 15 minutos e refresh token de 7 dias; o
  token carrega `customer_id`, e toda consulta de conversa/pedido é filtrada
  pelo cliente autenticado.
- **Agente ReAct próprio** sobre function calling do DeepSeek, sem framework de
  orquestração. Intent, rewriter e response writer são etapas separadas;
  todas as chamadas e tools são rastreadas.
- **Retrieval híbrido** com pgvector + FTS português, fusão RRF e expansão
  parent-child, sem reranker nesta fase.
- **Tools determinísticas para dados operacionais**; text-to-SQL tem contrato
  reservado, mas permanece desabilitado (`AGENT_TEXT_TO_SQL_ENABLED=false`).
- **Webhook assinado com HMAC-SHA256**: entrega em task separada, com retries e
  status persistido na mensagem; o receiver `/dev/webhooks/conversation` existe
  apenas em development.
- **Traces completos** em `agent_runs`/`agent_steps` (prompts, tools, tokens,
  latência e erros) para evolução futura do agente.

## O que eu faria com mais tempo

- **Prompts no banco de dados com cache em Redis**: permitir ajustes de prompt
  sem deploy, versionamento e rollback, mantendo os prompts quentes em runtime.
- **Contenção de reclamações e transbordo humano**: criar fila/atribuição para o
  time responsável, SLA de retorno, resolução e transbordo controlado para evitar
  sobrecarga do atendimento.
- **CRUD completo dos módulos operacionais**: complementar as rotas GET atuais
  com escrita para categorias, produtos, clientes, pedidos e promoções.
- **RBAC e papéis na API**: separar permissões de cliente, atendente,
  operador e administrador nas rotas autenticadas.
- **Processamento autoevolutivo dos agentes**: usar os traces já persistidos
  para avaliar, comparar e evoluir prompts, tools e políticas de roteamento.
- **Canais omnichannel**: adicionar entrada/saída para WhatsApp, web, Messenger
  e Instagram com uma camada comum de conversas e entrega.
- **Testes de LLM/agentes com DeepEval**: medir qualidade de resposta,
  fidelidade às políticas, uso correto de tools e regressões de prompt.
- **Reduzir a imagem do ingestion worker**: hoje ela chega a ~11 GB no target de
  desenvolvimento. O diagnóstico e o plano de redução estão em
  [`docs/worker_image_size.md`](docs/worker_image_size.md).

## Limitações conhecidas

- `/customers` e `/orders` ainda não exigem JWT; a proteção desta iteração cobre
  apenas `/auth`, `/conversations`, `/messages` e `/complaints`.
- Login usa e-mail + telefone como prova de identidade, sem senha; não há rate
  limiting nem revogação de refresh token.
- Não há outbox transacional: se o enfileiramento falhar após criar a mensagem,
  ela é marcada como `failed` e a API responde `503`.
- Text-to-SQL é opt-in e cobre catálogo, estoque, promoções e pedidos do próprio
  cliente; não há métricas da loja inteira, cache de consultas, múltiplos
  candidatos ou endpoint HTTP dedicado.
- O trace de Text-to-SQL guarda o SQL e as linhas retornadas (até o limite
  configurado); a política de retenção LGPD desses traces ainda é uma fase
  futura.
- Sem reranker, sumarização de histórico ou memória semântica de mensagens.
- Os traces guardam prompts e conteúdo de conversa (dados sensíveis) em tabelas
  internas; a política completa de LGPD/retenção fica para uma próxima fase.
- A validação de URL do webhook bloqueia hosts privados em hml/prod, mas não
  cobre DNS rebinding.
- A imagem do worker de ingestão ainda não foi otimizada; o tamanho atual e o
  plano de redução estão documentados em
  [`docs/worker_image_size.md`](docs/worker_image_size.md).
