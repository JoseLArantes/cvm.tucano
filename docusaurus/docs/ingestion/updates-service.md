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

1. **Varredura (Scanning)**: Um job diário às `00:30` no timezone `America/Sao_Paulo` (`run_daily_scanner_task`) varre todas as fontes cadastradas no `source_registry`. Os anos monitorados são derivados das ingestões bem-sucedidas já existentes no banco. A varredura compara `ETag`, `Last-Modified` ou `Content-Length`; no `cadastro`, quando esses headers são insuficientes, baixa os dois CSVs em streaming e compara SHA-256 com o baseline. Toda execução é persistida, inclusive quando nenhuma mudança é encontrada.
2. **Análise Detalhada (Deep Analysis)**: Quando configurado (`AUTO_ANALYZE_ON_DETECT = True`) ou solicitado via API/CLI, o serviço baixa temporariamente o arquivo (ex: ZIP anual do DFP), extrai os members CSV e calcula hashes, cabeçalhos e linhas. Ele compara SHA-256 com o baseline canônico da última importação bem-sucedida. Mudanças reais resultam em `ready_for_ingestion`; equivalência de todos os members resulta em `content_unchanged`.
3. **Resolução Controlada**: `ready_for_ingestion` permite disparar ingestão. `content_unchanged` oferece a ação `update_reference`, que reconhece os metadados remotos sem Celery e finaliza como `reference_updated`. Descartar não atualiza referência e pode permitir nova detecção do mesmo artefato.

---

## 2. Configurações Disponíveis

As variáveis de ambiente configuráveis em `.env` que controlam o comportamento do serviço:

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `UPDATES_SERVICE_ENABLED` | `true` | Habilita/desabilita o serviço. |
| `UPDATES_SCANNER_STALE_AFTER_HOURS` | `36` | Janela sem conclusão após a qual a saúde do scanner passa a `stale`. |
| `AUTO_TRIGGER_UPDATES` | `false` | Se `true`, o Celery Beat agenda ingestões diretas por fonte/ano. Se `false`, agenda o scanner diário e a ingestão depende de aprovação manual. |
| `AUTO_ANALYZE_ON_DETECT` | `true` | Realiza a análise de membros (Deep Analysis) automaticamente assim que o scanner detecta mudanças remotas. |
| `SESSION_TIMEOUT_HOURS` | `24` | Tempo limite de validade de uma sessão de atualização criada pelo operador. |
| `TEMP_DIR` | `data/temp_updates` | Diretório temporário para downloads e extrações locais durante a análise profunda. |

`ANOS_INICIAIS_DFP`, `ANOS_INICIAIS_ITR` e variáveis equivalentes não definem a cobertura do scanner. Elas controlam bootstrap de ingestão. A vigilância diária acompanha automaticamente todos os anos que possuem `IngestionRun` bem-sucedida para cada fonte.

As tasks do Updates Service usam a fila `ingestion_control`. Elas são processadas pelos workers de ingestão e não dependem dos workers de materialização.

`GET /updates/scanner/status` expõe separadamente `scanner_enabled`, `schedule_enabled` e `schedule_status`. Este último usa somente execuções com `summary.trigger=scheduled`; uma checagem manual recente não encobre ausência ou atraso do job diário.

---

## 3. Modelo de Dados (Database Schema)

O serviço é suportado pelas seguintes tabelas no PostgreSQL:

### `pending_updates`
Armazena a raiz de cada alteração de ZIP/CSV detectada.
* `id` (UUID): Identificador único.
* `fonte` (String): Tipo da fonte (ex: `dfp`, `itr`, `cadastro`).
* `ano` (Integer, Opcional): Ano de referência do formulário.
* `status` (String): Estado atual (`change_detected`, `analysis_queued`, `analyzing`, `analysis_failed`, `ready_for_ingestion`, `triggered`, `ingestion_failed`, `ingested`, `content_unchanged`, `reference_updated`, `discarded`). `triggered` é transitório: o despacho foi aceito e ainda aguarda execução ou possui ingestão ativa. `ingested` somente é gravado após a run terminal bem-sucedida confirmar a promoção canônica. `ingestion_failed` representa falha terminal.
* `detection_timestamp` (DateTime): Quando a mudança foi identificada.
* `change_summary` (JSON, Opcional): Sumário geral das mudanças de membros.
* `last_successful_run_id` (UUID, Opcional): ID da IngestionRun originada após o disparo com sucesso.
* `current_run_id` e `current_execution_id` (UUID, Opcionais): correlação com trabalho ativo ou ainda pendente de confirmação; são limpos na resolução terminal.
* `last_failed_run_id` (UUID, Opcional): última run terminalmente falha correlacionada.
* `ingestion_task_id` (String, Opcional): identificador transitório da tarefa Celery; é limpo ao concluir ou falhar.
* `resolved_timestamp` (DateTime, Opcional): momento da resolução terminal; o simples aceite pelo Celery não preenche este campo.

Os campos derivados `content_changed` e `recommended_action` orientam consumidores sem exigir inferência a partir de contagens. `content_changed=false` só é emitido após comparação dos hashes dos members.

As leituras de `GET /updates/pending` e `GET /updates/pending/{id}` aplicam reparo idempotente aos registros legados comprováveis. Um item `triggered`, sem correlação atual e cujo `last_successful_run_id` aponta para uma run terminal bem-sucedida em `complete`, é promovido para `ingested`. Registros sem essa evidência permanecem inalterados.

### `pending_update_members`
Detalhes de cada membro CSV interno para arquivos compactados (ZIP).
* `member_name` (String): Nome do arquivo CSV membro (ex: `dfp_cia_aberta_dre_con_2025.csv`).
* `change_category` (String): Categoria da alteração (`added`, `removed`, `modified`, `unchanged`).
* `status` (String): Estado detalhado (`schema_changed`, `modified`, `unchanged`, `required_missing`).
* `current_row_count` (Integer): Linhas do arquivo novo.
* `previous_row_count` (Integer): Linhas da última ingestão bem-sucedida.

### `update_scan_runs`

Registra cada execução automática ou manual do scanner:

- `status`: `queued`, `running`, `completed` ou `failed`;
- `summary.trigger`: `scheduled` ou `manual`;
- `summary.coverage_status`: `complete` ou `degraded`;
- `summary.scanned_scopes`: quantidade de fontes/anos efetivamente sondados;
- `summary.changed_count`, `unchanged_count`, `inconclusive_count`, `error_count` e `skipped_count`;
- `summary.items`: um log por fonte/ano com decisão, motivo, URL, sondas utilizadas e resultado da análise de members.

Uma execução sem novidades é saudável quando `coverage_status=complete`, `changed_count=0`, `inconclusive_count=0` e `error_count=0`. `detected_count=0` isoladamente não prova que a checagem funcionou.

### `acknowledged_artifact_references`

Registra a referência remota confirmada para um artefato `content_unchanged`. Cada registro mantém:

- fonte, ano e URL remota;
- `ETag`, `Last-Modified` e tamanho reconhecidos;
- fingerprint dos hashes dos members;
- operador e instante da confirmação;
- `baseline_ingestion_run_id` que limita a validade da referência.

Esta tabela não substitui `IngestionFile` nem `SourceArtifactSnapshot`: esses registros continuam descrevendo exclusivamente o que foi ingerido.

## 3.1 Baseline canônico de comparação

O Updates Service compara members usando, por ordem de prioridade:

1. `SourceMemberSnapshot` da última run bem-sucedida da fonte
2. `IngestionFileMember` da mesma run, apenas como fallback de compatibilidade

O baseline esperado por member inclui:

- `member_sha256`
- `row_count`
- `header`
- `header_hash`

O `cadastro` agora persiste esse mesmo baseline canônico para `cad_cia_aberta.csv` e `cad_cia_estrang.csv`, alinhando sua análise de updates ao comportamento já usado pelas fontes anuais em ZIP.

Para o artefato anual principal, a referência é a última `IngestionRun` bem-sucedida que possui um `IngestionFile`. Execuções filhas por CSV não substituem esse ZIP como baseline. A decisão usa, em ordem, `ETag`, `Last-Modified` e tamanho. Quando a ingestão anterior não persistiu os headers HTTP, tamanho idêntico combinado com `Last-Modified` não posterior a `downloaded_at` confirma que o remoto não é mais novo; tamanho diferente ou modificação posterior identifica mudança. O histórico de scans nunca é usado como baseline canônico, pois estabilidade entre duas sondas não prova igualdade com o artefato ingerido.

### `update_sessions` e `update_session_items`
Usados para agrupar múltiplas atualizações sob um lote lógico de execução e validação.

---

## 4. Uso via CLI (Interface de Linha de Comando)

`POST /updates/pending/{id}/retry-ingestion` somente aceita atualizações em
`ingestion_failed` com `retryable=true`. Falhas não retentáveis usam
`next_action=inspect_error`. Conteúdo em `content_unchanged` continua oferecendo apenas
`acknowledge-reference`: equivalência é comprovada por SHA-256 dos members, nunca
por igualdade de contagem de linhas.

Para gerenciar o ciclo de atualizações direto no terminal do container (`cvm_api`):

```bash
# Executar a varredura remota imediatamente
python -m app.updates.cli scanner run

# Consultar saúde e cobertura da última varredura
python -m app.updates.cli scanner status

# Listar todas as atualizações detectadas
python -m app.updates.cli pending list

# Ver sumário e membros afetados de uma atualização específica
python -m app.updates.cli pending show <uuid-da-atualizacao>

# Forçar/executar a análise detalhada
python -m app.updates.cli pending analyze <uuid-da-atualizacao>

# Disparar a ingestão
python -m app.updates.cli pending trigger <uuid-da-atualizacao>

# Atualizar referência de um artefato com conteúdo inalterado
python -m app.updates.cli pending acknowledge-reference <uuid-da-atualizacao>

# Descartar uma atualização
python -m app.updates.cli pending discard <uuid-da-atualizacao>

# Disparar todas as atualizações no estado ready_for_ingestion
python -m app.updates.cli trigger-all
```

> **UX Benefício:** O comando CLI salva automaticamente a chave da última sessão criada em `data/temp_updates/.cli_session` para facilitar comandos subsequentes sem necessidade de colar UUIDs de sessões longas.
