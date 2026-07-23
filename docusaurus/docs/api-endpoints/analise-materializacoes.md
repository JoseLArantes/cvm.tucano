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
| `GET` | `/analise/materializacoes/companhias/{codigo_cvm}/status` | Status de materializacao por companhia e escopo |
| `POST` | `/analise/materializacoes/companhias/{codigo_cvm}/repair` | Repair focado de materializacao por companhia, escopo e períodos |
| `GET` | `/analise/materializacoes/monitoramento` | Snapshot operacional da fila e dos workers de materializacao |
| `GET` | `/analise/materializacoes/controle` | Estado atual do gate de materializacao |
| `POST` | `/analise/materializacoes/controle/pause` | Pausa manual do gate de materializacao |
| `POST` | `/analise/materializacoes/controle/resume` | Retorno ao modo automatico do gate |
| `POST` | `/analise/materializacoes/recuperar-stale` | Recuperacao imediata de chunks stale |
| `POST` | `/analise/materializacoes/campanhas/{campanha_id}/recuperar` | Recuperacao imediata de chunks stale de uma campanha |
| `POST` | `/analise/materializacoes/campanhas/{campanha_id}/reativar` | Reativacao delegada de campanha presa ou com chunk stale |
| `POST` | `/analise/materializacoes/recuperacao/trigger` | Sweep delegado e limitado de campanhas pendentes recuperaveis |
| `GET` | `/analise/materializacoes/{execucao_id}` | Detalhe de uma execucao de materializacao |
| `POST` | `/analise/materializacoes/{execucao_id}/reconcile` | Reconciliação terminal individual, idempotente e auditável |

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
| `materialization_mode` | string | `full` ou `incremental` |
| `operational_state` | string | Filtra pela classificação operacional derivada |
| `has_action_required` | boolean | Filtra pela existência de ação autorizada |
| `started_from` | datetime | Limite inicial inclusivo em ISO-8601 |
| `started_to` | datetime | Limite final inclusivo em ISO-8601 |
| `ordenar` | string | `started_at:desc`, `started_at:asc`, `updated_at:desc` ou `updated_at:asc` |
| `pagina` | integer | Pagina da listagem |
| `tamanho_pagina` | integer | Quantidade de itens por pagina |

```bash
curl -X GET "http://localhost:8007/analise/materializacoes?status=running" \
  -H "Authorization: Bearer <token>"
```

O resumo paginado preserva `running`, `success` e `failed` e acrescenta `status_counts` e `operational_counts` para exatamente os mesmos filtros aplicados.

## `GET /analise/materializacoes/companhias/{codigo_cvm}/status`

Retorna o status consolidado de materializacao para uma companhia em um escopo societario.

Esse endpoint e orientado a consumidores desacoplados que precisam renderizar um sinal simples por companhia, sem consultar diretamente campanhas, chunks e execucoes. Ele combina:

- a revisao canonica atual da companhia e escopo;
- a ultima execucao de materializacao conhecida;
- eventual item `pending` ou `running` de campanha ativa;
- a lista de anos fiscais anuais `FY` presentes na revisao canonica corrente.

Quando ainda nao existe revisao canonica, o backend tenta inferir um ano a partir de `active_item.invalidated_from` ou da ultima execucao. Se tambem nao houver esse dado, `anos` fica vazio e o campo raiz `status` indica `missing`.

Parametros:

| Nome | Tipo | Descricao |
| --- | --- | --- |
| `codigo_cvm` | integer | Companhia consultada |
| `escopo` | string | `consolidated` ou `individual`; padrao `consolidated` |

```bash
curl -X GET "http://localhost:8007/analise/materializacoes/companhias/9512/status?escopo=consolidated" \
  -H "Authorization: Bearer <token>"
```

Campos principais:

| Campo | Tipo | Descricao |
| --- | --- | --- |
| `codigo_cvm` | integer | Companhia consultada |
| `escopo` | string | Escopo societario consultado |
| `status` | string | Estado consolidado para companhia/escopo: `missing`, `pending`, `queued`, `running`, `success`, `failed`, `stale`, `skipped`, `partial` ou `unknown` |
| `coverage_complete` | boolean | Cobertura da execucao mais relevante, quando houver |
| `latest_execution` | object | Ultima execucao conhecida no mesmo formato resumido de `/analise/materializacoes` |
| `active_item` | object | Item ativo ou pendente de campanha, quando houver |
| `anos` | array | Status por ano fiscal anual `FY` |
| `periodos_detalhe` | array | Detalhe por período canônico conhecido |
| `dados` | array | Alias de `anos` |
| `periodos` | array | Alias de `anos` |
| `materializacoes` | array | Alias de `anos` |
| `status_por_ano` | object | Mapa de ano fiscal para item de status |
| `generated_at` | string | Momento de geracao do snapshot |
| `updated_at` | string | Ultima atualizacao conhecida entre execucao, item e revisao canonica |

Cada item de `anos` contem:

| Campo | Tipo | Descricao |
| --- | --- | --- |
| `ano` | integer | Ano fiscal |
| `period_id` | string | Período canônico principal associado ao ano |
| `status` | string | Estado derivado para o ano |
| `escopo` | string | Escopo societario |
| `has_context_revision` | boolean | Existe revisão de contexto canônica cobrindo o período |
| `has_fact_revision` | boolean | Existe ao menos uma revisão de fato canônica para o período |
| `metrics_count` | integer | Quantidade de métricas disponíveis no período |
| `unavailable_count` | integer | Quantidade de indisponibilidades registradas no período |
| `coverage_complete` | boolean | Cobertura da execucao associada |
| `materialized_at` | string | Momento de conclusao da materializacao associada |
| `started_at` | string | Inicio da execucao ou item associado |
| `finished_at` | string | Fim da execucao ou item associado |
| `updated_at` | string | Ultima atualizacao operacional associada |
| `execution_id` | string | Execucao de materializacao associada |
| `materialization_execution_id` | string | Alias de `execution_id` |
| `calculation_version` | string | Versao do motor analitico |
| `source` | string | Origem do disparo |
| `materialization_mode` | string | `full` ou `incremental` |
| `message` | string | Mensagem operacional ou erro de item |

Cada item de `periodos_detalhe` contem `period_id`, `ano`, `periodicidade`, `base_periodo`, `escopo`, `has_context_revision`, `has_fact_revision`, `metrics_count`, `unavailable_count` e `coverage_complete`.

## `POST /analise/materializacoes/companhias/{codigo_cvm}/repair`

Cria uma campanha pequena de materializacao para recompor a camada canonica de uma companhia e escopo a partir de períodos específicos.

Autenticacao:

- aceita token de sistema (`TUCANO_CVM_TOKEN`)
- aceita usuario com `is_admin=true`
- aceita usuario com `pode_operar_materializacao=true`

Payload:

```json
{
  "escopo": "consolidated",
  "period_ids": ["FY2021", "FY2022", "FY2023"],
  "metricas": ["receita_liquida", "ebitda", "lucro_liquido"],
  "mode": "missing_only"
}
```

Semantica:

- `period_ids` define quais períodos serão avaliados para repair
- `metricas` valida e explica a solicitação, mas a recomposição real continua sendo por companhia, escopo e janela de conhecimento
- `mode=missing_only` aceita períodos com dado bruto e lacuna canônica/materializada
- o backend deriva `invalidated_from` pelo documento CVM mais antigo que suporta os períodos aceitos
- a campanha criada usa `source=manual_repair` e `chunk_size=1`
- se o gate estiver vermelho, a campanha fica pendente e a resposta retorna `gate_status=red`

Resposta:

| Campo | Tipo | Descricao |
| --- | --- | --- |
| `status` | string | `accepted`, `partial` ou `rejected` |
| `campanha_id` | string | Campanha criada, quando houver períodos aceitos |
| `accepted_items` | array | Períodos aceitos para repair |
| `rejected_items` | array | Períodos rejeitados com motivo acionável |
| `reason_code` | string | Motivo consolidado da resposta |
| `dispatcher_enqueued` | boolean | Indica se o orquestrador foi enfileirado |
| `gate_status` | string | `green` ou `red` no momento da solicitação |
| `triggered_at` | string | Momento da criação do repair |

Cada item de `accepted_items` e `rejected_items` contém `period_id`, `accepted`, `reason_code`, `reason_message`, `remediation_code` e `remediation_message`.

Rejeições comuns:

- `RAW_DATA_MISSING`: ingerir a fonte CVM antes do repair
- `METRIC_MAPPING_MISSING`: registrar ou corrigir o mapeamento da métrica
- `MATERIALIZATION_RUNNING`: aguardar a campanha ativa concluir
- `NO_MISSING_METRICS`: o período já possui as métricas solicitadas materializadas

## `GET /analise/materializacoes/monitoramento`

Retorna um snapshot operacional das filas e campanhas de materializacao.

Esse endpoint é uma fonte genérica para consoles administrativos, CLIs, automações e serviços externos.

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
- contagens por `operational_state`
- execuções em `completion_pending`, `stalled_recoverable` e `stalled_unrecoverable`
- IDs que exigem ação operacional

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
- `operational_counts`
- `completion_pending_execution_ids`
- `stalled_unrecoverable_execution_ids`
- `action_required_execution_ids`

Semantica importante:

- `recoverable_pending_campaigns` conta campanhas `pending` realmente elegiveis para retry naquele instante
- campanhas ja reenfileiradas entram temporariamente em `requeued` e saem desse contador ate o retry ser consumido ou a campanha voltar a ficar presa
- `stale_chunks`, `stale_item_count` e `stale_chunk_preview` representam apenas stale ainda acionavel no snapshot
- chunks historicos ja marcados como `stale` em campanhas concluidas nao entram mais nesses contadores nem no preview
- `campaigns[].active_chunk_id` continua existindo como identificador representativo de um dos chunks ativos
- `campaigns[].active_chunks` e `campaigns[].active_chunk_ids_preview` permitem refletir concorrencia intra-campanha
- com o gate em `red`, o backend bloqueia tambem o dispatcher e o reenfileiramento de campanhas; consumidores podem continuar vendo campanhas `pending`, mas nao devem esperar progresso ate o gate voltar a `green`
- a deteccao detalhada de campanhas pendentes recuperaveis no snapshot e limitada por `ANALISE_MATERIALIZACAO_PENDING_RECOVERY_MAX_CAMPAIGNS`; o sweep de recuperacao continua sendo a rotina responsavel por varrer e reativar o backlog em lotes
- cada preview de execução inclui `operational_state`, `reason_code`, `liveness`, `completion`, `recovery` e `allowed_actions`; o booleano legado `stalled` não é usado isoladamente para autorizar operações

## `GET /analise/materializacoes/controle`

Retorna o estado consolidado do gate de materializacao e do modo manual persistido.
As filas continuam isoladas: ingestao usa `ingestion` e `ingestion_control`; materializacao usa `analise_materializacao`.

Status de ingestao que fecham o gate automatico:

- `agendada`
- `em_execucao`
- `aguardando_ingestao`

Status finais, como `sucesso`, `sem_alteracao`, `skipped`, `falha` e `cancelada`, nao fecham o gate.

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
Execucoes `agendada`, `em_execucao` ou `aguardando_ingestao` fecham o gate; execucoes finais como `cancelada` e `falha` nao fecham.
Enquanto o gate estiver vermelho, o backend nao deve iniciar novas tasks efetivas de dispatcher, campanha, chunk ou materializacao direta por companhia.

## `POST /analise/materializacoes/recuperar-stale`

Executa a recuperacao imediata de chunks com lease expirado e ja classificados como stale pelo backend. Os itens ainda nao concluidos retornam para `pending` e a campanha volta a poder progredir.

Quando usar:

- use somente para operacao administrativa de baixo nivel
- use quando houver necessidade de limpar tecnicamente chunks stale em lote, mesmo sem passar pela classificacao por campanha
- nao use este endpoint como acao primaria de consumidores para retry operacional normal

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
- nao use este endpoint como acao primaria de consumidores para retry operacional normal; prefira `.../reativar`

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
- use este endpoint quando o consumidor nao souber qual campanha esta presa ou quiser solicitar uma varredura global de pendencias

## Como escolher o endpoint

| Endpoint | Publico esperado | Escopo | Quando usar | Quando nao usar |
| --- | --- | --- | --- | --- |
| `POST /analise/materializacoes/campanhas/{campanha_id}/reativar` | operador delegado ou admin | uma campanha | o consumidor conhece a campanha presa e quer retry operacional suportado | nao use para limpeza tecnica em lote |
| `POST /analise/materializacoes/recuperacao/trigger` | operador delegado ou admin | sweep limitado | o consumidor quer varrer campanhas `pending` sem saber qual esta presa | nao use como substituto de observabilidade |
| `POST /analise/materializacoes/recuperar-stale` | admin | lote tecnico | manutencao operacional administrativa de chunks stale | nao use como acao padrao de consumidores |
| `POST /analise/materializacoes/campanhas/{campanha_id}/recuperar` | admin | uma campanha, nivel tecnico | manutencao administrativa quando a campanha ja e conhecida | nao use como retry operacional padrao do usuario |

## `GET /analise/materializacoes/{execucao_id}`

Retorna o detalhe de uma execucao especifica, incluindo `summary` bruto persistido pela materializacao para auditoria operacional, o modo da execucao (`full` ou `incremental`), o cutoff `invalidated_from` quando aplicavel, os contadores de revisoes inseridas/encerradas/removidas e os vinculos opcionais `campanha_id`, `campanha_item_id`, `chunk_execucao_id`, `queue_name` e `position_in_chunk`.

O contrato operacional acrescenta:

- `operational_state`: `active`, `queued`, `waiting_for_gate`, `completion_pending`, `stalled_recoverable`, `stalled_unrecoverable`, `terminal_success`, `terminal_failed` ou `unknown`;
- `liveness`: última atividade, idade, task correlata, disponibilidade da inspeção, chunk e lease ativos e threshold;
- `completion`: progresso técnico, totais processados e motivo da finalização pendente;
- `recovery`: elegibilidade, estratégia e `reason_code`;
- `allowed_actions`: operações autorizadas com método, rota, confirmação e motivo estável.

Em uma execução bem-sucedida, `summary` também informa o prewarm do relatório agregado:

| Campo | Descrição |
| --- | --- |
| `fundamentalista_snapshot_status` | `success`, `failed` ou `disabled`. Uma falha de prewarm não invalida os fatos canônicos já materializados. |
| `fundamentalista_snapshot_source` | Origem usada para produzir o read model, normalmente `compiled_canonical`. |
| `fundamentalista_snapshot_error` | Classe do erro quando o prewarm falha; presente somente nesse caso. |

Quando uma companhia estiver com `situacao_registro=CANCELADA` e nao houver override explicito de inclusao, o `summary` pode trazer:

- `skipped_reason=COMPANHIA_CANCELADA`
- `company_status=CANCELADA`
- contadores de revisoes em zero

## `POST /analise/materializacoes/{execucao_id}/reconcile`

Reconcilia uma execução individual sem criar nova materialização e sem apagar revisões, snapshots, chunks, itens ou logs.

Autorização:

- token de sistema;
- usuário administrador;
- usuário com `pode_operar_materializacao=true`.

Payload:

```json
{
  "decision": "auto",
  "reason": "Execução sem task ou chunk ativo, com progresso técnico concluído."
}
```

Decisões:

- `auto`: marca sucesso somente em `completion_pending`; uma execução parada, incompleta e sem recuperação é encerrada como falha;
- `mark_success`: exige progresso integral, inatividade acima do threshold, inspeção Celery disponível, ausência de task/chunk/lease ativo, ausência de erro terminal e gate liberado;
- `mark_failed`: encerra explicitamente uma inconsistência sem trabalho ativo.

A operação grava uma linha imutável em `analise_materializacao_reconciliacoes` e também preserva o resumo da última decisão no `summary` da execução. Repetir a chamada após a resolução retorna o mesmo evento de auditoria sem duplicá-lo.

Erros operacionais:

- `409 ACTIVE_WORK_PRESENT`: task, chunk ou lease ainda ativo;
- `409 SUCCESS_INVARIANTS_NOT_SATISFIED`: `mark_success` sem evidência integral;
- `409 INSUFFICIENT_TERMINAL_EVIDENCE`: `auto` não consegue decidir com segurança;
- `503 TASK_INSPECTION_UNAVAILABLE`: inspeção Celery indisponível; resposta inclui `retryable=true` e `Retry-After`.

Um sweep periódico executa apenas a promoção segura de `completion_pending` para `success`. Estados sem evidência suficiente permanecem inalterados.
