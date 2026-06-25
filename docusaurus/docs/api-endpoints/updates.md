---
title: Endpoints de Atualizações (Updates Service API)
sidebar_position: 14
---

# Endpoints de Atualizações (Updates Service API)

Todos os endpoints listados abaixo exigem autenticação do tipo **Bearer Token** e são montados sob o prefixo `/api/updates`. Operações críticas como forçar varreduras exigem **permissão de administrador**.

---

## 1. Scanner & Detecção

### Obter Status do Scanner
* **Rota:** `GET /api/updates/scanner/status`
* **Descrição:** Retorna o status de processamento do scanner e a data/hora da última execução de sondagem remota.
* **Exemplo de Resposta:**
  ```json
  {
    "status": "idle",
    "last_run": "2026-06-19T00:30:00+00:00"
  }
  ```

### Rodar Scanner Manualmente
* **Rota:** `POST /api/updates/scanner/run`
* **Permissão:** Requer administrador (`is_admin=true` ou token de sistema).
* **Descrição:** Enfileira o job diário de varredura das fontes (`run_daily_scanner_task`) no worker Celery de forma assíncrona.
* **Exemplo de Resposta:**
  ```json
  {
    "status": "queued",
    "task_id": "469fa781-b258-45e3-a6b1-4f3dfa3bf004",
    "message": "Scanner task has been queued in the background."
  }
  ```

### Histórico do Scanner
* **Rota:** `GET /api/updates/scanner/history`
* **Descrição:** Retorna a lista das últimas 50 detecções salvas.
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
* **Rota:** `GET /api/updates/pending`
* **Parâmetros de Query:**
  * `fonte` (Opcional): Filtra por fonte (ex: `cadastro`, `itr`).
  * `status` (Opcional): Filtra por status (ex: `change_detected`, `ready_for_ingestion`).
* **Descrição:** Retorna a lista de atualizações pendentes filtradas.

### Detalhar Atualização
* **Rota:** `GET /api/updates/pending/{id}`
* **Descrição:** Retorna os metadados consolidados e o `change_summary` de uma atualização específica.

### Listar Membros da Atualização
* **Rota:** `GET /api/updates/pending/{id}/members`
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
* **Rota:** `POST /api/updates/pending/{id}/trigger`
* **Descrição:** Dispara a execução física da importação e atualiza o status para `triggered`. Retorna o ID da tarefa Celery que rodará a ingestão em background.
* **Exemplo de Resposta:**
  ```json
  {
    "status": "triggered",
    "task_id": "7bf3bf00-e3b1-4f3d-a6b1-469fa781e3a6",
    "pending_update_id": "180bfa1e-61d5-4554-ba5f-b52f6b866c1f"
  }
  ```

### Descartar Atualização
* **Rota:** `POST /api/updates/pending/{id}/discard`
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
* **Rota:** `POST /api/updates/session`
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
* **Rota:** `POST /api/updates/session/{session_key}/items?pending_update_id={id}`
* **Descrição:** Insere um item na lista de aprovação da sessão.

### Disparar Sessão (Trigger Lote)
* **Rota:** `POST /api/updates/session/{session_key}/trigger`
* **Descrição:** Dispara a execução simultânea de todas as atualizações selecionadas e confirmadas na sessão. Retorna os IDs das tarefas Celery geradas.
