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

Uso recomendado:

- barra global de operacao;
- automacoes de suporte;
- paineis de NOC;
- alertas de stale, gate e backlog.

## Interpretacao de `next_action`

| Valor | Significado |
| --- | --- |
| `wait` | run em andamento ou aguardando continuidade normal |
| `recover` | run stale ou falha recuperavel |
| `inspect_error` | erro impeditivo sem recover direto |
| `inspect_quarantine` | a fila de quarentena deve ser o proximo passo |
| `none` | sem acao sugerida |

## Recover e stale

O sistema executa recovery sweep sobre fases stale.

Efeitos esperados:

- uma run stale pode continuar em `state=stale` e `next_action=recover`;
- uma run pode sair de stale para `state=failed`, mas manter `last_error.retryable=true` e `next_action=recover`;
- cancelamentos pendentes em runs stale podem ser estabilizados como `cancelled`.
