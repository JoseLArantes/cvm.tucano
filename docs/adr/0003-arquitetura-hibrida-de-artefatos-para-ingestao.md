# ADR 0003: Arquitetura híbrida de artefatos para ingestão

## Status

Aceito

## Contexto

O pipeline atual de ingestão já usa `COPY` no stage PostgreSQL e já possui partes da promoção em lote. Mesmo assim, continua caro demais em CPU, memória e I/O porque o PostgreSQL ainda acumula quatro papéis ao mesmo tempo:

- base canônica de domínio;
- armazenamento principal de artefatos brutos de replay;
- staging detalhado por linha do caminho feliz;
- trilha operacional detalhada de validação e promoção por linha.

As evidências observadas até aqui incluem:

- `SIGKILL`/OOM em workers de ingestão durante members volumosos;
- execuções de member órfãs presas em `stage`;
- `ingestion_rows` com centenas de milhares de linhas `pending` após morte de worker;
- custo alto de escrita/releitura de JSON em PostgreSQL.

O ADR 0001 partia da hipótese de que a otimização deveria permanecer toda dentro da arquitetura relacional atual. Esse diagnóstico já não é suficiente diante das falhas operacionais observadas.

## Decisão

Adotar arquitetura híbrida para ingestão:

- PostgreSQL continua como base canônica de domínio e metadados operacionais.
- Artefatos brutos e artefatos normalizados deixam de usar PostgreSQL como storage principal do caminho feliz.
- O stage do caminho feliz passa a usar tabelas tipadas carregadas via `COPY`.
- `ingestion_rows` deixa de ser o staging detalhado obrigatório para linhas bem-sucedidas.
- Replay de member/run deve partir do artifact store; replay de linha deve partir do payload da exceção.
- O estado operacional da ingestão deve ser faseado, durável e exposto por API, incluindo liveness, cancelamento, recovery e erro estruturado.

## Consequências

Positivas:

- reduz pressão de memória e WAL em members volumosos;
- reduz releitura ORM de staging JSON;
- separa melhor fase de artifact handling da fase de promoção canônica;
- facilita recovery de fase e reprocessamento por checkpoints;
- preserva PostgreSQL onde ele agrega mais valor: integridade, domínio, lineage e APIs.
- melhora a capacidade de frontends, CLIs e automações acompanharem ingestão sem depender de logs de worker.

Negativas:

- introduz uma nova superfície operacional: artifact store local/S3-compatível;
- exige novo modelo de fases e recovery de orfandade;
- exige migração arquitetural por source e por fluxo de replay.
- aumenta a responsabilidade dos contratos de API de operação, que passam a precisar de compatibilidade e documentação cuidadosa.

## Não decisão

Este ADR não adota:

- NoSQL como base canônica de domínio;
- substituição integral de PostgreSQL por DuckDB;
- dependência imediata de object storage remoto na primeira entrega.

## Relação com ADRs anteriores

Este ADR substitui parcialmente o ADR 0001. O ponto preservado é:

- PostgreSQL continua canônico para domínio.

O ponto revisto é:

- PostgreSQL deixa de ser também o storage principal de artefato bruto e staging detalhado do caminho feliz.
