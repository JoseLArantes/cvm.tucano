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
- persistem o lote, a execução, a etapa na fila e a intenção de publicação antes de qualquer envio ao Celery;
- fecham automaticamente o gate de materializacao enquanto a execucao estiver em `agendada`, `em_execucao` ou `aguardando_ingestao`;
- apenas enfileiram o trabalho pesado; o acompanhamento deve ser feito pelos endpoints de monitoramento.

O `id_tarefa` retornado e persistido em `execucoes_sincronizacao.id_tarefa`. O `lote_id` identifica o pedido na fila.
Use ambos para correlacao; o acompanhamento da posição, etapa e motivo de espera fica em `GET /ingestion/queue`.

## Admissao da fila

O PostgreSQL guarda lotes, etapas, reservas e publicações pendentes. Um bloqueio global de linha serializa a seleção,
as mudanças de etapa, o cancelamento e o início efetivo do trabalho. A fila publica no Celery somente as etapas já
admitidas. Uma publicação repetida é inofensiva porque cada mensagem precisa apresentar o ID da etapa e o token de
reserva vigente.

Cadastro, preparação de ZIP e processamento de CSV compartilham `INGESTION_EXECUTION_SLOTS`. O chart deriva o
orçamento de `worker.replicaCount x worker.concurrency`; `ingestion.executionSlots` pode reduzir esse valor. Apenas
uma preparação de ZIP pode estar reservada ou em execução no cluster.

Quando uma vaga fica livre, a seleção prioriza CSVs prontos. O CSV de cabeçalho precede os membros dependentes. A
conclusão de uma etapa aplica a transição e registra novos CSVs elegíveis antes de liberar sua reserva. Se nenhum CSV
estiver pronto, o ZIP elegível mais antigo pode ocupar a próxima vaga. Antes de iniciar um ZIP, o worker verifica a
fila novamente sob o mesmo bloqueio; se um CSV tiver sido liberado nesse intervalo, a tentativa volta à fila.

`GET /ingestion/files?atividade=na_fila` mostra execução sem worker iniciado. `atividade=em_processamento` passa a
representar somente trabalho que um worker assumiu. Os status `reserved` e `transition_pending` permanecem visíveis
em `/ingestion/queue` e `/ingestion/operations`.

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
As oito execucoes sao registradas no mesmo lote, na ordem acima, e retornadas com `lote_id`. Nenhuma consulta à CVM,
download ou extração ocorre antes de uma vaga ser admitida. O cadastro ocupa a vaga primeiro. As fontes anuais já
ficam registradas na fila e avançam conforme capacidade, sem depender de publicação feita por um callback posterior.

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
  "status": "agendada",
  "lote_id": "3c67c684-2b82-4cdf-94f2-c6d7f1dabcde"
}
```

## Resposta de agendamento em lote

```json
{
  "status": "agendada",
  "lote_id": "3c67c684-2b82-4cdf-94f2-c6d7f1dabcde",
  "tarefas": [
    {"tipo_fonte": "cadastro", "ano": null, "id_tarefa": "task-1", "lote_id": "3c67c684-2b82-4cdf-94f2-c6d7f1dabcde"},
    {"tipo_fonte": "dfp", "ano": 2025, "id_tarefa": "task-2", "lote_id": "3c67c684-2b82-4cdf-94f2-c6d7f1dabcde"}
  ]
}
```

## Telemetria da fila

`GET /ingestion/queue?pagina=1&tamanho_pagina=25` retorna lotes por ordem de chegada. Cada lote contém `lote_id`,
posição, fontes e anos, progresso agregado, motivo de espera e etapas. O status `queued` ainda não foi assumido;
`reserved` aguarda confirmação de início pelo worker; `running` já iniciou; `transition_pending` aguarda aplicação
da transição persistida; `waiting_manual` aguarda confirmação explícita e não ocupa vaga.

`GET /ingestion/operations` inclui `ingestion_queue` com profundidade, idade do pedido mais antigo, capacidade,
preparações ZIP ativas e vagas reservadas ou em execução.

## Paralelismo e controle de fila

O chart Helm calcula `INGESTION_EXECUTION_SLOTS` como `worker.replicaCount x worker.concurrency`. `ingestion.executionSlots` define um limite menor opcional; valores maiores que o pool são limitados ao pool configurado.

O Celery usa `worker_prefetch_multiplier=1` e `-Ofair`. Para recursos escassos, reduza o número de réplicas, a concorrência ou `ingestion.executionSlots`. Para ampliar o processamento, aumente o pool e acompanhe a capacidade do PostgreSQL, pois cada processo de worker mantém seu próprio pool de conexões.

Ingestao consome `ingestion` e `ingestion_control`; materializacao consome somente `analise_materializacao` em workers separados, configurados por `materializationWorker.replicaCount` e `materializationWorker.concurrency`. O admission gate impede o inicio de novos chunks de materializacao durante ingestao ativa ou pausa manual.
