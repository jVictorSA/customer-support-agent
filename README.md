# Customer Support Agent

API de agente de atendimento ao cliente para uma loja de instrumentos musicais.

O projeto está em desenvolvimento. Nesta etapa, a base de persistência está
configurada: a API conecta em um Postgres 17.11 via SQLAlchemy async, as
migrations são gerenciadas pelo Alembic e o endpoint `/health/db` verifica a
conexão com o banco.

## Stack

- [Python 3.12+](https://www.python.org/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [Postgres 17.11](https://www.postgresql.org/)
- [SQLAlchemy 2.x async + asyncpg](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Alembic](https://alembic.sqlalchemy.org/)
- [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [uv](https://docs.astral.sh/uv/) para gerenciamento do ambiente e dependências
- [Docker Compose](https://docs.docker.com/compose/) para Postgres e API
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

O `.env` usa `POSTGRES_HOST=localhost` para permitir rodar a API e comandos
Alembic direto no host. No container, o Compose sobrescreve
`POSTGRES_HOST=db`.

## Como executar

Subir API e Postgres em desenvolvimento:

```bash
docker compose up --build -d
docker compose logs -f api
```

A API ficará disponível em `http://127.0.0.1:8000`, com documentação em
`http://127.0.0.1:8000/docs`.

O código é montado dentro do container com hot reload. O Postgres fica exposto
em `localhost:5432` para inspeção com clientes SQL.

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

## Migrations

O Alembic está configurado para usar a mesma `Settings` da aplicação, com engine
async. A migration inicial cria as tabelas `categories`, `products`,
`customers`, `orders`, `order_items` e `promotions`, com enums nativos do
Postgres, índices, checks e colunas de auditoria.

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
testes; não é preciso migrar manualmente.

## Endpoints

| Método | Rota         | Descrição |
| --- | --- | --- |
| `GET` | `/` | Nome, versão e status da API |
| `GET` | `/health` | Liveness da API |
| `GET` | `/health/db` | Readiness do banco (`SELECT 1`) |
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
│   └── postgres/init/        # criação do banco de testes
├── .agents/
│   ├── project-context/      # perfil do projeto para agentes
│   ├── rules/                # regras sempre carregadas
│   └── skills/               # fluxos reutilizáveis
├── src/
│   └── app/
│       ├── main.py           # aplicação FastAPI e lifespan
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
Nenhuma ferramenta de IA roda em produção — o agente de atendimento ao cliente é
o produto, não o assistente de codificação.

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
