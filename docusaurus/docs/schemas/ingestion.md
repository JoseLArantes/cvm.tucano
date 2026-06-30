---
title: Schemas de Ingestion
sidebar_position: 6
---

# Schemas de Ingestion

Esta pagina resume os principais contratos da superficie administrativa de ingestao.

Para definicoes exatas, a fonte de verdade continua sendo o OpenAPI gerado pela aplicacao.

## `IngestionRunResumo`

Representa a run tecnica do pipeline.

Campos principais:

| Campo | Tipo | Uso |
| --- | --- | --- |
| `id` | `string` | identificador da run |
| `execucao_sincronizacao_id` | `string \| null` | execucao administrativa correlata |
| `tipo_fonte` | `string` | fonte processada |
| `ano` | `integer \| null` | ano da run |
| `status` | `string` | estado persistido |
| `phase` | `string` | fase persistida |
| `state` | `string \| null` | estado agregado para UI |
| `progress` | `object \| null` | contadores resumidos |
| `liveness` | `object \| null` | heartbeat, task e stale |
| `blocking` | `object \| null` | motivo de espera |
| `cancellation` | `object \| null` | ultimo cancelamento |
| `last_error` | `object \| null` | erro mais recente |
| `next_action` | `string \| null` | acao recomendada |
| `remote_probe` | `object \| null` | decisao de preflight remoto |
| `change_summary` | `object \| null` | mudanca estrutural detectada |
| `quality_summary` | `object \| null` | resumo principal de progresso |
| `artifact_snapshot` | `object \| null` | snapshot do artefato avaliado |
| `member_snapshot_summary` | `object \| null` | inventario de members |
| `delivery_snapshot_summary` | `object \| null` | indice documental agregado |
| `reconcile_summary` | `object \| null` | remocoes do reconcile |
| `rows_reconciled_deleted` | `integer \| null` | atalho numerico do reconcile |
| `lifecycle_decision` | `object \| null` | explicacao compacta da decisao de lifecycle |
| `links` | `object \| null` | rotas relacionadas |

### Status persistido da run

- `em_execucao`
- `sucesso`
- `sucesso_com_alerta`
- `falha`
- `sem_alteracao`
- `skipped`
- `cancelada`

### Fase persistida da run

- `acquire`
- `stage`
- `promote`
- `reconcile`
- `complete`

## `ExecucaoSincronizacaoResumo` e `ExecucaoSincronizacaoDetalhe`

Representam o escopo administrativo disparado pela API ou pelo scheduler.

Campos adicionais importantes:

- `tipo_execucao`
- `id_execucao_pai`
- `arquivo_principal`
- `filhos_total`
- `filhos_concluidos`
- `filhos_falha`
- `filhos_em_andamento`
- `execucoes_filhas` no detalhe

Status persistidos mais relevantes:

- `agendada`
- `em_execucao`
- `aguardando_ingestao`
- `sucesso`
- `sucesso_com_alerta`
- `sem_alteracao`
- `falha`
- `falha_qualidade`
- `cancelada`

## `IngestionOperationalLiveness`

Objeto reutilizado em runs e execucoes.

Campos:

- `heartbeat_at`
- `lease_owner`
- `task_id`
- `phase_status`
- `is_stale`
- `stale_after_seconds`
- `heartbeat_age_seconds`

## `IngestionOperationalBlocking`

Campos:

- `reason_code`
- `detail`

Motivos esperados:

- `none`
- `queued`
- `awaiting_ingestion`
- `stale`
- `manual_cancel`

## `IngestionOperationalCancellation`

Campos:

- `status`
- `requested_by`
- `reason`
- `terminate_immediately`
- `requested_at`
- `propagated_at`
- `completed_at`
- `affected_task_ids`

Status esperados:

- `none`
- `requested`
- `propagated`
- `completed`

## `IngestionOperationalError`

Campos:

- `error_type`
- `error_message`
- `retryable`
- `phase`

## `IngestionRunPhaseExecutionResumo`

Representa uma tentativa persistida de fase da run.

Campos:

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
- `cancel_reason`
- `error_type`
- `error_message`
- `error_retryable`
- `input_artifact_uri`
- `output_artifact_uri`
- `metrics`

## `IngestionRunMemberResumo`

Representa o inventario operacional de um member.

Campos:

- `member_name`
- `member_sha256`
- `member_size_bytes`
- `row_count`
- `encoding`
- `delimiter`
- `header`
- `schema_status`
- `schema_message`
- `row_kind`
- `destino_promovido`
- `required_member`
- `lifecycle_status`
- `quarantine_total`
- `delivery_total`
- `state`
- `links`

Estados sinteticos atuais:

- `processed`
- `member_skipped`
- `schema_invalid`
- `unknown`

## `IngestionOperationsResumo`

Snapshot consolidado para consumidores desacoplados.

Campos:

- `generated_at`
- `run_counts`
- `execution_counts`
- `cancellation_counts`
- `task_counts`
- `materialization_gate`
- `active_runs`
- `recoverable_runs`

## `QuarantineItemResposta`

Contrato da fila de reparo.

Campos:

- `id`
- `ingestion_run_id`
- `ingestion_row_id`
- `arquivo_origem`
- `ano_origem`
- `linha_origem`
- `row_kind`
- `status`
- `motivo_codigo`
- `severidade`
- `reparavel`
- `tentativas_reprocessamento`
- `diagnostico`

Status atuais:

- `pendente`
- `resolvido_auto`
- `resolvido_manual`
- `ignorado`

## `QuarentenaResumoResposta`

Agregado da fila de reparo.

Campos:

- `total`
- `por_status`
- `por_erro`
- `por_arquivo`
- `por_arquivo_e_erro`
- `total_pendentes`
- `total_resolvidos`
- `total_historico`

## `ReplayResposta`

Resposta padrao das operacoes de replay e rebuild.

Campos:

- `status`
- `detalhe`

`detalhe` e um payload operacional do servico executado e varia conforme o endpoint:

- replay de quarentena;
- replay de run;
- recover de run;
- rebuild de identidade.
