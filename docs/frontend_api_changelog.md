# Changelog de Contrato da API para Clientes

Este arquivo registra apenas mudancas com impacto consumivel por clientes da API.

Convencoes deste changelog:

- cada entrada lista endpoints ou superficies afetadas;
- descreve o comportamento atual entregue ao cliente;
- documentacao editorial sem mudanca de contrato nao entra aqui;
- a fonte de verdade de campos e exemplos continua sendo o OpenAPI gerado pela aplicacao.

## 2026-07-01 - Disparo de ingestao passa a acionar o gate de materializacao imediatamente

### Endpoints e superficies com impacto operacional visivel

- `POST /ingestion/sincronizacoes/cadastro`
- `POST /ingestion/sincronizacoes/dfp/{ano}`
- `POST /ingestion/sincronizacoes/itr/{ano}`
- `POST /ingestion/sincronizacoes/fre/{ano}`
- `POST /ingestion/sincronizacoes/fca/{ano}`
- `POST /ingestion/sincronizacoes/ipe/{ano}`
- `POST /ingestion/sincronizacoes/vlmo/{ano}`
- `POST /ingestion/sincronizacoes/cgvn/{ano}`
- `POST /ingestion/sincronizacoes/tudo/{ano}`
- `POST /ingestion/sincronizacoes/reprocessar-arquivo`
- `GET /ingestion/sincronizacoes`
- `GET /ingestion/operations`
- `GET /analise/materializacoes/monitoramento`
- `GET /analise/materializacoes/controle`

### Mudanca de comportamento

- os endpoints de disparo de ingestao agora persistem `ExecucaoSincronizacao.status=agendada` antes de publicar a task Celery
- o `id_tarefa` retornado pela API e o mesmo valor persistido no banco e enviado ao Celery
- em `POST /ingestion/sincronizacoes/tudo/{ano}`, a API publica apenas `cadastro` no request HTTP; as fontes anuais ja registradas sao publicadas pelo worker quando `cadastro` termina com sucesso, `sem_alteracao` ou `skipped`
- o gate automatico de materializacao passa a considerar `agendada`, `em_execucao` e `aguardando_ingestao` como bloqueadores
- estados finais como `sucesso`, `sem_alteracao`, `skipped`, `falha` e `cancelada` continuam sem bloquear o gate
- quando uma ingestao e disparada durante materializacao, a UI deve esperar `gate.status=red` com `reason_code=INGESTION_ACTIVE` mesmo antes do worker iniciar a task
- `GET /analise/materializacoes/monitoramento` tolera falha/timeout de inspeção Celery e limita a deteccao detalhada de campanhas pendentes recuperaveis pela janela operacional de recovery

### Leitura recomendada pelo frontend

- apos disparar uma sincronizacao, usar `id_tarefa` para correlacionar a linha em `GET /ingestion/sincronizacoes`
- quando `gate.status=red`, pausar expectativas de progresso de novas campanhas/chunks de materializacao
- tratar execucoes `agendada` como trabalho aceito e aguardando worker, nao como chamada perdida

## 2026-06-30 - Direct path financeiro expoe fases e contadores mais precisos para DFP/ITR

### Endpoints e superficies com impacto operacional visivel

- `GET /ingestion/runs`
- `GET /ingestion/runs/{run_id}`
- `GET /ingestion/runs/{run_id}/phases`
- `GET /ingestion/runs/{run_id}/members`
- `GET /ingestion/operations`
- `POST /ingestion/runs/{run_id}/cleanup-transient-state`

### Mudanca de comportamento

- members financeiros DFP/ITR passam a reportar fases especificas: `profile`, `normalize_artifact`, `load_typed_staging`, `promote`, `reconcile` e `complete`
- linhas validas de DFP/ITR nao sao persistidas em `ingestion_rows`; a UI deve usar fases, counters e snapshots de artifacts para progresso operacional
- `quality_summary` e `metrics` podem incluir `rows_read`, `rows_normalized`, `rows_loaded_to_stage`, `rows_reconciled_deleted`, `typed_stage_rows_loaded`, `typed_stage_bytes_loaded`, `typed_stage_rows_replaced`, `typed_stage_rows_purged` e `typed_stage_copy_loads`
- a coordenacao de ZIP financeiro limita members ativos por pai, entao uma run ITR/DFP pode permanecer em execucao com poucos filhos ativos por vez; isso e esperado e reduz pressao no worker/banco
- as filas de ingestion ficam separadas em `ingestion` e `ingestion_control`; materializacao permanece em `analise_materializacao`
- novo endpoint administrativo `POST /ingestion/runs/{run_id}/cleanup-transient-state` limpa staging transitorio de run `cancelada` ou `falha`, fecha fases/execucoes presas e retorna contadores do que foi removido

### Leitura recomendada pelo frontend

- para progresso de ITR/DFP, priorizar `GET /ingestion/runs/{run_id}/phases` e os counters de `quality_summary`
- para tela de filhos/members, tratar filhos aguardando como fila pendente normal quando a janela ativa do pai estiver cheia
- para diagnostico de stuck, considerar `heartbeat_at` e evolucao dos counters da fase atual, nao apenas o status `em_execucao`
- oferecer limpeza transitoria apenas para operadores e apenas depois de cancelamento/falha, pois o endpoint prepara a run para reconstrução a partir dos artifacts/dados remotos

## 2026-06-30 - Snapshots operacionais de ingestao passam a expor ponteiros duraveis para artifacts locais

### Endpoints e superficies com impacto operacional visivel

- `GET /ingestion/runs`
- `GET /ingestion/runs/{run_id}`

### Mudanca de comportamento

- `artifact_snapshot` passa a expor `storage_uri`, `storage_role`, `storage_content_type` e `storage_size_bytes` quando a run persistiu o artifact local correspondente
- `member_snapshot_summary.members[]` passa a poder expor `raw_artifact_uri`, `raw_artifact_content_type`, `raw_artifact_size_bytes`, `normalized_artifact_uri`, `normalized_artifact_format`, `normalized_artifact_content_sha256` e `normalized_artifact_size_bytes`
- esses campos tornam explicito, no contrato da API, qual artifact bruto foi usado no replay e qual artifact normalizado foi produzido para staging e promocao

### Leitura recomendada pelo frontend

- para drill-down operacional de run, usar `artifact_snapshot.storage_uri` como ponteiro primario do artifact persistido da run
- para troubleshooting de member, usar `member_snapshot_summary.members[].raw_artifact_uri` para replay bruto e `member_snapshot_summary.members[].normalized_artifact_uri` para rastrear o artifact que alimentou o staging tipado
- a mudanca e aditiva; consumidores que ignoram esses campos continuam compativeis

## 2026-06-30 - Ingestao ganha recovery sweep para runs stale e `next_action=recover` em falhas recuperaveis

### Endpoints e superficies com impacto operacional visivel

- `GET /ingestion/runs`
- `GET /ingestion/runs/{run_id}`
- `GET /ingestion/sincronizacoes`
- `GET /ingestion/sincronizacoes/{id_execucao}`

### Mudanca de comportamento

- o backend passa a executar recovery sweep periodico sobre fases de ingestao com heartbeat stale
- quando o sweep encontra run presa sem cancelamento pendente, a run pode sair de `state=stale` para `state=failed`, mas com `last_error.retryable=true` e `next_action=recover`
- quando o sweep encontra cancelamento propagado em uma run stale, ele conclui o cancelamento e estabiliza o estado final como `cancelled`
- `next_action=recover` deixa de significar apenas `state=stale`; agora tambem cobre falha recuperavel marcada pelo sweep

### Leitura recomendada pelo frontend

- usar `next_action` como sinal primario de recuperacao administrativa, em vez de depender apenas de `state=stale`
- quando `state=failed` e `last_error.retryable=true`, oferecer a mesma acao de recuperacao usada para stale
- para troubleshooting fino, ler `liveness`, `last_error` e `cancellation` em conjunto

## 2026-06-30 - Ingestao expande telemetria de staging tipado financeiro no resumo operacional

### Endpoints e superficies com impacto operacional visivel

- `GET /ingestion/runs`
- `GET /ingestion/runs/{run_id}`
- `GET /ingestion/sincronizacoes`
- `GET /ingestion/sincronizacoes/{id_execucao}`

### Mudanca de comportamento

- o backend passa a expor no `quality_summary` e no `progress` das runs os sinais `typed_stage_rows_loaded`, `typed_stage_bytes_loaded`, `typed_stage_rows_replaced`, `typed_stage_rows_purged` e `typed_stage_copy_loads`
- esses campos permitem separar custo de carga no staging tipado, recarga de member e limpeza pos-promocao sem depender de logs de worker
- o staging tipado financeiro passa a ser purgado explicitamente ao final do processamento do member, mantendo replay baseado em artifact normalizado e reduzindo residuo operacional

### Leitura recomendada pelo frontend

- para cards de progresso por run: ler `progress.typed_stage_rows_loaded`, `progress.typed_stage_bytes_loaded` e `progress.typed_stage_copy_loads`
- para troubleshooting de custo ou loops de recarga: ler `quality_summary.typed_stage_rows_replaced` e `quality_summary.typed_stage_rows_purged`
- para consumidores que ja usam `quality_summary`, a mudanca e aditiva e nao exige remocao de campos antigos

## 2026-06-30 - Ingestao ganha inventario por member, snapshot consolidado de operacao e acoes diretas por run

### Endpoints e superficies com impacto operacional visivel

- `GET /ingestion/runs/{run_id}/members`
- `GET /ingestion/operations`
- `POST /ingestion/runs/{run_id}/cancel`
- `POST /ingestion/runs/{run_id}/members/{member_id}/cancel`
- `POST /ingestion/runs/{run_id}/recover`

### Mudanca de comportamento

- o backend passa a expor inventario paginado de members por run, com `member_name`, `schema_status`, `lifecycle_status`, `delivery_total`, `quarantine_total`, `state` e `links`
- consumidores desacoplados agora podem ler `GET /ingestion/operations` para obter um snapshot unico de runs ativas, runs recuperaveis, cancelamentos, sinais de fila Celery e estado do gate de materializacao
- cancelamento direto por `run_id` deixa de exigir descoberta previa de `id_execucao`
- cancelamento direto por `member_id` permite interromper apenas o CSV alvo quando existir execucao filha correspondente
- recuperacao administrativa de run (`POST /ingestion/runs/{run_id}/recover`) reaplica o replay completo da run quando ela estiver `stale` ou com erro recuperavel

### Leitura recomendada pelo frontend

- para tabela de ZIP/member: usar `GET /ingestion/runs/{run_id}/members`
- para toolbar operacional global: usar `GET /ingestion/operations`
- para acao de parar ZIP: usar `POST /ingestion/runs/{run_id}/cancel`
- para acao de parar CSV individual: usar `POST /ingestion/runs/{run_id}/members/{member_id}/cancel`
- quando `next_action=recover` em uma run e a UI optar por acao automatizada de operador, usar `POST /ingestion/runs/{run_id}/recover`

## 2026-06-30 - Ingestao passa a expor estado operacional agregado e timeline de fases

### Endpoints e superficies com impacto operacional visivel

- `GET /ingestion/sincronizacoes`
- `GET /ingestion/sincronizacoes/{id_execucao}`
- `GET /ingestion/runs`
- `GET /ingestion/runs/{run_id}`
- `GET /ingestion/runs/{run_id}/phases`
- `POST /ingestion/sincronizacoes/cancelar`

### Mudanca de comportamento

- execucoes administrativas e runs tecnicas passam a expor `state`, `liveness`, `blocking`, `cancellation`, `last_error`, `next_action` e `links`
- `state` deixa explicito se o escopo esta `queued`, `waiting`, `running`, `stale`, `succeeded`, `skipped`, `failed` ou `cancelled`
- `liveness` passa a refletir heartbeat, owner do lease, task ativa e classificacao `is_stale`, evitando depender de logs para diagnostico de run presa
- `blocking` resume por que a execucao esta parada ou aguardando, com codigos como `queued`, `awaiting_ingestion`, `stale` e `manual_cancel`
- `cancellation` passa a refletir o ultimo pedido de cancelamento persistido, inclusive `requested`, `propagated` e `completed`
- o backend agora persiste a timeline operacional de fases da run e a expõe em `GET /ingestion/runs/{run_id}/phases`

### Leitura recomendada pelo frontend

- para listagem operacional: consumir `GET /ingestion/runs` e `GET /ingestion/sincronizacoes`
- para detalhe de run: consumir `GET /ingestion/runs/{run_id}` e `GET /ingestion/runs/{run_id}/phases`
- para detalhe de execucao ZIP/member: consumir `GET /ingestion/sincronizacoes/{id_execucao}`
- quando `state=stale`, tratar `next_action=recover` como sinal de recuperacao administrativa ou investigacao operacional
- quando `status=aguardando_ingestao`, tratar `blocking.reason_code=awaiting_ingestion` como espera normal da fase 2

## 2026-06-29 - Gate de materializacao passa a bloquear tambem o despacho e o inicio de tasks

### Endpoints e superficies com impacto operacional visivel

- `GET /analise/materializacoes/monitoramento`
- `GET /analise/materializacoes/controle`
- `POST /analise/materializacoes/controle/pause`
- `POST /analise/materializacoes/controle/resume`
- campanhas automaticas de materializacao disparadas por pos-ingestao

### Mudanca de comportamento

- o gate de materializacao deixa de atuar apenas dentro da execucao da campanha e passa a bloquear tambem o enfileiramento do dispatcher, o reenfileiramento de campanhas e o inicio de chunks
- quando o gate esta `red`, campanhas podem continuar existindo em `pending`, mas novas tasks de dispatcher/campanha/chunk nao devem entrar em execucao efetiva
- a task direta de materializacao por companhia tambem passa a respeitar o gate antes de iniciar trabalho
- o roteamento Celery de ingestao e materializacao fica explicito: ingestao na fila `celery`, materializacao na fila dedicada `analise_materializacao`

## 2026-06-29 - Worker de replay de member reduz footprint por chunk

### Superficies com impacto operacional visivel

- `POST /ingestion/sincronizacoes/reprocessar-arquivo`
- `GET /ingestion/sincronizacoes`
- `GET /ingestion/sincronizacoes/{id_execucao}`

### Mudanca de comportamento

- o worker de replay de member deixa de materializar todos os chunks restantes de `fre` em memoria de uma vez
- a leitura de `ingestion_rows` por chunk passa a carregar apenas os campos minimos necessarios ao promote e expunge os rows processados da sessao antes de seguir para o proximo chunk
- isso reduz crescimento do identity map por member e diminui o risco de `SIGKILL` em workers durante promote de CSVs volumosos

## 2026-06-27 - Replay de member deixa de reconstruir estado cumulativo do ano

### Superficies com impacto operacional visivel

- `POST /ingestion/sincronizacoes/reprocessar-arquivo`
- `GET /ingestion/sincronizacoes`
- `GET /ingestion/sincronizacoes/{id_execucao}`

### Mudanca de comportamento

- o replay de member isolado para `dfp`, `itr`, `fre` e `fca` deixa de reconstruir em memoria o historico completo de staging de siblings ja processados no mesmo ano
- a task passa a semear a resolucao por cabecalho a partir das tabelas canonicas de documentos ja promovidos, com footprint por task limitado e previsivel
- isso reduz o risco de degradacao progressiva, `SIGKILL` por pressao de memoria e reruns interminaveis do mesmo CSV durante reprocessamentos seletivos

## 2026-06-26 - Gate de materializacao bloqueia apenas ingestao em execucao

### Endpoints com ajuste operacional visivel

- `GET /analise/materializacoes/monitoramento`
- `GET /analise/materializacoes/controle`
- `POST /analise/materializacoes/controle/resume`

### Mudanca de comportamento

- o admission gate da materializacao deixa de considerar execucoes apenas `agendada` ou `cancelada` como bloqueadoras
- somente execucoes de ingestao realmente em `em_execucao` mantem o gate em `red` por `INGESTION_ACTIVE`
- com isso, telas operacionais deixam de exibir bloqueio vermelho indevido quando nao ha ingestao rodando de fato

## 2026-06-26 - Reprocessamento seletivo aceita nomes de arquivos com maiusculas

### Endpoint com correcao de validacao

- `POST /ingestion/sincronizacoes/reprocessar-arquivo`

### Mudanca de comportamento

- o backend agora valida `arquivo` de forma case-insensitive no reprocessamento seletivo
- nomes de members CVM com siglas em maiusculas, como `BPA`, `BPP`, `BPR`, `DRE`, `DVA` e similares, deixam de falhar com `422 Unprocessable Entity`
- o backend passa a preservar o nome canonico do arquivo ao persistir a execucao filha e ao despachar a task de member; o valor nao e mais regravado em minusculas
- nao houve mudanca de payload nem de shape da resposta; a correcao e apenas de aceitacao do nome informado

## 2026-06-26 - Rerun anual de ingestion reaproveita members bem-sucedidos de execucao pai falhada

### Endpoints com semantica operacional atualizada

- `POST /ingestion/sincronizacoes/dfp/{ano}`
- `POST /ingestion/sincronizacoes/itr/{ano}`
- `POST /ingestion/sincronizacoes/fre/{ano}`
- `POST /ingestion/sincronizacoes/fca/{ano}`
- `POST /ingestion/sincronizacoes/ipe/{ano}`
- `POST /ingestion/sincronizacoes/vlmo/{ano}`
- `POST /ingestion/sincronizacoes/cgvn/{ano}`
- `POST /ingestion/sincronizacoes/tudo/{ano}`
- `POST /ingestion/sincronizacoes/reprocessar-arquivo`
- `GET /ingestion/runs`
- `GET /ingestion/runs/{run_id}`

### Mudanca de comportamento

- um rerun anual da mesma fonte/ano agora funciona como rerun de recuperacao
- se a execucao anual anterior falhou, members que ja tinham sido concluídos com sucesso continuam elegiveis para reaproveitamento por `member_sha256`
- o rerun passa a reprocessar apenas members falhados, ausentes, interrompidos ou com SHA alterado
- `force_reimport=true` continua sendo o override explicito para reprocessar tudo
- `/ingestion/sincronizacoes/reprocessar-arquivo` permanece para recuperacao cirurgica, mas nao e mais o caminho normal exigido para falha parcial em ZIP anual

### Leitura recomendada pelo frontend

Para qualquer tela que mostre uma run anual:

1. ler `GET /ingestion/runs` para listagem, cards e badges resumidos
2. ler `GET /ingestion/runs/{run_id}` para detalhe operacional
3. tratar `quality_summary` como fonte principal de contadores
4. tratar `member_snapshot_summary` como inventario duravel por member
5. tratar `lifecycle_decision` como explicacao compacta da decisao de reaproveitamento

### Campos novos ou agora operacionalmente relevantes

#### Em `quality_summary`

- `members_reused_from_previous`
- `members_reused_from_failed_parent`
- `members_reprocessed`
- `members_processados`
- `members_skipped`

#### Em `lifecycle_decision`

- `members_skipped_by_sha`
- `members_processed`
- `members_reused_from_previous`
- `members_reused_from_failed_parent`

#### Em `member_snapshot_summary`

- `by_status.processed`
- `by_status.member_skipped`
- `by_schema_status.ok`
- `by_schema_status.reused`
- `members[]`

### Semantica exata para UI

#### `quality_summary.members_reprocessed`

- representa quantos members realmente voltaram para o fluxo `stage -> promote -> reconcile`
- este e o numero correto para mostrar como "members executados neste rerun"
- nao deve ser somado com `members_reused_from_previous` para representar falha; o reaproveitamento e comportamento esperado

#### `quality_summary.members_reused_from_previous`

- representa quantos members foram reaproveitados por igualdade de `member_sha256`
- este e o numero correto para mostrar como "members reaproveitados" ou "members pulados por igualdade"
- pode incluir reaproveitamento vindo de uma run anual anterior bem-sucedida ou falha

#### `quality_summary.members_reused_from_failed_parent`

- representa o subconjunto de `members_reused_from_previous` cuja execucao anual pai anterior terminou em `falha`
- use este campo para explicar o caso operacional que motivou a mudanca: rerun anual apos falha parcial
- este campo nao substitui `members_reused_from_previous`; ele apenas detalha sua origem

#### `quality_summary.members_processados`

- continua significando members que entraram no fluxo normal da run atual
- em reruns de recuperacao, tende a acompanhar `members_reprocessed`
- para frontend novo, prefira exibir `members_reprocessed` como label principal e manter `members_processados` como compatibilidade/apoio

#### `quality_summary.members_skipped`

- continua sendo o total de members encerrados como `skipped` nesta run
- inclui principalmente skip por igualdade
- para explicar a causa do skip, o frontend deve cruzar com `lifecycle_decision.members_skipped_by_sha` e `member_snapshot_summary.by_schema_status.reused`

#### `lifecycle_decision.members_skipped_by_sha`

- resumo compacto da decisao de lifecycle
- serve bem para badges pequenos e listagens
- para drill-down por member, nao use sozinho; complemente com `member_snapshot_summary`

#### `member_snapshot_summary.by_status.member_skipped`

- inventario duravel por status de member
- e o melhor campo para tabelas por member e dashboards que precisem mostrar distribuicao por status

#### `member_snapshot_summary.by_schema_status.reused`

- identifica members reaproveitados por `member_sha256`
- em telas detalhadas, pode ser apresentado como motivo tecnico do skip

### Exemplo de leitura de uma run de recuperacao

Se uma resposta vier com:

- `quality_summary.members_total = 19`
- `quality_summary.members_reprocessed = 3`
- `quality_summary.members_reused_from_previous = 16`
- `quality_summary.members_reused_from_failed_parent = 16`

o frontend deve comunicar algo como:

- "19 members avaliados"
- "3 members reprocessados neste rerun"
- "16 members reaproveitados por igualdade"
- "os 16 reaproveitados vieram de members bem-sucedidos de uma execucao anual anterior que terminou em falha"

### O que muda no comportamento de botoes e fluxos

#### Fluxo recomendado para falha parcial em ZIP anual

- manter o botao normal de rerun anual
- nao forcar o operador a escolher manualmente os CSVs que falharam
- apos o rerun, mostrar no detalhe da run quantos members foram reaproveitados e quantos realmente rodaram

#### Fluxo recomendado para `/ingestion/sincronizacoes/reprocessar-arquivo`

- manter como acao especializada
- usar quando o operador quer agir sobre um member/arquivo especifico
- nao sugerir esse endpoint como fluxo principal para "3 arquivos falharam em 19", porque o rerun anual agora ja resolve isso de forma inteligente

### Impacto esperado no frontend

- telas operacionais de runs devem diferenciar members reaproveitados de members efetivamente reprocessados
- badges ou resumos de recuperacao podem usar `members_reused_from_failed_parent` para explicar por que um rerun anual nao rodou todos os CSVs novamente
- o frontend deve continuar tratando `/ingestion/sincronizacoes/reprocessar-arquivo` como acao especializada, nao como fluxo padrao para recuperar falha parcial em ZIP anual
- tabelas detalhadas podem mostrar:
  - status da run
  - total de members
  - members reprocessados
  - members reaproveitados
  - members reaproveitados de pai falhado
  - members skipped

### Compatibilidade

- nao houve remocao de endpoint
- nao houve quebra de rota
- a mudanca e de semantica operacional e de campos resumidos que agora devem ser priorizados pela UI
- clientes antigos continuam funcionando, mas nao aproveitam a nova explicacao de recuperacao se ignorarem os novos campos

## 2026-06-25 - Updates Service usa baseline canônico de members para cadastro e demais fontes

### Endpoints com semântica corrigida

- `GET /updates/pending/{id}`
- `GET /updates/pending/{id}/members`

### Mudança de comportamento

- a análise detalhada de updates passa a priorizar o baseline canônico de lifecycle (`SourceMemberSnapshot`) da última run bem-sucedida
- `IngestionFileMember` permanece apenas como fallback de compatibilidade quando o snapshot canônico ainda não existir
- o fluxo de `cadastro` agora persiste o mesmo baseline estrutural de members já usado nas fontes anuais em ZIP

### Impacto esperado no frontend

- redução de falsos `added` em updates de `cadastro`
- maior confiabilidade em `change_summary.members_added`, `members_modified` e no detalhamento retornado por `/updates/pending/{id}/members`
- members removidos passam a preservar metadados anteriores corretos no payload de comparação

## 2026-06-25 - Autorizacao consistente para operacoes delegadas de materializacao

### Endpoints impactados

- `GET /auth/me`
- `GET /usuarios`
- `GET /usuarios/{usuario_id}`
- `POST /usuarios`
- `PATCH /usuarios/{usuario_id}`
- `POST /analise/materializacoes/campanhas/{campanha_id}/reativar`
- `POST /analise/materializacoes/recuperacao/trigger`

### Mudanca de autorizacao

- os endpoints delegados de recuperacao da materializacao deixam de usar token dedicado
- a autorizacao agora aceita:
  - token de sistema
  - usuario com `is_admin=true`
  - usuario com `pode_operar_materializacao=true`

### Campos novos em contratos de usuario

- `pode_operar_materializacao` em:
  - `GET /auth/me`
  - itens de `GET /usuarios`
  - `GET /usuarios/{usuario_id}`
  - resposta de `POST /usuarios`
  - resposta de `PATCH /usuarios/{usuario_id}`
  - payloads de `POST /usuarios`
  - payloads de `PATCH /usuarios/{usuario_id}`

### Impacto esperado no frontend

- telas administrativas podem conceder ou revogar a capacidade operacional de materializacao sem promover o usuario a admin
- o frontend pode usar `GET /auth/me` para habilitar ou ocultar acoes de reativacao e sweep sem depender de configuracao externa
- clientes que usavam token dedicado para os endpoints delegados devem migrar para login de usuario ou token de sistema
- `is_admin` continua implicando acesso operacional, mas a UI nao precisa mais acoplar retry de materializacao a perfil administrativo amplo

## 2026-06-25 - Self-healing delegado para materializacao presa

### Endpoints novos

- `POST /analise/materializacoes/campanhas/{campanha_id}/reativar`
- `POST /analise/materializacoes/recuperacao/trigger`

### Modelo de autenticacao

- os endpoints acima usam o mesmo modelo geral da API
- autorizacao valida token de sistema, usuario admin ou usuario com `pode_operar_materializacao=true`

### Campos novos em `/analise/materializacoes/monitoramento`

- `recoverable_pending_campaigns`
- `undispatched_stuck_campaigns`
- `oldest_undispatched_campaign_created_at`
- `oldest_undispatched_campaign_elapsed_seconds`
- `recoverable_campaign_ids`
- `last_pending_recovery_sweep_at`
- `last_pending_recovery_sweep_summary`
- `pending_recovery_active_tasks`

### Campos novos em `campaigns[]`

- `recovery_state`
- `last_recovery_check_at`
- `last_recovery_action`
- `last_recovery_reason_code`

### Contrato de resposta dos endpoints delegados

- `status`: `triggered`, `recovered`, `noop` ou `rejected`
- `reason_code`: um entre `PENDING_UNDISPATCHED`, `STALE_CHUNK`, `WAITING_FOR_GATE`, `WAITING_FOR_SLOT`, `CHUNK_IN_PROGRESS`, `NO_PENDING_ITEMS`, `CAMPAIGN_NOT_FOUND`, `NOT_PENDING`, `PENDING_RECOVERY_DISABLED`
- `affected_campaigns`
- `requeued_campaigns`
- `recovered_chunks`
- `recovered_items`
- `dispatcher_enqueued`
- `triggered_at`

Campos adicionais do sweep global:

- `scanned_campaigns`
- `recoverable_campaigns`

### Semantica operacional atual

- `PENDING_UNDISPATCHED` representa campanha pendente com itens pendentes, sem chunk ativo, sem execucao canônica `running` e sem bloqueio operacional explícito
- `STALE_CHUNK` continua significando campanha com chunk stale ou recuperável
- quando o worker de campanha encontra chunks stale ativos, ele tenta recuperar e reenfileirar inline antes de permanecer em espera operacional
- quando uma campanha e efetivamente reativada ou reenfileirada, o backend a registra temporariamente como `requeued`; durante essa janela curta ela sai de `recoverable_pending_campaigns` e de `recoverable_campaign_ids`
- a reativacao delegada nao ignora gate vermelho, nao ignora saturacao de slots e nao interrompe chunk vivo
- o trigger global executa apenas uma varredura limitada, respeitando os limites configurados de sweep e reenfileiramento
- o backend agora persiste o resumo do ultimo sweep automatico, usado pelo monitoramento

### Impacto esperado no frontend

- paineis operacionais podem oferecer acao de retry sem exigir acesso administrativo amplo
- campanhas pendentes agora podem ser distinguidas entre bloqueadas, recuperaveis e efetivamente presas
- a UI deve tratar `noop` como resposta operacional válida, nao como erro tecnico
- `recoverable_campaign_ids` e `campaigns[].recovery_state` passam a ser os sinais recomendados para habilitar botao de reativacao
- campanhas marcadas como `requeued` nao devem continuar sendo exibidas pela UI como "ainda recuperaveis agora"; elas ja estao em janela de retry em transito

### Guia rapido de uso dos endpoints

- `POST /analise/materializacoes/campanhas/{campanha_id}/reativar`
  - retry operacional suportado para uma campanha conhecida
- `POST /analise/materializacoes/recuperacao/trigger`
  - sweep limitado para encontrar e recuperar campanhas pendentes elegiveis
- `POST /analise/materializacoes/recuperar-stale`
  - operacao administrativa de baixo nivel para recuperar stale em lote
- `POST /analise/materializacoes/campanhas/{campanha_id}/recuperar`
  - operacao administrativa de baixo nivel para recuperar stale em uma campanha especifica

## 2026-06-24 - Exclusao padrao de companhias canceladas na materializacao

### Superficie impactada

- comportamento operacional de campanhas de materializacao
- `GET /analise/materializacoes`
- `GET /analise/materializacoes/{execucao_id}`
- `GET /analise/materializacoes/monitoramento`

### Semantica operacional atual

- campanhas automaticas e fluxos padrao de materializacao nao incluem companhias com `situacao_registro=CANCELADA`
- a materializacao pontual de uma companhia cancelada continua possivel apenas com override explicito no disparo operacional
- quando uma companhia cancelada for disparada sem esse override, o backend pode registrar uma execucao concluida sem revisoes, usando sinalizacao de skip operacional no `summary`

### Impacto esperado no frontend

- paineis operacionais passam a observar menos itens/campanhas originados de companhias canceladas
- detalhamento de execucao deve tolerar `summary.skipped_reason=COMPANHIA_CANCELADA` sem tratar isso como falha tecnica
- contagens e previsoes de backlog de materializacao deixam de considerar canceladas por padrao

## 2026-06-24 - Materializacao incremental com observabilidade expandida

### Endpoints afetados

- `GET /analise/materializacoes`
- `GET /analise/materializacoes/{execucao_id}`
- `GET /analise/materializacoes/monitoramento`

### Novos campos em execucoes de materializacao

- `materialization_mode`: `full` ou `incremental`
- `invalidated_from`: primeira data de conhecimento recomposta quando a execucao e incremental
- `window_total_knowledge_dates`
- `window_processed_knowledge_dates`
- `inserted_context_revisions`
- `inserted_fact_revisions`
- `closed_context_revisions`
- `closed_fact_revisions`
- `deleted_future_context_revisions`
- `deleted_future_fact_revisions`

### Novos campos em `/analise/materializacoes/monitoramento`

- `running_full_executions`
- `running_incremental_executions`
- `lowest_running_invalidated_from`
- `stalled_incremental_execution_ids`
- `running_execution_previews`

### Novos campos em previews de item

- `materialization_mode` em:
  - `running_items_preview`
  - `pending_items_preview`
- `invalidated_from` em:
  - `running_items_preview`
  - `pending_items_preview`

### Semantica operacional atual

- A primeira materializacao de uma companhia/escopo continua podendo ser `full`.
- Materializacoes recorrentes podem ser `incremental`, recomponto apenas o sufixo a partir de `invalidated_from`.
- `progress.total_knowledge_dates` e `progress.processed_knowledge_dates` passam a representar a janela efetivamente processada pela execucao, nao necessariamente toda a historia da companhia.
- O frontend deve usar `materialization_mode`, `invalidated_from` e os contadores de revisao para distinguir refresh historico completo de recomposicao incremental.
- `running_execution_previews` e `stalled_incremental_execution_ids` sao os sinais recomendados para painel operacional e diagnostico de execucoes presas.

## 2026-06-24 - Quarentena aberta por padrão e métricas separadas de histórico

### Ajustes de contrato em `GET /ingestion/quarentena`

- quando `status` não é enviado, a listagem retorna apenas itens `pendente`
- para consultar histórico completo, o frontend deve enviar `status=all`

### Ajustes de contrato em `GET /ingestion/quarentena/resumo`

- quando `status` não é enviado, `total`, `por_erro`, `por_arquivo` e `por_arquivo_e_erro` passam a refletir apenas a fila aberta (`pendente`)
- novos campos:
  - `total_pendentes`
  - `total_resolvidos`
  - `total_historico`
- `por_status` continua trazendo a distribuição histórica sob os filtros contextuais aplicados

### Impacto esperado

- telas de “Fila de Reparos” deixam de exibir itens já resolvidos por padrão
- contadores de “arquivos com erros” deixam de misturar pendências abertas com histórico resolvido
- o frontend passa a ter uma forma explícita de mostrar fila aberta e histórico sem inferência local

## 2026-06-23 - FRE de plano de recompra por classe sem obrigatoriedade de tipo preferencial

### Ajustes de contrato em `GET /fre/plano-recompra-classes-acoes`

- `tipo_classe_acao_preferencial` passa a aceitar `null`
- novo campo `especie_acao`

### Semântica atual

- o backend não trata mais `Tipo_Classe_Acao_Preferencial` como obrigatório para `fre_cia_aberta_plano_recompra_classe_acao`
- quando esse campo vier vazio, a linha continua elegível para ingestão desde que a espécie da ação esteja presente
- a identidade lógica dessa linha passa a considerar `especie_acao` junto do identificador do plano

## 2026-06-24 - Tolerância ampliada para diagnósticos reais de quarentena em FRE e ITR

### Ajustes de comportamento

- `fre_relacao_subordinacao` não exige mais `Nome_Pessoa_Relacionada` para aceitar a linha
- `fre_relacao_subordinacao` passa a aceitar `nome_administrador = null` quando a linha traz a pessoa relacionada e demais sinais materiais válidos
- `fre_relacao_familiar` passa a tolerar linhas da CVM com aspas desbalanceadas em `Cargo_Pessoa_Relacionada`, preservando `tipo_parentesco` e `observacao` nas colunas corretas
- `fre_participacao_sociedade` passa a tratar `CNPJ=0000000000000` como ausente
- o fluxo financeiro (`DFP` e `ITR`) passa a permitir companhia provisória quando a linha tem identidade suficiente, mas a companhia não está no cadastro local

### Impacto esperado

- menos falsos positivos de `normalizacao_invalida: campo_obrigatorio_ausente` em FRE
- `GET /fre/relacoes-subordinacao` pode retornar `nome_administrador: null` para refletir fielmente linhas válidas publicadas pela CVM
- redução de quarentena causada por `ProgramLimitExceeded` quando uma linha de `fre_relacao_familiar` vinha deslocada por aspas malformadas na origem CVM
- eliminação de quarentena para CNPJ zerado usado como placeholder em participações societárias
- redução de `companhia_nao_encontrada` em documentos financeiros válidos da CVM

## 2026-06-23 - Recuperacao automatica de chunks stale na materializacao

### Novos endpoints operacionais

- `POST /analise/materializacoes/recuperar-stale`
- `POST /analise/materializacoes/campanhas/{campanha_id}/recuperar`

### Campos novos em execucoes e previews

- `chunk_execucao_id` em:
  - `GET /analise/materializacoes`
  - `GET /analise/materializacoes/{execucao_id}`
  - `running_items_preview`
  - `pending_items_preview`

### Campos novos em `/analise/materializacoes/monitoramento`

- `recovering_campaigns`
- `queued_chunks`
- `running_chunks`
- `stale_chunks`
- `stale_item_count`
- `stale_chunk_preview`

### Campos novos em resumo de campanha

- `active_chunks`
- `active_chunk_id`
- `active_chunk_lease_expires_at`
- `active_chunk_ids_preview`
- `stale_chunks`
- `wait_reason`

### Semântica operacional atual

- Liveness de chunk não deve mais ser inferido apenas por `running_items`.
- Cada chunk possui lease e heartbeat persistidos.
- Chunks `queued` ou `running` com lease expirado entram no fluxo de recuperação.
- A recuperação devolve itens inacabados para `pending` e preserva itens já concluídos.
- `stale_chunks`, `stale_item_count` e `stale_chunk_preview` passaram a representar apenas stale ainda acionável no snapshot operacional.
- Chunks stale históricos de campanhas já concluídas não devem mais ser tratados pelo frontend como itens bloqueados ou pendências de recuperação.
- A materialização agora distingue concorrência entre campanhas e concorrência de chunks dentro da mesma campanha.
- `ANALISE_MATERIALIZACAO_MAX_ACTIVE_CAMPAIGNS` limita campanhas simultâneas.
- `ANALISE_MATERIALIZACAO_MAX_ACTIVE_CHUNKS_PER_CAMPAIGN` limita chunks simultâneos dentro da mesma campanha.
- `active_chunks` e `active_chunk_ids_preview` devem ser usados quando a UI precisar refletir paralelismo intra-campanha.
- Campanhas em `pending` por gate vermelho não ficam mais se auto-reagendando continuamente.
- A retomada do processamento pendente acontece por dispatcher explícito quando o sistema volta a verde.
- O frontend pode distinguir:
  - campanha progredindo;
  - campanha aguardando gate vermelho;
  - campanha aguardando recuperação de chunk stale.

## 2026-06-23 - Gate de admissao e controle operacional da materializacao

### Novos endpoints operacionais

- `GET /analise/materializacoes/controle`
- `POST /analise/materializacoes/controle/pause`
- `POST /analise/materializacoes/controle/resume`

### Campos novos em `/analise/materializacoes/monitoramento`

- `gate`
- `waiting_for_gate_campaigns`

### Campos principais de `gate`

- `status`: `green` ou `red`
- `reason_code`: `NO_BLOCKERS`, `INGESTION_ACTIVE`, `MANUAL_PAUSE` ou `GATE_DISABLED`
- `gate_enabled`: indica se o gate automático está ativo
- `manual_control`: `auto` ou `paused`
- `manual_reason`: motivo textual da pausa manual, quando houver
- `blocking_ingestions`: quantidade de execuções/runs bloqueadoras
- `pending_ingestions`: quantidade de execuções em `aguardando_ingestao`
- `next_check_at`: próxima rechecagem recomendada enquanto o gate estiver vermelho
- `blockers`: preview dos bloqueadores operacionais

### Ajustes de comportamento que impactam telas operacionais

- A campanha não enfileira mais todos os chunks de uma vez.
- O orquestrador enfileira um único chunk por ciclo.
- Se a ingestão estiver ativa, a campanha fica `pending` com `wait_reason=INGESTION_ACTIVE`.
- Se houver pausa manual, a campanha fica `pending` com `wait_reason=MANUAL_PAUSE`.
- O chunk em execução termina a companhia atual antes de respeitar o gate vermelho.
- Itens ainda não iniciados voltam para `pending` quando o gate fecha durante um chunk.

## 2026-06-23 - Campanhas e chunks de materializacao analitica

### Mudancas de orquestracao operacional

- O pos-ingestao financeiro nao dispara mais uma task Celery por companhia/escopo.
- O backend agora cria uma campanha de materializacao e a divide em chunks.
- A execucao canônica por companhia continua existindo, mas agora pode ser vinculada a:
  - `campanha_id`
  - `campanha_item_id`
  - `queue_name`
  - `position_in_chunk`
- O frontend administrativo pode mostrar progresso por campanha e por item sem inferencia local.

### Filtros e campos novos

- `GET /analise/materializacoes` aceita `campanha_id`
- `GET /analise/materializacoes` e `GET /analise/materializacoes/{execucao_id}` agora podem retornar:
  - `campanha_id`
  - `campanha_item_id`
  - `queue_name`
  - `position_in_chunk`

### Campos novos em `/analise/materializacoes/monitoramento`

- `fila.materialization_orchestrator_active_tasks`
- `fila.materialization_chunk_active_tasks`
- `fila.materialization_queue_depth`
- `pending_campaigns`
- `running_campaigns`
- `pending_items`
- `running_items`
- `success_items`
- `failed_items`
- `skipped_items`
- `campaigns`
- `running_items_preview`
- `pending_items_preview`

## 2026-06-22 - Consolidacao da API analitica em `/analise/companhias`

### Superficie oficial atual

- `GET /analise/metricas`
- `GET /analise/materializacoes`
- `GET /analise/materializacoes/monitoramento`
- `GET /analise/materializacoes/{execucao_id}`
- `GET /analise/companhias/{codigo_cvm}`
- `GET /analise/companhias/{codigo_cvm}/series`
- `GET /analise/companhias/{codigo_cvm}/comparacoes`
- `GET /analise/companhias/{codigo_cvm}/qualidade`
- `GET /analise/companhias/{codigo_cvm}/sinais`
- `GET /analise/companhias/{codigo_cvm}/eventos`
- `GET /analise/companhias/{codigo_cvm}/restatements`
- `GET /analise/companhias/{codigo_cvm}/governanca`
- `GET /analise/companhias/{codigo_cvm}/pessoas`
- `GET /analise/companhias/{codigo_cvm}/brief`

### Remapeamento obrigatorio de rotas

- `/companhias/{codigo_cvm}/analise/v2` -> `/analise/companhias/{codigo_cvm}`
- `/companhias/{codigo_cvm}/analise/v2/series` -> `/analise/companhias/{codigo_cvm}/series`
- `/companhias/{codigo_cvm}/analise/v2/comparacoes` -> `/analise/companhias/{codigo_cvm}/comparacoes`
- `/companhias/{codigo_cvm}/analise/v2/qualidade` -> `/analise/companhias/{codigo_cvm}/qualidade`
- `/companhias/{codigo_cvm}/analise/v2/sinais` -> `/analise/companhias/{codigo_cvm}/sinais`
- `/companhias/{codigo_cvm}/analise/v2/eventos` -> `/analise/companhias/{codigo_cvm}/eventos`
- `/companhias/{codigo_cvm}/analise/v2/restatements` -> `/analise/companhias/{codigo_cvm}/restatements`

### Rotas removidas sem compatibilidade

- `/companhias/{codigo_cvm}/analise`
- `/companhias/{codigo_cvm}/analise/overview`
- `/companhias/{codigo_cvm}/analise/financeiro`
- `/companhias/{codigo_cvm}/analise/comparativo`
- `/companhias/{codigo_cvm}/analise/eventos`
- `/companhias/{codigo_cvm}/analise/pessoas-remuneracao`
- `/companhias/{codigo_cvm}/analise/mercado-insiders`

Todas as rotas acima agora devem ser consideradas inexistentes. O cliente deve esperar `404 Not Found`, não `410`.

### Convencoes obrigatorias de cliente

- Datas e datetimes usam ISO 8601.
- Valores decimais continuam sendo strings decimais canonicas.
- Razoes usam valor decimal e `unit=ratio`.
- Variacoes em pontos percentuais usam `unit=percentage_point`.
- O cliente nao deve inferir percentual a partir de qualquer campo sem olhar `unit`.
- O cliente nao deve derivar trimestre isolado a partir de acumulados quando consultar `base_periodo=quarter`, pois o backend ja faz isso.

### Parametros e valores permitidos

- `periodicidade`: `annual` ou `quarterly`
- `base_periodo`: `fy`, `quarter` ou `ytd`
- `escopo`: `consolidated` ou `individual`
- `metricas`: lista CSV de ids estaveis do catalogo
- `as_of`: data de corte em `AAAA-MM-DD`
- `horizonte_anos`: horizonte anual maximo retornado em consultas historicas de FY

### Campos importantes do contrato

- `resolution.mode`: `canonical` ou `runtime_fallback`
- `resolution.materialization_execution_id`: id da execucao canônica usada pela resposta
- `resolution.materialized_at`: timestamp de conclusao da materializacao canônica
- `resolution.as_of`: data de corte efetivamente considerada
- `period_id`: id canonico do periodo (`FY2025`, `2025-Q3`, `2025-YTDQ3`)
- `period_nature`: `instant` ou `duration`
- `period_basis`: `fy`, `quarter` ou `ytd`
- `form`: `DFP`, `ITR` ou `DERIVED`
- `version`: versao documental utilizada
- `restated`: indica se a observacao depende de reapresentacao
- `value_source`: `reported`, `derived_from_ytd_delta`, `derived_from_dfp_minus_ytd` ou `derived_from_formula`
- `comparables`: referencia explicita de `yoy_period_id` e `qoq_period_id`
- `provenance`: lista completa de evidencias documentais
- `issues`: problemas contextuais detectados
- `indisponibilidades`: itens nao calculados com `reason_code`
- `horizonte_anos`: ecoa o horizonte anual efetivamente aplicado em `/series` e `/comparacoes`
- `metric_unit`: unidade dos valores atual e comparavel em `/comparacoes`
- `comparison_unit`: unidade do resultado comparativo em `/comparacoes`
- `event_id`: identificador estavel de cada evento em `/eventos`

### Expansoes analiticas anuais e temporais

- `/series` com `periodicidade=annual&base_periodo=fy&horizonte_anos=5` devolve ate cinco FY historicos por metrica.
- `/comparacoes` preserva a unidade economica da metrica em `metric_unit` e usa `comparison_unit` para o resultado comparativo. Em `BASE100`, por exemplo, os valores continuam em `BRL` e o indice usa `index`.
- `/eventos` agora expoe `event_id`, adequado para chave estavel de lista, deduplicacao e deep link.
- `/governanca` retorna observacoes temporais anuais com suporte a `as_of` e `horizonte_anos`.
- `/pessoas` retorna observacoes temporais anuais de remuneracao e empregados com suporte a `as_of` e `horizonte_anos`.
- `/brief` consolida trimestre atual, trimestre anterior, comparavel anual, FY atual e FY anterior no mesmo payload.

### Novas metricas oficiais

- `depreciacao_amortizacao`
- `capex`
- `divida_bruta`
- `ebitda`
- `caixa_livre`
- `divida_liquida`
- `alavancagem`
- `conversao_lucro_caixa`

### Monitoramento da materializacao canônica

Novos endpoints operacionais:

- `GET /analise/materializacoes`
- `GET /analise/materializacoes/monitoramento`
- `GET /analise/materializacoes/{execucao_id}`

Campos principais para monitoramento:

- `status`: `running`, `success` ou `failed`
- `started_at`: inicio da execucao
- `finished_at`: conclusao da execucao, quando houver
- `updated_at`: ultimo heartbeat persistido
- `elapsed_seconds`: tempo decorrido
- `estimated_remaining_seconds`: tempo restante estimado, quando houver progresso parcial suficiente
- `estimated_finish_at`: horario estimado de conclusao
- `progress.total_knowledge_dates`: total previsto de datas de conhecimento
- `progress.processed_knowledge_dates`: quantidade ja processada
- `progress.current_known_from`: data de conhecimento atualmente em processamento
- `progress.progress_ratio`: progresso estimado de `0` a `1`
- `progress.context_revisions`: revisoes de contexto acumuladas
- `progress.fact_revisions`: revisoes de fatos acumuladas
- `summary`: payload bruto persistido para auditoria operacional no endpoint de detalhe
- `campanha_id`: campanha associada a execucao, quando houver
- `campanha_item_id`: item da campanha associado, quando houver
- `queue_name`: fila Celery usada pela execucao
- `position_in_chunk`: posicao do item dentro do chunk processado

Campos do snapshot de fila:

- `fila.workers_reporting`: quantidade de workers que responderam ao inspect
- `fila.materialization_active_tasks`: tasks de materializacao ativas
- `fila.materialization_reserved_tasks`: tasks de materializacao reservadas
- `fila.materialization_scheduled_tasks`: tasks de materializacao agendadas
- `fila.materialization_orchestrator_active_tasks`: tasks orquestradoras de campanha ativas
- `fila.materialization_chunk_active_tasks`: tasks de chunk ativas
- `fila.materialization_queue_depth`: profundidade observada da fila dedicada, quando disponivel
- `running_executions`: execucoes `running` persistidas no banco
- `pending_campaigns`: campanhas pendentes
- `running_campaigns`: campanhas em andamento
- `pending_items`: itens pendentes nas campanhas
- `running_items`: itens em andamento nas campanhas
- `success_items`: itens concluidos com sucesso nas campanhas
- `failed_items`: itens com falha nas campanhas
- `skipped_items`: itens deduplicados/skipped
- `oldest_running_started_at`: inicio da execucao mais antiga em andamento
- `longest_running_elapsed_seconds`: tempo da execucao mais antiga em andamento
- `stalled_threshold_seconds`: janela usada para detectar heartbeat ausente
- `stalled_execution_ids`: execucoes `running` com `updated_at` mais antigo que o threshold
- `campaigns`: resumo das campanhas relevantes
- `running_items_preview`: preview dos itens atualmente em execucao
- `pending_items_preview`: preview dos proximos itens pendentes

### Mudanca de orquestracao operacional

- O pos-ingestao financeiro nao dispara mais uma task Celery por companhia/escopo.
- O backend agora cria uma campanha de materializacao e a divide em chunks.
- A execucao canônica por companhia continua existindo, mas agora pode ser vinculada a:
  - `campanha_id`
  - `campanha_item_id`
  - `queue_name`
  - `position_in_chunk`
- O frontend administrativo pode mostrar progresso por campanha e por item sem inferencia local.

### Mapeamento pratico de consultas do frontend

- Painel operacional da materializacao: usar `/analise/materializacoes`
- Banner ou widget de saturacao dos workers: usar `/analise/materializacoes/monitoramento`
- Drill-down de uma execucao especifica: usar `/analise/materializacoes/{execucao_id}`
- Tela de resumo analitico da companhia: usar `/analise/companhias/{codigo_cvm}`
- Graficos historicos: usar `/analise/companhias/{codigo_cvm}/series`
- Cartoes de YoY, QoQ, CAGR, vertical e base 100: usar `/analise/companhias/{codigo_cvm}/comparacoes`
- Avisos de consistencia e cobertura: usar `/analise/companhias/{codigo_cvm}/qualidade`
- Badges e alertas deterministas: usar `/analise/companhias/{codigo_cvm}/sinais`
- Timeline de eventos: usar `/analise/companhias/{codigo_cvm}/eventos`
- Detalhe de reapresentacoes: usar `/analise/companhias/{codigo_cvm}/restatements`
- Timeline temporal de governanca: usar `/analise/companhias/{codigo_cvm}/governanca`
- Timeline temporal de pessoas e remuneracao: usar `/analise/companhias/{codigo_cvm}/pessoas`
- Brief analitico de leitura rapida: usar `/analise/companhias/{codigo_cvm}/brief`

### Renomeacoes recomendadas no frontend

- Renomear hooks, clients, query keys e types que contenham `V2` para nomes sem versão.
- Remover qualquer tratamento específico para `ANALISE_V1_REMOVED`.
- Ajustar builders de URL para usar o prefixo canônico `/analise/companhias`.

### Calculos de frontend que devem ser removidos

- Conversao cega de razao para percentual sem olhar `unit`
- Derivacao manual de `2T`, `3T` e `4T` a partir de acumulados
- Inferencia manual de periodo comparavel para YoY ou QoQ
- Regras deterministicas hoje cobertas por `/sinais`

### Exemplo de serie trimestral isolada

```json
{
  "resolution": {
    "mode": "canonical",
    "materialization_execution_id": "4f7b0ed0-f2c4-4d7a-90b4-c0b2a0e2db78",
    "materialized_at": "2026-06-22T12:00:00Z",
    "as_of": "2025-11-08"
  },
  "observacoes": [
    {
      "metric_id": "receita_liquida",
      "period_id": "2025-Q3",
      "fiscal_year": 2025,
      "quarter": 3,
      "period_nature": "duration",
      "period_basis": "quarter",
      "start_date": "2025-07-01",
      "end_date": "2025-09-30",
      "value": "127906000000",
      "unit": "BRL",
      "scope": "consolidated",
      "form": "ITR",
      "version": 1,
      "restated": false,
      "value_source": "reported",
      "comparables": {
        "yoy_period_id": "2024-Q3",
        "qoq_period_id": "2025-Q2"
      },
      "provenance": [
        {
          "source": "CVM",
          "dataset": "demonstracoes_financeiras",
          "form": "ITR",
          "document_id": 9103,
          "version": 1,
          "account_code": "3.01"
        }
      ]
    }
  ]
}
```

### Exemplo de comparacao indisponivel

```json
{
  "resolution": {
    "mode": "canonical",
    "materialization_execution_id": "4f7b0ed0-f2c4-4d7a-90b4-c0b2a0e2db78",
    "materialized_at": "2026-06-22T12:00:00Z",
    "as_of": "2025-11-08"
  },
  "comparacoes": [
    {
      "metric_id": "receita_liquida",
      "period_id": "2025-YTDQ3",
      "comparison_kind": "QoQ",
      "status": "unavailable",
      "reason_code": "QOQ_NOT_SUPPORTED_FOR_YTD_FLOW",
      "metric_unit": "BRL",
      "comparison_unit": "ratio"
    }
  ]
}
```

### Sugerestao de contratos TypeScript

```ts
type AnalisePeriodicidade = "annual" | "quarterly";
type AnaliseBasePeriodo = "fy" | "quarter" | "ytd";
type AnaliseEscopo = "consolidated" | "individual";
type AnaliseUnit = "BRL" | "ratio" | "percentage_point" | "count" | "shares" | "index";
type AnaliseResolutionMode = "canonical" | "runtime_fallback";

type AnaliseResolutionMetadata = {
  mode: AnaliseResolutionMode;
  materialization_execution_id: string | null;
  materialized_at: string | null;
  as_of: string | null;
};

type AnaliseMaterializacaoStatus = "running" | "success" | "failed";

type AnaliseMaterializacaoProgress = {
  total_knowledge_dates: number | null;
  processed_knowledge_dates: number | null;
  current_known_from: string | null;
  progress_ratio: number | null;
  context_revisions: number | null;
  fact_revisions: number | null;
};

## 2026-06-29 - Manifesto de artifacts por fase de ingestao

Impacto para frontend/admin: **sim**. O endpoint operacional `GET /ingestion/runs/{run_id}/phases` passou a expor metadados duraveis sobre os artifacts locais efetivamente usados e produzidos por cada fase.

### Alteracoes de contrato

- Schema `IngestionRunPhaseExecutionResumo`:
  - novo campo `input_artifact_uri: string | null`
  - novo campo `output_artifact_uri: string | null`
- Campo existente `metrics`:
  - pode incluir `artifacts: Array<{
      uri: string;
      role: string;
      content_type: string;
      logical_name: string;
      size_bytes: number;
      content_sha256: string;
    }>`

### Uso esperado no consumidor

- Usar `input_artifact_uri` para explicar qual artifact de entrada foi realmente consumido pela fase.
- Usar `output_artifact_uri` para drill-down de replay e troubleshooting operacional.
- Usar `metrics.artifacts` para exibir manifesto resumido por fase sem depender de logs do worker.
- O nome logico do member preserva o case original em `logical_name`.

### Compatibilidade

- Campos novos sao aditivos.
- Consumidores atuais continuam funcionando se ignorarem `input_artifact_uri`, `output_artifact_uri` e `metrics.artifacts`.

type AnaliseMaterializacaoExecucaoResumo = {
  id: string;
  codigo_cvm: number;
  escopo: AnaliseEscopo;
  calculation_version: string;
  status: AnaliseMaterializacaoStatus;
  coverage_complete: boolean;
  source: string;
  started_at: string | null;
  finished_at: string | null;
  updated_at: string | null;
  elapsed_seconds: number | null;
  estimated_remaining_seconds: number | null;
  estimated_finish_at: string | null;
  progress: AnaliseMaterializacaoProgress;
};

type AnaliseMaterializacaoMonitoramento = {
  as_of: string;
  fila: {
    workers_reporting: number;
    materialization_active_tasks: number;
    materialization_reserved_tasks: number;
    materialization_scheduled_tasks: number;
  };
  running_executions: number;
  oldest_running_started_at: string | null;
  longest_running_elapsed_seconds: number | null;
  stalled_threshold_seconds: number;
  stalled_execution_ids: string[];
};

type AnaliseSeriesObservation = {
  metric_id: string;
  period_id: string;
  fiscal_year: number;
  quarter: number | null;
  period_nature: "instant" | "duration";
  period_basis: AnaliseBasePeriodo;
  start_date: string | null;
  end_date: string;
  value: string;
  unit: AnaliseUnit;
  scope: AnaliseEscopo;
  form: "DFP" | "ITR" | "DERIVED";
  version: number | null;
  restated: boolean;
  value_source: "reported" | "derived_from_ytd_delta" | "derived_from_dfp_minus_ytd" | "derived_from_formula";
  comparables: {
    yoy_period_id: string | null;
    qoq_period_id: string | null;
  };
  provenance: Array<{
    source: string;
    dataset: string;
    form: "DFP" | "ITR" | "DERIVED";
    document_id: number | null;
    version: number | null;
    account_code: string | null;
  }>;
};
```

### Checklist de migracao de frontend

- Remapear todas as chamadas antigas para os endpoints sem versão
- Trocar parsing de datas analiticas para ISO 8601
- Passar a respeitar `unit` antes de formatar qualquer valor
- Remover calculos locais de QoQ, YoY comparavel e trimestre isolado
- Consumir `issues` e `indisponibilidades` em vez de assumir ausencia silenciosa
- Tratar `404` das rotas analiticas antigas como contrato removido
- Consumir `/analise/metricas` para ids, nomes e unidades oficiais
- Expor `resolution` para inspeção operacional e troubleshooting de dados `as_of`
- Se houver tela operacional ou admin, consumir `/analise/materializacoes` e `/analise/materializacoes/monitoramento`
