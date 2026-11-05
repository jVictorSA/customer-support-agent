# Tamanho da imagem do ingestion worker

Documento de diagnóstico e plano futuro. Nenhuma alteração de imagem, dependência
ou Compose foi feita nesta fase.

## Medição atual

A imagem de desenvolvimento do worker (`worker-dev`) ocupa aproximadamente
**11,1 GB** neste ambiente. O `worker-runtime` de produção não foi medido
isoladamente, mas usa o mesmo ambiente Python e tende a apresentar o mesmo
problema.

| Item | Tamanho aproximado |
| --- | ---: |
| `.venv` | 6,5 GB |
| `nvidia/*` (bibliotecas CUDA) | 3,0 GB |
| `triton` | 1,0 GB |
| pacotes apt (Tesseract, `libgl`, `libglib`) | 311 MB |
| `torch` | 1,2 GB |

## Causa principal

O `torch` está sendo resolvido do PyPI comum, com dependências CUDA, apesar do
índice `pytorch-cpu` declarado no `pyproject.toml`.

O `[tool.uv.sources]` vale para dependências diretas. Como o `torch` entra
transitivamente pelo `docling`/`docling-ibm-models`, o lock atual aponta para
`registry = "https://pypi.org/simple"` e a imagem baixa `nvidia-*` e `triton`
mesmo executando em CPU.

## Plano de redução

### 1. Forçar o backend CPU

- Usar `UV_TORCH_BACKEND=cpu` no build e regenerar o lock com
  `uv lock --torch-backend cpu`.
- Se o backend não for aplicado ao `torch` transitivo, declarar `torch` e
  `torchvision` como dependências diretas do grupo `worker`, mantendo o índice
  `pytorch-cpu`.
- Validar que o `uv.lock` final não contém `nvidia-*` nem `triton`.
- Validar no container:

  ```bash
  python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
  pip list | grep -E "nvidia|triton"
  ```

Ganho esperado: aproximadamente 4 GB.

### 2. Tornar o OCR opcional na imagem

O OCR já é desligado por padrão (`DOCUMENTS_OCR_ENABLED=false`), mas a imagem
sempre instala Tesseract e os pacotes de OCR do Docling.

- Colocar `tesseract-ocr`, `tesseract-ocr-por` e `tesseract-ocr-eng` atrás de um
  build arg (`INSTALL_OCR=false` por padrão).
- Criar uma variante/target com OCR para quem habilitar o recurso.
- Avaliar a remoção de `rapidocr`, `onnxruntime`, `opencv` e
  `opencv-python-headless` somente depois de testar o parsing com Docling sem
  OCR.

Ganho esperado: 300–500 MB, dependendo do que for seguro remover.

### 3. Externalizar os modelos do Docling

O target de runtime copia `/models` para dentro da imagem.

- Criar um volume nomeado `docling_models`.
- Criar um serviço de inicialização que execute
  `docling-tools models download -o /models` uma única vez.
- Montar o volume no worker como somente leitura.
- Para ambientes offline, documentar que o volume precisa ser pré-populado ou
  manter um target específico com os modelos embutidos.

Ganho esperado: remove os modelos do tamanho da imagem; o consumo total de disco
permanece, mas o pull da imagem fica menor.

### 4. Limpeza de build

- Não copiar cache do `uv`, `/root/.cache`, fontes de build ou artefatos de teste
  para o estágio final.
- Manter `--no-install-recommends` e a remoção de `/var/lib/apt/lists/*`.
- Adicionar `samples/`, `tests/`, `docs/`, `data/`, `.agents/` e `graphify-out/`
  ao `.dockerignore` quando não forem necessários na imagem.
- Avaliar `UV_COMPILE_BYTECODE=0` apenas se o tamanho for crítico; hoje ele
  acelera o startup.

### 5. Opção “worker-lite”

O `DoclingPdfParser` já tem fallback para PyMuPDF quando o Docling falha. Um
target sem Docling/torch, usando apenas PyMuPDF, pode ficar abaixo de 1 GB.

- Vantagem: imagem muito menor.
- Desvantagem: perde estrutura de tabelas, layout e o parser hierárquico do
  Docling.
- Para as políticas da loja, que são majoritariamente texto, pode ser
  suficiente.

## Validação futura

Antes e depois da otimização, medir com:

```bash
docker build --target worker-runtime -t csa-worker:before .
docker image inspect csa-worker:before --format '{{.Size}}'
docker history --no-trunc csa-worker:before
docker run --rm --entrypoint sh csa-worker:before -c \
  'du -sh /app/.venv /models /app/.tiktoken'
```

Depois, validar a ingestão completa com Docker Compose, MinIO, RabbitMQ e uma
chamada real a `POST /documents`.
