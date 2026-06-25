---
title: API Analitica
sidebar_position: 7
---

# API Analitica

A API analítica é composta por um catálogo global de métricas e por blocos por companhia em `/analise/companhias/{codigo_cvm}`. O backend resolve períodos canônicos, unidades, comparabilidade, qualidade e evidências a partir de fatos CVM normalizados, com leitura preferencial da camada canônica persistida e fallback controlado para resolução em tempo de execução.

A materialização canônica usa uma fila dedicada, campanhas agregadas, processamento em chunks, lease persistido por chunk, dispatcher de campanhas pendentes e um gate de admissão. Quando a ingestão está ativa, a materialização permanece pendente e só retoma novos chunks quando o sistema volta a verde. Por padrão, campanhas automáticas e fluxos operacionais padrão não incluem companhias com `situacao_registro=CANCELADA`. A materialização pontual de uma companhia cancelada exige override explícito no disparo manual.

## Endpoints

| Método | Rota | Descrição |
| --- | --- | --- |
| `GET` | `/analise/metricas` | Catálogo versionado de métricas analíticas |
| `GET` | `/analise/materializacoes` | Listagem de execuções de materialização analítica |
| `GET` | `/analise/materializacoes/monitoramento` | Snapshot operacional da fila e dos workers de materialização |
| `GET` | `/analise/materializacoes/controle` | Estado atual do gate de materialização |
| `POST` | `/analise/materializacoes/controle/pause` | Pausa manual do gate de materialização |
| `POST` | `/analise/materializacoes/controle/resume` | Retorno ao modo automático do gate |
| `POST` | `/analise/materializacoes/recuperar-stale` | Recuperação imediata de chunks stale |
| `POST` | `/analise/materializacoes/campanhas/{campanha_id}/recuperar` | Recuperação imediata de chunks stale de uma campanha |
| `POST` | `/analise/materializacoes/campanhas/{campanha_id}/reativar` | Reativação delegada de campanha presa ou com chunk stale |
| `POST` | `/analise/materializacoes/recuperacao/trigger` | Sweep delegado e limitado de campanhas pendentes recuperáveis |
| `GET` | `/analise/materializacoes/{execucao_id}` | Detalhe de uma execução de materialização |
| `GET` | `/analise/companhias/{codigo_cvm}` | Manifesto analítico da companhia |
| `GET` | `/analise/companhias/{codigo_cvm}/series` | Séries normalizadas por métrica e período |
| `GET` | `/analise/companhias/{codigo_cvm}/comparacoes` | Comparações prontas sobre as séries |
| `GET` | `/analise/companhias/{codigo_cvm}/qualidade` | Diagnóstico de qualidade analítica |
| `GET` | `/analise/companhias/{codigo_cvm}/sinais` | Sinais determinísticos com evidências |
| `GET` | `/analise/companhias/{codigo_cvm}/eventos` | Timeline analítica de eventos |
| `GET` | `/analise/companhias/{codigo_cvm}/restatements` | Histórico de reapresentações |
| `GET` | `/analise/companhias/{codigo_cvm}/governanca` | Observações temporais anuais de governança |
| `GET` | `/analise/companhias/{codigo_cvm}/pessoas` | Observações temporais anuais de pessoas e remuneração |
| `GET` | `/analise/companhias/{codigo_cvm}/brief` | Brief analítico consolidado da companhia |

## Convenções do contrato

- Datas e datetimes usam ISO 8601.
- Valores decimais são serializados como string decimal canônica.
- Razões usam `unit=ratio` e o valor decimal correspondente.
- Variações em pontos percentuais usam `unit=percentage_point`.
- O escopo societário é explícito: `consolidated` ou `individual`.
- Para fluxo trimestral, `base_periodo=quarter` significa trimestre isolado. `base_periodo=ytd` significa acumulado no exercício.
- As respostas analíticas expõem `resolution` para indicar se o payload veio da camada canônica persistida (`canonical`) ou do resolvedor em tempo de execução (`runtime_fallback`).
- O parâmetro `as_of` representa o que era conhecido na data informada, usando `data_recebimento` do documento quando disponível.

## `GET /analise/metricas`

Retorna o catálogo oficial de métricas com identificador estável, tipo, unidade, fórmula, contas CVM candidatas, estratégia de resolução, bases temporais e limitações metodológicas.

```bash
curl -X GET "http://localhost:8007/analise/metricas" \
  -H "Authorization: Bearer <token>"
```

## `GET /analise/materializacoes`

Lista execuções da camada canônica com status, modo de materialização, janela efetivamente recomposta, progresso parcial, tempo decorrido, estimativa de conclusão e vínculo opcional com campanhas, itens e chunks de materialização.

Cada execução pode ser:

- `full`: recompõe toda a linha do tempo canônica da companhia/escopo
- `incremental`: recompõe apenas o sufixo a partir de `invalidated_from`, preservando o prefixo canônico anterior

Regra operacional atual:

- campanhas automáticas e fluxos padrão excluem companhias com `situacao_registro=CANCELADA`
- se uma execução pontual for disparada sem override para uma companhia cancelada, a execução é registrada e concluída sem produzir revisões, com sinalização de skip operacional no `summary`
- a materialização pontual de canceladas só ocorre quando o operador informa explicitamente o override de inclusão

Parâmetros:

| Nome | Tipo | Descrição |
| --- | --- | --- |
| `status` | string | `running`, `success` ou `failed` |
| `codigo_cvm` | integer | Filtra por companhia |
| `escopo` | string | `consolidated` ou `individual` |
| `source` | string | Origem do disparo, como `post_ingestion`, `manual` ou `backfill` |
| `campanha_id` | string | Filtra por campanha de materialização |
| `pagina` | integer | Página da listagem |
| `tamanho_pagina` | integer | Quantidade de itens por página |

```bash
curl -X GET "http://localhost:8007/analise/materializacoes?status=running" \
  -H "Authorization: Bearer <token>"
```

## `GET /analise/materializacoes/monitoramento`

Retorna um snapshot operacional das filas e campanhas de materialização, combinando:

- quantidade de execuções `running` persistidas no banco;
- quantidade de execuções `running` em modo `full` versus `incremental`;
- quantidade de tasks ativas, reservadas e agendadas nos workers Celery;
- estado atual do gate de admissão da materialização;
- quantidade de campanhas pendentes e em andamento;
- quantidade de campanhas em recuperação por chunk stale;
- quantidade de campanhas pendentes recuperáveis por self-healing;
- quantidade de campanhas pendentes especificamente presas por ausência de despacho inicial;
- quantidade de campanhas pendentes especificamente porque o gate está fechado;
- quantidade de itens pendentes, em andamento, com sucesso, falha e skipped;
- quantidade de chunks `queued`, `running` e `stale`;
- quantidade de tasks orquestradoras e de chunk em execução;
- previews dos itens correntes, da fila pendente e de chunks stale já recuperáveis;
- previews das execuções correntes, incluindo modo, cutoff incremental e contadores de revisões afetadas;
- exclusão padrão de companhias canceladas nas campanhas automáticas;
- execução em andamento mais antiga;
- execuções com `updated_at` sem heartbeat recente.

O snapshot distingue:

- gate automático por ingestão ativa versus pausa manual;
- campanha aguardando recuperação automática de chunk stale;
- campanha aguardando dispatcher após liberação do gate;
- task orquestradora da campanha;
- tasks de chunk;
- execuções canônicas por companhia;
- profundidade observada da fila dedicada `analise_materializacao`, quando disponível;
- worker da fila dedicada versus workers da fila padrão `celery`.

```bash
curl -X GET "http://localhost:8007/analise/materializacoes/monitoramento" \
  -H "Authorization: Bearer <token>"
```

Campos operacionais principais do gate:

- `gate.status`: `green` ou `red`
- `gate.reason_code`: `NO_BLOCKERS`, `INGESTION_ACTIVE`, `MANUAL_PAUSE` ou `GATE_DISABLED`
- `gate.blocking_ingestions`: quantidade de execuções/runs que mantêm o gate fechado
- `gate.pending_ingestions`: quantidade de execuções em `aguardando_ingestao`, expostas para contexto
- `gate.blockers`: preview das execuções/runs que estão bloqueando novos chunks
- `waiting_for_gate_campaigns`: campanhas pendentes especificamente por bloqueio do gate
- `recovering_campaigns`: campanhas pendentes aguardando recuperação de chunk stale
- `recoverable_pending_campaigns`: campanhas pendentes que já podem ser reativadas pelo fluxo de self-healing
- `undispatched_stuck_campaigns`: campanhas pendentes sem chunk, sem execução ativa e sem bloqueio operacional explícito
- `oldest_undispatched_campaign_created_at`, `oldest_undispatched_campaign_elapsed_seconds`: idade da campanha presa mais antiga
- `recoverable_campaign_ids`: preview dos identificadores reativáveis
- `last_pending_recovery_sweep_at`, `last_pending_recovery_sweep_summary`: último sweep automático persistido
- `running_full_executions`, `running_incremental_executions`: divisão das execuções correntes por modo
- `lowest_running_invalidated_from`: menor cutoff incremental observado entre as execuções correntes
- `queued_chunks`, `running_chunks`, `stale_chunks`: contadores globais por estado do chunk
- `stale_item_count`: itens ainda associados a chunks marcados como `stale`
- `stale_chunk_preview`: preview dos chunks já identificados como `stale`
- `pending_recovery_active_tasks`: tasks ativas do sweep automático de campanhas pendentes
- `stalled_incremental_execution_ids`: subset stalled apenas do modo incremental
- `running_execution_previews`: previews das execuções correntes com `materialization_mode`, `invalidated_from` e progresso

Comportamento operacional importante:

- o gate vermelho impede progresso material da campanha;
- o orquestrador não fica mais em polling contínuo por campanha enquanto o gate está fechado;
- novas campanhas pendentes são retomadas por um dispatcher específico quando a ingestão termina ou quando o controle volta ao modo liberado.
- campanhas pendentes sem chunk inicial agora podem ser detectadas e reativadas por sweep automático ou por chamada explícita de operador.

## `GET /analise/materializacoes/controle`

Retorna o estado consolidado do gate de materialização e do modo manual persistido.

## `POST /analise/materializacoes/controle/pause`

Ativa pausa manual. Novos chunks deixam de iniciar, mas a companhia já em processamento termina antes da pausa efetiva.

Parâmetros:

| Nome | Tipo | Descrição |
| --- | --- | --- |
| `reason` | string | Motivo textual opcional para a pausa manual |

```bash
curl -X POST "http://localhost:8007/analise/materializacoes/controle/pause?reason=janela-de-carga" \
  -H "Authorization: Bearer <token>"
```

## `POST /analise/materializacoes/controle/resume`

Remove a pausa manual e devolve o gate ao modo automático. Se ainda houver ingestão ativa, o gate continua vermelho por `INGESTION_ACTIVE`.

## `POST /analise/materializacoes/recuperar-stale`

Executa a recuperação imediata de chunks com lease expirado e já classificados como stale pelo backend. Os itens ainda não concluídos retornam para `pending` e a campanha volta a poder progredir.

Retorna:

- `recovered_chunks`
- `recovered_items`
- `affected_campaigns`
- `chunk_ids`

## `POST /analise/materializacoes/campanhas/{campanha_id}/recuperar`

Executa a mesma recuperação, mas limitada a uma campanha específica.

## `POST /analise/materializacoes/campanhas/{campanha_id}/reativar`

Endpoint operacional delegado para reativar uma campanha específica sem exigir acesso administrativo amplo.

Autenticação:

- requer bearer token dedicado de operação de materialização
- o token operacional não substitui o token geral da API para outros endpoints protegidos

Estados tratados:

- `STALE_CHUNK`: executa recuperação de chunks stale e reenfileira a campanha
- `PENDING_UNDISPATCHED`: reenfileira a campanha quando ela está pendente, com itens pendentes, sem chunk ativo, sem execução ativa e sem bloqueio operacional
- `WAITING_FOR_GATE`: devolve `noop`; não força bypass de gate vermelho
- `WAITING_FOR_SLOT`: devolve `noop`; não força bypass do limite de campanhas simultâneas
- `CHUNK_IN_PROGRESS`: devolve `noop`; não interfere em chunk vivo
- `NO_PENDING_ITEMS`: devolve `noop`

Contrato de resposta:

- `status`: `triggered`, `recovered`, `noop` ou `rejected`
- `reason_code`: classificação objetiva do estado encontrado
- `affected_campaigns`
- `requeued_campaigns`
- `recovered_chunks`
- `recovered_items`
- `dispatcher_enqueued`
- `triggered_at`

Semântica importante:

- a operação é limitada à campanha informada
- a operação é idempotente do ponto de vista operacional: se nada estiver recuperável, a resposta será `noop`
- a operação não modifica o gate e não altera limites de concorrência

## `POST /analise/materializacoes/recuperacao/trigger`

Executa um sweep limitado sobre campanhas pendentes para self-healing operacional delegado.

Autenticação:

- requer o mesmo bearer token dedicado de operação de materialização

Comportamento:

- inspeciona somente campanhas `pending`
- respeita `ANALISE_MATERIALIZACAO_PENDING_RECOVERY_MAX_CAMPAIGNS`
- respeita `ANALISE_MATERIALIZACAO_PENDING_RECOVERY_MAX_REQUEUES`
- considera a idade mínima `ANALISE_MATERIALIZACAO_PENDING_RECOVERY_MIN_AGE_SECONDS` para o caso `PENDING_UNDISPATCHED`
- pode recuperar `STALE_CHUNK`
- pode reenfileirar `PENDING_UNDISPATCHED`
- não força progresso quando o motivo real é `WAITING_FOR_GATE`, `WAITING_FOR_SLOT` ou `CHUNK_IN_PROGRESS`

Campos adicionais da resposta:

- `scanned_campaigns`: quantidade de campanhas pendentes inspecionadas
- `recoverable_campaigns`: quantidade de campanhas efetivamente classificadas como recuperáveis no sweep

Semântica importante:

- este endpoint dispara uma varredura limitada, não um requeue irrestrito de todas as campanhas
- o resultado também alimenta `last_pending_recovery_sweep_at` e `last_pending_recovery_sweep_summary` no monitoramento

## `GET /analise/materializacoes/{execucao_id}`

Retorna o detalhe de uma execução específica, incluindo `summary` bruto persistido pela materialização para auditoria operacional, o modo da execução (`full` ou `incremental`), o cutoff `invalidated_from` quando aplicável, os contadores de revisões inseridas/encerradas/removidas e os vínculos opcionais `campanha_id`, `campanha_item_id`, `chunk_execucao_id`, `queue_name` e `position_in_chunk`.

Quando uma companhia estiver com `situacao_registro=CANCELADA` e não houver override explícito de inclusão, o `summary` pode trazer:

- `skipped_reason=COMPANHIA_CANCELADA`
- `company_status=CANCELADA`
- contadores de revisões em zero

## `GET /analise/companhias/{codigo_cvm}`

Retorna o manifesto analítico da companhia: contexto padrão, períodos disponíveis, resumo de qualidade e links para os demais blocos.

Parâmetros:

| Nome | Tipo | Descrição |
| --- | --- | --- |
| `codigo_cvm` | integer | Código CVM da companhia |
| `escopo` | string | `consolidated` ou `individual` |
| `as_of` | string | Data de corte informacional em `AAAA-MM-DD` |

```bash
curl -X GET "http://localhost:8007/analise/companhias/9512?escopo=consolidated" \
  -H "Authorization: Bearer <token>"
```

## `GET /analise/companhias/{codigo_cvm}/series`

Resolve observações analíticas normalizadas.

Parâmetros:

| Nome | Tipo | Descrição |
| --- | --- | --- |
| `metricas` | string | Lista CSV de métricas estáveis |
| `periodicidade` | string | `annual` ou `quarterly` |
| `base_periodo` | string | `fy`, `quarter` ou `ytd` |
| `escopo` | string | `consolidated` ou `individual` |
| `as_of` | string | Data de corte informacional em `AAAA-MM-DD` |
| `horizonte_anos` | integer | Horizonte anual máximo quando `periodicidade=annual` e `base_periodo=fy` |

```bash
curl -X GET "http://localhost:8007/analise/companhias/9512/series?metricas=receita_liquida,lucro_liquido&periodicidade=quarterly&base_periodo=quarter&escopo=consolidated" \
  -H "Authorization: Bearer <token>"
```

Cada resposta de série inclui:

- `resolution.mode`: `canonical` ou `runtime_fallback`
- `resolution.materialization_execution_id`: UUID da materialização canônica usada, quando houver
- `resolution.materialized_at`: instante de conclusão da materialização
- `resolution.as_of`: data de corte informacional efetivamente aplicada
- `horizonte_anos`: horizonte anual efetivamente aplicado em consultas históricas FY

## `GET /analise/companhias/{codigo_cvm}/comparacoes`

Retorna comparações analíticas prontas sobre as séries resolvidas. O backend produz YoY, QoQ, CAGR, análise vertical e índice base 100 quando matematicamente definidos. Quando uma comparação não puder ser produzida, a resposta traz `status=unavailable` e `reason_code`.

As comparações reutilizam a mesma origem de resolução declarada em `resolution`.

Parâmetros:

| Nome | Tipo | Descrição |
| --- | --- | --- |
| `metricas` | string | Lista CSV de métricas estáveis |
| `periodicidade` | string | `annual` ou `quarterly` |
| `base_periodo` | string | `fy`, `quarter` ou `ytd` |
| `escopo` | string | `consolidated` ou `individual` |
| `as_of` | string | Data de corte informacional em `AAAA-MM-DD` |
| `horizonte_anos` | integer | Horizonte anual máximo quando `periodicidade=annual` e `base_periodo=fy` |

Cada comparação expõe:

- `metric_unit`: unidade dos valores `current_value` e `comparable_value`
- `comparison_unit`: unidade do resultado comparativo, como `ratio`, `percentage_point` ou `index`
- `horizonte_anos`: horizonte anual efetivamente aplicado em consultas históricas FY

## `GET /analise/companhias/{codigo_cvm}/qualidade`

Executa verificações auditáveis de completude, comparabilidade, consistência e reapresentações.

Parâmetros:

| Nome | Tipo | Descrição |
| --- | --- | --- |
| `periodicidade` | string | `annual` ou `quarterly` |
| `escopo` | string | `consolidated` ou `individual` |
| `as_of` | string | Data de corte informacional em `AAAA-MM-DD` |

## `GET /analise/companhias/{codigo_cvm}/sinais`

Avalia regras determinísticas do backend e retorna o sinal com threshold, valor observado e evidências.

Os sinais são calculados sobre as séries e comparáveis corretos para o `as_of` informado.

Parâmetros:

| Nome | Tipo | Descrição |
| --- | --- | --- |
| `escopo` | string | `consolidated` ou `individual` |
| `as_of` | string | Data de corte informacional em `AAAA-MM-DD` |

## `GET /analise/companhias/{codigo_cvm}/eventos`

Retorna a timeline analítica atual unificando IPE, reapresentações financeiras, alterações de capital e negociações relevantes.

Cada evento expõe `event_id`, identificador estável adequado para chave de renderização, paginação incremental e deep links.

## `GET /analise/companhias/{codigo_cvm}/restatements`

Compara versões consecutivas de DFP e ITR no escopo solicitado e informa as contas alteradas, com valores antes/depois e impacto absoluto/relativo.

Parâmetros:

| Nome | Tipo | Descrição |
| --- | --- | --- |
| `escopo` | string | `consolidated` ou `individual` |
| `as_of` | string | Data de corte informacional em `AAAA-MM-DD` |

## `GET /analise/companhias/{codigo_cvm}/governanca`

Retorna observações temporais anuais de governança, com corte `as_of` e horizonte histórico explícito.

Parâmetros:

| Nome | Tipo | Descrição |
| --- | --- | --- |
| `escopo` | string | `consolidated` ou `individual` |
| `as_of` | string | Data de corte informacional em `AAAA-MM-DD` |
| `horizonte_anos` | integer | Horizonte anual máximo a retornar |

O contrato atual expõe, entre outras observações:

- `governanca_praticas_adotadas_ratio`
- `governanca_praticas_com_explicacao`

## `GET /analise/companhias/{codigo_cvm}/pessoas`

Retorna observações temporais anuais de pessoas e remuneração, com corte `as_of` e horizonte histórico explícito.

Parâmetros:

| Nome | Tipo | Descrição |
| --- | --- | --- |
| `escopo` | string | `consolidated` ou `individual` |
| `as_of` | string | Data de corte informacional em `AAAA-MM-DD` |
| `horizonte_anos` | integer | Horizonte anual máximo a retornar |

O contrato atual expõe, entre outras observações:

- `pessoas_remuneracao_total_orgao`
- `pessoas_empregados_total`

## `GET /analise/companhias/{codigo_cvm}/brief`

Retorna um brief analítico com:

- trimestre corrente;
- trimestre anterior;
- mesmo trimestre do ano anterior;
- exercício corrente;
- exercício anterior;
- métricas, comparações, sinais, qualidade e eventos recentes.

Parâmetros:

| Nome | Tipo | Descrição |
| --- | --- | --- |
| `escopo` | string | `consolidated` ou `individual` |
| `as_of` | string | Data de corte informacional em `AAAA-MM-DD` |
| `metricas` | string | Lista CSV opcional de métricas a priorizar |
| `incluir_eventos` | boolean | Controla a inclusão dos eventos recentes |
