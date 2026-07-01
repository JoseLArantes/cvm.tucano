# Guia de Integracao do Frontend para Materializacao Analitica

## Objetivo

Este documento descreve como o frontend deve consumir os endpoints operacionais de materializacao analitica sem depender de leitura do codigo backend.

O foco aqui e:

- observabilidade operacional
- retry delegado
- diferenca entre endpoints de uso normal e endpoints administrativos
- semantica dos estados retornados
- como habilitar ou esconder acoes na UI

## Visao geral

A materializacao analitica possui dois grupos de endpoints operacionais:

1. Endpoints delegados para uso normal de operadores:
   - `POST /analise/materializacoes/campanhas/{campanha_id}/reativar`
   - `POST /analise/materializacoes/recuperacao/trigger`

2. Endpoints administrativos de baixo nivel:
   - `POST /analise/materializacoes/recuperar-stale`
   - `POST /analise/materializacoes/campanhas/{campanha_id}/recuperar`

Regra principal para frontend:

- para acao normal de retry na UI, use os endpoints delegados
- nao use os endpoints `recuperar*` como botao principal de retry
- trate `recuperar*` como ferramenta administrativa/manual

## Autorizacao

### Endpoints delegados

Os endpoints abaixo aceitam:

- token de sistema
- usuario com `is_admin=true`
- usuario com `pode_operar_materializacao=true`

Endpoints:

- `POST /analise/materializacoes/campanhas/{campanha_id}/reativar`
- `POST /analise/materializacoes/recuperacao/trigger`

### Endpoints administrativos

Os endpoints abaixo exigem:

- token de sistema
- usuario admin

Endpoints:

- `POST /analise/materializacoes/recuperar-stale`
- `POST /analise/materializacoes/campanhas/{campanha_id}/recuperar`

### Como o frontend deve decidir se mostra acoes

Use `GET /auth/me`.

Considere que o usuario pode operar retry delegado quando:

- `is_admin = true`, ou
- `pode_operar_materializacao = true`

Considere que o usuario pode operar recovery administrativo de baixo nivel quando:

- `is_admin = true`

## Endpoint por endpoint

## `POST /analise/materializacoes/campanhas/{campanha_id}/reativar`

### Finalidade

Retry operacional suportado para uma campanha especifica.

### Quando usar

- a UI ja conhece a `campanha_id`
- a UI quer oferecer acao de "tentar novamente" para uma campanha presa
- a campanha aparece como recuperavel no monitoramento

### O que este endpoint pode fazer

- recuperar chunks stale ativos e reenfileirar a campanha
- reenfileirar uma campanha `PENDING_UNDISPATCHED`
- devolver `noop` quando a campanha nao pode ser destravada naquele momento

### O que este endpoint nao faz

- nao ignora gate vermelho
- nao ignora limite de concorrencia
- nao interrompe chunk vivo
- nao faz requeue irrestrito de outras campanhas

### Campos relevantes da resposta

- `status`
- `reason_code`
- `affected_campaigns`
- `requeued_campaigns`
- `recovered_chunks`
- `recovered_items`
- `dispatcher_enqueued`
- `triggered_at`

### Interpretacao recomendada da UI

#### `status = "recovered"`

Interpretacao:

- havia `STALE_CHUNK`
- o backend recuperou os chunks e reenfileirou a campanha

Comportamento recomendado:

- mostrar feedback de sucesso operacional
- atualizar monitoramento
- retirar badge de "recuperavel agora" se a campanha passar a `requeued`

#### `status = "triggered"`

Interpretacao:

- a campanha estava em `PENDING_UNDISPATCHED`
- o backend reenfileirou a campanha

Comportamento recomendado:

- mostrar feedback de retry disparado
- atualizar monitoramento

#### `status = "noop"`

Interpretacao:

- nao havia acao operacional valida naquele instante

Comportamento recomendado:

- nao tratar como erro tecnico
- mostrar o `reason_code` como motivo operacional

#### `status = "rejected"`

Interpretacao:

- campanha inexistente ou contexto invalido

Comportamento recomendado:

- tratar como erro operacional real

## `POST /analise/materializacoes/recuperacao/trigger`

### Finalidade

Sweep limitado para encontrar e recuperar campanhas pendentes elegiveis.

### Quando usar

- a UI nao sabe qual campanha esta presa
- a UI quer oferecer acao global do tipo "tentar recuperar pendencias"
- operador quer pedir uma varredura limitada em vez de retry por campanha

### O que este endpoint pode fazer

- varrer campanhas `pending`
- recuperar campanhas com `STALE_CHUNK`
- reenfileirar campanhas `PENDING_UNDISPATCHED`

### O que este endpoint nao faz

- nao ignora gate
- nao ignora concorrencia
- nao reprocessa tudo
- nao e substituto de monitoramento

### Campos adicionais da resposta

- `scanned_campaigns`
- `recoverable_campaigns`

### Interpretacao recomendada da UI

- tratar como operacao em lote
- mostrar contadores retornados
- atualizar monitoramento apos sucesso
- nao presumir que todas as campanhas pendentes foram tocadas

## `POST /analise/materializacoes/recuperar-stale`

### Finalidade

Recovery administrativo de baixo nivel para chunks stale em lote.

### Quando usar

- somente em telas administrativas
- somente quando houver necessidade de manutencao tecnica
- quando o operador quiser limpar stale em varias campanhas sem passar pela classificacao delegada

### Risco de uso inadequado

Se o frontend usar este endpoint como botao padrao:

- a UI mistura operacao administrativa com retry normal
- o contrato fica mais dificil de explicar
- aumenta o risco de acionar recovery tecnico sem contexto

### Recomendacao

- esconder este endpoint em fluxos normais
- expor apenas em telas administrativas/diagnostico

## `POST /analise/materializacoes/campanhas/{campanha_id}/recuperar`

### Finalidade

Recovery administrativo de baixo nivel para stale em uma campanha especifica.

### Quando usar

- somente em tela administrativa
- somente quando a campanha ja e conhecida
- quando o operador quer limpar stale tecnico sem usar o fluxo delegado

### Recomendacao

- nao usar como CTA principal da UI operacional
- preferir `.../reativar` para o fluxo normal de usuario

## Como o frontend deve escolher o endpoint

| Situacao | Endpoint recomendado |
| --- | --- |
| usuario clicou em retry de uma campanha especifica | `POST /analise/materializacoes/campanhas/{campanha_id}/reativar` |
| usuario quer varrer um lote de pendencias sem saber quais campanhas estao presas | `POST /analise/materializacoes/recuperacao/trigger` |
| admin precisa executar limpeza tecnica de stale em lote | `POST /analise/materializacoes/recuperar-stale` |
| admin precisa executar limpeza tecnica de stale em uma campanha especifica | `POST /analise/materializacoes/campanhas/{campanha_id}/recuperar` |

## Uso do monitoramento

Endpoint principal:

- `GET /analise/materializacoes/monitoramento`

## Controles de concorrencia

Existem dois limites distintos no backend:

- `ANALISE_MATERIALIZACAO_MAX_ACTIVE_CAMPAIGNS`
- `ANALISE_MATERIALIZACAO_MAX_ACTIVE_CHUNKS_PER_CAMPAIGN`

Semantica:

- o primeiro limita quantas campanhas diferentes podem ficar em execucao ao mesmo tempo
- o segundo limita quantos chunks da mesma campanha podem rodar em paralelo

Regra importante para frontend e operacao:

- uma campanha unica muito grande nao passa a paralelizar so porque `MAX_ACTIVE_CAMPAIGNS` foi aumentado
- a paralelizacao intra-campanha depende de `MAX_ACTIVE_CHUNKS_PER_CAMPAIGN`

Campos mais importantes para frontend:

- `recoverable_pending_campaigns`
- `recoverable_campaign_ids`
- `undispatched_stuck_campaigns`
- `campaigns[]`
- `recovering_campaigns`
- `waiting_for_gate_campaigns`
- `last_pending_recovery_sweep_at`
- `last_pending_recovery_sweep_summary`
- `pending_recovery_active_tasks`
- `stale_chunks`
- `stale_item_count`
- `stale_chunk_preview`
- `campaigns[].active_chunks`
- `campaigns[].active_chunk_ids_preview`

## Como interpretar stale no monitoramento

Os campos:

- `stale_chunks`
- `stale_item_count`
- `stale_chunk_preview`

devem ser tratados como sinal de stale ainda acionavel, nao como historico bruto.

Isso significa:

- entram apenas chunks stale que ainda possuem itens nao terminais associados
- stale historico de campanha ja concluida nao deve acender badge de bloqueio
- frontend nao deve inferir item travado apenas porque houve chunk stale no passado

Uso recomendado:

- usar `stale_chunks > 0` como sinal de atencao operacional atual
- usar `stale_chunk_preview` para drill-down do que ainda requer acao
- nao usar chunks stale historicos como impeditivo para marcar campanha concluida

## Como interpretar concorrencia da campanha

Os campos:

- `campaigns[].active_chunks`
- `campaigns[].active_chunk_id`
- `campaigns[].active_chunk_ids_preview`

devem ser lidos assim:

- `active_chunks` e a contagem real de chunks ativos da campanha
- `active_chunk_id` permanece como identificador representativo para compatibilidade
- `active_chunk_ids_preview` e o campo correto para UI que precisa mostrar mais de um chunk simultaneo

Uso recomendado:

- usar `active_chunks` para badges numericos
- usar `active_chunk_ids_preview` para detalhe, tooltip ou drawer
- nao assumir mais que existe somente um chunk ativo por campanha

## Como interpretar `recoverable_pending_campaigns`

Representa quantas campanhas `pending` estao elegiveis para retry operacional naquele instante.

Inclui:

- campanhas com `STALE_CHUNK` ativo e recuperavel
- campanhas `PENDING_UNDISPATCHED` elegiveis

Nao deve continuar incluindo campanhas que ja foram reenfileiradas recentemente.

### Semantica de campanha reenfileirada

Quando o backend efetivamente dispara um retry, a campanha passa temporariamente para:

- `recovery_state = "requeued"`

Durante essa janela curta:

- ela sai de `recoverable_pending_campaigns`
- ela sai de `recoverable_campaign_ids`
- a UI nao deve continuar mostrando a campanha como "retry necessario agora"

Se o reenfileiramento nao se materializar em progresso real e a campanha voltar a ficar presa, ela pode reaparecer depois como recuperavel.

## Como interpretar `campaigns[].recovery_state`

Valores relevantes para UI:

- `recoverable`: campanha elegivel para retry agora
- `requeued`: retry ja disparado; aguardar propagacao
- `blocked`: campanha bloqueada por gate, slot ou chunk vivo
- `noop`: sem trabalho recuperavel naquele momento
- `pending_threshold`: ainda jovem demais para sweep automatico de `PENDING_UNDISPATCHED`

## Como interpretar `last_recovery_action`

Valores relevantes para UI:

- `requeued`
- `recovered_and_requeued`
- `worker_recovered_and_requeued`
- `noop`
- `sweep_noop`
- `sweep_threshold_skip`

Uso recomendado:

- mostrar isso em drawer de detalhes operacionais
- nao usar sozinho como criterio principal de CTA
- combinar com `recovery_state` e `recoverable_campaign_ids`

## Regras de UX recomendadas

### Botao de retry por campanha

Habilite quando:

- o usuario tiver permissao delegada, e
- `campanha_id` estiver em `recoverable_campaign_ids`, ou
- `campaigns[].recovery_state = "recoverable"`

Desabilite quando:

- `recovery_state = "requeued"`
- `recovery_state = "blocked"`
- a campanha nao estiver marcada como recuperavel

### Botao de retry global

Use `POST /analise/materializacoes/recuperacao/trigger`.

Mostre quando:

- o usuario tiver permissao delegada
- houver campanhas pendentes ou sinais de recuperabilidade

### Acoes administrativas

`recuperar-stale` e `campanhas/{campanha_id}/recuperar` devem ficar:

- em area administrativa
- com linguagem de manutencao tecnica
- separados visualmente das acoes normais de retry

## Polling recomendado

Depois de chamar `.../reativar` ou `.../recuperacao/trigger`:

1. atualizar imediatamente a tela com estado "retry solicitado"
2. refazer `GET /analise/materializacoes/monitoramento`
3. refazer a consulta novamente em curto intervalo
4. parar quando:
   - `recovery_state` deixar de ser `requeued`, ou
   - a campanha sair da lista relevante, ou
   - houver progresso real de chunk/execucao

Sugestao inicial:

- refresh imediato
- depois 3 a 5 segundos
- depois seguir cadencia normal do painel

## Tratamento de erros

### 200 com `status = noop`

Nao e erro tecnico.

Exemplo de leitura:

- gate fechado
- slot ocupado
- chunk em progresso
- nao havia itens pendentes reais

### 401

- token invalido ou ausente

### 403

- usuario sem permissao para aquela superficie

### 422

- `campanha_id` invalido

## Exemplos de fluxo

### Fluxo 1: retry por campanha

1. frontend carrega monitoramento
2. encontra `campanha_id` em `recoverable_campaign_ids`
3. usuario clica em retry
4. frontend chama `POST /analise/materializacoes/campanhas/{campanha_id}/reativar`
5. backend responde `triggered` ou `recovered`
6. frontend atualiza painel
7. campanha deixa de contar em `recoverable_pending_campaigns` enquanto o retry esta em transito

### Fluxo 2: retry global

1. frontend percebe backlog recuperavel
2. operador aciona "tentar recuperar pendencias"
3. frontend chama `POST /analise/materializacoes/recuperacao/trigger`
4. backend varre campanhas elegiveis dentro do limite configurado
5. frontend atualiza monitoramento e apresenta contadores retornados

### Fluxo 3: operacao administrativa

1. admin identifica stale tecnico
2. admin usa `POST /analise/materializacoes/recuperar-stale` ou `.../campanhas/{campanha_id}/recuperar`
3. frontend apresenta resultado tecnico:
   - `recovered_chunks`
   - `recovered_items`
   - `affected_campaigns`
   - `chunk_ids`

## Resumo prático

- use `.../reativar` para retry normal de uma campanha
- use `.../recuperacao/trigger` para retry global limitado
- deixe `recuperar*` para admin
- use `recoverable_campaign_ids` e `campaigns[].recovery_state` para decidir CTAs
- trate `requeued` como "retry ja solicitado"
- trate `noop` como resposta operacional valida
