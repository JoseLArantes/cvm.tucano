---
title: Endpoints de Atualizações (Updates Service API)
sidebar_position: 14
---

# Endpoints de Atualizações (Updates Service API)

Todos os endpoints listados abaixo exigem autenticação do tipo **Bearer Token** e são montados sob o prefixo `/updates`. Operações críticas como forçar varreduras exigem **permissão de administrador**.

---

## 1. Scanner & Detecção

### Obter Status do Scanner
* **Rota:** `GET /updates/scanner/status`
* **Descrição:** Retorna o estado operacional, saúde, cobertura e contadores da última execução persistida.
* **Exemplo de Resposta:**
  ```json
  {
    "status": "idle",
    "health_status": "healthy",
    "scanner_enabled": true,
    "schedule_enabled": true,
    "schedule_status": "healthy",
    "last_run": "15/07/2026 00:30:03",
    "last_scan_run_id": "180bfa1e-61d5-4554-ba5f-b52f6b866c1f",
    "last_scan_status": "completed",
    "last_scheduled_scan_run_id": "180bfa1e-61d5-4554-ba5f-b52f6b866c1f",
    "last_scheduled_scan_status": "completed",
    "trigger": "scheduled",
    "coverage_status": "complete",
    "expected_scopes": 50,
    "scanned_scopes": 50,
    "changed_count": 0,
    "unchanged_count": 50,
    "inconclusive_count": 0,
    "error_count": 0,
    "skipped_count": 0,
    "sources_without_scope": [],
    "expected_interval_hours": 24,
    "stale_after_hours": 36
  }
  ```

`health_status` combina a qualidade da última varredura com a saúde do agendamento. `schedule_status` considera somente execuções com `trigger=scheduled`: uma execução manual não mascara um Beat parado ou obsoleto.

### Rodar Scanner Manualmente
* **Rota:** `POST /updates/scanner/run`
* **Permissão:** Requer administrador (`is_admin=true` ou token de sistema).
* **Descrição:** Enfileira o job diário de varredura das fontes (`run_daily_scanner_task`) no worker Celery de forma assíncrona.
* **Exemplo de Resposta:**
  ```json
  {
    "status": "queued",
    "task_id": "469fa781-b258-45e3-a6b1-4f3dfa3bf004",
    "scan_run_id": "180bfa1e-61d5-4554-ba5f-b52f6b866c1f",
    "message": "Scanner task has been queued in the background."
  }
  ```

### Histórico das Execuções do Scanner
* **Rota:** `GET /updates/scanner/runs`
* **Parâmetros:** `pagina`, `tamanho_pagina` e `status` opcional.
* **Descrição:** Retorna todas as varreduras agendadas e manuais, inclusive as que terminaram sem detectar atualizações. Cada item contém `summary.items`, o log por fonte/ano.

Cada item de `summary.items` informa `fonte`, `ano`, `artifact_decision`, `decision_reason`, os metadados consultados em `probe_details` e o resultado em `member_scan`. Assim, uma tela pode distinguir ausência real de mudança, erro remoto, baseline ausente e comparação inconclusiva.

### Última Execução
* **Rota:** `GET /updates/scanner/runs/latest`
* **Descrição:** Retorna o log consolidado mais recente.

### Detalhe de uma Execução
* **Rota:** `GET /updates/scanner/runs/{scan_run_id}`
* **Descrição:** Retorna uma execução específica para polling ou auditoria.

### Histórico de Alterações Detectadas
* **Rota:** `GET /updates/scanner/history`
* **Descrição:** Retorna somente as últimas 50 mudanças detectadas. Não use esta rota para verificar se o scanner diário executou; use `/scanner/runs`.
* **Exemplo de Resposta:**
  ```json
  [
    {
      "id": "180bfa1e-61d5-4554-ba5f-b52f6b866c1f",
      "fonte": "dfp",
      "ano": 2025,
      "status": "ready_for_ingestion",
      "detection_timestamp": "2026-06-19T16:00:00Z",
      "artifact_url": "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/dfp_cia_aberta_2025.zip",
      "change_type": "artifact_changed"
    }
  ]
  ```

---

## 2. Gerenciamento de Pendências

### Listar Atualizações Pendentes
* **Rota:** `GET /updates/pending`
* **Parâmetros de Query:**
  * `fonte` (Opcional): Filtra por fonte (ex: `cadastro`, `itr`).
  * `status` (Opcional): Filtra por status (ex: `change_detected`, `ready_for_ingestion`).
* **Descrição:** Retorna a lista de atualizações filtradas após reconciliar correlações terminais comprovadas.

Cada item também informa:

- `content_changed`: `true`, `false` ou `null` enquanto não houver conclusão;
- `recommended_action`: `analyze`, `wait`, `ingest`, `update_reference` ou `none`;
- `status=content_unchanged` quando todos os members mantêm o mesmo SHA-256;
- `status=reference_updated` após reconhecimento da referência sem ingestão.
- `status=triggered` enquanto o despacho aguarda uma run ou a run correlata permanece ativa;
- `status=ingested` somente após conclusão terminal bem-sucedida e promoção canônica confirmada;
- `status=ingestion_failed` após falha terminal;
- `current_run_id`, `current_execution_id` e `ingestion_task_id` somente enquanto representam trabalho ativo ou pendente de correlação;
- `last_successful_run_id` e `last_failed_run_id` preservam a última resolução correlacionada.

O endpoint também repara, de forma idempotente, o caso legado comprovável em que um item `triggered` não tem IDs atuais, mas `last_successful_run_id` aponta para uma run bem-sucedida em fase `complete`. Casos ambíguos não são alterados.

### Detalhar Atualização
* **Rota:** `GET /updates/pending/{id}`
* **Descrição:** Retorna os metadados consolidados e o `change_summary` de uma atualização específica.

### Listar Membros da Atualização
* **Rota:** `GET /updates/pending/{id}/members`
* **Descrição:** Detalha a lista de arquivos membros (ex: tabelas CSV internas do ZIP) com o status individual de cada um.
* **Exemplo de Resposta:**
  ```json
  [
    {
      "id": "cb1c3664-d10c-43f1-9c60-c440be57fbe1",
      "pending_update_id": "180bfa1e-61d5-4554-ba5f-b52f6b866c1f",
      "member_name": "dfp_cia_aberta_DRE_con_2025.csv",
      "change_category": "modified",
      "status": "modified",
      "previous_row_count": 45120,
      "current_row_count": 45310,
      "is_required": true
    }
  ]
  ```

### Disparar Ingestão (Trigger)
* **Rota:** `POST /updates/pending/{id}/trigger`
* **Descrição:** Dispara a execução física da importação e atualiza o item para `triggered`. Esse estado é transitório e não comprova ingestão: permanece enquanto o despacho aguarda ou a run está ativa. A resposta confirma o aceite assíncrono como `ingestion_queued`.
* **Pré-condição:** Somente `ready_for_ingestion`. Para `content_unchanged`, use a atualização de referência.
* **Exemplo de Resposta:**
  ```json
  {
    "status": "ingestion_queued",
    "task_id": "7bf3bf00-e3b1-4f3d-a6b1-469fa781e3a6",
    "pending_update_id": "180bfa1e-61d5-4554-ba5f-b52f6b866c1f"
  }
  ```

### Atualizar Referência Sem Ingestão

* **Rota:** `POST /updates/pending/{id}/acknowledge-reference`
* **Pré-condições:** `total_changes=0`, todos os members com SHA-256 anterior e atual idênticos, e baseline canônico identificado.
* **Descrição:** Registra os headers do artefato remoto como referência reconhecida e finaliza a pendência em `reference_updated`. Não cria task Celery, não promove dados e não altera o `IngestionFile` original.
* **Exemplo de resposta:**

  ```json
  {
    "status": "reference_updated",
    "pending_update_id": "180bfa1e-61d5-4554-ba5f-b52f6b866c1f",
    "ingestion_triggered": false,
    "acknowledged_references": [
      {
        "id": "9d713c0d-d1c8-41db-a6f8-90b71b46b747",
        "resource_url": "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/CGVN/DADOS/cgvn_cia_aberta_2026.zip",
        "remote_etag": "\"6a537c26-19b01\"",
        "remote_last_modified": "15/07/2026 18:00:00",
        "remote_content_length": 105217,
        "member_fingerprint": "d12d7d7b37fd97b14f09bffdd0e34339a36661583fe672844e31bc5a28c7c514",
        "confirmation_method": "member_sha256",
        "confirmed_by": "admin",
        "confirmed_at": "15/07/2026 18:40:00"
      }
    ]
  }
  ```

Descartar um item `content_unchanged` não reconhece seus headers. Se o remoto continuar diferente do baseline, o scanner poderá detectá-lo novamente.

### Descartar Atualização
* **Rota:** `POST /updates/pending/{id}/discard`
* **Descrição:** Cancela a atualização pendente.
* **Exemplo de Resposta:**
  ```json
  {
    "status": "discarded",
    "pending_update_id": "180bfa1e-61d5-4554-ba5f-b52f6b866c1f"
  }
  ```

---

## 3. Lotes (Sessions)

### Criar Sessão
* **Rota:** `POST /updates/session`
* **Descrição:** Inicia uma nova sessão de seleção para processamento em lote.
* **Exemplo de Resposta:**
  ```json
  {
    "id": "e932ba3b-fa1b-4fde-ba46-0e1236ea0bc1",
    "session_key": "9cf3a58e2a3a0e104f58c7ab12e6ac7b9a5e8c1f03f7a62b",
    "expires_at": "2026-06-20T20:00:00Z",
    "status": "active"
  }
  ```

### Adicionar Item na Sessão
* **Rota:** `POST /updates/session/{session_key}/items?pending_update_id={id}`
* **Descrição:** Insere um item na lista de aprovação da sessão.

### Disparar Sessão (Trigger Lote)
* **Rota:** `POST /updates/session/{session_key}/trigger`
* **Descrição:** Dispara a execução simultânea de todas as atualizações selecionadas e confirmadas na sessão. Retorna os IDs das tarefas Celery geradas.
