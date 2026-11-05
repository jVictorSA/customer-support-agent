# Políticas de demonstração

O pipeline de ingestão aceita PDF. Para reproduzir os exemplos:

1. Use o PDF fornecido no desafio (`políticas_da_loja.pdf`) ou gere um PDF a
   partir de `docs/dev-docs/politicas_loja.md`.
2. Faça o upload:

   ```bash
   curl -X POST http://127.0.0.1:8000/documents \
     -F "file=@samples/policies/politicas_da_loja.pdf" \
     -F "name=Políticas da loja"
   ```

3. Aguarde o processamento em `GET /documents` e confirme os chunks em
   `GET /documents/{public_id}/chunks`.

O arquivo PDF não é versionado neste repositório para evitar binários e
duplicação do material original do desafio.
