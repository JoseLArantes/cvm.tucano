---
title: Administracao da Ingestao - Visao Geral
sidebar_position: 1
---

# Administracao da Ingestao - Visao Geral

## Visão Geral

Os endpoints de **Administracao da Ingestao** permitem que operadores de backoffice, auditores e gerentes de compliance disparem, monitorem, cancelem e corrijam sincronizacoes de dados da CVM. Todos os endpoints desta secao exigem **permissao administrativa** (`is_admin=true` ou token de sistema).

## Endpoints Disponíveis

### Disparo de Sincronizações

| Método | Rota | Descrição |
|--------|------|-----------|
| `POST` | `/ingestion/sincronizacoes/cadastro` | Disparar sincronização do cadastro |
| `POST` | `/ingestion/sincronizacoes/dfp/{ano}` | Disparar sincronização DFP |
| `POST` | `/ingestion/sincronizacoes/itr/{ano}` | Disparar sincronização ITR |
| `POST` | `/ingestion/sincronizacoes/fre/{ano}` | Disparar sincronização FRE |
| `POST` | `/ingestion/sincronizacoes/fca/{ano}` | Disparar sincronização FCA |
| `POST` | `/ingestion/sincronizacoes/ipe/{ano}` | Disparar sincronização IPE |
| `POST` | `/ingestion/sincronizacoes/vlmo/{ano}` | Disparar sincronização VLMO |
| `POST` | `/ingestion/sincronizacoes/cgvn/{ano}` | Disparar sincronização CGVN |
| `POST` | `/ingestion/sincronizacoes/tudo/{ano}` | Disparar todas as fontes para um ano |
| `POST` | `/ingestion/sincronizacoes/reprocessar-arquivo` | Reprocessamento seletivo por arquivo |

### Execução em Duas Fases

| Método | Rota | Descrição |
|--------|------|-----------|
| `POST` | `/ingestion/sincronizacoes/pre-processar/cadastro` | Fase 1 do cadastro |
| `POST` | `/ingestion/sincronizacoes/pre-processar/{tipo_fonte}/{ano}` | Fase 1 de fonte anual |
| `POST` | `/ingestion/sincronizacoes/{id_execucao}/ingerir` | Fase 2 de execução pré-processada |

### Cancelamento

| Método | Rota | Descrição |
|--------|------|-----------|
| `POST` | `/ingestion/sincronizacoes/cancelar` | Cancelar sincronização em andamento |

### Monitoramento

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/ingestion/sincronizacoes` | Listar execuções de sincronização |
| `GET` | `/ingestion/sincronizacoes/{id_execucao}` | Detalhar execução |
| `GET` | `/ingestion/runs` | Listar runs do pipeline |
| `GET` | `/ingestion/runs/{run_id}` | Detalhar run |
| `GET` | `/ingestion/dashboard` | Dashboard consolidado |
| `GET` | `/ingestion/alteracoes` | Histórico de alterações |

### Quarentena e Replay

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/ingestion/quarentena` | Listar itens em quarentena |
| `GET` | `/ingestion/quarentena/resumo` | Resumo analítico da quarentena |
| `POST` | `/ingestion/replay/quarentena` | Reprocessar quarentena |
| `POST` | `/ingestion/runs/{run_id}/replay` | Reprocessar run completa |

### Identidade e Auditoria

| Método | Rota | Descrição |
|--------|------|-----------|
| `POST` | `/ingestion/identity/rebuild` | Reconstruir grafo de identidade |
| `GET` | `/ingestion/fontes` | Listar fontes registradas |
| `GET` | `/ingestion/fontes/{fonte}` | Detalhar fonte |
| `POST` | `/ingestion/fontes/auditar` | Auditar fontes |

---

## Parâmetro Universal: `force_reimport`

Todos os endpoints de disparo aceitam o parâmetro `?force_reimport=true`:

| Valor | Comportamento |
|-------|---------------|
| `false` (padrão) | Usa otimização por hash: se o hash do arquivo já foi processado com sucesso, o reprocessamento é pulado |
| `true` | Força re-ingestão total: ignora checagem de hash, faz limpeza atômica de dados antigos e re-executa a ingestão |

### Quando usar `force_reimport=true`

- Após correção de bug no normalizador
- Após aplicação de novas regras de reparo
- Quando o pipeline v1 legado precisa ser migrado
- Para garantir idempotência após falhas parciais

### Quando NÃO usar

- Sincronizações rotineiras (desperdiça recursos)
- Quando o hash já indica processamento bem-sucedido

---

## Status de Execução

| Status | Descrição |
|--------|-----------|
| `agendada` | Task enfileirada no Celery |
| `em_execucao` | Processamento ativo |
| `aguardando_ingestao` | Fase 1 concluída, aguardando Fase 2 |
| `sucesso` | Ingestão finalizada sem erros |
| `sucesso_com_alerta` | Concluída com alertas (ex: erros de schema) |
| `sem_alteracao` | Arquivo fonte não mudou |
| `skipped` | Ignorado por hash idêntico |
| `falha` | Erro durante processamento |
| `falha_qualidade` | Violação do quality gate |
| `cancelada` | Abortada manualmente |

---

## Fases do Pipeline

| Fase | Descrição |
|------|-----------|
| `acquire` | Sondagem remota + download do arquivo |
| `stage` | Parsing CSV → `ingestion_rows` |
| `validate` | Validação de header e schema |
| `resolve` | Resolução de identidade da companhia |
| `promote` | Escrita nas tabelas de domínio |
| `reconcile` | Remoção de linhas obsoletas |
| `complete` | Pipeline finalizado |

---

## Arquitetura em Duas Fases

O pipeline é dividido em duas fases para garantir resiliência:

### Fase 1: Pré-processamento (`acquire` + `stage`)

1. **Sondagem remota** (CKAN/HEAD) para evitar downloads desnecessários
2. **Download com SHA-256** on-the-fly
3. **Extração de membros** do ZIP
4. **Persistência de payloads** brutos para self-healing
5. **Change tracking** estrutural

### Fase 2: Ingestão (`promote` + `reconcile`)

1. **Stage** com COPY protocol (5.000 linhas/chunk)
2. **Validação** de schema
3. **Normalização** e resolução de identidade
4. **Promoção** resiliente (`safe_promote_chunk`)
5. **Reconcile** set-based

> **Self-healing:** Os payloads brutos são persistidos em `IngestionFileMemberPayload`. Se um worker reiniciar entre fases, o CSV pode ser reconstruído do banco sem redownload.

---

## Próximos Passos

- [Disparo de Sincronizações](./dispatch.md) - Como disparar sincronizações
- [Monitoramento](./monitoring.md) - Como acompanhar execuções
- [Quarentena e Replay](./quarantine.md) - Como tratar erros
- [Identidade e Auditoria](./identity.md) - Reconstrução e auditoria
