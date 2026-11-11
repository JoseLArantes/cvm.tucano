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
| `recovery` | `object` | elegibilidade e estrategia executavel de recovery |
| `remote_probe` | `object \| null` | decisao de preflight remoto |
| `change_summary` | `object \| null` | mudanca estrutural detectada |
| `quality_summary` | `object \| null` | resumo principal de progresso |
| `artifact_snapshot` | `object \| null` | snapshot do artefato avaliado, incluindo ponteiro do artifact local persistido |
| `member_snapshot_summary` | `object \| null` | inventario de members com ponteiros para artifact bruto e normalizado quando disponiveis |
| `delivery_snapshot_summary` | `object \| null` | indice documental agregado |
| `reconcile_summary` | `object \| null` | remocoes do reconcile |
| `rows_reconciled_deleted` | `integer \| null` | atalho numerico do reconcile |
| `lifecycle_decision` | `object \| null` | explicacao compacta da decisao de lifecycle |
| `links` | `object \| null` | rotas relacionadas |

### Status persistido da run

- `agendada`
- `aguardando_ingestao` (inclui espera por vaga global de member)
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

### Campos chave dentro de `artifact_snapshot`

- `resource_url`
- `source_filename`
- `storage_uri`
- `storage_role`
- `storage_content_type`
- `storage_size_bytes`
- `content_sha256`

### Campos chave dentro de `member_snapshot_summary.members[]`

- `member_name`
- `member_sha256`
- `raw_artifact_uri`
- `raw_artifact_content_type`
- `raw_artifact_size_bytes`
- `normalized_artifact_uri`
- `normalized_artifact_format`
- `normalized_artifact_content_sha256`
- `normalized_artifact_size_bytes`

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
- `awaiting_parent_window`
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

Durante backoff de uma retentativa Celery de member, `retryable=true` acompanha a execucao em `agendada` e a fase em
`failed_retryable`. Quando o limite automatico de tentativas termina, o erro final pode continuar recuperavel e oferecer
a acao administrativa correspondente, desde que exista fonte executavel.

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

Fases encerradas por erro transitorio usam `status=failed_retryable`, preservam `error_type`, `error_message` e
`error_retryable=true`, e nao sao tratadas como fase stale enquanto aguardam o Celery. A nova tentativa cria outro
registro de fase com o proximo valor de `attempt`.

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

Os previews em `active_runs` e `recoverable_runs` incluem `recovery` com:

- `eligible`: se o estado atual autoriza recovery e existe uma fonte executavel;
- `strategy`: `replay_staged_rows` ou `rerun_member_execution`, quando elegivel;
- `reason_code`: `STAGED_ROWS_AVAILABLE`, `MEMBER_EXECUTION_AVAILABLE`, `NO_RECOVERY_SOURCE`, `NON_RETRYABLE_FAILURE`, `RUN_ALREADY_COMPLETED` ou `RUN_NOT_RECOVERABLE`.

`recoverable_runs` inclui somente runs com `next_action=recover` e `recovery.eligible=true`.
Runs concluidas ou com falha nao retentavel permanecem terminais, nao entram nessa lista e nao bloqueiam um novo dispatch equivalente. Para falhas terminais, `allowed_actions[]` inclui `start_ingestion` com `reason_code=TERMINAL_RUN_REDISPATCH_ALLOWED`.

O campo `ingestion_queue` resume a fila persistida e inclui profundidade, idade do pedido mais antigo, lotes ativos,
vagas reservadas/em execução, capacidade configurada, preparações ZIP ativas e contagens por status.

## `IngestionQueueListResponse`

Resposta paginada de `GET /ingestion/queue`, ordenada por chegada do lote.

- `total`, `pagina`, `tamanho_pagina`
- `dados[]`: `lote_id`, `posicao`, `fontes[]` (`tipo_fonte`, `ano`), `status`, `solicitado_em`, `motivo_espera`
- `progresso`: contagens `total`, `concluidos`, `em_execucao`, `aguardando`
- `itens[]`: `item_id`, `execucao_id`, fonte/ano/arquivo, `etapa`, `status`, `motivo_espera`, `reservado_em`, `iniciado_em` e `tentativa`

Os status `queued`, `reserved`, `running`, `transition_pending` e `waiting_manual` distinguem espera por vaga,
publicação pendente, trabalho iniciado, aplicação de transição e confirmação de operador. `waiting_manual` não consome
vaga. `completed`, `failed` e `cancelled` encerram uma etapa.

Runs falhadas podem incluir `failure_acknowledgement`:

- `acknowledged_at`: momento do reconhecimento;
- `acknowledged_by`: ator autenticado;
- `reason`: conclusao da investigacao;
- `failure_key`: identificador da ocorrencia exata reconhecida.

Antes do reconhecimento, uma falha não retentável expõe as ações `inspect_error`, `acknowledge_failure` e `start_ingestion`. Depois de `POST /ingestion/runs/{run_id}/acknowledge-failure`, `next_action=none` e as ações passam a ser `inspect` e `start_ingestion`. O reconhecimento remove a pendência operacional, mas preserva `state=failed`, `last_error` e toda a trilha histórica.

## Controle de despacho e trabalho

`IngestionDispatchPlanRequest` recebe `scopes[]`, `strategy` (`direct` ou `two_step`), `force_reimport` e motivo opcional. A resposta inclui `plan_token`, expiração, escopos válidos/inválidos, conflitos e impacto no gate. `IngestionDispatchRequest` deve repetir o plano e usar `Idempotency-Key`. A confirmação persiste todas as execuções no mesmo lote e retorna `lote_id` em cada `work_item`; só etapas admitidas são publicadas ao Celery.

O work item contém `id`, `fonte`, `ano`, correlação de atualização, execução e run, `state`, `next_action` e `allowed_actions[]`. Cada ação é orientada a máquina: `code`, `operation`, `resource`, `requires_confirmation`, `reason_code` e `constraints`.

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
