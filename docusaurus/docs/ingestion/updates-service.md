---
title: Serviço de Atualizações de Dados (CVM Data Updates Service)
sidebar_position: 6
---

# Serviço de Atualizações de Dados (CVM Data Updates Service)

O **Serviço de Atualizações de Dados (CVM Data Updates Service)** introduz um fluxo de ingestão baseado em **detecção prévia** (detection-first workflow). Em vez de disparar a ingestão total de arquivos automaticamente quando mudanças são detectadas remotamente, o serviço separa a descoberta de alterações da sua execução física, oferecendo controle granular e visibilidade aos operadores.

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│  Scanner Diário │ ────▶ │  Deep Analyzer  │ ────▶ │  Trigger Manual │
│ (HEAD/ETag remote)│     │  (Member Diff)  │       │ (API / CLI/ UI) │
└─────────────────┘       └─────────────────┘       └─────────────────┘
```

---

## 1. Funcionamento Geral

O serviço é dividido em três etapas sequenciais:

1. **Varredura (Scanning)**: Um job diário (`run_daily_scanner_task`) varre todas as fontes cadastradas no `source_registry`. Usando requisições HTTP `HEAD` rápidas, ele compara o `ETag`, `Last-Modified` ou `Content-Length` atual com o da última execução bem-sucedida. Se houver divergência, uma atualização pendente é registrada na tabela `pending_updates` com o status `change_detected`.
2. **Análise Detalhada (Deep Analysis)**: Quando configurado (`AUTO_ANALYZE_ON_DETECT = True`) ou solicitado via API/CLI, o serviço baixa temporariamente o arquivo (ex: ZIP anual do DFP), extrai os membros CSV e calcula os hashes e linhas de cada um deles. Ele os compara com os metadados da última importação com sucesso e gera uma listagem fina de mudanças no nível de arquivo membro (adicionado, removido, modificado, sem alterações).
3. **Disparo Controlado (Manual Trigger)**: Nenhuma ingestão de dados ocorre automaticamente. Os operadores revisam as mudanças e realizam o disparo (via endpoint HTTP ou comando CLI) para uma única atualização pendente ou um lote delas.

---

## 2. Configurações Disponíveis

As variáveis de ambiente configuráveis em `.env` que controlam o comportamento do serviço:

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `UPDATES_SERVICE_ENABLED` | `true` | Habilita/desabilita o serviço. |
| `AUTO_TRIGGER_UPDATES` | `false` | Se `true`, ativa o comportamento legado do Celery beat (ingestão automática imediata). Se `false` (padrão), o pipeline de ingestão diário só roda após aprovação manual. |
| `AUTO_ANALYZE_ON_DETECT` | `true` | Realiza a análise de membros (Deep Analysis) automaticamente assim que o scanner detecta mudanças remotas. |
| `SESSION_TIMEOUT_HOURS` | `24` | Tempo limite de validade de uma sessão de atualização criada pelo operador. |
| `TEMP_DIR` | `data/temp_updates` | Diretório temporário para downloads e extrações locais durante a análise profunda. |

---

## 3. Modelo de Dados (Database Schema)

O serviço é suportado pelas seguintes tabelas no PostgreSQL:

### `pending_updates`
Armazena a raiz de cada alteração de ZIP/CSV detectada.
* `id` (UUID): Identificador único.
* `fonte` (String): Tipo da fonte (ex: `dfp`, `itr`, `cadastro`).
* `ano` (Integer, Opcional): Ano de referência do formulário.
* `status` (String): Estado atual (`change_detected`, `analyzing`, `ready_for_ingestion`, `triggered`, `discarded`).
* `detection_timestamp` (DateTime): Quando a mudança foi identificada.
* `change_summary` (JSON, Opcional): Sumário geral das mudanças de membros.
* `last_successful_run_id` (UUID, Opcional): ID da IngestionRun originada após o disparo com sucesso.

### `pending_update_members`
Detalhes de cada membro CSV interno para arquivos compactados (ZIP).
* `member_name` (String): Nome do arquivo CSV membro (ex: `dfp_cia_aberta_dre_con_2025.csv`).
* `change_category` (String): Categoria da alteração (`added`, `removed`, `modified`, `unchanged`).
* `status` (String): Estado detalhado (`schema_changed`, `modified`, `unchanged`, `required_missing`).
* `current_row_count` (Integer): Linhas do arquivo novo.
* `previous_row_count` (Integer): Linhas da última ingestão bem-sucedida.

### `update_sessions` e `update_session_items`
Usados para agrupar múltiplas atualizações sob um lote lógico de execução e validação.

---

## 4. Uso via CLI (Interface de Linha de Comando)

Para gerenciar o ciclo de atualizações direto no terminal do container (`cvm_api`):

```bash
# Executar a varredura remota imediatamente
python -m app.updates.cli scanner run

# Listar todas as atualizações detectadas
python -m app.updates.cli pending list

# Ver sumário e membros afetados de uma atualização específica
python -m app.updates.cli pending show <uuid-da-atualizacao>

# Forçar/executar a análise detalhada
python -m app.updates.cli pending analyze <uuid-da-atualizacao>

# Disparar a ingestão
python -m app.updates.cli pending trigger <uuid-da-atualizacao>

# Descartar uma atualização
python -m app.updates.cli pending discard <uuid-da-atualizacao>

# Disparar todas as atualizações no estado ready_for_ingestion
python -m app.updates.cli trigger-all
```

> **UX Benefício:** O comando CLI salva automaticamente a chave da última sessão criada em `data/temp_updates/.cli_session` para facilitar comandos subsequentes sem necessidade de colar UUIDs de sessões longas.
