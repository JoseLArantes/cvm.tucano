---
title: Schemas de Analise
sidebar_position: 5
---

# Schemas de Analise

Os contratos analíticos atuais são fechados e orientados a períodos, métricas, comparabilidade, qualidade e evidências.

## Manifesto

`AnaliseManifestoResposta` descreve a companhia, o contexto padrão, os períodos disponíveis, a disponibilidade compacta por métrica, o resumo de qualidade e os links para os demais blocos analíticos.

Campos principais:

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `companhia` | object | Resumo cadastral da companhia |
| `contexto_padrao.periodo_id` | string | Período padrão sugerido |
| `periodos_disponiveis` | array | Lista de períodos canônicos disponíveis |
| `periodos_disponiveis_por_metrica` | array | Lista compacta de `metric_id` e `period_ids` disponíveis |
| `qualidade` | object | Resumo de completude, comparabilidade e consistência |
| `calculation_version` | string | Versão do motor analítico |
| `resolution` | object | Origem efetiva do payload (`canonical` ou `runtime_fallback`) |
| `links` | object | URLs relativas dos blocos analíticos |

Os links atuais incluem `series`, `comparacoes`, `qualidade`, `sinais`, `eventos`, `restatements`, `governanca`, `pessoas` e `brief`.

## Coverage

`AnaliseCoverageResposta` cruza dados brutos, contexto canônico e fatos canônicos.

Campos principais:

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `companhia` | object | Resumo cadastral da companhia |
| `escopo` | string | `consolidated` ou `individual` |
| `as_of` | string | Data de corte informacional |
| `resolution` | object | Camada usada para a leitura de cobertura |
| `periodos` | array | Matriz por período |

Cada item de `periodos` inclui:

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `period_id` | string | Período canônico |
| `ano` | integer | Ano fiscal |
| `periodicidade` | string | `annual` ou `quarterly` |
| `base_periodo` | string | `fy`, `quarter` ou `ytd` |
| `escopo` | string | Escopo societário |
| `form` | string | Formulário ou origem principal |
| `has_raw_data` | boolean | Existe dado bruto/promovido para o período |
| `has_canonical_context` | boolean | A revisão de contexto canônica lista o período |
| `has_canonical_facts` | boolean | Existe ao menos uma revisão de fato canônica para o período |
| `has_materialized_metrics` | boolean | Existem métricas materializadas disponíveis |
| `has_series` | boolean | Existe ao menos uma métrica canônica disponível |
| `metrics_count` | integer | Quantidade de métricas disponíveis |
| `unavailable_count` | integer | Quantidade de métricas indisponíveis registradas |
| `metrics_available` | array | Métricas disponíveis |
| `metrics_unavailable` | array | Métricas indisponíveis registradas |
| `latest_execution_id` | string | Execução de materialização associada |
| `materialized_at` | string | Conclusão da materialização associada |

## Diagnóstico de Séries

`AnaliseSeriesDiagnosticoResposta` explica lacunas de `/series`.

Campos principais:

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `requested_metrics` | array | Métricas reconhecidas pelo backend |
| `candidate_periods` | array | Períodos candidatos nos dados brutos para os filtros |
| `returned_periods` | array | Períodos com ao menos uma observação retornada |
| `rejected_periods` | array | Períodos com lacunas explicáveis |
| `unavailable_reasons` | array | Indisponibilidades consolidadas do resolvedor |

Cada item de `rejected_periods` informa métricas retornadas e rejeitadas, contas ausentes, formulários ausentes, mismatch de escopo, mismatch de materialização, status completo do pipeline e `metric_reasons`.

Campos acionáveis por período rejeitado:

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `has_raw_data` | boolean | Existe dado bruto/promovido no escopo solicitado |
| `has_canonical_context` | boolean | O contexto canônico lista o período |
| `has_canonical_facts` | boolean | Existem fatos canônicos para o período |
| `has_materialized_metrics` | boolean | Existem métricas disponíveis materializadas |
| `materialization_status` | string | Estado operacional mais relevante |
| `materialization_execution_id` | string | Execução mais relevante |
| `latest_execution_id` | string | Alias operacional da execução mais recente |
| `metrics_count` | integer | Quantidade de métricas disponíveis |
| `unavailable_count` | integer | Quantidade de métricas indisponíveis |
| `metric_reasons` | array | Motivos e remediações por métrica |

Cada item de `metric_reasons` contém:

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `metric_id` | string | Métrica rejeitada |
| `reason_code` | string | Código estável da causa |
| `reason_message` | string | Descrição objetiva da causa |
| `layer` | string | `raw`, `canonical_context`, `canonical_fact`, `metric_calculation`, `materialization`, `scope` ou `filter` |
| `remediation_code` | string | Código estável da ação recomendada |
| `remediation_message` | string | Ação operacional recomendada |

## Repair de Materialização

`AnaliseMaterializacaoRepairRequest` aceita `escopo`, `period_ids`, `metricas` e `mode=missing_only`.

`AnaliseMaterializacaoRepairResposta` retorna:

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `status` | string | `accepted`, `partial` ou `rejected` |
| `campanha_id` | string | Campanha criada para executar o repair |
| `accepted_items` | array | Períodos aceitos |
| `rejected_items` | array | Períodos rejeitados com motivo |
| `reason_code` | string | Motivo consolidado |
| `dispatcher_enqueued` | boolean | Indica se a campanha foi enfileirada |
| `gate_status` | string | Estado do gate no momento da criação |
| `triggered_at` | string | Momento da criação |

## Resolution

`AnaliseResolutionMetadata` aparece em manifesto, séries, comparações, qualidade e sinais.

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `mode` | string | `canonical` ou `runtime_fallback` |
| `materialization_execution_id` | string | UUID da execução canônica usada, quando houver |
| `materialized_at` | string | Timestamp ISO 8601 da conclusão da materialização |
| `as_of` | string | Data de corte informacional aplicada |

## O que a materialização faz

A análise pode ser resolvida de dois modos:

- `runtime_fallback`: o backend lê os fatos CVM brutos e calcula a resposta no momento da requisição;
- `canonical`: o backend lê uma camada analítica já materializada e persistida.

A materialização existe para transformar cálculos analíticos caros e repetitivos em artefatos persistidos, prontos para consulta. Isso reduz custo de CPU por request, melhora latência, torna o comportamento mais previsível e permite responder corretamente a perguntas do tipo `as_of`, isto é, “o que era conhecido naquela data”.

Na prática, materializar significa:

- percorrer as datas de conhecimento relevantes de uma companhia;
- reconstruir, para cada data, o contexto analítico que o mercado teria naquele momento;
- recalcular períodos disponíveis, qualidade, observações e indisponibilidades;
- comparar cada snapshot com o anterior;
- persistir apenas as revisões de contexto e de fatos, em vez de copiar snapshots completos sem mudança.

Isso faz com que a camada canônica funcione como um histórico versionado de análise, não apenas como um cache simples.

## Lease, heartbeat e recuperação automática

O backend trata o chunk como a unidade autoritativa de liveness operacional.

Cada chunk persistido possui:

- `status`: `queued`, `running`, `success`, `failed`, `stale` ou `cancelled`;
- `lease_owner`: identidade lógica da task Celery que possui o chunk;
- `lease_expires_at`: prazo atual do lease;
- `heartbeat_at`: último heartbeat persistido;
- contadores de progresso do próprio chunk.

O fluxo operacional atual é:

1. a campanha reivindica um conjunto de itens `pending`;
2. o backend cria um registro de chunk e vincula os itens a esse chunk;
3. a task do chunk renova lease e heartbeat no início, antes de cada item e após cada item;
4. se o worker morrer ou perder o lease, o chunk deixa de ser considerado vivo após a expiração;
5. uma varredura periódica recupera chunks stale, devolve os itens inacabados para `pending` e reagenda a campanha.

Com isso:

- `running_items` continua útil como contador resumido, mas não define sozinho se existe trabalho vivo;
- a recuperação é automática e observável pela API;
- limpeza manual fica restrita a endpoints administrativos, não a mutação direta em banco.

## Como a materialização funciona

O fluxo atual é:

1. A ingestão financeira identifica quais companhias foram afetadas.
2. O backend cria uma campanha de materialização.
3. A campanha elimina por padrão companhias com `situacao_registro=CANCELADA`.
4. A campanha é dividida em itens por `codigo_cvm` e `escopo`.
5. Antes de cada novo chunk, o backend consulta um gate de admissão.
6. Se houver ingestão ativa ou pausa manual, a campanha permanece pendente.
7. Quando o gate está verde, um dispatcher volta a entregar campanhas pendentes ao orquestrador.
8. O orquestrador enfileira apenas um chunk por ciclo.
9. Cada item executa a materialização canônica da companhia.
10. Se o gate fechar no meio do chunk, os itens ainda não iniciados voltam para `pending`.
11. O resultado alimenta as tabelas de revisões de contexto e de fatos.
12. Um sweep automático e limitado pode reativar campanhas pendentes que nunca chegaram a formar chunk inicial.

Enquanto o gate está vermelho, a campanha pode continuar visível como pendente no monitoramento, mas não deve consumir polling contínuo por auto-reagendamento do próprio orquestrador.

Com isso, a API pode:

- servir respostas canônicas com `resolution.mode=canonical`;
- expor progresso operacional por campanha, item e execução;
- evitar recalcular a mesma história analítica inteira a cada request;
- dar prioridade operacional total para ingestão e atualizações.

Execução pontual de companhia cancelada:

- o comportamento padrão continua sendo não processar `CANCELADA`
- uma execução individual só pode incluir canceladas quando o operador informa override explícito
- sem override, a execução pode ser registrada apenas como skip observável, sem gerar revisões

## Self-healing de campanhas pendentes

O backend agora separa dois grupos de campanhas pendentes:

- pendência operacional legítima, causada por gate vermelho, saturação de slots ou chunk ainda vivo
- pendência presa, quando a campanha continua `pending` apesar de já ter trabalho disponível e nenhum progresso possível ter sido iniciado

Classificações operacionais principais:

- `STALE_CHUNK`
- `PENDING_UNDISPATCHED`
- `WAITING_FOR_GATE`
- `WAITING_FOR_SLOT`
- `CHUNK_IN_PROGRESS`
- `NO_PENDING_ITEMS`

Essas classificações alimentam:

- os endpoints delegados de reativação
- o sweep automático periódico
- os novos sinais de monitoramento
- o `summary` operacional persistido da campanha

## Materialização Canônica

`AnaliseMaterializacaoExecucaoResumo` expõe o estado operacional da geração da camada canônica.

O backend agora distingue:

- `full`: recompõe toda a linha do tempo canônica da companhia/escopo
- `incremental`: recompõe apenas a janela a partir de `invalidated_from`

Campos principais:

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `id` | string | ID da execução |
| `codigo_cvm` | integer | Companhia materializada |
| `escopo` | string | `consolidated` ou `individual` |
| `status` | string | `running`, `success` ou `failed` |
| `coverage_complete` | boolean | Indica cobertura canônica concluída |
| `source` | string | Origem do disparo |
| `materialization_mode` | string | `full` ou `incremental` |
| `invalidated_from` | string | Primeira data de conhecimento recomposta, quando incremental |
| `started_at` | string | Início da execução |
| `finished_at` | string | Fim da execução, quando houver |
| `updated_at` | string | Último heartbeat persistido |
| `elapsed_seconds` | integer | Tempo decorrido em segundos |
| `estimated_remaining_seconds` | integer | Estimativa de tempo restante, quando houver progresso parcial |
| `estimated_finish_at` | string | Momento estimado de conclusão |
| `campanha_id` | string | Campanha de materialização associada, quando houver |
| `campanha_item_id` | string | Item da campanha associado, quando houver |
| `chunk_execucao_id` | string | Chunk operacional associado, quando houver |
| `queue_name` | string | Fila Celery usada para a execução |
| `position_in_chunk` | integer | Posição do item no chunk processado |
| `window_total_knowledge_dates` | integer | Total de datas no recorte efetivamente processado |
| `window_processed_knowledge_dates` | integer | Quantidade já processada nesse recorte |
| `inserted_context_revisions` | integer | Revisões de contexto inseridas nesta execução |
| `inserted_fact_revisions` | integer | Revisões de fatos inseridas nesta execução |
| `closed_context_revisions` | integer | Revisões antigas de contexto encerradas |
| `closed_fact_revisions` | integer | Revisões antigas de fatos encerradas |
| `deleted_future_context_revisions` | integer | Revisões futuras de contexto removidas por substituição |
| `deleted_future_fact_revisions` | integer | Revisões futuras de fatos removidas por substituição |
| `progress` | object | Progresso estruturado da execução |

### `AnaliseMaterializacaoProgress`

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `total_knowledge_dates` | integer | Total de datas de conhecimento previstas |
| `processed_knowledge_dates` | integer | Quantidade já processada |
| `current_known_from` | string | Data de conhecimento atual |
| `progress_ratio` | number | Progresso estimado entre 0 e 1 |
| `context_revisions` | integer | Revisões de contexto já acumuladas |
| `fact_revisions` | integer | Revisões de fatos já acumuladas |

### `AnaliseMaterializacaoCompanhiaStatusResposta`

`GET /analise/materializacoes/companhias/{codigo_cvm}/status` retorna um snapshot compacto para telas de companhia.

O contrato evita que clientes precisem recompor status a partir de campanhas, chunks e execuções. A resposta usa a revisão canônica atual para montar os anos fiscais anuais `FY` e usa a última execução ou item ativo de campanha para indicar o estado operacional.

Campos principais:

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `codigo_cvm` | integer | Companhia consultada |
| `escopo` | string | `consolidated` ou `individual` |
| `status` | string | Estado consolidado da companhia/escopo |
| `coverage_complete` | boolean | Cobertura da última execução conhecida |
| `latest_execution` | object | Última execução de materialização conhecida |
| `active_item` | object | Item ativo ou pendente de campanha, quando houver |
| `anos` | array | Status por ano fiscal anual |
| `dados` | array | Alias de `anos` |
| `periodos` | array | Alias de `anos` |
| `materializacoes` | array | Alias de `anos` |
| `status_por_ano` | object | Mapa por ano fiscal |
| `generated_at` | string | Momento de geração do snapshot |
| `updated_at` | string | Última atualização operacional conhecida |

Estados esperados em `status` e `anos[].status`:

- `missing`
- `pending`
- `queued`
- `running`
- `success`
- `failed`
- `stale`
- `skipped`
- `partial`
- `unknown`

Cada item de `anos` inclui `ano`, `status`, `escopo`, `coverage_complete`, timestamps operacionais, identificadores de execução, `calculation_version`, `source`, `materialization_mode` e `message`.

### Estado operacional de execução

`AnaliseMaterializacaoExecucaoResumo` e o detalhe individual expõem:

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `operational_state` | string | Estado derivado de liveness, progresso, gate e recuperação |
| `reason_code` | string | Motivo estável da classificação |
| `liveness` | object | Task, chunk, lease, última atividade, idade e threshold |
| `completion` | object | Progresso técnico e indicação de finalização pendente |
| `recovery` | object | Elegibilidade, estratégia e motivo |
| `allowed_actions` | array | Operações autorizadas pelo backend |
| `has_action_required` | boolean | Atalho para existência de ação autorizada |

Estados possíveis:

- `active`
- `queued`
- `waiting_for_gate`
- `completion_pending`
- `stalled_recoverable`
- `stalled_unrecoverable`
- `terminal_success`
- `terminal_failed`
- `unknown`

`completion_pending` exige progresso integral, inatividade acima do threshold, inspeção Celery disponível, ausência de task/chunk/lease ativo, ausência de erro terminal e gate liberado.

### Monitoramento da fila

`AnaliseMaterializacaoMonitoramentoResposta` combina banco e Celery para responder:

- quantas execuções estão em `running`;
- quantas execuções `running` são `full` versus `incremental`;
- se a materialização está liberada ou bloqueada pelo gate;
- quantas tasks da materialização estão ativas, reservadas ou agendadas;
- quantas campanhas e itens existem por estado;
- quantos chunks existem em `queued`, `running` e `stale`;
- quais campanhas estão em andamento;
- quais campanhas aguardam recuperação de chunk stale;
- quais campanhas pendentes já são recuperáveis;
- quais campanhas pendentes estão presas por ausência de despacho inicial;
- quais itens estão rodando agora e quais seguem pendentes;
- quais chunks stale merecem atenção operacional;
- quais execuções correntes estão incrementais, qual cutoff elas usam e quais parecem stalled;
- qual a execução em andamento mais antiga;
- quais execuções parecem sem heartbeat recente.

Campos adicionais importantes:

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `gate` | object | Snapshot consolidado do gate de admissão |
| `running_full_executions` | integer | Execuções full em andamento |
| `running_incremental_executions` | integer | Execuções incrementais em andamento |
| `lowest_running_invalidated_from` | string | Menor cutoff incremental entre as execuções correntes |
| `pending_campaigns` | integer | Quantidade de campanhas pendentes |
| `running_campaigns` | integer | Quantidade de campanhas em andamento |
| `waiting_for_gate_campaigns` | integer | Campanhas pendentes especificamente por gate vermelho |
| `recovering_campaigns` | integer | Campanhas pendentes aguardando recuperação de chunk stale |
| `recoverable_pending_campaigns` | integer | Campanhas pendentes elegíveis para self-healing |
| `undispatched_stuck_campaigns` | integer | Campanhas pendentes presas sem chunk inicial e sem bloqueio operacional explícito |
| `oldest_undispatched_campaign_created_at` | string | Data de criação da campanha presa mais antiga |
| `oldest_undispatched_campaign_elapsed_seconds` | integer | Tempo decorrido da campanha presa mais antiga |
| `recoverable_campaign_ids` | array | Preview das campanhas recuperáveis |
| `last_pending_recovery_sweep_at` | string | Momento do último sweep automático de recuperação |
| `last_pending_recovery_sweep_summary` | object | Resumo persistido do último sweep automático |
| `pending_items` | integer | Quantidade de itens pendentes |
| `running_items` | integer | Quantidade de itens em processamento |
| `success_items` | integer | Quantidade de itens concluídos com sucesso |
| `failed_items` | integer | Quantidade de itens com falha |
| `skipped_items` | integer | Quantidade de itens deduplicados/skipped |
| `queued_chunks` | integer | Quantidade de chunks aguardando início |
| `running_chunks` | integer | Quantidade de chunks com lease ativo |
| `stale_chunks` | integer | Quantidade de chunks stale ainda acionaveis, com itens nao terminais associados |
| `stale_item_count` | integer | Quantidade de itens nao terminais ainda vinculados a chunks stale acionaveis |
| `stalled_incremental_execution_ids` | array | Subconjunto stalled apenas do modo incremental |
| `pending_recovery_active_tasks` | integer | Tasks ativas específicas do sweep automático de campanhas pendentes |
| `running_execution_previews` | array | Preview das execuções correntes |
| `campaigns` | array | Resumo das campanhas relevantes no snapshot |
| `stale_chunk_preview` | array | Preview dos chunks stale ainda acionaveis no snapshot |
| `running_items_preview` | array | Preview dos itens atualmente em execução |
| `pending_items_preview` | array | Preview dos próximos itens pendentes |
| `operational_counts` | object | Contagens por estado operacional |
| `completion_pending_execution_ids` | array | Execuções aguardando finalização terminal |
| `stalled_unrecoverable_execution_ids` | array | Execuções paradas sem recuperação automática |
| `action_required_execution_ids` | array | Execuções com ação autorizada |

### `running_items_preview` e `pending_items_preview`

Os previews de item agora também carregam:

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `materialization_mode` | string | Modo planejado para o item (`full` ou `incremental`) |
| `invalidated_from` | string | Cutoff incremental do item, quando houver |

### `AnaliseMaterializacaoFilaSnapshot`

Além dos totais gerais de tasks, o snapshot atual expõe:

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `materialization_orchestrator_active_tasks` | integer | Tasks orquestradoras de campanha ativas |
| `materialization_chunk_active_tasks` | integer | Tasks de chunk ativas |
| `materialization_queue_depth` | integer | Profundidade observada da fila dedicada, quando disponível |

### `AnaliseMaterializacaoGateSnapshot`

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `status` | string | `green` ou `red` |
| `reason_code` | string | Motivo objetivo do estado atual |
| `gate_enabled` | boolean | Indica se o gate automático está habilitado |
| `manual_control` | string | `auto` ou `paused` |
| `manual_reason` | string | Motivo textual da pausa manual, quando houver |
| `blocking_ingestions` | integer | Quantidade de execuções/runs bloqueadoras |
| `pending_ingestions` | integer | Quantidade de execuções em `aguardando_ingestao` |
| `next_check_at` | string | Próxima rechecagem recomendada enquanto o gate estiver vermelho |
| `blockers` | array | Preview dos bloqueadores operacionais |

### `AnaliseMaterializacaoIngestionBlocker`

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `source_type` | string | Fonte de ingestão associada ao bloqueio do gate |
| `execution_id` | string | ID da execução de sincronização, quando houver |
| `run_id` | string | ID da run de ingestão, quando houver |
| `year` | integer | Ano da carga, quando aplicável |
| `status` | string | Status operacional bloqueador |
| `phase` | string | Fase da run, quando houver |
| `started_at` | string | Momento em que o bloqueador começou |

### `AnaliseMaterializacaoCampanhaResumo`

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `campanha_id` | string | Identificador da campanha |
| `source` | string | Origem do disparo |
| `status` | string | `pending`, `running`, `success`, `failed` ou `partial` |
| `chunk_size` | integer | Tamanho do chunk |
| `total_items` | integer | Total de itens na campanha |
| `processed_items` | integer | Itens concluídos, incluindo skipped |
| `pending_items` | integer | Itens pendentes |
| `running_items` | integer | Itens em andamento |
| `failed_items` | integer | Itens com falha |
| `skipped_items` | integer | Itens deduplicados/skipped |
| `progress_ratio` | number | Progresso estimado entre 0 e 1 |
| `estimated_remaining_seconds` | integer | Tempo restante estimado |
| `active_chunks` | integer | Quantidade de chunks ativos atuais da campanha |
| `active_chunk_id` | string | Chunk ativo atual da campanha, quando houver |
| `active_chunk_lease_expires_at` | string | Expiração do lease do chunk ativo |
| `active_chunk_ids_preview` | array | Preview dos identificadores dos chunks ativos atuais |
| `stale_chunks` | integer | Quantidade de chunks stale ligados à campanha |
| `wait_reason` | string | Motivo operacional da espera atual, quando houver |
| `recovery_state` | string | Classificação persistida mais recente da campanha para fins de self-healing |
| `last_recovery_check_at` | string | Último momento em que a campanha foi classificada pelo fluxo de recuperação |
| `last_recovery_action` | string | Última ação executada pelo fluxo de recuperação |
| `last_recovery_reason_code` | string | Último reason code emitido para a campanha |
| `operational_state` | string | Estado operacional atual da campanha |
| `reason_code` | string | Motivo estável da classificação |
| `recovery` | object | Elegibilidade e estratégia de recuperação |
| `allowed_actions` | array | Ações autorizadas para a campanha |

### `AnaliseMaterializacaoCampanhaItemPreview`

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `item_id` | string | Identificador do item |
| `codigo_cvm` | integer | Companhia alvo |
| `escopo` | string | `consolidated` ou `individual` |
| `campanha_id` | string | Campanha de origem |
| `chunk_execucao_id` | string | Chunk associado, quando houver |
| `status` | string | Estado atual do item |
| `started_at` | string | Início efetivo do item, quando houver |

### `AnaliseMaterializacaoChunkExecucaoResumo`

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `chunk_execucao_id` | string | Identificador do chunk |
| `campanha_id` | string | Campanha dona do chunk |
| `status` | string | `queued`, `running`, `success`, `failed`, `stale` ou `cancelled` |
| `lease_owner` | string | Identidade da task/worker que possui o lease |
| `lease_expires_at` | string | Momento atual de expiração do lease |
| `heartbeat_at` | string | Último heartbeat persistido |
| `item_count` | integer | Quantidade total de itens no chunk |
| `processed_items` | integer | Quantidade processada no chunk |
| `success_items` | integer | Quantidade bem-sucedida no chunk |
| `failed_items` | integer | Quantidade com falha no chunk |
| `started_at` | string | Início efetivo do chunk |
| `finished_at` | string | Fim do chunk, quando houver |
| `updated_at` | string | Última atualização persistida |

## Respostas de reativação operacional

### `AnaliseMaterializacaoReativacaoResposta`

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `status` | string | `triggered`, `recovered`, `noop` ou `rejected` |
| `reason_code` | string | Código objetivo do estado encontrado |
| `affected_campaigns` | array | Campanhas avaliadas ou afetadas |
| `requeued_campaigns` | array | Campanhas efetivamente reenfileiradas |
| `recovered_chunks` | integer | Quantidade de chunks stale recuperados |
| `recovered_items` | integer | Quantidade de itens devolvidos para `pending` |
| `dispatcher_enqueued` | boolean | Indica se houve reenfileiramento efetivo |
| `triggered_at` | string | Momento da operação |

### `AnaliseMaterializacaoReativacaoSweepResposta`

Além do envelope acima, o sweep global expõe:

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `scanned_campaigns` | integer | Quantidade de campanhas pendentes inspecionadas no sweep |
| `recoverable_campaigns` | integer | Quantidade de campanhas efetivamente classificadas como recuperáveis dentro do sweep |

## Catálogo de Métricas

`AnaliseMetricasCatalogoResposta` retorna uma lista de `AnaliseMetricaCatalogoItem`.

Campos principais por métrica:

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `id` | string | Identificador estável |
| `nome` | string | Nome profissional |
| `type` | string | `stock`, `flow`, `ratio` ou `count` |
| `unit` | string | Unidade oficial |
| `formula` | string | Fórmula declarada quando derivada |
| `contas_cvm_candidatas` | array | Contas CVM candidatas |
| `estrategia_resolucao` | string | Estratégia aplicada pelo backend |
| `disponibilidades` | array | Bases temporais suportadas |
| `limitations` | array | Limitações metodológicas |

## Série

`AnaliseSeriesResposta` traz `resolution`, observações disponíveis e indisponibilidades explícitas.

Campos adicionais do envelope:

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `horizonte_anos` | integer | Horizonte anual efetivamente aplicado em consultas FY históricas |

### `AnaliseSeriesObservation`

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `metric_id` | string | Métrica resolvida |
| `period_id` | string | Período canônico |
| `fiscal_year` | integer | Ano fiscal |
| `quarter` | integer | Trimestre fiscal quando aplicável |
| `period_nature` | string | `instant` ou `duration` |
| `period_basis` | string | `fy`, `quarter` ou `ytd` |
| `start_date` | string | Data inicial em ISO 8601 |
| `end_date` | string | Data final em ISO 8601 |
| `value` | string | Valor decimal canônico |
| `unit` | string | Unidade explícita |
| `scope` | string | `consolidated` ou `individual` |
| `form` | string | `DFP`, `ITR` ou `DERIVED` |
| `version` | integer | Versão documental usada |
| `restated` | boolean | Indica reapresentação |
| `value_source` | string | `reported`, `derived_from_ytd_delta`, `derived_from_dfp_minus_ytd` ou `derived_from_formula` |
| `comparables` | object | Referência para YoY e QoQ |
| `provenance` | array | Evidência documental completa |

### `AnaliseSeriesUnavailable`

Quando a série não puder ser produzida para uma métrica/período, a resposta inclui um item com:

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `metric_id` | string | Métrica indisponível |
| `period_id` | string | Período avaliado |
| `status` | string | Sempre `unavailable` |
| `reason_code` | string | Motivo estável |
| `message` | string | Explicação objetiva |
| `missing` | array | Componentes ou fatos ausentes |

## Comparações

`AnaliseComparacoesResposta` retorna uma lista de `AnaliseComparacaoItem`.

O envelope também inclui `resolution`, `metricas`, `periodicidade`, `base_periodo`, `escopo` e `issues`.

Campos principais:

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `comparison_kind` | string | `YoY`, `QoQ`, `CAGR`, `VERTICAL` ou `BASE100` |
| `status` | string | `available` ou `unavailable` |
| `metric_unit` | string | Unidade dos valores atual e comparável |
| `comparison_unit` | string | Unidade do resultado comparativo |
| `current_value` | string | Valor atual |
| `comparable_period_id` | string | Período comparável |
| `comparable_metric_id` | string | Métrica base ou denominadora |
| `absolute_change` | string | Variação absoluta |
| `relative_change` | string | Variação relativa em decimal |
| `percentage_point_change` | string | Variação em pontos percentuais para métricas do tipo ratio |
| `base100_value` | string | Índice base 100 |
| `evidence` | array | Evidências explicativas |

Em `BASE100`, `metric_unit` preserva a unidade econômica da observação, como `BRL`, e `comparison_unit` assume `index`.

## Qualidade

`AnaliseQualidadeResumo` retorna dimensões auditáveis sem score único.

Campos principais:

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `completude` | string | `complete`, `partial` ou `missing` |
| `comparabilidade` | string | `complete`, `partial` ou `missing` |
| `consistencia` | string | `complete`, `partial` ou `missing` |
| `restatements` | integer | Quantidade de reapresentações no contexto |
| `issues` | array | Regras disparadas e problemas detectados |
| `checked_at` | string | Timestamp ISO 8601 da avaliação |
| `ruleset_version` | string | Versão do ruleset |

## Sinais

`AnaliseSinaisResposta` retorna uma lista de `AnaliseSignal`.

O envelope também inclui `resolution` para declarar a origem das séries usadas no cálculo.

Campos principais:

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `rule_id` | string | Identificador da regra |
| `rule_version` | string | Versão da regra |
| `severity` | string | `info`, `watch`, `warning` ou `critical` |
| `period_id` | string | Período principal do sinal |
| `title` | string | Título curto |
| `explanation` | string | Explicação objetiva |
| `threshold` | string | Threshold usado |
| `observed` | string | Valor observado |
| `unit` | string | Unidade do threshold/observado |
| `evidence` | array | Evidências do disparo |

## Eventos

`AnaliseEventosResposta` retorna `companhia` e `eventos`.

Cada `AnaliseEvento` traz:

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `event_id` | string | Identificador estável do evento |
| `occurred_at` | string | Data do evento em ISO 8601 |
| `family` | string | Família documental |
| `event_type` | string | Tipo do evento |
| `severity` | string | Severidade informativa |
| `title` | string | Título curto |
| `explanation` | string | Explicação objetiva |
| `period_id` | string | Período afetado quando houver |
| `link_documento` | string | Link oficial do documento |

## Governança Temporal

`AnaliseGovernancaResposta` retorna observações anuais auditáveis de governança, com suporte a `as_of` e `horizonte_anos`.

Cada `AnaliseTemporalObservation` inclui:

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `metric_id` | string | Métrica temporal |
| `period_id` | string | Período canônico anual |
| `fiscal_year` | integer | Ano fiscal |
| `start_date` | string | Data inicial do exercício |
| `end_date` | string | Data final do exercício |
| `value` | string | Valor decimal canônico |
| `unit` | string | Unidade explícita |
| `source_dataset` | string | Dataset CVM de origem |
| `document_id` | integer | Documento usado |
| `version` | integer | Versão documental |
| `restated` | boolean | Indica reapresentação |
| `details` | object | Dimensões auxiliares da observação |

Métricas temporais atualmente publicadas:

- `governanca_praticas_adotadas_ratio`
- `governanca_praticas_com_explicacao`

## Pessoas Temporais

`AnalisePessoasResposta` reutiliza `AnaliseTemporalObservation` para publicar séries anuais de pessoas e remuneração.

Métricas temporais atualmente publicadas:

- `pessoas_remuneracao_total_orgao`
- `pessoas_empregados_total`

## Brief Analítico

`AnaliseBriefResposta` agrega:

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `periodos_referencia` | object | Referências `quarter_current`, `quarter_previous`, `quarter_yoy`, `fy_current` e `fy_previous` |
| `metricas` | array | Observações selecionadas para os períodos de referência |
| `comparacoes` | array | Comparações selecionadas para os períodos de referência |
| `sinais` | array | Sinais determinísticos relevantes |
| `qualidade` | object | Resumo de qualidade do contexto |
| `eventos` | array | Eventos recentes |
| `issues` | array | Problemas agregados do brief |

## Reapresentações

`AnaliseRestatementsResposta` retorna uma lista de `AnaliseRestatementItem`.

Campos principais:

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `form` | string | `DFP` ou `ITR` |
| `period_id` | string | Período afetado |
| `previous_version` | integer | Versão anterior |
| `current_version` | integer | Versão atual |
| `restated_at` | string | Data da reapresentação |
| `document_link` | string | Link oficial do documento |
| `changed_accounts` | array | Contas alteradas entre versões |

Cada conta alterada inclui:

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `account_code` | string | Código de conta CVM |
| `account_label` | string | Nome determinístico da conta, quando conhecido |
| `statement_type` | string | Tipo da demonstração |
| `statement_label` | string | Nome legível da demonstração |
| `unit` | string | Unidade factual associada |
| `display_rank` | integer | Ordem determinística para exibição; não representa materialidade |
| `is_focus` | boolean | Indica se a conta pertence ao conjunto de foco operacional do relatório |
| `reason_if_available` | string | Descrição factual disponível sobre a diferença entre versões |
| `evidence_id` | string | Identificador opaco da evidência da reapresentação |
| `order` | string | Valor de `ordem_exercicio` |
| `start_date` | string | Data inicial da observação |
| `before_value` | string | Valor anterior |
| `after_value` | string | Valor reapresentado |
| `absolute_change` | string | Diferença absoluta |
| `relative_change` | string | Variação relativa |

## Relatório Fundamentalista

`AnaliseFundamentalistaResposta` descreve a resposta completa e unificada para o relatório fundamentalista da companhia.

O schema do payload é independente da origem de entrega. Em `resolution.mode=canonical`, o backend pode responder pelo read model persistido ou por sua cópia descartável no Redis. Em `resolution.mode=runtime_fallback`, o mesmo contrato é compilado sob demanda. A origem operacional aparece em `X-Analise-Source`, não em um campo novo do payload.

Campos principais:

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `report_id` | string | Identificador único e determinístico do relatório |
| `report_version` | string | Versão de layout/motor de cálculo do relatório |
| `companhia` | object | Resumo cadastral da companhia |
| `contexto` | object | Contexto padrão (período sugerido, escopo, periodicidade) |
| `qualidade` | object | Resumo consolidado de qualidade do contexto |
| `resolution` | object | Metadados de resolução do resolvedor (`canonical` ou `runtime_fallback`) |
| `metodologia` | object | Metadados descrevendo premissas metodológicas e versões aplicadas |
| `etapas` | object | Estrutura contendo os pilares: `ponto_partida`, `resultado_eficiencia`, `caixa_solidez` e `governanca_conclusao` |
| `evidence_index` | object | Mapa de identificador estável para referências compactas das evidências |
| `evidence_graph` | object | Grafo opcional com nós (`nodes`) e arestas (`edges`) expressando relacionamentos |
| `event_buckets` | array | Buckets agregados de eventos por ano ou mês |
| `evidence_dossier` | array | Dossiê factual priorizado para a UI |

### `AnaliseStageCaixaSolidez`

Além de `series`, `comparacoes`, `sinais`, `reapresentacoes` e `evidence_ids`, o pilar de caixa retorna:

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `ponte_caixa` | array | Ponte de caixa por período, calculada pelo backend quando os componentes são compatíveis |
| `painel_posicao_financeira` | object | Separação entre séries monetárias e séries de razão/índice |

### `AnalisePonteCaixaPeriodo`

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `period_id` | string | Período canônico |
| `unit` | string | Unidade padrão do período |
| `items` | array | Itens reconciliadores |
| `unavailable_reason` | object | Motivo factual quando a ponte não está disponível |

Cada item de `items` contém `metric_id`, `label`, `value`, `unit`, `role` e `evidence_ids`. `role` pode ser `opening`, `operating_cash`, `capex`, `adjustment` ou `free_cash`.

### `AnalisePainelPosicaoFinanceira`

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `monetary_series` | array | Observações monetárias (`unit=BRL`) com proveniência completa |
| `ratio_series` | array | Observações de razão, ponto percentual ou índice com proveniência completa |

### `AnaliseEventBucket`

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `bucket` | string | `YYYY` ou `YYYY-MM` |
| `start_date` | string | Início do bucket |
| `end_date` | string | Fim do bucket, respeitando `as_of` |
| `total` | integer | Quantidade total de eventos |
| `by_family` | object | Contagem por família |
| `by_severity` | object | Contagem por severidade |
| `has_more` | boolean | Indica se há detalhes consultáveis no endpoint de eventos |

### `AnaliseEvidenceDossierItem`

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `group` | string | `available`, `attention` ou `limitation` |
| `display_rank` | integer | Ordem determinística de exibição |
| `type` | string | `observation`, `signal`, `event`, `document` ou `restatement` |
| `label` | string | Rótulo factual |
| `summary` | string | Resumo factual sem recomendação ou avaliação qualitativa |
| `period_id` | string | Período associado |
| `occurred_at` | string | Data do evento ou protocolo |
| `evidence_id` | string | Identificador opaco da evidência |
| `source_status` | string | `available`, `unavailable` ou `partial` |
| `link_documento` | string | Link oficial quando disponível |

## Evidência sob Demanda

`AnaliseFundamentalistaEvidenciaDetalhe` fornece os detalhes completos de uma evidência para auditoria.

Campos principais:

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `evidence_id` | string | Identificador único e estável da evidência |
| `type` | string | Tipo de evidência: `observation`, `signal`, `event`, `document` ou `restatement` |
| `label` | string | Rótulo amigável em português para exibição |
| `period_id` | string | Período correspondente (se aplicável) |
| `metric` | object | Metadados e catálogo da métrica (para observações) |
| `observation` | object | Observação canônica correspondente contendo valor, unidade e proveniência (para observações) |
| `document` | object | Formulário, versão, data de entrega e link de download na CVM (se aplicável) |
| `relationships` | array | Lista de arestas/relacionamentos a partir desta evidência |

## Eventos do Relatório Fundamentalista

`AnaliseFundamentalistaEventosResposta` pagina eventos oficiais usados pelo relatório.

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `companhia` | object | Resumo cadastral da companhia |
| `calculation_version` | string | Versão do motor analítico |
| `escopo` | string | Escopo aplicado |
| `periodicidade` | string | Periodicidade aplicada |
| `base_periodo` | string | Base temporal aplicada |
| `horizonte_anos` | integer | Horizonte aplicado |
| `as_of` | string | Data de corte informacional |
| `bucket` | string | Bucket filtrado, quando informado |
| `items` | array | Lista de `AnaliseEvento` |
| `next_cursor` | string | Cursor opaco para próxima página |

## Trilha Focal de Evidência

`AnaliseEvidenceTrailResponse` retorna uma visão curta e limitada da linhagem factual de uma evidência.

| Campo | Tipo | Descrição |
| --- | --- | --- |
| `root_evidence_id` | string | Evidência raiz solicitada |
| `nodes` | array | Nós da trilha |
| `edges` | array | Relações factuais entre nós |
| `truncated` | boolean | Indica truncamento por limite de profundidade ou quantidade |
