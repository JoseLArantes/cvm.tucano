---
title: Materializacoes Analiticas
sidebar_position: 9
---

# Materializacoes Analiticas

Esta pagina documenta a parte meta e operacional da superficie `/analise`.

Aqui ficam endpoints usados pelo proprio sistema para:

- persistir camada canonica
- coordenar campanhas
- controlar chunks
- observar workers e filas
- tratar retries operacionais
- executar self-healing

Esse bloco nao e a documentacao principal para leitura de dado financeiro final. Ele explica processos internos e operacao do backend.

## Endpoints

| Metodo | Rota | Descricao |
| --- | --- | --- |
| `GET` | `/analise/materializacoes` | Listagem de execucoes de materializacao analitica |
| `GET` | `/analise/materializacoes/monitoramento` | Snapshot operacional da fila e dos workers de materializacao |
| `GET` | `/analise/materializacoes/controle` | Estado atual do gate de materializacao |
| `POST` | `/analise/materializacoes/controle/pause` | Pausa manual do gate de materializacao |
| `POST` | `/analise/materializacoes/controle/resume` | Retorno ao modo automatico do gate |
| `POST` | `/analise/materializacoes/recuperar-stale` | Recuperacao imediata de chunks stale |
| `POST` | `/analise/materializacoes/campanhas/{campanha_id}/recuperar` | Recuperacao imediata de chunks stale de uma campanha |
| `POST` | `/analise/materializacoes/campanhas/{campanha_id}/reativar` | Reativacao delegada de campanha presa ou com chunk stale |
| `POST` | `/analise/materializacoes/recuperacao/trigger` | Sweep delegado e limitado de campanhas pendentes recuperaveis |
| `GET` | `/analise/materializacoes/{execucao_id}` | Detalhe de uma execucao de materializacao |

## Contexto operacional

A materializacao canonica usa:

- fila dedicada
- campanhas agregadas
- chunks com lease persistido
- concorrencia independente por campanha e por chunk
- dispatcher de campanhas pendentes
- gate de admissao
- retries operacionais
- self-healing para campanhas presas ou chunks stale

Por padrao:

- campanhas automaticas e fluxos padrao nao incluem companhias com `situacao_registro=CANCELADA`
- companhias canceladas so entram com override explicito em disparos pontuais

Controles de concorrencia:

- `ANALISE_MATERIALIZACAO_MAX_ACTIVE_CAMPAIGNS`: limita quantas campanhas distintas podem ficar em `running` ao mesmo tempo
- `ANALISE_MATERIALIZACAO_MAX_ACTIVE_CHUNKS_PER_CAMPAIGN`: limita quantos chunks da mesma campanha podem ficar ativos em paralelo

Semantica importante:

- aumentar apenas `MAX_ACTIVE_CAMPAIGNS` nao paraleliza uma campanha unica muito grande
- para processar varias companhias em paralelo dentro da mesma campanha, e preciso aumentar `MAX_ACTIVE_CHUNKS_PER_CAMPAIGN`

## `GET /analise/materializacoes`

Lista execucoes da camada canonica com status, modo de materializacao, janela efetivamente recomposta, progresso parcial, tempo decorrido, estimativa de conclusao e vinculo opcional com campanhas, itens e chunks de materializacao.

Cada execucao pode ser:

- `full`: recompõe toda a linha do tempo canonica da companhia/escopo
- `incremental`: recompõe apenas o sufixo a partir de `invalidated_from`, preservando o prefixo canonico anterior

Regra operacional atual:

- campanhas automaticas e fluxos padrao excluem companhias com `situacao_registro=CANCELADA`
- se uma execucao pontual for disparada sem override para uma companhia cancelada, a execucao e registrada e concluida sem produzir revisoes, com sinalizacao de skip operacional no `summary`
- a materializacao pontual de canceladas so ocorre quando o operador informa explicitamente o override de inclusao

Parametros:

| Nome | Tipo | Descricao |
| --- | --- | --- |
| `status` | string | `running`, `success` ou `failed` |
| `codigo_cvm` | integer | Filtra por companhia |
| `escopo` | string | `consolidated` ou `individual` |
| `source` | string | Origem do disparo, como `post_ingestion`, `manual` ou `backfill` |
| `campanha_id` | string | Filtra por campanha de materializacao |
| `pagina` | integer | Pagina da listagem |
| `tamanho_pagina` | integer | Quantidade de itens por pagina |

```bash
curl -X GET "http://localhost:8007/analise/materializacoes?status=running" \
  -H "Authorization: Bearer <token>"
```

## `GET /analise/materializacoes/monitoramento`

Retorna um snapshot operacional das filas e campanhas de materializacao.

Esse endpoint e a principal fonte para frontend operacional.

Ele combina:

- execucoes `running` persistidas no banco
- divisao entre `full` e `incremental`
- tasks ativas, reservadas e agendadas nos workers Celery
- estado atual do gate de admissao
- campanhas pendentes e em andamento
- campanhas em recuperacao por stale
- campanhas pendentes recuperaveis
- campanhas presas sem despacho inicial
- itens pendentes, running, success, failed e skipped
- chunks `queued`, `running` e `stale`
- previews dos itens correntes, da fila pendente e de chunks stale

```bash
curl -X GET "http://localhost:8007/analise/materializacoes/monitoramento" \
  -H "Authorization: Bearer <token>"
```

Campos operacionais principais:

- `gate.status`
- `gate.reason_code`
- `waiting_for_gate_campaigns`
- `recovering_campaigns`
- `recoverable_pending_campaigns`
- `recoverable_campaign_ids`
- `undispatched_stuck_campaigns`
- `last_pending_recovery_sweep_at`
- `last_pending_recovery_sweep_summary`
- `queued_chunks`
- `running_chunks`
- `stale_chunks`
- `stale_item_count`
- `pending_recovery_active_tasks`
- `campaigns[].active_chunks`
- `campaigns[].active_chunk_ids_preview`

Semantica importante:

- `recoverable_pending_campaigns` conta campanhas `pending` realmente elegiveis para retry naquele instante
- campanhas ja reenfileiradas entram temporariamente em `requeued` e saem desse contador ate o retry ser consumido ou a campanha voltar a ficar presa
- `stale_chunks`, `stale_item_count` e `stale_chunk_preview` representam apenas stale ainda acionavel no snapshot
- chunks historicos ja marcados como `stale` em campanhas concluidas nao entram mais nesses contadores nem no preview
- `campaigns[].active_chunk_id` continua existindo como identificador representativo de um dos chunks ativos
- `campaigns[].active_chunks` e `campaigns[].active_chunk_ids_preview` devem ser usados quando a UI precisar refletir concorrencia intra-campanha
- com o gate em `red`, o backend bloqueia tambem o dispatcher e o reenfileiramento de campanhas; a UI pode continuar vendo campanhas `pending`, mas nao deve esperar progresso ate o gate voltar a `green`

## `GET /analise/materializacoes/controle`

Retorna o estado consolidado do gate de materializacao e do modo manual persistido.
As filas continuam isoladas: ingestao usa `celery` e materializacao usa `analise_materializacao`.

## `POST /analise/materializacoes/controle/pause`

Ativa pausa manual. Novos chunks deixam de iniciar, mas a companhia ja em processamento termina antes da pausa efetiva.

Parametros:

| Nome | Tipo | Descricao |
| --- | --- | --- |
| `reason` | string | Motivo textual opcional para a pausa manual |

```bash
curl -X POST "http://localhost:8007/analise/materializacoes/controle/pause?reason=janela-de-carga" \
  -H "Authorization: Bearer <token>"
```

## `POST /analise/materializacoes/controle/resume`

Remove a pausa manual e devolve o gate ao modo automatico. Se ainda houver ingestao ativa, o gate continua vermelho por `INGESTION_ACTIVE`.
Execucoes apenas `agendada` ou `cancelada` nao fecham o gate; o bloqueio automatico vale apenas para ingestao realmente em `em_execucao`.
Enquanto o gate estiver vermelho, o backend nao deve iniciar novas tasks efetivas de dispatcher, campanha, chunk ou materializacao direta por companhia.

## `POST /analise/materializacoes/recuperar-stale`

Executa a recuperacao imediata de chunks com lease expirado e ja classificados como stale pelo backend. Os itens ainda nao concluidos retornam para `pending` e a campanha volta a poder progredir.

Quando usar:

- use somente para operacao administrativa de baixo nivel
- use quando houver necessidade de limpar tecnicamente chunks stale em lote, mesmo sem passar pela classificacao por campanha
- nao use este endpoint como acao primaria de frontend para retry operacional normal

Autorizacao:

- requer token de sistema ou usuario admin

Semantica importante:

- atua no nivel tecnico de chunk, nao no nivel de decisao operacional por campanha
- pode afetar multiplas campanhas
- reenfileira campanhas afetadas depois da recuperacao tecnica
- `200` nao significa que houve recuperacao; confirme por `recovered_chunks` e `affected_campaigns`

Retorna:

- `recovered_chunks`
- `recovered_items`
- `affected_campaigns`
- `chunk_ids`

## `POST /analise/materializacoes/campanhas/{campanha_id}/recuperar`

Executa a mesma recuperacao, mas limitada a uma campanha especifica.

Quando usar:

- use somente para operacao administrativa de baixo nivel
- use quando o operador ja sabe a `campanha_id` e quer limpar apenas os chunks stale daquela campanha
- nao use este endpoint como acao primaria de frontend para retry operacional normal; prefira `.../reativar`

Autorizacao:

- requer token de sistema ou usuario admin

Semantica importante:

- atua no nivel tecnico de chunk
- nao substitui a classificacao operacional da campanha
- `200` nao significa que houve recuperacao; confirme por `recovered_chunks` e `affected_campaigns`

## `POST /analise/materializacoes/campanhas/{campanha_id}/reativar`

Endpoint operacional delegado para reativar uma campanha especifica sem exigir acesso administrativo amplo.

Autenticacao:

- aceita token de sistema (`TUCANO_CVM_TOKEN`)
- aceita usuario com `is_admin=true`
- aceita usuario com `pode_operar_materializacao=true`

Estados tratados:

- `STALE_CHUNK`: executa recuperacao de chunks stale e reenfileira a campanha
- `PENDING_UNDISPATCHED`: reenfileira a campanha quando ela esta pendente, com itens pendentes, sem chunk ativo, sem execucao ativa e sem bloqueio operacional
- `WAITING_FOR_GATE`: devolve `noop`
- `WAITING_FOR_SLOT`: devolve `noop`
- `CHUNK_IN_PROGRESS`: devolve `noop`
- `NO_PENDING_ITEMS`: devolve `noop`

Contrato de resposta:

- `status`
- `reason_code`
- `affected_campaigns`
- `requeued_campaigns`
- `recovered_chunks`
- `recovered_items`
- `dispatcher_enqueued`
- `triggered_at`

Semantica importante:

- a operacao e limitada a campanha informada
- a operacao e idempotente do ponto de vista operacional
- a operacao nao modifica o gate e nao altera limites de concorrencia
- o worker de campanha tambem tenta recuperar chunks stale inline antes de cair no estado de espera
- quando a campanha e reenfileirada, o backend a registra temporariamente como `requeued`; durante essa janela, `recoverable_pending_campaigns` e `recoverable_campaign_ids` deixam de trata-la como pendencia recuperavel

## `POST /analise/materializacoes/recuperacao/trigger`

Executa um sweep limitado sobre campanhas pendentes para self-healing operacional delegado.

Autenticacao:

- aceita token de sistema (`TUCANO_CVM_TOKEN`)
- aceita usuario com `is_admin=true`
- aceita usuario com `pode_operar_materializacao=true`

Comportamento:

- inspeciona somente campanhas `pending`
- respeita `ANALISE_MATERIALIZACAO_PENDING_RECOVERY_MAX_CAMPAIGNS`
- respeita `ANALISE_MATERIALIZACAO_PENDING_RECOVERY_MAX_REQUEUES`
- considera a idade minima `ANALISE_MATERIALIZACAO_PENDING_RECOVERY_MIN_AGE_SECONDS` para `PENDING_UNDISPATCHED`
- pode recuperar `STALE_CHUNK`
- pode reenfileirar `PENDING_UNDISPATCHED`
- nao forca progresso quando o motivo real e `WAITING_FOR_GATE`, `WAITING_FOR_SLOT` ou `CHUNK_IN_PROGRESS`

Campos adicionais da resposta:

- `scanned_campaigns`
- `recoverable_campaigns`

Semantica importante:

- este endpoint dispara uma varredura limitada, nao um requeue irrestrito
- o resultado tambem alimenta `last_pending_recovery_sweep_at` e `last_pending_recovery_sweep_summary` no monitoramento
- use este endpoint quando a UI nao souber qual campanha esta presa ou quiser oferecer acao global de "tentar recuperar pendencias"

## Como escolher o endpoint

| Endpoint | Publico esperado | Escopo | Quando usar | Quando nao usar |
| --- | --- | --- | --- | --- |
| `POST /analise/materializacoes/campanhas/{campanha_id}/reativar` | operador delegado ou admin | uma campanha | a UI conhece a campanha presa e quer retry operacional suportado | nao use para limpeza tecnica em lote |
| `POST /analise/materializacoes/recuperacao/trigger` | operador delegado ou admin | sweep limitado | a UI quer varrer campanhas `pending` sem saber qual esta presa | nao use como substituto de observabilidade |
| `POST /analise/materializacoes/recuperar-stale` | admin | lote tecnico | manutencao operacional administrativa de chunks stale | nao use como botao padrao de frontend |
| `POST /analise/materializacoes/campanhas/{campanha_id}/recuperar` | admin | uma campanha, nivel tecnico | manutencao administrativa quando a campanha ja e conhecida | nao use como retry operacional padrao do usuario |

## `GET /analise/materializacoes/{execucao_id}`

Retorna o detalhe de uma execucao especifica, incluindo `summary` bruto persistido pela materializacao para auditoria operacional, o modo da execucao (`full` ou `incremental`), o cutoff `invalidated_from` quando aplicavel, os contadores de revisoes inseridas/encerradas/removidas e os vinculos opcionais `campanha_id`, `campanha_item_id`, `chunk_execucao_id`, `queue_name` e `position_in_chunk`.

Quando uma companhia estiver com `situacao_registro=CANCELADA` e nao houver override explicito de inclusao, o `summary` pode trazer:

- `skipped_reason=COMPANHIA_CANCELADA`
- `company_status=CANCELADA`
- contadores de revisoes em zero
