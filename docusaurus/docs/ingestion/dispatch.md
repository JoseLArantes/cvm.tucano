---
title: Disparo de Sincronizacoes
sidebar_position: 2
---

# Disparo de Sincronizacoes

## Regras gerais

Todos os endpoints desta pagina:

- exigem token administrativo;
- respondem com `RespostaAgendamentoSincronizacao` ou `RespostaAgendamentoEmLote`;
- aceitam `force_reimport` nos cenarios de disparo;
- persistem uma `ExecucaoSincronizacao` em `agendada` antes de publicar a task Celery;
- fecham automaticamente o gate de materializacao enquanto a execucao estiver em `agendada`, `em_execucao` ou `aguardando_ingestao`;
- apenas enfileiram o trabalho pesado; o acompanhamento deve ser feito pelos endpoints de monitoramento.

O `id_tarefa` retornado e o mesmo valor persistido em `execucoes_sincronizacao.id_tarefa`.
Use esse identificador para cancelamento, auditoria e correlacao com logs Celery.

## `force_reimport`

Use `force_reimport=true` quando o objetivo for obrigar novo processamento do escopo inteiro.

Sem `force_reimport`, o lifecycle atual pode:

- encerrar como `sem_alteracao` quando o artefato remoto nao mudou;
- reaproveitar members por `member_sha256` em reruns anuais;
- limitar o trabalho aos members que realmente precisam voltar ao hot path.

## Disparo por fonte

### Cadastro

`POST /ingestion/sincronizacoes/cadastro`

Exemplo:

```bash
curl -X POST "http://localhost:8007/ingestion/sincronizacoes/cadastro?force_reimport=false" \
  -H "Authorization: Bearer <token-admin>"
```

### Fontes anuais

| Rota | Ano minimo |
| --- | --- |
| `POST /ingestion/sincronizacoes/dfp/{ano}` | `2010` |
| `POST /ingestion/sincronizacoes/itr/{ano}` | `2010` |
| `POST /ingestion/sincronizacoes/fre/{ano}` | `2010` |
| `POST /ingestion/sincronizacoes/fca/{ano}` | `2010` |
| `POST /ingestion/sincronizacoes/ipe/{ano}` | `2003` |
| `POST /ingestion/sincronizacoes/vlmo/{ano}` | `2018` |
| `POST /ingestion/sincronizacoes/cgvn/{ano}` | `2018` |

Exemplo:

```bash
curl -X POST "http://localhost:8007/ingestion/sincronizacoes/itr/2025?force_reimport=false" \
  -H "Authorization: Bearer <token-admin>"
```

## Disparo em lote anual

`POST /ingestion/sincronizacoes/tudo/{ano}`

Este endpoint agenda:

1. `cadastro`
2. `dfp`
3. `itr`
4. `fre`
5. `fca`
6. `ipe`
7. `vlmo`
8. `cgvn`

O ano usado nas fontes anuais e exatamente o valor do path.
Todas as execucoes do lote sao registradas como `agendada` antes do workflow ser enviado para o Celery.
Isso impede que materializacao continue iniciando novos chunks enquanto a ingestao ainda esta apenas na fila.

Exemplo:

```bash
curl -X POST "http://localhost:8007/ingestion/sincronizacoes/tudo/2025?force_reimport=false" \
  -H "Authorization: Bearer <token-admin>"
```

## Reprocessamento seletivo

`POST /ingestion/sincronizacoes/reprocessar-arquivo`

Use quando o escopo correto for um arquivo especifico, seja ZIP principal ou member CSV.

Exemplo de body:

```json
{
  "arquivo": "itr_cia_aberta_BPA_con_2026.csv",
  "ano": 2026,
  "force_reimport": true
}
```

Regras importantes:

- a validacao do nome do arquivo e case-insensitive;
- o nome canonico do member e preservado internamente;
- o replay isolado usa o artefato retido do escopo correspondente;
- para falha parcial de uma run anual, o caminho principal continua sendo o rerun anual da mesma fonte/ano.

## Preprocessamento manual em duas etapas

### Etapa 1 do cadastro

`POST /ingestion/sincronizacoes/pre-processar/cadastro`

### Etapa 1 de fonte anual

`POST /ingestion/sincronizacoes/pre-processar/{tipo_fonte}/{ano}`

Esta chamada baixa o artefato, extrai members, registra snapshots e deixa a execucao em `aguardando_ingestao`.

### Etapa 2 de uma execucao preprocessada

`POST /ingestion/sincronizacoes/{id_execucao}/ingerir`

Use apenas quando a execucao administrativa estiver em `aguardando_ingestao`.

Exemplo:

```bash
curl -X POST "http://localhost:8007/ingestion/sincronizacoes/6a31c7f8-1c89-4f3d-87db-7e6a8e196999/ingerir?force_reimport=false" \
  -H "Authorization: Bearer <token-admin>"
```

## Resposta de agendamento simples

```json
{
  "id_tarefa": "a37f0f88-44b9-4cff-9b0d-b826e4e8f367",
  "status": "agendada"
}
```

## Resposta de agendamento em lote

```json
{
  "status": "agendada",
  "tarefas": [
    {"tipo_fonte": "cadastro", "ano": null, "id_tarefa": "task-1"},
    {"tipo_fonte": "dfp", "ano": 2025, "id_tarefa": "task-2"}
  ]
}
```
