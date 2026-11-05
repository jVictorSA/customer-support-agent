API_DESCRIPTION = """
API do agente de atendimento da Empório da Música.

## Autenticação

O fluxo conversacional usa JWT. Faça login em `POST /auth/login` com e-mail e
telefone, copie o `access_token` e use **Authorize** com o esquema `Bearer`.

## Formato das respostas

- Listas usam `page`/`page_size` e retornam `{items, total, page, page_size}`.
- Erros de aplicação retornam `{code, message}`.
- Mensagens de chat são assíncronas: `POST /conversations/{public_id}/messages`
  retorna `202` e a resposta é obtida por polling.
- Webhooks são assinados com HMAC-SHA256 no header `X-Webhook-Signature`.

## Ambientes

O receiver `POST /dev/webhooks/conversation` existe apenas em
`APP_ENV=development`. Em `hml`/`prod`, detalhes internos de erro não são
expostos.
"""

TAGS_METADATA = [
    {"name": "Root", "description": "Identificação e status básico da API."},
    {"name": "Health", "description": "Liveness e readiness do banco."},
    {
        "name": "Auth",
        "description": "Login, refresh e perfil do cliente autenticado.",
    },
    {
        "name": "Conversations",
        "description": "Criação, listagem e detalhe das conversas.",
    },
    {
        "name": "Messages",
        "description": "Envio assíncrono e polling de mensagens.",
    },
    {
        "name": "Complaints",
        "description": "Reclamações registradas e encaminhadas ao humano.",
    },
    {
        "name": "Documents",
        "description": "Ingestão e consulta de PDFs para RAG.",
    },
    {
        "name": "Categories",
        "description": "Catálogo: categorias de instrumentos.",
    },
    {"name": "Products", "description": "Catálogo: produtos e estoque."},
    {"name": "Customers", "description": "Clientes da loja."},
    {"name": "Orders", "description": "Pedidos e itens do cliente."},
    {"name": "Promotions", "description": "Promoções e janelas de validade."},
    {
        "name": "Dev Webhooks",
        "description": "Receiver local de webhook, apenas em development.",
    },
]
