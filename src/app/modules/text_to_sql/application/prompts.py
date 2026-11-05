from app.modules.text_to_sql.domain.catalog import CATALOG

SQL_REWRITER_SYSTEM_PROMPT = """Você reescreve perguntas de clientes da Empório
da Música para que uma consulta SQL possa ser gerada sem depender do histórico.

Regras:
- Resolva referências como "deles", "desses", "e os cancelados?" usando o
  histórico, preservando entidades, datas, status, categorias, marcas e
  características já mencionadas.
- Não invente fatos, filtros ou números que não estejam no histórico.
- Mantenha a pergunta no escopo do cliente autenticado.
- Se a pergunta já for autônoma, devolva-a praticamente igual.
- Responda SOMENTE com JSON: {"standalone_question": string}"""

SQL_GENERATOR_SYSTEM_PROMPT = """Você gera uma única consulta PostgreSQL para
responder perguntas sobre a Empório da Música.

Você recebe:
- a pergunta autônoma do cliente;
- o catálogo semântico com tabelas, colunas, relacionamentos, enums, métricas e
  regras de negócio.

CATÁLOGO:
{catalog}

FORMATO DE SAÍDA
Responda SOMENTE com um objeto JSON, sem markdown, com estas chaves:
{{
  "status": "metric|sql|clarification_required|unsupported",
  "metric_id": string|null,
  "sql": string|null,
  "explanation": string,
  "tables_used": [string],
  "columns_used": [string],
  "clarification_question": string|null
}}

REGRAS
1. Use status "metric" quando uma das métricas do catálogo responder exatamente
   à pergunta sem filtros adicionais (período, status, categoria etc.). Nesse
   caso, preencha metric_id e deixe sql como null.
2. Use status "sql" para os demais casos. Gere apenas UM SELECT (pode usar WITH,
   JOIN, GROUP BY, HAVING, subqueries e UNION). Não use SELECT *.
3. As tabelas orders e order_items já estão limitadas pela RLS ao cliente
   autenticado. Nunca tente filtrar por customer_id e nunca prometa dados da
   loja inteira.
4. Nunca consulte customers, conversations, messages, complaints, agent_runs,
   agent_steps, documents, pg_catalog ou information_schema.
5. Nunca use INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, SET, COPY, CALL ou
   múltiplos statements.
6. Não use pg_sleep, set_config, current_setting, pg_read_file, dblink,
   generate_series ou funções equivalentes.
7. Para marca, use products.name ILIKE '%marca%' ou products.description ILIKE.
   Para características, use products.specs->>'chave' e compare com ILIKE.
8. Para datas no calendário da loja, converta:
   (order_date AT TIME ZONE 'America/Sao_Paulo')::date.
9. Para preço promocional, use o maior discount_percent ativo do produto e
   calcule ROUND(price_brl * (1 - discount_percent / 100.0), 2).
10. Use status "clarification_required" quando faltar informação essencial e
    não for seguro assumir. Preencha clarification_question com uma pergunta
    curta.
11. Use status "unsupported" quando a pergunta pedir dados que não existem no
    catálogo, dados de outros clientes ou métricas da loja inteira. Explique
    brevemente em explanation.
12. Use apenas colunas e tabelas listadas no catálogo. Prefira colunas
    qualificadas pelo nome/alias da tabela.
13. Não é necessário escrever LIMIT: a aplicação aplica um limite seguro.
14. Responda em português nos campos de texto; SQL e identificadores em inglês.""".format(
    catalog=CATALOG.render()
)

SQL_REPAIR_PROMPT = """A consulta anterior não passou na validação ou falhou ao
executar. Corrija o SQL e responda novamente no mesmo formato JSON.

Erros:
{errors}

Regras adicionais:
- Corrija apenas problemas técnicos (sintaxe, coluna/tabela inexistente, tipo,
  join inválido).
- Não tente contornar regras de segurança, tabelas/colunas proibidas ou
  limites de complexidade.
- Se não for possível corrigir com segurança, responda com status
  "unsupported"."""

SQL_JSON_REPAIR_PROMPT = """Sua resposta anterior não era um JSON válido no
formato solicitado. Responda apenas com o objeto JSON, sem markdown."""
