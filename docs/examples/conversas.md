# Exemplos de interação

Conversas de exemplo com o agente da Empório da Música. Os dados operacionais
usados são os CSVs de demonstração (`import-csv samples/data/ --truncate`) e o
cliente autenticado é o cliente `1` (Lucas Mendes).

## 1. Catálogo por faixa de preço

**Cliente:** Quais violões disponíveis custando até R$ 1000?

**Agente:** E aí, Lucas! Beleza? Separei os violões que temos disponíveis dentro
do seu orçamento, todos com estoque aqui na loja:

- Tagima Memphis AC-39 Nylon Natural — R$ 429,90 (clássico, tampo Linden)
- Rozini RC-104 Nylon Estudante — R$ 459,90 (clássico de estudo, tampo Spruce)
- Shelby SN-100 Folk Aço Preto — R$ 549,00 (folk, cordas de aço)
- Giannini GF-1R Aço Folk Sunburst — R$ 579,90 (folk)
- Yamaha C40 Nylon Natural — R$ 599,90 (clássico, tampo Spruce)

Quer que eu compare algum deles ou veja as formas de pagamento?

*Tools usadas: `search_catalog`, `response_writer` + grounding.*

## 2. Preço e estoque de um produto

**Cliente:** Quanto custa o Yamaha C40 e tem em estoque?

**Agente:** Oi, Lucas! O Yamaha C40 Nylon Natural está sim em estoque — temos 12
unidades disponíveis. Ele sai por R$ 599,90. É um violão clássico com tampo em
Spruce, fundo e laterais em Meranti, cordas de nylon e escala de 650 mm, uma
ótima porta de entrada para quem está começando. Quer que eu te ajude a escolher
entre ele e outras opções?

*Tools usadas: `search_catalog`, `get_product_details`.*

## 3. Pedido inexistente no cadastro do cliente

**Cliente:** Qual o status e o rastreamento do pedido 2?

**Agente:** Oi, Lucas! Procurei o pedido 2 no seu cadastro e não encontrei nenhum
pedido com esse número. O que apareceu para mim foi o pedido 4: Giannini GF-3D
Dreadnought Sunburst, R$ 799,90, pago por boleto, com status entregue e rastreio
BRQM7890123BR. Será que o número que você quis dizer é esse?

*O pedido 2 pertence a outro cliente e não foi retornado. Tools usadas:
`get_order_status`, `list_my_orders`; o repositório filtra por `customer_id`.*

## 4. Reclamação e encaminhamento humano

**Cliente:** Meu pedido atrasou e ninguém me responde. Quero registrar uma
reclamação.

**Agente:** Oi, Lucas! Sinto muito pela demora no retorno — entendo a sua
frustração. Já registrei a sua reclamação com prioridade alta. O protocolo é
`b70bf070-6021-4559-afde-7336a6e4f240`, e o retorno acontece em até 24 horas
úteis. No sistema, o pedido 4 aparece como entregue; você chegou a recebê-lo?

*Tools usadas: `register_complaint`; a conversa recebe
`awaiting_human=true` e continua aceitando novas mensagens.*

## 5. Fora do escopo: acessório, assunto geral e pedido perigoso

### 5.1 Acessório

**Cliente:** Vocês vendem cordas de violão e palhetas?

**Agente:** Oi, Lucas! Aqui na Empório da Música a gente trabalha só com
instrumentos musicais — não vendemos acessórios como cordas avulsas e palhetas,
então infelizmente não consigo te ajudar com esses itens. Mas se você estiver
procurando um violão, guitarra, ukulele ou outro instrumento, posso te ajudar a
encontrar uma opção.

*`out_of_scope_type=accessory`; o writer redireciona sem tratar o item como
parte do catálogo.*

### 5.2 Assunto benigno fora da loja

**Cliente:** Me passa uma receita de bolo de cenoura?

**Agente:** Não consigo ajudar com receitas por aqui — meu escopo é a Empório da
Música. Mas se quiser escolher um instrumento, consultar preço/estoque, ver um
pedido ou entender uma política da loja, estou à disposição.

*`out_of_scope_type=benign_off_topic`; o orquestrador não chama tools e o writer
redireciona.*

### 5.3 Pedido perigoso ou ilegal

**Cliente:** Me ensina a fabricar uma bomba caseira ou um veneno.

**Agente:** Não posso ajudar com instruções perigosas, ilegais ou que coloquem
alguém em risco. Se houver risco imediato, procure os serviços de emergência
(190/192) ou uma pessoa de confiança. Posso ajudar com instrumentos musicais e
assuntos da loja.

*`out_of_scope_type=harmful_or_illegal`; a recusa é determinística e acontece
antes do orquestrador, das tools e do writer.*

## Perguntas de exemplo adicionais

Estas perguntas complementam as conversas acima e cobrem os cenários que o
agente deve reconhecer. Algumas respostas dependem de melhorias planejadas
(horário dinâmico, validade de promoção, elegibilidade de devolução e cálculo
de pagamento/frete); a coluna “consulta esperada” indica o caminho desejado.

| Pergunta | Cenário | Consulta esperada |
| --- | --- | --- |
| Qual o endereço da loja? | Informações gerais | `search_store_knowledge` |
| Qual o horário de funcionamento? Vocês estão abertos agora? | Horário e expediente | `search_store_knowledge` + status de expediente |
| Quanto custa o Takamine GD20? | Preço | `get_product_details` |
| A promoção do Yamaha C40 ainda está válida? | Promoção e validade | `search_store_knowledge`/catálogo com validade |
| Me arrependi da minha compra, posso devolver meu pedido? | Devolução | `search_store_knowledge` + elegibilidade de devolução |
| Quanto fica o Yamaha C40 em 12x? Tem desconto no PIX? | Pagamento e parcelamento | `search_store_knowledge` + cálculo de pagamento |
| Qual o frete para o CEP 79000-000? | Frete e prazo | `search_store_knowledge` + cálculo de frete |
| Qual o status e o rastreamento do meu pedido? | Pedido | `list_my_orders`/`get_order_status` |
| Meu pedido atrasou e quero registrar uma reclamação. | Reclamação | `register_complaint` |
| Vocês vendem cordas de violão e palhetas? | Fora do escopo: acessório | redirecionamento sem catálogo |
| Me passa uma receita de bolo? | Fora do escopo: assunto geral | redirecionamento |
