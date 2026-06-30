---
title: Administracao da Ingestao - Visao Geral
sidebar_position: 1
---

# Administracao da Ingestao - Visao Geral

## Escopo

A superficie `/ingestion/*` concentra as operacoes administrativas e o monitoramento operacional do pipeline de ingestao.

Esta documentacao cobre o comportamento atual do sistema:

- disparo de sincronizacoes anuais e de cadastro;
- preprocessamento manual em duas etapas;
- monitoramento de execucoes administrativas e runs tecnicas;
- cancelamento de run inteira ou de member individual;
- replay de run, replay de quarentena e recover administrativo;
- inventario de members, fases, quarentena e snapshot consolidado de operacao.

Todos os endpoints desta area exigem token administrativo.

## Modelo operacional

O pipeline trabalha com dois niveis de observabilidade:

1. `ExecucaoSincronizacao`
   - representa o escopo administrativo disparado pela API ou pelo scheduler;
   - e a melhor fonte para auditoria do pedido original, tipo de execucao e agregacao pai/filho.

2. `IngestionRun`
   - representa a execucao tecnica do pipeline;
   - e a melhor fonte para progresso, fase, liveness, erros, reconcile, inventario de members e snapshots operacionais.

Regra pratica:

- para listagens de operador, prefira `GET /ingestion/runs`;
- para auditoria de disparo e arvore pai/filho, prefira `GET /ingestion/sincronizacoes`;
- para drill-down de uma run, combine `GET /ingestion/runs/{run_id}`, `/phases` e `/members`;
- para visao consolidada do cluster, use `GET /ingestion/operations`.

## Fases da run

As runs expõem `phase` com o seguinte significado:

| Fase | Significado |
| --- | --- |
| `acquire` | probe remoto, decisão de download e captura do artefato |
| `stage` | extração de members, análise de header/schema, snapshots e carga operacional intermediária |
| `promote` | normalização, resolução de companhia, deduplicação e escrita nas tabelas canônicas |
| `reconcile` | remoção de linhas promovidas que ficaram obsoletas para o escopo reprocessado |
| `complete` | encerramento final da run |

## Estados operacionais agregados

Runs e execuções administrativas expõem `state` para consumo direto por UI e automações:

| `state` | Uso |
| --- | --- |
| `queued` | aguardando worker ou continuidade de fase |
| `waiting` | aguardando ingestão manual da fase 2 ou outra continuidade normal |
| `running` | trabalho ativo em andamento |
| `stale` | heartbeat expirado para uma fase que deveria estar ativa |
| `succeeded` | encerrada com sucesso |
| `skipped` | encerrada sem processamento adicional |
| `failed` | encerrada com erro |
| `cancelled` | encerrada por cancelamento |

Campos complementares:

- `liveness`: heartbeat, task atual, lease owner e `is_stale`;
- `blocking`: motivo compacto de espera;
- `cancellation`: último pedido de cancelamento persistido;
- `last_error`: erro operacional mais recente;
- `next_action`: ação recomendada para consumidor desacoplado.

## Endpoints principais

### Disparo

| Metodo | Rota | Uso |
| --- | --- | --- |
| `POST` | `/ingestion/sincronizacoes/cadastro` | sincronizar cadastro |
| `POST` | `/ingestion/sincronizacoes/{fonte}/{ano}` | sincronizar fonte anual |
| `POST` | `/ingestion/sincronizacoes/tudo/{ano}` | sincronizar cadastro + todas as fontes anuais |
| `POST` | `/ingestion/sincronizacoes/reprocessar-arquivo` | reprocessar ZIP ou member especifico |

### Duas etapas

| Metodo | Rota | Uso |
| --- | --- | --- |
| `POST` | `/ingestion/sincronizacoes/pre-processar/cadastro` | executar apenas preprocessamento do cadastro |
| `POST` | `/ingestion/sincronizacoes/pre-processar/{tipo_fonte}/{ano}` | executar apenas preprocessamento da fonte anual |
| `POST` | `/ingestion/sincronizacoes/{id_execucao}/ingerir` | iniciar a fase 2 de uma execucao em `aguardando_ingestao` |

### Monitoramento

| Metodo | Rota | Uso |
| --- | --- | --- |
| `GET` | `/ingestion/sincronizacoes` | auditoria administrativa e arvore pai/filho |
| `GET` | `/ingestion/sincronizacoes/{id_execucao}` | detalhe de execucao administrativa |
| `GET` | `/ingestion/runs` | monitoramento principal das runs |
| `GET` | `/ingestion/runs/{run_id}` | detalhe completo da run |
| `GET` | `/ingestion/runs/{run_id}/phases` | timeline persistida de fases |
| `GET` | `/ingestion/runs/{run_id}/members` | inventario paginado de members |
| `GET` | `/ingestion/operations` | snapshot consolidado do cluster |

### Cancelamento e recuperacao

| Metodo | Rota | Uso |
| --- | --- | --- |
| `POST` | `/ingestion/sincronizacoes/cancelar` | cancelamento administrativo por seletor |
| `POST` | `/ingestion/runs/{run_id}/cancel` | cancelar a run inteira |
| `POST` | `/ingestion/runs/{run_id}/members/{member_id}/cancel` | cancelar somente um member |
| `POST` | `/ingestion/runs/{run_id}/recover` | recuperar run stale ou com erro recuperavel |
| `POST` | `/ingestion/runs/{run_id}/replay` | replay completo da run |

### Quarentena

| Metodo | Rota | Uso |
| --- | --- | --- |
| `GET` | `/ingestion/quarentena` | listar fila de reparo |
| `GET` | `/ingestion/quarentena/resumo` | métricas agregadas |
| `POST` | `/ingestion/replay/quarentena` | replay de itens pendentes |

## Rerun anual

Para fontes anuais, o rerun compara o ZIP corrente e o inventario de members da mesma fonte/ano.

Cada member pode seguir um de dois caminhos:

- `reprocessado`: entra novamente em `stage -> promote -> reconcile`;
- `reaproveitado`: permanece fora do hot path quando o `member_sha256` permite reutilizacao segura.

Os campos centrais para explicar essa decisao sao:

- `quality_summary.members_reprocessed`
- `quality_summary.members_reused_from_previous`
- `quality_summary.members_reused_from_failed_parent`
- `member_snapshot_summary.by_status`
- `lifecycle_decision`

## Staging tipado e artifact normalizado

O pipeline usa artifact normalizado por member e staging tipado para parte do processamento volumoso.

Formato atual do artifact normalizado:

- default: `typed_csv`
- opcional: `parquet`

Decisao atual do projeto:

- manter `typed_csv` como default;
- usar `parquet` apenas em benchmarks e medições específicas por fonte/member.

Benchmark oficial no ambiente Docker:

```bash
docker compose run --rm cvm_api sh -lc "pip install --no-cache-dir -e '.[parquet]' && python -m tests.scripts.benchmark_normalized_artifacts --rows 100000 --output json"
```

Resultado registrado em `2026-06-30` no container `cvm_api`:

- `typed_csv`: escrita `5.56s`, leitura `1.87s`, pico `26.90 MB`, tamanho `26.76 MB`
- `parquet`: escrita `5.09s`, leitura `6.36s`, pico `219.16 MB`, tamanho `3.93 MB`

Decisao operacional atual: `typed_csv` continua sendo o formato default.

## Proximos guias

- [Disparo de Sincronizações](./dispatch.md)
- [Monitoramento](./monitoring.md)
- [Quarentena e Replay](./quarantine.md)
- [Identidade e Auditoria](./identity.md)
