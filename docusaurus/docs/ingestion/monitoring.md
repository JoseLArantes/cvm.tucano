---
title: Monitoramento de Sincronizações
sidebar_position: 3
---

# Monitoramento de Sincronizações

## Visão Geral

Endpoints para monitorar execuções de sincronização, runs do pipeline e obter dashboards consolidados.

Além da listagem de runs e execuções, a superfície operacional atual passa a incluir:

- `GET /ingestion/runs/{run_id}/members` para inventário paginado de CSVs/members de uma run;
- `GET /ingestion/operations` para snapshot consolidado de runs ativas, cancelamentos, sinais de fila Celery e gate de materialização;
- `POST /ingestion/runs/{run_id}/cancel`, `POST /ingestion/runs/{run_id}/members/{member_id}/cancel` e `POST /ingestion/runs/{run_id}/recover` para ação direta sem depender de navegação prévia por `id_execucao`.

---

## `GET /ingestion/sincronizacoes`

Lista paginada das execuções registradas no sistema.

Cada item agora expõe também um sinal operacional agregado:

- `state`: classificação pronta para UI (`queued`, `waiting`, `running`, `stale`, `succeeded`, `skipped`, `failed`, `cancelled`)
- `liveness`: heartbeat, task/lease atual e flag `is_stale`
- `blocking`: motivo compacto de espera ou bloqueio
- `cancellation`: último pedido de cancelamento persistido
- `last_error`: erro operacional mais recente conhecido
- `next_action`: ação recomendada para consumidor desacoplado (`wait`, `recover`, `inspect_error`, `inspect_quarantine`, `none`)

### Query Parameters

| Parâmetro | Tipo | Padrão | Descrição |
|-----------|------|--------|-----------|
| `pagina` | integer | `1` | Número da página |
| `tamanho_pagina` | integer | `100` | Itens por página (máx: 500) |
| `tipo_execucao` | string | - | Filtrar por tipo: `arquivo_zip`, `arquivo_membro`, `arquivo_simples` |
| `id_execucao_pai` | UUID | - | Filtrar por ID da execução pai |
| `somente_filhos` | boolean | `false` | Retorna apenas execuções filhas (membros) |
| `somente_pais` | boolean | `false` | Retorna apenas execuções pais (ZIP ou simples) |

### Exemplo

```bash
curl -X GET "http://localhost:8007/ingestion/sincronizacoes?pagina=1&tamanho_pagina=50" \
  -H "Authorization: Bearer <token-admin>"
```

### Response 200

**Schema:** `ListaExecucoesSincronizacao`

```json
{
  "dados": [
    {
      "id": "6a31c7f8-1c89-4f3d-87db-7e6a8e196999",
      "id_tarefa": "a37f0f88-44b9-4cff-9b0d-b826e4e8f367",
      "tipo_fonte": "dfp",
      "arquivo": "dfp_cia_aberta_2025.zip",
      "status": "sucesso",
      "iniciada_em": "2026-06-15T08:00:00Z",
      "finalizada_em": "2026-06-15T08:15:30Z",
      "total_linhas_lidas": 125000,
      "total_inseridos": 124500,
      "total_atualizados": 300,
      "total_inalterados": 150,
      "total_rejeitados": 50,
      "analise_arquivos": [...],
      "id_execucao_pai": null,
      "tipo_execucao": "arquivo_zip",
      "filhos_total": 15,
      "filhos_concluidos": 15,
      "filhos_falha": 0,
      "filhos_em_andamento": 0,
      "state": "succeeded",
      "liveness": null,
      "blocking": {"reason_code": "none", "detail": null},
      "cancellation": {"status": "none"},
      "last_error": null,
      "next_action": "none",
      "links": {
        "execucao_detail": "/ingestion/sincronizacoes/6a31c7f8-1c89-4f3d-87db-7e6a8e196999",
        "run_detail": "/ingestion/runs/6a31c7f8-1c89-4f3d-87db-7e6a8e196999",
        "quarantine": "/ingestion/quarentena?execucao_sincronizacao_id=6a31c7f8-1c89-4f3d-87db-7e6a8e196999"
      }
    }
  ],
  "paginacao": {
    "pagina": 1,
    "tamanho_pagina": 50,
    "total": 1
  }
}
```

---

## `GET /ingestion/sincronizacoes/{id_execucao}`

Retorna detalhamento completo de uma execução.

### Path Parameters

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `id_execucao` | UUID | ID da execução |

### Exemplo

```bash
curl -X GET "http://localhost:8007/ingestion/sincronizacoes/6a31c7f8-1c89-4f3d-87db-7e6a8e196999" \
  -H "Authorization: Bearer <token-admin>"
```

### Response 200

**Schema:** `ExecucaoSincronizacaoDetalhe`

```json
{
  "id": "6a31c7f8-1c89-4f3d-87db-7e6a8e196999",
  "id_tarefa": "a37f0f88-44b9-4cff-9b0d-b826e4e8f367",
  "tipo_fonte": "dfp",
  "ano": 2025,
  "arquivo": "dfp_cia_aberta_2025.zip",
  "url": "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/dfp_cia_aberta_2025.zip",
  "hash_arquivo": "abc123...",
  "status": "sucesso",
  "iniciada_em": "2026-06-15T08:00:00Z",
  "finalizada_em": "2026-06-15T08:15:30Z",
  "total_linhas_lidas": 125000,
  "total_inseridos": 124500,
  "total_atualizados": 300,
  "total_inalterados": 150,
  "total_rejeitados": 50,
  "mensagem_erro": null,
  "analise_arquivos": [
    {
      "file_name": "dfp_cia_aberta_DRE_con_2025.csv",
      "file_size": "2.5 MB",
      "rows_count": 8500,
      "columns_count": 15,
      "header_columns": ["CNPJ_CIA", "DT_REFER", "VERSAO", ...],
      "encoding": "utf-8-sig",
      "delimiter": ";"
    }
  ],
  "id_execucao_pai": null,
  "tipo_execucao": "arquivo_zip",
  "arquivo_principal": null,
  "filhos_total": 15,
  "filhos_concluidos": 15,
  "filhos_falha": 0,
  "filhos_em_andamento": 0,
  "execucoes_filhas": [...]
}
```

### Campos Importantes

| Campo | Descrição |
|-------|-----------|
| `status` | Status atual da execução |
| `total_rejeitados` | Linhas enviadas para quarentena |
| `analise_arquivos` | Análise detalhada dos arquivos processados |
| `filhos_*` | Contadores de execuções filhas (para ZIP) |
| `execucoes_filhas` | Lista detalhada de execuções filhas |

---

## `GET /ingestion/runs`

Lista paginada das runs do pipeline de ingestão.

Além dos snapshots estruturais (`remote_probe`, `change_summary`, `quality_summary`, `member_snapshot_summary`), cada run agora expõe:

- `state`: estado operacional agregado
- `progress`: contadores resumidos para cards e progresso
- `liveness`: heartbeat, owner do lease e classificação `stale`
- `blocking`: motivo de espera ou bloqueio
- `cancellation`: último pedido de cancelamento persistido
- `last_error`: erro operacional mais recente conhecido
- `next_action`: próxima ação recomendada
- `links`: rotas relativas para detalhe, fases, replay e quarentena

### Query Parameters

| Parâmetro | Tipo | Padrão | Descrição |
|-----------|------|--------|-----------|
| `pagina` | integer | `1` | Número da página |
| `tamanho_pagina` | integer | `100` | Itens por página (máx: 500) |

### Exemplo

```bash
curl -X GET "http://localhost:8007/ingestion/runs?pagina=1&tamanho_pagina=50" \
  -H "Authorization: Bearer <token-admin>"
```

### Response 200

**Schema:** `ListaIngestionRuns`

```json
{
  "dados": [
    {
      "id": "6a31c7f8-1c89-4f3d-87db-7e6a8e196999",
      "execucao_sincronizacao_id": "02be26d3-8db8-48a1-bcd0-4737b8157116",
      "tipo_fonte": "dfp",
      "ano": 2025,
      "status": "sucesso_com_alerta",
      "phase": "complete",
      "remote_probe": {...},
      "change_summary": {...},
      "quality_summary": {...},
      "artifact_snapshot": {...},
      "member_snapshot_summary": {...},
      "delivery_snapshot_summary": {...},
      "reconcile_summary": {...},
      "rows_reconciled_deleted": 4,
      "lifecycle_decision": {...},
      "state": "running",
      "progress": {"members_processed": 13, "quarantine_total": 3},
      "liveness": {
        "heartbeat_at": "2026-06-29T20:26:10Z",
        "lease_owner": "task-dfp-2025",
        "task_id": "task-dfp-2025",
        "phase_status": "running",
        "is_stale": false,
        "stale_after_seconds": 1800,
        "heartbeat_age_seconds": 12
      },
      "blocking": {"reason_code": "none", "detail": null},
      "cancellation": {"status": "none"},
      "last_error": null,
      "next_action": "wait",
      "links": {
        "run_detail": "/ingestion/runs/6a31c7f8-1c89-4f3d-87db-7e6a8e196999",
        "run_phases": "/ingestion/runs/6a31c7f8-1c89-4f3d-87db-7e6a8e196999/phases",
        "run_replay": "/ingestion/runs/6a31c7f8-1c89-4f3d-87db-7e6a8e196999/replay",
        "quarantine": "/ingestion/quarentena?ingestion_run_id=6a31c7f8-1c89-4f3d-87db-7e6a8e196999"
      }
    }
  ],
  "paginacao": {
    "pagina": 1,
    "tamanho_pagina": 50,
    "total": 1
  }
}
```

---

## `GET /ingestion/runs/{run_id}`

Retorna uma run específica do pipeline com todos os metadados operacionais.

### Path Parameters

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `run_id` | UUID | ID da run |

### Exemplo

```bash
curl -X GET "http://localhost:8007/ingestion/runs/6a31c7f8-1c89-4f3d-87db-7e6a8e196999" \
  -H "Authorization: Bearer <token-admin>"
```

### Response 200

**Schema:** `IngestionRunResumo`

Use `state`, `liveness` e `next_action` como contrato primário para UX operacional. `quality_summary` continua sendo a fonte principal dos contadores de processamento; `liveness` responde se a run ainda parece viva; e `GET /ingestion/runs/{run_id}/phases` é o drill-down recomendado quando a UI precisar mostrar tentativas, heartbeat, falha por fase e o manifesto local de artifacts usados ou produzidos pela fase.

---

## `GET /ingestion/runs/{run_id}/members`

Retorna o inventário paginado de members associados à run.

Cada item combina:

- metadados persistidos em `ingestion_file_members`;
- status estrutural do snapshot (`schema_status`, `row_kind`, `destino_promovido`);
- decisão de lifecycle (`lifecycle_status`, `state`);
- volume de deliveries capturadas (`delivery_total`);
- volume de quarentena ancorada no member (`quarantine_total`);
- links relativos para drill-down e cancelamento direto do CSV.

### Response 200

**Schema:** `ListaIngestionRunMembers`

---

## `GET /ingestion/operations`

Retorna um snapshot operacional consolidado para consumidores desacoplados.

O payload agrega:

- `run_counts`: distribuição das runs por estado operacional agregado;
- `execution_counts`: contagem de execuções por status persistido;
- `cancellation_counts`: distribuição dos pedidos de cancelamento;
- `task_counts`: contagem total e contagem específica de tasks de ingestão em `active`, `reserved` e `scheduled`;
- `materialization_gate`: estado atual do gate da materialização, incluindo blockers conhecidos;
- `active_runs`: preview das runs atualmente em `queued`, `waiting`, `running` ou `stale`;
- `recoverable_runs`: preview das runs cujo `next_action` atual é `recover`.

### Response 200

**Schema:** `IngestionOperationsResumo`

---

## `POST /ingestion/runs/{run_id}/cancel`

Cancela diretamente uma run a partir do `run_id`.

Use esta rota quando a UI já está posicionada no detalhe da run e não precisa fazer uma etapa extra para descobrir `id_execucao`.

---

## `POST /ingestion/runs/{run_id}/members/{member_id}/cancel`

Cancela apenas o member/CSV informado dentro da run, quando existir execução filha correspondente.

Este é o endpoint recomendado para ações de parar reprocessamento seletivo sem afetar siblings do mesmo ZIP.

---

## `POST /ingestion/runs/{run_id}/recover`

Executa recuperação administrativa controlada de uma run marcada como `stale` ou com erro recuperável.

Na implementação atual, a recuperação reaplica o replay completo da run a partir dos artefatos já retidos.

---

## `GET /ingestion/runs/{run_id}/phases`

Retorna a timeline persistida de fases da run.

Campos de artifact:

- `input_artifact_uri`: artifact de entrada efetivamente consumido pela fase, quando conhecido.
- `output_artifact_uri`: artifact gerado pela fase, quando conhecido.
- `metrics.artifacts`: manifesto resumido com `uri`, `role`, `content_type`, `logical_name`, `size_bytes` e `content_sha256`.

### Exemplo

```bash
curl -X GET "http://localhost:8007/ingestion/runs/6a31c7f8-1c89-4f3d-87db-7e6a8e196999/phases" \
  -H "Authorization: Bearer <token-admin>"
```

### Response 200

**Schema:** `ListaIngestionRunPhaseExecutions`

```json
{
  "dados": [
    {
      "id": "7b6d2875-5f59-41f7-b5f9-c3b76014e584",
      "phase": "promote",
      "status": "running",
      "attempt": 1,
      "task_id": "task-dfp-2025",
      "lease_owner": "task-dfp-2025",
      "started_at": "2026-06-29T20:15:00Z",
      "heartbeat_at": "2026-06-29T20:26:10Z",
      "finished_at": null,
      "cancel_requested_at": null,
      "cancelled_at": null,
      "cancel_reason": null,
      "error_type": null,
      "error_message": null,
      "error_retryable": null,
      "input_artifact_uri": "/var/lib/cvm/artifacts/member_payloads/769d9633-4989-4668-8eba-89d62f32bde7/itr_cia_aberta_BPA_con_2026.csv",
      "output_artifact_uri": "/var/lib/cvm/artifacts/member_payloads/769d9633-4989-4668-8eba-89d62f32bde7/itr_cia_aberta_BPA_con_2026.csv",
      "metrics": {
        "members_processados": 13,
        "artifacts": [
          {
            "uri": "/var/lib/cvm/artifacts/member_payloads/769d9633-4989-4668-8eba-89d62f32bde7/itr_cia_aberta_BPA_con_2026.csv",
            "role": "raw_member_payload",
            "content_type": "text/csv",
            "logical_name": "itr_cia_aberta_BPA_con_2026.csv",
            "size_bytes": 1048576,
            "content_sha256": "4d8f5c2d7ff53f6eec4f7f686cb4d88a8e6508b66f661d4ec0d1a9f1848401fb"
          }
        ]
      }
    }
  ]
}
```

```json
{
  "id": "6a31c7f8-1c89-4f3d-87db-7e6a8e196999",
  "execucao_sincronizacao_id": "02be26d3-8db8-48a1-bcd0-4737b8157116",
  "tipo_fonte": "dfp",
  "ano": 2025,
  "status": "sucesso_com_alerta",
  "phase": "complete",
  "remote_probe": {
    "dataset_url": "https://dados.cvm.gov.br/dataset/cia_aberta-doc-dfp",
    "decision": "changed",
    "decision_reason": "metadata_changed:resource_last_modified",
    "probe_sources": ["ckan", "head"],
    "resource_last_modified": "Mon, 09 Jun 2026 08:03:41 GMT",
    "resource_url": "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/dfp_cia_aberta_2025.zip"
  },
  "change_summary": {
    "member_added": [],
    "member_removed": ["dfp_cia_aberta_DVA_ind_2025.csv"],
    "required_member_missing": [],
    "optional_member_missing": [],
    "header_changed": [
      {
        "member_name": "dfp_cia_aberta_DRE_ind_2025.csv",
        "before": ["CNPJ_CIA", "DT_REFER", "VERSAO"],
        "after": ["CNPJ_CIA", "DT_REFER", "VERSAO", "COLUNA_DF"]
      }
    ],
    "schema_changed": [],
    "row_count_changed": [
      {
        "member_name": "dfp_cia_aberta_DRE_ind_2025.csv",
        "before": 12034,
        "after": 12080
      }
    ],
    "delivery_index_changed": [
      {
        "member_name": "dfp_cia_aberta_2025.csv",
        "before_count": 1200,
        "after_count": 1204,
        "added": 4,
        "removed": 0
      }
    ]
  },
  "quality_summary": {
    "members_total": 14,
    "members_processados": 13,
    "members_skipped": 1,
    "members_reprocessed": 2,
    "members_reused_from_previous": 1,
    "members_reused_from_failed_parent": 0,
    "row_status_counts": {
      "valid": 1200,
      "invalid": 3
    },
    "reason_counts": {
      "companhia_nao_encontrada": 2,
      "schema_inesperado": 1
    },
    "resolver_methods": {
      "codigo_cvm_identificador_alta": 1180,
      "repair_rule": 20
    },
    "quarantine_total": 3,
    "staged_rows_purged": 1197,
    "typed_stage_rows_loaded": 1198,
    "typed_stage_bytes_loaded": 845231,
    "typed_stage_rows_replaced": 0,
    "typed_stage_rows_purged": 1198,
    "typed_stage_copy_loads": 14,
    "reconciled_deleted": 4
  },
  "artifact_snapshot": {
    "resource_url": "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/dfp_cia_aberta_2025.zip",
    "source_filename": "dfp_cia_aberta_2025.zip",
    "content_sha256": "abc123...",
    "probe_decision": "changed",
    "probe_confidence": "medium",
    "sha_confirmation_result": "different",
    "status": "sucesso_com_alerta"
  },
  "member_snapshot_summary": {
    "total": 14,
    "by_status": {
      "processed": 13,
      "member_skipped": 1
    },
    "by_schema_status": {
      "ok": 13,
      "reused": 1
    }
  },
  "delivery_snapshot_summary": {
    "total": 1204,
    "by_status": {
      "captured": 1204
    },
    "by_member": {
      "dfp_cia_aberta_2025.csv": 1204
    }
  },
  "reconcile_summary": {
    "scope": "member_replace",
    "target_tables": ["demonstracoes_financeiras"],
    "rows_reconciled_deleted": 4
  },
  "rows_reconciled_deleted": 4,
  "lifecycle_decision": {
    "remote_probe": "download_required",
    "artifact_sha": "changed",
    "members_processed": 13,
    "members_skipped_by_sha": 1,
    "members_reused_from_previous": 1,
    "members_reused_from_failed_parent": 0
  }
}
```

### Campos Importantes

| Campo | Descrição |
|-------|-----------|
| `remote_probe` | Decisão de preflight remoto antes do download |
| `change_summary` | Drift estrutural entre pacotes |
| `quality_summary` | Contadores operacionais do processamento, incluindo members reprocessados e members reaproveitados em reruns |
| `artifact_snapshot` | Evidência remota/local usada para skip/download |
| `member_snapshot_summary` | Inventário de members processados/reaproveitados |
| `delivery_snapshot_summary` | Índice documental capturado |
| `reconcile_summary` | Remoções feitas no reconcile |
| `lifecycle_decision` | Resumo da decisão do lifecycle engine, inclusive reaproveitamento por igualdade de `member_sha256` |

### Leitura recomendada dos counters de lifecycle

- `members_processed`: members que realmente entraram no hot path de `stage -> promote -> reconcile`;
- `members_skipped_by_sha`: members pulados por igualdade observada durante o lifecycle;
- `members_reused_from_previous`: subset de reaproveitamento vindo de execucoes anteriores bem-sucedidas;
- `members_reused_from_failed_parent`: subset de reaproveitamento vindo de execucao pai anual que terminou `falha`, mas tinha children ja consolidados corretamente.

Esses counters existem para o operador e para o frontend distinguirem tres cenarios que antes pareciam iguais: run sem alteracao, rerun anual que reutilizou members bons e run que realmente reprocessou members do zero.

### Leitura recomendada dos counters de staging tipado financeiro

- `typed_stage_rows_loaded`: total de linhas carregadas dos artifacts normalizados para o staging tipado;
- `typed_stage_bytes_loaded`: volume total, em bytes, dos artifacts normalizados consumidos nessa carga;
- `typed_stage_rows_replaced`: linhas antigas removidas antes de recarregar o mesmo member no staging;
- `typed_stage_rows_purged`: linhas removidas do staging tipado ao final do processamento do member;
- `typed_stage_copy_loads`: quantidade de cargas que usaram o caminho PostgreSQL `COPY`.

Esses campos sao aditivos e servem para diagnosticar se o custo da run esta concentrado em normalizacao, carga de staging ou promote.

---

## `GET /ingestion/dashboard`

Retorna consolidado simples para operação: status, rejeições e últimas execuções.

### Exemplo

```bash
curl -X GET "http://localhost:8007/ingestion/dashboard" \
  -H "Authorization: Bearer <token-admin>"
```

### Response 200

**Schema:** `DashboardExecucoesResposta`

```json
{
  "total_execucoes": 150,
  "total_sucesso": 145,
  "total_sem_alteracao": 3,
  "total_falha": 2,
  "total_rejeitados": 42,
  "ultimas_execucoes": [
    {
      "id": "6a31c7f8-1c89-4f3d-87db-7e6a8e196999",
      "tipo_fonte": "dfp",
      "arquivo": "dfp_cia_aberta_2025.zip",
      "status": "sucesso",
      "iniciada_em": "2026-06-15T08:00:00Z",
      "finalizada_em": "2026-06-15T08:15:30Z",
      "total_linhas_lidas": 125000,
      "total_inseridos": 124500,
      "total_rejeitados": 50
    }
  ]
}
```

---

## `GET /ingestion/alteracoes`

Lista paginada de alterações campo a campo registradas nas sincronizações.

### Query Parameters

| Parâmetro | Tipo | Padrão | Descrição |
|-----------|------|--------|-----------|
| `pagina` | integer | `1` | Número da página |
| `tamanho_pagina` | integer | `100` | Itens por página (máx: 500) |
| `entidade` | string | - | Filtrar por entidade alterada (ex: `documentos_financeiros`) |

### Exemplo

```bash
curl -X GET "http://localhost:8007/ingestion/alteracoes?entidade=companhias&pagina=1" \
  -H "Authorization: Bearer <token-admin>"
```

### Response 200

**Schema:** `ListaHistoricoAlteracoes`

```json
{
  "dados": [
    {
      "id": "alter-uuid-1",
      "entidade": "companhias",
      "entidade_id": "comp-uuid-1",
      "companhia_id": "comp-uuid-1",
      "campo": "situacao_registro",
      "valor_anterior": "ATIVO",
      "valor_novo": "SUSPENSO(A) - DECISAO ADM",
      "alterado_em": "2026-06-15T08:10:00Z",
      "execucao_sincronizacao_id": "exec-uuid-1",
      "arquivo_origem": "cad_cia_aberta.csv",
      "ano_origem": 2026
    }
  ],
  "paginacao": {
    "pagina": 1,
    "tamanho_pagina": 100,
    "total": 1
  }
}
```

---

## Casos de Uso

### Caso 1: Monitorar Sincronização em Andamento

```bash
# 1. Disparar sincronização
POST /ingestion/sincronizacoes/dfp/2025

# 2. Listar execuções recentes
GET /ingestion/sincronizacoes?pagina=1&tamanho_pagina=10

# 3. Detalhar execução específica
GET /ingestion/sincronizacoes/{id_execucao}
```

### Caso 2: Dashboard Operacional

```bash
# Obter visão consolidada
GET /ingestion/dashboard

# Verificar últimas execuções
GET /ingestion/sincronizacoes?pagina=1&tamanho_pagina=20
```

### Caso 3: Auditoria de Mudanças

```bash
# Listar alterações de companhias
GET /ingestion/alteracoes?entidade=companhias

# Listar alterações de documentos financeiros
GET /ingestion/alteracoes?entidade=documentos_financeiros
```

### Caso 4: Python - Monitoramento Automatizado

```python
import httpx
from datetime import datetime, timedelta

def verificar_falhas_recentes(base_url, token):
    """Verifica execuções com falha nas últimas 24 horas."""
    headers = {"Authorization": f"Bearer {token}"}
    
    response = httpx.get(
        f"{base_url}/ingestion/sincronizacoes",
        params={"pagina": 1, "tamanho_pagina": 100},
        headers=headers
    )
    response.raise_for_status()
    
    execucoes = response.json()["dados"]
    limite = datetime.now() - timedelta(hours=24)
    
    falhas = [
        e for e in execucoes
        if e["status"] in ["falha", "falha_qualidade"]
        and datetime.fromisoformat(e["iniciada_em"].replace("Z", "+00:00")) > limite
    ]
    
    if falhas:
        print(f"⚠️ {len(falhas)} execuções com falha nas últimas 24h")
        for f in falhas:
            print(f"  - {f['tipo_fonte']} {f.get('ano', '')}: {f['status']}")
    
    return falhas

# Uso
falhas = verificar_falhas_recentes("http://localhost:8007", "seu-token")
```

---

## Notas para Usuários

### Para Operadores de Backoffice

- Use `/dashboard` para visão rápida do status operacional
- Monitore `total_rejeitados` para identificar problemas
- Use `/sincronizacoes/{id}` para drill-down em execuções específicas

### Para Auditores

- Use `/runs/{run_id}` para inspeção detalhada de drift estrutural
- Monitore `change_summary` para detectar mudanças de schema
- Use `/alteracoes` para rastrear mudanças campo a campo

### Para Compliance

- Monitore `quality_summary` para validar quality gates
- Use `remote_probe` para auditar decisões de download
- Documente `reconcile_summary` para auditoria de remoções

---

## Próximos Passos

- [Quarentena e Replay](./quarantine.md) - Tratar erros
- [Identidade e Auditoria](./identity.md) - Reconstrução e auditoria
