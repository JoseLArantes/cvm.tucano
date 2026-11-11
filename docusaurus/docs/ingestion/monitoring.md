---
title: Monitoramento de Sincronizacoes
sidebar_position: 3
---

# Monitoramento de Sincronizacoes

## Leitura recomendada

Para cada tipo de tela:

| Tela | Endpoint principal |
| --- | --- |
| visao operacional centrada em arquivos | `GET /ingestion/files` |
| detalhe e linhagem do arquivo logico | `GET /ingestion/files/{file_id}` |
| linha do tempo de membro delimitada | `GET /ingestion/files/{file_id}/members/{member_name}/timeline` |
| lista operacional de runs | `GET /ingestion/runs` |
| detalhe de run | `GET /ingestion/runs/{run_id}` |
| timeline de fases | `GET /ingestion/runs/{run_id}/phases` |
| inventario de members | `GET /ingestion/runs/{run_id}/members` |
| linha do tempo e ciclo de vida do member | `GET /ingestion/members/{member_name}/timeline` |
| auditoria do disparo | `GET /ingestion/sincronizacoes` |
| detalhe da execucao administrativa | `GET /ingestion/sincronizacoes/{id_execucao}` |
| snapshot global do cluster | `GET /ingestion/operations` |
| lotes e posições da fila de admissão | `GET /ingestion/queue` |
| limpeza transitoria de run cancelada/falha | `POST /ingestion/runs/{run_id}/cleanup-transient-state` |

## `GET /ingestion/runs`

Visao principal do pipeline.

Cada run traz:

- identidade do escopo (`id`, `tipo_fonte`, `ano`);
- estado persistido (`status`, `phase`);
- estado agregado (`state`);
- progresso (`progress`);
- snapshots estruturais (`remote_probe`, `change_summary`, `artifact_snapshot`, `member_snapshot_summary`, `delivery_snapshot_summary`, `reconcile_summary`, `lifecycle_decision`);
- sinais operacionais (`liveness`, `blocking`, `cancellation`, `last_error`, `next_action`);
- links relativos (`links`).

Campos mais importantes para UI:

| Campo | Uso |
| --- | --- |
| `state` | badge operacional |
| `progress` | contadores rápidos |
| `quality_summary` | cards de linhas, members, quarentena e staging |
| `liveness` | detectar stale |
| `blocking` | explicar espera |
| `cancellation` | exibir pedido de cancelamento |
| `last_error` | exibir erro mais recente |
| `next_action` | habilitar ação de operador |

Exemplo:

```bash
curl -X GET "http://localhost:8007/ingestion/runs?pagina=1&tamanho_pagina=50" \
  -H "Authorization: Bearer <token-admin>"
```

## `GET /ingestion/runs/{run_id}`

Drill-down completo da run.

Use quando a UI precisar:

- explicar a decisao de download ou `sem_alteracao`;
- mostrar contadores detalhados;
- mostrar reuso de members;
- abrir troubleshooting de erro;
- decidir entre replay, recover, cancelamento ou investigacao de quarentena.

Leitura recomendada do rerun anual:

- `quality_summary.members_reprocessed`
- `quality_summary.members_reused_from_previous`
- `quality_summary.members_reused_from_failed_parent`
- `artifact_snapshot.storage_uri`
- `artifact_snapshot.storage_role`
- `member_snapshot_summary.by_status`
- `member_snapshot_summary.members[].raw_artifact_uri`
- `member_snapshot_summary.members[].normalized_artifact_uri`
- `lifecycle_decision`

## `GET /ingestion/runs/{run_id}/phases`

Timeline persistida das fases da run.

Cada item inclui:

- `phase`
- `status`
- `attempt`
- `task_id`
- `lease_owner`
- `started_at`
- `heartbeat_at`
- `finished_at`
- `cancel_requested_at`
- `cancelled_at`
- `error_type`
- `error_message`
- `error_retryable`
- `input_artifact_uri`
- `output_artifact_uri`
- `metrics`

Use este endpoint para:

- diagnosticar stale;
- diferenciar falha recuperavel e falha final;
- entender retentativas;
- auditar artifacts de entrada e saida por fase.

Fases esperadas para members financeiros DFP/ITR:

| Fase | Sinal principal |
| --- | --- |
| `profile` | CSV identificado e schema validado |
| `normalize_artifact` | linhas lidas e normalizadas para artifact |
| `load_typed_staging` | artifact carregado no staging tipado |
| `promote` | linhas promovidas para tabelas canonicas |
| `reconcile` | registros obsoletos removidos no escopo do member |
| `complete` | execucao estabilizada |

Metricas comuns em `metrics` ou `quality_summary`:

- `rows_read`
- `rows_normalized`
- `rows_loaded_to_stage`
- `rows_reconciled_deleted`
- `typed_stage_rows_loaded`
- `typed_stage_bytes_loaded`
- `typed_stage_rows_replaced`
- `typed_stage_rows_purged`
- `typed_stage_copy_loads`

Para DFP/ITR, linhas validas nao aparecem em `ingestion_rows`; a leitura operacional deve usar fases, counters e snapshots de artifacts.

## `GET /ingestion/runs/{run_id}/members`

Inventario paginado dos CSVs de uma run.

Cada member inclui:

- identificacao (`id`, `ingestion_file_id`, `member_name`);
- metadados do payload (`member_sha256`, `member_size_bytes`, `row_count`, `encoding`, `delimiter`, `header`);
- status de schema (`schema_status`, `schema_message`);
- metadados do snapshot (`row_kind`, `destino_promovido`, `required_member`, `lifecycle_status`);
- contadores por member (`quarantine_total`, `delivery_total`);
- estado sintetico (`state`);
- links de operacao (`links`).

Estados sinteticos hoje:

- `processed`
- `member_skipped`
- `schema_invalid`
- `unknown`

## `GET /ingestion/members/{member_name}/timeline`

Linha do tempo e ciclo de vida completo de um arquivo member CSV especifico (ex: `fre_cia_aberta_auditor_responsavel_2021.csv`).

Disseca em profundidade tudo o que ocorreu com o arquivo:

- **Metadados do dataset**: chave do dataset, descricao funcional, entidade de destino promovido e se o membro e obrigatorio;
- **Historico de execucoes de sincronizacao**: lista todas as execucoes do member (`ExecucaoSincronizacao`), o arquivo ZIP pai de origem, horarios de inicio/fim, contadores de linhas (lidas, inseridas, atualizadas, inalteradas, rejeitadas) e a timeline detalhada de todas as fases operacionais executadas (`profile`, `stage`, `load_typed_staging`, `promote`, `reconcile`, `complete`);
- **Snapshots do artefato**: historico de versoes do payload observadas nos downloads (SHA-256, tamanho em bytes, contagem de linhas, schema status, lifecycle status e caminhos dos artefatos bruto e normalizado em disco);
- **Historico de drifts CVM (`pending_updates`)**: deteccoes de alteracoes entre versoes de pacotes publicadas pela CVM (`change_category`: `new_member`, `modified`, `unchanged`, `removed`), comparando SHA anterior vs atual e contagem de linhas;
- **Resumo e itens de quarentena**: total de rejeicoes, itens pendentes, distribuicao por codigo de erro e amostra dos itens mais recentes;
- **Impacto no dominio**: total de alteracoes em campos de entidades de negocio promovidas a partir deste arquivo (`HistoricoAlteracaoCampo`).

Exemplo:

```bash
curl -X GET "http://localhost:8007/ingestion/members/fre_cia_aberta_auditor_responsavel_2021.csv/timeline" \
  -H "Authorization: Bearer <token-admin>"
```

## `GET /ingestion/sincronizacoes`

Lista paginada das execucoes administrativas.

Use quando precisar:

- auditar o disparo original;
- navegar pela arvore pai/filho;
- localizar execucao administrativa correlata de uma run;
- acompanhar o preprocessamento manual.

Campos operacionais relevantes:

- `tipo_execucao`
- `id_execucao_pai`
- `filhos_total`
- `filhos_concluidos`
- `filhos_falha`
- `filhos_em_andamento`
- `state`
- `liveness`
- `blocking`
- `cancellation`
- `last_error`
- `next_action`

## `GET /ingestion/sincronizacoes/{id_execucao}`

Detalhe da execucao administrativa, inclusive:

- URL e hash do artefato;
- analise de arquivos (`analise_arquivos`);
- counters agregados;
- execucoes filhas quando aplicavel;
- sinais operacionais agregados.

## `GET /ingestion/operations`

Snapshot consolidado do cluster para consumidores desacoplados.

O retorno agrega:

- `run_counts`
- `execution_counts`
- `cancellation_counts`
- `task_counts`
- `materialization_gate`
- `active_runs`
- `recoverable_runs`
- `ingestion_queue` com profundidade, idade do pedido mais antigo, capacidade configurada, reservas e preparações ZIP ativas

### `GET /ingestion/queue`

Retorna lotes paginados pela ordem persistida de chegada. Cada lote inclui fontes/anos, posição, progresso agregado,
motivo de espera e as etapas relacionadas. Use `lote_id` recebido no disparo para localizar o lote.

```bash
curl -X GET "http://localhost:8007/ingestion/queue?pagina=1&tamanho_pagina=25" \
  -H "Authorization: Bearer <token-admin>"
```

Cada etapa inclui `item_id`, `execucao_id`, fonte, ano, arquivo, etapa, status, tentativa, início e reserva. Os status
operacionais são:

| Status | Interpretação |
| --- | --- |
| `queued` | aguarda uma vaga do pool e ainda não foi enviada ao worker |
| `reserved` | vaga reservada e intenção de publicação registrada no outbox |
| `running` | um worker validou o token e assumiu a etapa |
| `transition_pending` | resultado já persistido; a transição de fase precisa ser aplicada |
| `waiting_manual` | espera confirmação do operador e não ocupa vaga |
| `completed`, `failed`, `cancelled` | estado terminal da etapa |

O outbox é publicado após o commit. Mensagens duplicadas não executam a etapa sem a reserva e o token vigentes. Um
dispatcher periódico retoma publicações pendentes e aplica transições interrompidas após reinício.

## Filas e independencia operacional

Ingestao e materializacao usam filas separadas:

| Fila | Responsabilidade |
| --- | --- |
| `ingestion` | cadastro, preparação de ZIP, CSV e finalização admitidos |
| `ingestion_control` | seleção global, outbox e reconciliação da fila de ingestão |
| `analise_materializacao` | chunks e campanhas de materializacao |

O worker de ingestão pesado consome somente `ingestion`. Um worker de controle separado consome `ingestion_control` e
`celery`, preservando capacidade para seleção, outbox e recovery enquanto uma etapa usa CPU ou banco. O PostgreSQL
serializa a reserva global por uma linha de controle, inclusive entre réplicas do dispatcher. A capacidade é derivada
de `worker.replicaCount x worker.concurrency`, com opção `ingestion.executionSlots` para impor um limite menor. Apenas
uma preparação ZIP é admitida por vez. Quando não há vaga, a execução permanece `agendada` e aparece em
`GET /ingestion/queue`; `em_processamento` só aparece depois da validação da reserva no início do worker.

Ao liberar dependentes, CSVs elegíveis são selecionados antes de novos ZIPs. O CSV de cabeçalho precisa terminar antes
dos members que dependem dele. A etapa que terminou mantém sua reserva lógica até que a transição e a nova elegibilidade
sejam persistidas. O worker revalida a fila antes de iniciar um ZIP e devolve uma publicação deslocada à posição
original se um CSV tiver passado à frente.

O gate de materializacao bloqueia a execucao de novos chunks de materializacao quando ha ingestao ativa ou pausa manual. Ele nao bloqueia workers de ingestao.

## Limpeza transitoria

`POST /ingestion/runs/{run_id}/cleanup-transient-state` prepara uma run `cancelada` ou `falha` para reconstrução operacional.

O endpoint:

- remove staging generico (`ingestion_rows`) e eventos/quarentena associados a linhas da run;
- remove staging tipado financeiro;
- fecha fases ainda abertas como `cancelled`;
- marca execucoes relacionadas nao finais como `cancelada`;
- retorna contadores do que foi removido ou fechado.

Ele nao remove dados canonicos promovidos.

Uso recomendado:

- barra global de operacao;
- automacoes de suporte;
- paineis de NOC;
- alertas de stale, gate e backlog.

## Contratos de controle de ingestao

### Stream de eventos SSE

`GET /ingestion/events/stream` entrega eventos `text/event-stream` autenticados com
o mesmo bearer usado pela superfície de ingestão. O endpoint aceita
`Last-Event-ID`, `cursor` ou `since_revision` (apenas um por conexão) e
`scope=fonte:ano` para limitar um escopo operacional real.

Os tipos estáveis são `ingestion.operations.updated`, `ingestion.run.updated`,
`ingestion.work_item.updated`, `ingestion.member.updated`,
`ingestion.queue.updated`, `ingestion.materialization.updated` e `heartbeat`.
Cada payload inclui `event_id`, `revision`, `occurred_at`, `entity_type`,
`entity_id`, `reason_code` e `data`. O SSE é uma notificação compacta de
invalidação; detalhes autoritativos permanecem nos endpoints REST.

Se o pool de banco estiver temporariamente saturado, a conexão não é encerrada:
o stream envia `heartbeat` com `reason_code=DATABASE_POOL_EXHAUSTED` e
`data.retry_after_seconds`, depois tenta novamente. Clientes devem manter a
conexão e usar o polling REST apenas como contingência.

Nas chamadas REST, saturação residual do pool retorna `503` com
`detail.reason_code=DATABASE_POOL_EXHAUSTED`, `detail.retryable=true` e
`Retry-After: 1`. A autenticação não mantém uma conexão reservada durante a
vida do SSE nem durante operações externas como a inspeção Celery.

`GET /ingestion/work-items` entrega uma linha por escopo fonte/ano, correlacionando atualização, execução administrativa, run técnica, resultado, próxima transição e `allowed_actions`. A lista aceita filtros por estado, ação, fonte, ano, origem, datas, quarentena e drift, além de paginação e ordenação no servidor. Use `GET /ingestion/work-items/{id}` para detalhe e `GET /ingestion/work-items/{id}/events` para a timeline cursorizada.

`GET /ingestion/scopes` consolida cobertura por fonte e ano sem N+1: baseline, última run, members esperados, atualização pendente, trabalho ativo, quarentena, estado de cobertura e próxima ação. `GET /ingestion/runs/{run_id}/completion-evidence` separa members processados e reutilizados, escrita canônica, reconcile, quarentena, drift e contadores de promoção. `GET /ingestion/quarentena/grupos` agrega a fila por motivo, fonte, ano, arquivo, row kind ou reparabilidade.

`POST /ingestion/dispatch/plan` valida escopos e devolve `plan_token` de validade curta, conflitos, possibilidade de reuso por SHA-256 e impacto no gate de materialização. `POST /ingestion/dispatch` confirma o mesmo conjunto com `plan_token` e o header obrigatório `Idempotency-Key`. A resposta é persistida por ator/operação/chave durante 24h; chave repetida com payload diferente retorna `409`. `force_reimport=true` exige `reason` e gera auditoria persistida.

`GET /ingestion/operations` também informa `revision`, `poll_after_ms`, `action_counts`, `waiting_for_operator_count`, progresso agregado, totais reais, truncamento de preview e `queue_health[]`. Cada fila inclui workers observados, slots ocupados, tasks ativas/reservadas/agendadas, backlog e estado `ready`, `paused` ou `without_worker`. Respostas de monitoramento podem reutilizar o mesmo snapshot por até `INGESTION_MONITOR_SNAPSHOT_CACHE_TTL_SECONDS` (3 segundos no Helm; `0` desativa o cache), mantendo baixa latência em polling frequente.

## Interpretacao de `next_action`

| Valor | Significado |
| --- | --- |
| `wait` | run em andamento, na fila ou member filho aguardando vaga global ou janela de despacho do ZIP pai ativo (`blocking.reason_code=awaiting_parent_window`) |
| `start_ingestion` | pre-processamento concluido em modo two-step; use a execucao correlata para iniciar a fase 2 |
| `recover` | run stale, falha recuperavel ou member aguardando retomada apos falha do ZIP pai, desde que possua fonte executavel |
| `inspect_error` | erro impeditivo sem recover direto |
| `inspect_quarantine` | a fila de quarentena deve ser o proximo passo |
| `none` | sem acao sugerida |

## Recover e stale

O sistema executa recovery sweep sobre fases stale.

Efeitos esperados:

- uma run stale so usa `next_action=recover` quando `recovery.eligible=true`;
- uma run pode sair de stale para `state=failed` e manter `last_error.retryable=true` apenas quando houver staging reaplicavel ou execucao de member correlata;
- sem uma estrategia executavel, `recovery` retorna `{ "eligible": false, "strategy": null, "reason_code": "NO_RECOVERY_SOURCE" }`, `next_action=inspect_error` e a run nao entra em `recoverable_runs`;
- `recovery.eligible` representa autorizacao no estado atual, nao apenas existencia historica de uma fonte: runs concluidas usam `RUN_ALREADY_COMPLETED` e falhas nao retentaveis usam `NON_RETRYABLE_FAILURE`;
- processamento de member que nao le nenhuma linha termina como `falha` com mensagem `NO_ROWS_PROCESSED`, em vez de sucesso vazio;
- runs terminais nao bloqueiam novo dispatch do mesmo escopo, e o work item oferece `start_ingestion` com `TERMINAL_RUN_REDISPATCH_ALLOWED`, sem exigir limpeza de filas ou staging para liberar a nova execucao;
- cancelamentos pendentes em runs stale podem ser estabilizados como `cancelled`.

Durante uma retentativa automatica de member, a execucao filha e a run ficam em `agendada`, a fase fica
`failed_retryable` e `last_error.retryable=true`. A UI deve apresentar o member como aguardando nova tentativa, sem
marcar a run como falha terminal. Cada tentativa e registrada separadamente; se o limite de tentativas for esgotado, a
run termina em `state=failed`, com a fase `failed_final` e `last_error.retryable=true` quando o erro continuar
recuperavel.

Uma run com `recovery.strategy=rerun_member_execution` so e recuperavel quando existe `IngestionFile` persistido para o
pacote pai. O replay direto do member sem essa fonte responde `409` com `detail.reason_code=NO_RECOVERY_SOURCE`,
`detail.next_action=replay_parent_execution` e `parent_execucao_id`; a execucao filha nao e alterada nem publicada.
Nesse caso, reprocesse o ZIP pai primeiro. Ao fechar um ZIP com falhas, `ExecucaoSincronizacao.mensagem_erro` resume
nomes dos members e a primeira linha de seus erros; use o detalhe da execucao filha para o erro completo.

`POST /ingestion/runs/{run_id}/recover` retorna `409` com o mesmo objeto `recovery` e `reason_code=NO_RECOVERY_SOURCE` quando nao existir fonte executavel. O comando nao devolve sucesso com uma lista vazia nesse caso.

Quando a estrategia for `rerun_member_execution` ou `rerun_parent_execution`, o comando cria um lote persistido, retorna
`status=agendada` e `lote_id`, e nao executa o processamento pesado dentro da requisicao HTTP. Acompanhe a ordem, a etapa
e o motivo de espera em `GET /ingestion/queue`.

Falha de publicacao do Celery nao converte o pedido de recovery em falha terminal nem altera a run para `failed_final`:
o item continua reservado com erro de publicacao e o dispatcher periodico tenta publicar novamente. O lote e a execucao
permanecem visiveis em `GET /ingestion/queue` enquanto aguardam publicacao ou inicio pelo worker. A reaplicacao de staging
retido que nao exige nova execucao de ZIP ou CSV continua sendo sincrona no banco.

## Encerramento de falhas investigadas

`POST /ingestion/runs/{run_id}/acknowledge-failure` encerra uma pendencia `inspect_error` depois da investigacao. O payload exige:

```json
{
  "reason": "Falha de infraestrutura confirmada; novo dispatch sera criado."
}
```

A operacao nao apaga run, fases, staging, quarentena, filas ou dados promovidos. Ela grava uma auditoria imutavel com ator, motivo e uma chave da ocorrencia da falha. A resposta e `failure_acknowledgement` com `acknowledged_at`, `acknowledged_by`, `reason` e `failure_key`.

Depois do reconhecimento:

- a run preserva `state=failed` e `last_error` para historico;
- `next_action` passa de `inspect_error` para `none`;
- o work item deixa de aparecer em `GET /ingestion/work-items?next_action=inspect_error`;
- `allowed_actions[]` troca `inspect_error` e `acknowledge_failure` por `inspect`, mantendo `start_ingestion` para um novo dispatch equivalente;
- repeticao do comando e idempotente para a mesma ocorrencia;
- uma falha posterior na mesma run possui outra `failure_key` e exige novo reconhecimento.

Use `acknowledge-failure` para limpar a fila de atencao sem perda de evidencia. `cleanup-transient-state` tem outra finalidade: remove estado transitorio quando uma reconstrução administrativa exigir essa limpeza.

## Superficie Operacional Centrada no Arquivo

A superficie de consulta centrada no arquivo organiza o ciclo de vida operacional na hierarquia do dominio:
**ANO → ARQUIVO PRINCIPAL → MEMBRO → TENTATIVAS E ETAPAS → RESULTADO**.

Arquivos simples (como o cadastro global `cadastro:cad_cia_aberta.csv`) nao possuem ZIP, ano ficticio ou membro artificial.
Runs, work items e execucoes administrativas sao registros subordinados e nao definem a identidade do arquivo.

### Identificadores Estaveis

- **Arquivo Logico**: `file_id` estavel:
  - Pacotes anuais: `{tipo_fonte}:{ano}:{arquivo_principal}` (ex: `dfp:2022:dfp_cia_aberta_2022.zip`)
  - Arquivos simples sem ano: `{tipo_fonte}:{arquivo_principal}` (ex: `cadastro:cad_cia_aberta.csv`)
- **Membro**: `member_id` delimitado pelo arquivo pai e chave canonica:
  - `{file_id}:{member_name}` (ex: `dfp:2022:dfp_cia_aberta_2022.zip:dfp_cia_aberta_BPA_con_2022.csv`)
  - Membros homonimos em pacotes diferentes nunca misturam historicos ou estados.

### Integridade, Atividade e Versoes

A API retorna separadamente:
1. `versao_em_uso`: versao de dados efetivamente em uso no banco, com sua integridade comprovada.
2. `versao_alvo`: versao alvo da ingestao mais recente ou em processamento (mostrando se foi apenas detectada, se esta em processamento ou se falhou).
   Uma falha no processamento de uma atualizacao CVM nao torna, por si so, a versao em uso anterior incompleta!
3. `atividade_atual`: `idle`, `em_processamento`, `aguardando_ingestao`, `aguardando_parent_window` (espera automatica) ou `bloqueada`.

#### Estados de Integridade Calculados no Servidor

- `completo`: todos os membros obrigatorios esperados pelo catalogo foram processados e promovidos com escrita confirmada, sem ressalvas.
- `completo_com_ressalvas`: dados centrais promovidos, com ressalvas nao bloqueantes (ex: itens em quarentena ou membros opcionais ausentes).
- `parcial`: promocao incompleta (membros obrigatorios faltantes no pacote, ou com falha/quarentena impeditiva).
- `nao_aplicado`: arquivo apenas detectado, agendado ou falhou antes do download/promocao.
- `evidencia_insuficiente`: registros incompletos ou legados sem confirmacao de escrita canonica.

#### Resolucao de Falhas

- `aberta`: falha ativa pendente de solucao.
- `em_nova_tentativa`: nova tentativa em processamento.
- `restaurada_com_evidencia`: recuperada ou reprocessada com sucesso comprovado na mesma versao.
- `versao_substituida`: substituida por uma versao mais recente integra (sem provar que a antiga foi reparada).
- `encerrada_sem_restauracao`: falha investigada e reconhecida via `acknowledge-failure` (encerra a investigacao sem reparar a integridade).

### `GET /ingestion/files`

Listagem paginada por arquivo logico com contagem nao truncada e filtros server-side:

```bash
curl -X GET "http://localhost:8007/ingestion/files?ano=2022&fonte=dfp&pagina=1&tamanho_pagina=50" \
  -H "Authorization: Bearer <token-admin>"
```

Parametros de consulta suportados:
- `ano`: ano de referencia
- `fonte`: tipo de fonte (`dfp`, `itr`, `fre`, `fca`, `ipe`, `cgvn`, `vlmo`, `cadastro`)
- `arquivo`: filtro por trecho do nome do arquivo
- `atividade`: filtrar por atividade corrente (`idle`, `na_fila`, `em_processamento`, `aguardando_ingestao`, `aguardando_parent_window`, `bloqueada`)
- `integridade`: filtrar por integridade em uso (`completo`, `completo_com_ressalvas`, `parcial`, `nao_aplicado`, `evidencia_insuficiente`)
- `necessidade_intervencao`: booleano indicando necessidade de intervencao manual de operador
- `resolucao_falha`: `aberta`, `em_nova_tentativa`, `restaurada_com_evidencia`, `versao_substituida`, `encerrada_sem_restauracao`
- `concluido_apos` e `concluido_antes`: intervalo de data/hora de conclusao
- `pagina` e `tamanho_pagina`

`atividade=na_fila` identifica uma execução que aguarda vaga ou confirmação de reserva pelo worker. `atividade=em_processamento` identifica somente etapas com início confirmado pelo worker. A listagem reutiliza snapshots idênticos pelo TTL configurado em `INGESTION_MONITOR_SNAPSHOT_CACHE_TTL_SECONDS` (3 segundos no Helm; `0` desativa o cache).

### `GET /ingestion/files/{file_id}`

Detalhe completo do arquivo logico com versoes, membros, auditoria de integridade com evidencias, historico de tentativas correlacionadas e acoes permitidas:

```bash
curl -X GET "http://localhost:8007/ingestion/files/dfp:2022:dfp_cia_aberta_2022.zip" \
  -H "Authorization: Bearer <token-admin>"
```

### `GET /ingestion/files/{file_id}/members/{member_name}/timeline`

Linha do tempo e ciclo de vida completo do membro delimitado pelo arquivo principal:

```bash
curl -X GET "http://localhost:8007/ingestion/files/dfp:2022:dfp_cia_aberta_2022.zip/members/dfp_cia_aberta_BPA_con_2022.csv/timeline" \
  -H "Authorization: Bearer <token-admin>"
```

