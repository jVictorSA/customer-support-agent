# Customer Support Agent

API de agente de atendimento ao cliente para uma loja de instrumentos musicais.

O projeto está em desenvolvimento e, por enquanto, expõe apenas os endpoints
básicos de identificação e verificação de saúde da API.

## Stack

- [Python 3.12+](https://www.python.org/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [uv](https://docs.astral.sh/uv/) para gerenciamento do ambiente e dependências
- [pytest](https://docs.pytest.org/) para testes

## Requisitos

- Python 3.12 ou superior
- uv instalado

## Instalação

Clone o repositório e instale as dependências:

```bash
git clone git@github.com:jVictorSA/customer-support-agent.git
cd customer-support-agent
uv sync
```

## Como executar

O entrypoint da aplicação está configurado no `pyproject.toml`, então basta
iniciar o servidor de desenvolvimento:

```bash
uv run fastapi dev
```

Também é possível rodar diretamente com o Uvicorn:

```bash
uv run uvicorn customer_support_agent.app:app --reload --port 8000
```

A API ficará disponível em `http://127.0.0.1:8000`. A documentação interativa
pode ser acessada em `http://127.0.0.1:8000/docs`.

## Testes

```bash
uv run pytest
```

## Endpoints

| Método | Rota      | Descrição                                      |
| ------ | --------- | ---------------------------------------------- |
| `GET`  | `/`       | Nome, versão e status da API                   |
| `GET`  | `/health` | Verificação de saúde da API                    |

### `GET /`

```json
{
  "name": "Customer Support Agent API",
  "version": "0.1.0",
  "status": "ok"
}
```

### `GET /health`

```json
{
  "status": "ok"
}
```

## Estrutura do projeto

```text
.
├── docs/
│   └── dev-docs/           # Documentação de referência do domínio
├── src/
│   └── customer_support_agent/
│       ├── __init__.py
│       └── app.py          # Aplicação FastAPI
├── tests/
│   └── test_health.py
├── pyproject.toml
└── README.md
```
