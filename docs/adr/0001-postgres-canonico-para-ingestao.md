# ADR 0001: PostgreSQL canônico para ingestão

## Status

Parcialmente superado pelo ADR 0003

## Contexto

O pipeline de ingestão do Tucano CVM processa milhões de linhas com requisitos fortes de:

- idempotência por chave natural;
- rastreabilidade por arquivo, ano, linha e hash;
- quarentena e replay de exceções reais;
- reconciliação de linhas promovidas que deixaram de existir na entrega atual;
- observabilidade operacional por execução, member, run e quality summary.

O custo operacional da ingestão é alto para a camada relacional, principalmente em staging, promoção e reconcile. Isso motivou a avaliação de alternativas como NoSQL ou um armazenamento separado para acelerar escrita.

## Decisão

PostgreSQL continua sendo a base canônica da ingestão e das tabelas de domínio.

As otimizações prioritárias devem acontecer dentro da arquitetura atual:

- `COPY` e batching para staging;
- índices compostos alinhados às queries reais;
- promoção cada vez mais set-based;
- retenção apenas do staging necessário para processamento ativo, quarentena e replay;
- benchmark e observabilidade SQL antes de qualquer mudança estrutural maior.

NoSQL não será introduzido como write model canônico nesta etapa.

## Nota histórica

O ADR 0003 mantém PostgreSQL como base canônica de domínio, mas revê a parte desta decisão que tratava PostgreSQL como storage principal do caminho feliz para artefatos brutos e staging detalhado.

## Consequências

Positivas:

- preserva constraints, integridade relacional e contratos atuais;
- evita duplicar lógica crítica de reconciliação e lineage fora do banco;
- mantém o modelo operacional e a API consistentes;
- permite melhorias incrementais com risco menor para a ingestão crítica.

Negativas:

- a ingestão continua sensível a tuning de índices, WAL e padrões de escrita;
- parte da performance máxima depende de SQL específico de PostgreSQL, com fallback portátil para testes SQLite.

## Reavaliação futura

Esta decisão pode ser reaberta se métricas mostrarem que, mesmo após:

- promoção set-based nos fluxos mais volumosos;
- ajustes de índices e chunking;
- benchmark ponta a ponta por member e por fonte;
- observabilidade via consultas e estatísticas do PostgreSQL,

o custo operacional ainda exigir separação entre write model canônico e read model analítico.

Se isso acontecer, a próxima hipótese a avaliar é um read model analítico derivado, não a substituição imediata da base canônica transacional.
