"""Static semantic catalog for the store's structured data.

The catalog is intentionally small: the whole schema fits in the generation
prompt, so no schema retrieval or embeddings are needed. A drift test compares
this representation with the real database schema.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ColumnSpec:
    name: str
    data_type: str
    description: str
    aliases: tuple[str, ...] = ()
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class TableSpec:
    name: str
    description: str
    aliases: tuple[str, ...]
    columns: tuple[ColumnSpec, ...]
    primary_key: tuple[str, ...]
    relationships: tuple[str, ...] = ()

    @property
    def column_names(self) -> frozenset[str]:
        return frozenset(column.name for column in self.columns)


@dataclass(frozen=True, slots=True)
class MetricSpec:
    metric_id: str
    description: str
    examples: tuple[str, ...]
    result_columns: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SemanticCatalog:
    tables: tuple[TableSpec, ...]
    metrics: tuple[MetricSpec, ...]
    rules: tuple[str, ...]
    denied_columns: frozenset[str]

    @property
    def table_names(self) -> frozenset[str]:
        return frozenset(table.name for table in self.tables)

    @property
    def metric_ids(self) -> frozenset[str]:
        return frozenset(metric.metric_id for metric in self.metrics)

    def table(self, name: str) -> TableSpec | None:
        lowered = name.lower()
        for table in self.tables:
            if table.name == lowered:
                return table
        return None

    def columns_for(self, table_name: str) -> frozenset[str]:
        table = self.table(table_name)
        return table.column_names if table is not None else frozenset()

    def all_allowed_columns(self) -> frozenset[str]:
        return frozenset(
            column.name
            for table in self.tables
            for column in table.columns
        )

    def render(self) -> str:
        lines: list[str] = []
        for table in self.tables:
            lines.append(f"Tabela {table.name}: {table.description}")
            if table.aliases:
                lines.append(
                    "  Sinônimos: " + ", ".join(table.aliases)
                )
            lines.append(
                "  Chave primária: " + ", ".join(table.primary_key)
            )
            for column in table.columns:
                detail = f"  - {column.name} {column.data_type}: {column.description}"
                if column.aliases:
                    detail += " (sinônimos: " + ", ".join(column.aliases) + ")"
                if column.notes:
                    detail += f" [{column.notes}]"
                lines.append(detail)
            if table.relationships:
                lines.append("  Relacionamentos:")
                lines.extend(
                    f"    - {relationship}"
                    for relationship in table.relationships
                )
            lines.append("")

        lines.append("Métricas determinísticas disponíveis:")
        for metric in self.metrics:
            lines.append(
                f"- {metric.metric_id}: {metric.description}"
            )
            if metric.examples:
                lines.append(
                    "  Exemplos: " + "; ".join(metric.examples)
                )
            lines.append(
                "  Colunas de resultado: "
                + ", ".join(metric.result_columns)
            )

        lines.append("")
        lines.append("Regras de negócio:")
        lines.extend(f"- {rule}" for rule in self.rules)
        return "\n".join(lines).strip()


_TABLES: tuple[TableSpec, ...] = (
    TableSpec(
        name="categories",
        description="Categorias de instrumentos musicais.",
        aliases=("categoria", "segmento"),
        primary_key=("category_id",),
        columns=(
            ColumnSpec(
                "category_id",
                "integer",
                "Identificador da categoria.",
                aliases=("id da categoria",),
            ),
            ColumnSpec(
                "name",
                "text",
                "Nome da categoria (ex.: Violões, Guitarras).",
                aliases=("nome", "nome da categoria"),
            ),
            ColumnSpec(
                "description",
                "text",
                "Descrição livre da categoria.",
                aliases=("descrição",),
            ),
        ),
        relationships=(
            "categories.category_id = products.category_id (1:N)",
        ),
    ),
    TableSpec(
        name="products",
        description="Instrumentos musicais vendidos pela loja.",
        aliases=("produtos", "instrumentos", "catálogo"),
        primary_key=("product_id",),
        columns=(
            ColumnSpec(
                "product_id",
                "integer",
                "Identificador do produto.",
                aliases=("id do produto",),
            ),
            ColumnSpec(
                "price_brl",
                "numeric(12,2)",
                "Preço de tabela em reais, sem promoção.",
                aliases=("preço", "preço de tabela", "valor"),
            ),
            ColumnSpec(
                "name",
                "text",
                "Nome do produto. A marca costuma aparecer no início do nome.",
                aliases=("nome", "nome do produto", "marca"),
                notes="não existe coluna brand; busque a marca com ILIKE em name/description",
            ),
            ColumnSpec(
                "category_id",
                "integer",
                "Categoria do produto.",
                aliases=("categoria",),
            ),
            ColumnSpec(
                "description",
                "text",
                "Descrição comercial do instrumento.",
                aliases=("descrição", "detalhes"),
            ),
            ColumnSpec(
                "stock_quantity",
                "integer",
                "Unidades disponíveis em estoque.",
                aliases=("estoque", "quantidade em estoque"),
            ),
            ColumnSpec(
                "status",
                "product_status",
                "active, coming_soon ou discontinued.",
                aliases=("situação", "disponibilidade"),
            ),
            ColumnSpec(
                "specs",
                "jsonb",
                "Características técnicas. Use specs->>'chave' para extrair texto.",
                aliases=("especificações", "características", "ficha técnica"),
                notes=(
                    "chaves conhecidas: top, back_sides, neck, strings, scale, "
                    "electronics, color, body, shells, pieces, hardware, keys, "
                    "type, polyphony"
                ),
            ),
        ),
        relationships=(
            "products.category_id = categories.category_id (N:1)",
            "products.product_id = promotions.product_id (1:N)",
            "products.product_id = order_items.product_id (1:N)",
        ),
    ),
    TableSpec(
        name="promotions",
        description="Promoções cadastradas por produto.",
        aliases=("promoções", "descontos", "ofertas"),
        primary_key=("promotion_id",),
        columns=(
            ColumnSpec(
                "promotion_id",
                "integer",
                "Identificador da promoção.",
            ),
            ColumnSpec(
                "product_id",
                "integer",
                "Produto promovido.",
            ),
            ColumnSpec(
                "discount_percent",
                "integer",
                "Percentual de desconto entre 0 e 100.",
                aliases=("desconto", "percentual de desconto"),
            ),
            ColumnSpec(
                "description",
                "text",
                "Descrição da campanha promocional.",
                aliases=("descrição", "campanha"),
            ),
            ColumnSpec(
                "is_active",
                "boolean",
                "Indica se a promoção está habilitada.",
                aliases=("ativa", "habilitada"),
            ),
            ColumnSpec(
                "starts_at",
                "timestamptz",
                "Início da vigência da promoção, quando informado.",
                aliases=("início", "data de início"),
            ),
            ColumnSpec(
                "ends_at",
                "timestamptz",
                "Fim da vigência da promoção, quando informado.",
                aliases=("fim", "data de fim", "validade"),
            ),
        ),
        relationships=(
            "promotions.product_id = products.product_id (N:1)",
        ),
    ),
    TableSpec(
        name="orders",
        description=(
            "Pedidos do cliente autenticado. A RLS já limita as linhas ao "
            "próprio cliente; nunca trate como dados da loja inteira."
        ),
        aliases=("pedidos", "compras"),
        primary_key=("order_id",),
        columns=(
            ColumnSpec(
                "order_id",
                "integer",
                "Identificador do pedido.",
                aliases=("id do pedido", "número do pedido"),
            ),
            ColumnSpec(
                "order_date",
                "timestamptz",
                "Data/hora do pedido em UTC.",
                aliases=("data do pedido", "data da compra"),
                notes=(
                    "para dias/meses no calendário da loja, converta com "
                    "AT TIME ZONE 'America/Sao_Paulo'"
                ),
            ),
            ColumnSpec(
                "status",
                "order_status",
                "cancelled, confirmed, delivered, pending ou shipped.",
                aliases=("situação", "status do pedido"),
            ),
            ColumnSpec(
                "total_brl",
                "numeric(12,2)",
                "Valor total do pedido em reais.",
                aliases=("total", "valor total"),
            ),
            ColumnSpec(
                "payment_method",
                "payment_method",
                "boleto, pix, debit, credit_3x, credit_6x ou credit_12x.",
                aliases=("forma de pagamento", "pagamento"),
            ),
            ColumnSpec(
                "sales_channel",
                "sales_channel",
                "online ou in_store.",
                aliases=("canal", "canal de venda"),
            ),
            ColumnSpec(
                "tracking_code",
                "text",
                "Código de rastreamento, quando disponível.",
                aliases=("rastreio", "rastreamento"),
            ),
            ColumnSpec(
                "estimated_delivery",
                "timestamptz",
                "Previsão de entrega, quando disponível.",
                aliases=("previsão de entrega", "entrega estimada"),
            ),
            ColumnSpec(
                "delivered_at",
                "timestamptz",
                "Data real de recebimento, quando disponível.",
                aliases=("data de recebimento", "entregue em"),
            ),
        ),
        relationships=(
            "orders.order_id = order_items.order_id (1:N)",
            "orders.customer_id = customers.customer_id (N:1, não exposto)",
        ),
    ),
    TableSpec(
        name="order_items",
        description=(
            "Itens dos pedidos do cliente autenticado. A RLS acompanha o "
            "pedido correspondente."
        ),
        aliases=("itens do pedido", "itens"),
        primary_key=("order_id", "product_id"),
        columns=(
            ColumnSpec(
                "order_id",
                "integer",
                "Pedido ao qual o item pertence.",
            ),
            ColumnSpec(
                "product_id",
                "integer",
                "Produto comprado.",
            ),
            ColumnSpec(
                "quantity",
                "integer",
                "Quantidade comprada.",
                aliases=("quantidade",),
            ),
            ColumnSpec(
                "is_final_sale",
                "boolean",
                "Item de liquidação com venda final.",
                aliases=("venda final", "liquidação"),
            ),
            ColumnSpec(
                "is_customized",
                "boolean",
                "Item personalizado ou ajustado sob encomenda.",
                aliases=("personalizado", "sob encomenda"),
            ),
            ColumnSpec(
                "is_hygiene_restricted",
                "boolean",
                "Item com restrição de higiene para troca.",
                aliases=("higiene", "boquilha"),
            ),
        ),
        relationships=(
            "order_items.order_id = orders.order_id (N:1)",
            "order_items.product_id = products.product_id (N:1)",
        ),
    ),
)

_METRICS: tuple[MetricSpec, ...] = (
    MetricSpec(
        metric_id="my_total_spent",
        description=(
            "Total gasto pelo cliente em pedidos não cancelados, com a "
            "quantidade de pedidos considerada."
        ),
        examples=(
            "Quanto eu já gastei na loja?",
            "Qual é o total das minhas compras?",
        ),
        result_columns=("total_brl", "order_count"),
    ),
    MetricSpec(
        metric_id="my_order_count",
        description=(
            "Quantidade de pedidos do cliente por status, incluindo cancelados."
        ),
        examples=(
            "Quantos pedidos eu tenho?",
            "Quantos pedidos eu cancelei?",
        ),
        result_columns=("status", "order_count"),
    ),
    MetricSpec(
        metric_id="my_average_order_value",
        description=(
            "Ticket médio do cliente em pedidos não cancelados."
        ),
        examples=(
            "Qual é o meu ticket médio?",
            "Qual é o valor médio dos meus pedidos?",
        ),
        result_columns=("average_order_value_brl", "order_count"),
    ),
    MetricSpec(
        metric_id="my_top_products",
        description=(
            "Os 5 produtos que o cliente mais comprou, por quantidade, "
            "desconsiderando pedidos cancelados."
        ),
        examples=(
            "Quais produtos eu mais comprei?",
            "Qual instrumento eu comprei mais vezes?",
        ),
        result_columns=("product_name", "quantity"),
    ),
    MetricSpec(
        metric_id="catalog_availability",
        description=(
            "Resumo do catálogo por categoria: produtos ativos, em breve, "
            "descontinuados e unidades em estoque."
        ),
        examples=(
            "Quais categorias têm mais produtos?",
            "Quantos produtos ativos existem por categoria?",
        ),
        result_columns=(
            "category_name",
            "total_products",
            "active_products",
            "coming_soon_products",
            "discontinued_products",
            "stock_units",
        ),
    ),
    MetricSpec(
        metric_id="active_promotions",
        description=(
            "Promoções ativas de produtos ativos, ordenadas pelo maior desconto."
        ),
        examples=(
            "Quais promoções estão ativas?",
            "Quais instrumentos estão em promoção?",
        ),
        result_columns=(
            "product_name",
            "discount_percent",
            "description",
        ),
    ),
)

_RULES: tuple[str, ...] = (
    "orders e order_items já vêm filtrados pela RLS para o cliente autenticado. "
    "Nunca apresente esses dados como vendas ou pedidos da loja inteira.",
    "Perguntas sobre vendas, faturamento ou produtos mais vendidos da loja são "
    "unsupported: não há acesso a dados agregados de todos os clientes.",
    "Pedidos com status 'cancelled' não entram em total gasto, ticket médio ou "
    "produtos mais comprados.",
    "Promoções não são cumulativas. Para preço promocional, use o maior "
    "discount_percent ativo do produto e calcule "
    "ROUND(price_brl * (1 - discount_percent / 100.0), 2). O desconto PIX de 5% "
    "não se aplica a preço promocional.",
    "Não existe coluna de marca. Busque a marca em products.name ou "
    "products.description com ILIKE. Características técnicas ficam em "
    "products.specs e devem ser consultadas com specs->>'chave'.",
    "Use comparações de data no calendário America/Sao_Paulo, por exemplo "
    "(order_date AT TIME ZONE 'America/Sao_Paulo')::date.",
    "Sempre selecione colunas explícitas; nunca use SELECT *.",
    "Dinheiro usa numeric; arredonde valores calculados com ROUND(..., 2).",
)

DENIED_COLUMNS: frozenset[str] = frozenset(
    {
        "customer_id",
        "notes",
        "created_at",
        "updated_at",
        "phone",
        "email",
        "document",
        "password_hash",
        "embedding",
    }
)

CATALOG = SemanticCatalog(
    tables=_TABLES,
    metrics=_METRICS,
    rules=_RULES,
    denied_columns=DENIED_COLUMNS,
)
