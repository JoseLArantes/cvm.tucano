---
title: Monitoramento de Sincronizacoes
sidebar_position: 3
---

# Monitoramento de Sincronizacoes

## Leitura recomendada

Para cada tipo de tela:

| Tela | Endpoint principal |
| --- | --- |
| lista operacional de runs | `GET /ingestion/runs` |
| detalhe de run | `GET /ingestion/runs/{run_id}` |
| timeline de fases | `GET /ingestion/runs/{run_id}/phases` |
| inventario de members | `GET /ingestion/runs/{run_id}/members` |
| auditoria do disparo | `GET /ingestion/sincronizacoes` |
| detalhe da execucao administrativa | `GET /ingestion/sincronizacoes/{id_execucao}` |
| snapshot global do cluster | `GET /ingestion/operations` |
| limpeza transitoria de run cancelada/falha | `POST /ingestion/runs/{run_id}/cleanup-transient-state` |

## `GET /ingestion/runs`

Visao principal do pipeline.

Cada run traz:

- identidade do escopo (`id`, `tipo_fonte`, `ano`);
- estado persistido (`status`, `phase`);
- estado agregado (`state`);
- progresso (`progress`);
- snapshots estruturais (`remote_probe`, `change_summary`, `artifact_snapshot`, `member_snapshot_summary`, `delivery_snapshot_summary`, `reconcile_summary`, `lifecycle_decision`);
- sinais operacionais (`liveness`, `blocking`, `cancellation`, `last_error`, `next_action`);
- links relativos (`links`).

Campos mais importantes para UI:

| Campo | Uso |
| --- | --- |
| `state` | badge operacional |
| `progress` | contadores rápidos |
| `quality_summary` | cards de linhas, members, quarentena e staging |
| `liveness` | detectar stale |
| `blocking` | explicar espera |
| `cancellation` | exibir pedido de cancelamento |
| `last_error` | exibir erro mais recente |
| `next_action` | habilitar ação de operador |

Exemplo:

```bash
curl -X GET "http://localhost:8007/ingestion/runs?pagina=1&tamanho_pagina=50" \
  -H "Authorization: Bearer <token-admin>"
```

## `GET /ingestion/runs/{run_id}`

Drill-down completo da run.

Use quando a UI precisar:

- explicar a decisao de download ou `sem_alteracao`;
- mostrar contadores detalhados;
- mostrar reuso de members;
- abrir troubleshooting de erro;
- decidir entre replay, recover, cancelamento ou investigacao de quarentena.

Leitura recomendada do rerun anual:

- `quality_summary.members_reprocessed`
- `quality_summary.members_reused_from_previous`
- `quality_summary.members_reused_from_failed_parent`
- `artifact_snapshot.storage_uri`
- `artifact_snapshot.storage_role`
- `member_snapshot_summary.by_status`
- `member_snapshot_summary.members[].raw_artifact_uri`
- `member_snapshot_summary.members[].normalized_artifact_uri`
- `lifecycle_decision`

## `GET /ingestion/runs/{run_id}/phases`

Timeline persistida das fases da run.

Cada item inclui:

- `phase`
- `status`
- `attempt`
- `task_id`
- `lease_owner`
- `started_at`
- `heartbeat_at`
- `finished_at`
- `cancel_requested_at`
- `cancelled_at`
- `error_type`
- `error_message`
- `error_retryable`
- `input_artifact_uri`
- `output_artifact_uri`
- `metrics`

Use este endpoint para:

- diagnosticar stale;
- diferenciar falha recuperavel e falha final;
- entender retentativas;
- auditar artifacts de entrada e saida por fase.

Fases esperadas para members financeiros DFP/ITR:

| Fase | Sinal principal |
| --- | --- |
| `profile` | CSV identificado e schema validado |
| `normalize_artifact` | linhas lidas e normalizadas para artifact |
| `load_typed_staging` | artifact carregado no staging tipado |
| `promote` | linhas promovidas para tabelas canonicas |
| `reconcile` | registros obsoletos removidos no escopo do member |
| `complete` | execucao estabilizada |

Metricas comuns em `metrics` ou `quality_summary`:

- `rows_read`
- `rows_normalized`
- `rows_loaded_to_stage`
- `rows_reconciled_deleted`
- `typed_stage_rows_loaded`
- `typed_stage_bytes_loaded`
- `typed_stage_rows_replaced`
- `typed_stage_rows_purged`
- `typed_stage_copy_loads`

Para DFP/ITR, linhas validas nao aparecem em `ingestion_rows`; a leitura operacional deve usar fases, counters e snapshots de artifacts.

## `GET /ingestion/runs/{run_id}/members`

Inventario paginado dos CSVs de uma run.

Cada member inclui:

- identificacao (`id`, `ingestion_file_id`, `member_name`);
- metadados do payload (`member_sha256`, `member_size_bytes`, `row_count`, `encoding`, `delimiter`, `header`);
- status de schema (`schema_status`, `schema_message`);
- metadados do snapshot (`row_kind`, `destino_promovido`, `required_member`, `lifecycle_status`);
- contadores por member (`quarantine_total`, `delivery_total`);
- estado sintetico (`state`);
- links de operacao (`links`).

Estados sinteticos hoje:

- `processed`
- `member_skipped`
- `schema_invalid`
- `unknown`

## `GET /ingestion/sincronizacoes`

Lista paginada das execucoes administrativas.

Use quando precisar:

- auditar o disparo original;
- navegar pela arvore pai/filho;
- localizar execucao administrativa correlata de uma run;
- acompanhar o preprocessamento manual.

Campos operacionais relevantes:

- `tipo_execucao`
- `id_execucao_pai`
- `filhos_total`
- `filhos_concluidos`
- `filhos_falha`
- `filhos_em_andamento`
- `state`
- `liveness`
- `blocking`
- `cancellation`
- `last_error`
- `next_action`

## `GET /ingestion/sincronizacoes/{id_execucao}`

Detalhe da execucao administrativa, inclusive:

- URL e hash do artefato;
- analise de arquivos (`analise_arquivos`);
- counters agregados;
- execucoes filhas quando aplicavel;
- sinais operacionais agregados.

## `GET /ingestion/operations`

Snapshot consolidado do cluster para consumidores desacoplados.

O retorno agrega:

- `run_counts`
- `execution_counts`
- `cancellation_counts`
- `task_counts`
- `materialization_gate`
- `active_runs`
- `recoverable_runs`

## Filas e independencia operacional

Ingestao e materializacao usam filas separadas:

| Fila | Responsabilidade |
| --- | --- |
| `ingestion` | processamento pesado de members |
| `ingestion_control` | coordenacao, finalizacao e recovery de ingestao |
| `analise_materializacao` | chunks e campanhas de materializacao |

O gate de materializacao bloqueia a execucao de novos chunks de materializacao quando ha ingestao ativa ou pausa manual. Ele nao bloqueia workers de ingestao.

## Limpeza transitoria

`POST /ingestion/runs/{run_id}/cleanup-transient-state` prepara uma run `cancelada` ou `falha` para reconstrução operacional.

O endpoint:

- remove staging generico (`ingestion_rows`) e eventos/quarentena associados a linhas da run;
- remove staging tipado financeiro;
- fecha fases ainda abertas como `cancelled`;
- marca execucoes relacionadas nao finais como `cancelada`;
- retorna contadores do que foi removido ou fechado.

Ele nao remove dados canonicos promovidos.

Uso recomendado:

- barra global de operacao;
- automacoes de suporte;
- paineis de NOC;
- alertas de stale, gate e backlog.

## Contratos de controle de ingestao

### Stream de eventos SSE

`GET /ingestion/events/stream` entrega eventos `text/event-stream` autenticados com
o mesmo bearer usado pela superfície de ingestão. O endpoint aceita
`Last-Event-ID`, `cursor` ou `since_revision` (apenas um por conexão) e
`scope=fonte:ano` para limitar um escopo operacional real.

Os tipos estáveis são `ingestion.operations.updated`, `ingestion.run.updated`,
`ingestion.work_item.updated`, `ingestion.member.updated`,
`ingestion.queue.updated`, `ingestion.materialization.updated` e `heartbeat`.
Cada payload inclui `event_id`, `revision`, `occurred_at`, `entity_type`,
`entity_id`, `reason_code` e `data`. O SSE é uma notificação compacta de
invalidação; detalhes autoritativos permanecem nos endpoints REST.

Se o pool de banco estiver temporariamente saturado, a conexão não é encerrada:
o stream envia `heartbeat` com `reason_code=DATABASE_POOL_EXHAUSTED` e
`data.retry_after_seconds`, depois tenta novamente. Clientes devem manter a
conexão e usar o polling REST apenas como contingência.

Nas chamadas REST, saturação residual do pool retorna `503` com
`detail.reason_code=DATABASE_POOL_EXHAUSTED`, `detail.retryable=true` e
`Retry-After: 1`. A autenticação não mantém uma conexão reservada durante a
vida do SSE nem durante operações externas como a inspeção Celery.

`GET /ingestion/work-items` entrega uma linha por escopo fonte/ano, correlacionando atualização, execução administrativa, run técnica, resultado, próxima transição e `allowed_actions`. A lista aceita filtros por estado, ação, fonte, ano, origem, datas, quarentena e drift, além de paginação e ordenação no servidor. Use `GET /ingestion/work-items/{id}` para detalhe e `GET /ingestion/work-items/{id}/events` para a timeline cursorizada.

`GET /ingestion/scopes` consolida cobertura por fonte e ano sem N+1: baseline, última run, members esperados, atualização pendente, trabalho ativo, quarentena, estado de cobertura e próxima ação. `GET /ingestion/runs/{run_id}/completion-evidence` separa members processados e reutilizados, escrita canônica, reconcile, quarentena, drift e contadores de promoção. `GET /ingestion/quarentena/grupos` agrega a fila por motivo, fonte, ano, arquivo, row kind ou reparabilidade.

`POST /ingestion/dispatch/plan` valida escopos e devolve `plan_token` de validade curta, conflitos, possibilidade de reuso por SHA-256 e impacto no gate de materialização. `POST /ingestion/dispatch` confirma o mesmo conjunto com `plan_token` e o header obrigatório `Idempotency-Key`. A resposta é persistida por ator/operação/chave durante 24h; chave repetida com payload diferente retorna `409`. `force_reimport=true` exige `reason` e gera auditoria persistida.

`GET /ingestion/operations` também informa `revision`, `poll_after_ms`, `action_counts`, `waiting_for_operator_count`, progresso agregado, totais reais, truncamento de preview e `queue_health[]`. Cada fila inclui workers observados, slots ocupados, tasks ativas/reservadas/agendadas, backlog e estado `ready`, `paused` ou `without_worker`.

## Interpretacao de `next_action`

| Valor | Significado |
| --- | --- |
| `wait` | run em andamento ou aguardando continuidade normal |
| `start_ingestion` | pre-processamento concluido; use a execucao correlata para iniciar a fase 2 |
| `recover` | run stale, falha recuperavel ou member aguardando retomada apos falha do ZIP pai, desde que possua fonte executavel |
| `inspect_error` | erro impeditivo sem recover direto |
| `inspect_quarantine` | a fila de quarentena deve ser o proximo passo |
| `none` | sem acao sugerida |

## Recover e stale

O sistema executa recovery sweep sobre fases stale.

Efeitos esperados:

- uma run stale so usa `next_action=recover` quando `recovery.eligible=true`;
- uma run pode sair de stale para `state=failed` e manter `last_error.retryable=true` apenas quando houver staging reaplicavel ou execucao de member correlata;
- sem uma estrategia executavel, `recovery` retorna `{ "eligible": false, "strategy": null, "reason_code": "NO_RECOVERY_SOURCE" }`, `next_action=inspect_error` e a run nao entra em `recoverable_runs`;
- `recovery.eligible` representa autorizacao no estado atual, nao apenas existencia historica de uma fonte: runs concluidas usam `RUN_ALREADY_COMPLETED` e falhas nao retentaveis usam `NON_RETRYABLE_FAILURE`;
- processamento de member que nao le nenhuma linha termina como `falha` com mensagem `NO_ROWS_PROCESSED`, em vez de sucesso vazio;
- runs terminais nao bloqueiam novo dispatch do mesmo escopo, e o work item oferece `start_ingestion` com `TERMINAL_RUN_REDISPATCH_ALLOWED`, sem exigir limpeza de filas ou staging para liberar a nova execucao;
- cancelamentos pendentes em runs stale podem ser estabilizados como `cancelled`.

`POST /ingestion/runs/{run_id}/recover` retorna `409` com o mesmo objeto `recovery` e `reason_code=NO_RECOVERY_SOURCE` quando nao existir fonte executavel. O comando nao devolve sucesso com uma lista vazia nesse caso.

Quando a estrategia for `rerun_member_execution`, o comando agenda uma task na fila de ingestao e responde `status=agendada`; ele nao executa o processamento pesado dentro da requisicao HTTP.
