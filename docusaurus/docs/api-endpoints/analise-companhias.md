---
title: Analise por Companhia
sidebar_position: 8
---

# Analise por Companhia

Esta pagina documenta a parte da API analitica orientada ao usuario final.

Aqui ficam os endpoints que retornam dados relevantes para:

- analise financeira
- leitura de tendencias
- comparacao entre periodos
- diagnostico de qualidade do dado
- consumo em dashboards, briefs e telas de produto

Ao contrario de materializacao e monitoramento operacional, os endpoints abaixo expõem informacao de negocio, nao metadados de processamento interno.

## Endpoints

| Metodo | Rota | Descricao |
| --- | --- | --- |
| `GET` | `/analise/metricas` | Catalogo versionado de metricas analiticas |
| `GET` | `/analise/companhias/{codigo_cvm}` | Manifesto analitico da companhia |
| `GET` | `/analise/companhias/{codigo_cvm}/coverage` | Matriz de cobertura entre dado bruto, contexto canonico e series |
| `GET` | `/analise/companhias/{codigo_cvm}/series` | Series normalizadas por metrica e periodo |
| `GET` | `/analise/companhias/{codigo_cvm}/series/diagnostico` | Diagnostico de lacunas das series |
| `GET` | `/analise/companhias/{codigo_cvm}/comparacoes` | Comparacoes prontas sobre as series |
| `GET` | `/analise/companhias/{codigo_cvm}/qualidade` | Diagnostico de qualidade analitica |
| `GET` | `/analise/companhias/{codigo_cvm}/sinais` | Sinais deterministicos com evidencias |
| `GET` | `/analise/companhias/{codigo_cvm}/eventos` | Timeline analitica de eventos |
| `GET` | `/analise/companhias/{codigo_cvm}/restatements` | Historico de reapresentacoes |
| `GET` | `/analise/companhias/{codigo_cvm}/governanca` | Observacoes temporais anuais de governanca |
| `GET` | `/analise/companhias/{codigo_cvm}/pessoas` | Observacoes temporais anuais de pessoas e remuneracao |
| `GET` | `/analise/companhias/{codigo_cvm}/brief` | Brief analitico consolidado da companhia |

## `GET /analise/metricas`

Retorna o catalogo oficial de metricas com identificador estavel, tipo, unidade, formula, contas CVM candidatas, estrategia de resolucao, bases temporais e limitacoes metodologicas.

```bash
curl -X GET "http://localhost:8007/analise/metricas" \
  -H "Authorization: Bearer <token>"
```

## `GET /analise/companhias/{codigo_cvm}`

Retorna o manifesto analítico da companhia: contexto padrão, períodos disponíveis, disponibilidade compacta por métrica, resumo de qualidade e links para os demais blocos.

Parametros:

| Nome | Tipo | Descricao |
| --- | --- | --- |
| `codigo_cvm` | integer | Codigo CVM da companhia |
| `escopo` | string | `consolidated` ou `individual` |
| `as_of` | string | Data de corte informacional em `AAAA-MM-DD` |

```bash
curl -X GET "http://localhost:8007/analise/companhias/9512?escopo=consolidated" \
  -H "Authorization: Bearer <token>"
```

Campos de disponibilidade:

- `periodos_disponiveis`: períodos canônicos disponíveis no contexto padrão
- `periodos_disponiveis_por_metrica`: lista compacta por métrica, com `metric_id` e `period_ids`, para a UI saber se um gráfico pode existir sem chamar `/series`
- `resolution.mode`: `canonical` quando a resposta veio da camada materializada; `runtime_fallback` quando foi calculada no request

## `GET /analise/companhias/{codigo_cvm}/coverage`

Retorna uma matriz de cobertura por período.

Use este endpoint quando a UI precisa explicar por que um período aparece nos dados brutos, mas não aparece em uma série ou gráfico.

Para os mesmos filtros de `periodicidade`, `base_periodo`, `escopo`, `as_of` e `horizonte_anos`, `/coverage`, `/series` e `/series/diagnostico` usam a mesma janela de períodos. Quando um item de `/coverage` retorna `has_series=true` e `metrics_count>0`, `/series` deve retornar as observações materializadas desse período para as métricas solicitadas disponíveis.

Parametros:

| Nome | Tipo | Descricao |
| --- | --- | --- |
| `escopo` | string | `consolidated` ou `individual` |
| `periodicidade` | string | Filtro opcional: `annual` ou `quarterly` |
| `base_periodo` | string | Filtro opcional: `fy`, `quarter` ou `ytd` |
| `as_of` | string | Data de corte informacional em `AAAA-MM-DD` |
| `horizonte_anos` | integer | Horizonte anual maximo quando `periodicidade=annual` e `base_periodo=fy` |

```bash
curl -X GET "http://localhost:8007/analise/companhias/9512/coverage?escopo=consolidated" \
  -H "Authorization: Bearer <token>"
```

Cada item de `periodos` contém:

| Campo | Descricao |
| --- | --- |
| `period_id` | Período canônico, como `FY2025`, `2025-Q3` ou `2025-YTDQ3` |
| `ano` | Ano fiscal |
| `periodicidade` | `annual` ou `quarterly` |
| `base_periodo` | `fy`, `quarter` ou `ytd` |
| `escopo` | Escopo societário avaliado |
| `form` | Formulário ou origem principal do período |
| `has_raw_data` | Há dado financeiro bruto/promovido suficiente para listar o período |
| `has_canonical_context` | A revisão de contexto canônica lista o período |
| `has_canonical_facts` | Há ao menos uma revisão de fato canônica, disponível ou indisponível, para o período |
| `has_materialized_metrics` | Há métricas materializadas disponíveis para o período |
| `has_series` | Há ao menos uma métrica canônica disponível para o período |
| `metrics_count` | Quantidade de métricas canônicas disponíveis |
| `unavailable_count` | Quantidade de métricas canônicas avaliadas como indisponíveis |
| `metrics_available` | Métricas disponíveis na camada canônica |
| `metrics_unavailable` | Métricas avaliadas e indisponíveis na camada canônica |
| `latest_execution_id` | Execução de materialização usada |
| `materialized_at` | Momento de conclusão da materialização usada |

## `GET /analise/companhias/{codigo_cvm}/series`

Resolve observações analíticas normalizadas.

Parametros:

| Nome | Tipo | Descricao |
| --- | --- | --- |
| `metricas` | string | Lista CSV de metricas estaveis |
| `periodicidade` | string | `annual` ou `quarterly` |
| `base_periodo` | string | `fy`, `quarter` ou `ytd` |
| `escopo` | string | `consolidated` ou `individual` |
| `as_of` | string | Data de corte informacional em `AAAA-MM-DD` |
| `horizonte_anos` | integer | Horizonte anual maximo quando `periodicidade=annual` e `base_periodo=fy` |

```bash
curl -X GET "http://localhost:8007/analise/companhias/9512/series?metricas=receita_liquida,lucro_liquido&periodicidade=quarterly&base_periodo=quarter&escopo=consolidated" \
  -H "Authorization: Bearer <token>"
```

Cada resposta de serie inclui:

- `resolution.mode`: `canonical` ou `runtime_fallback`
- `resolution.materialization_execution_id`: UUID da materializacao canonica usada, quando houver
- `resolution.materialized_at`: instante de conclusao da materializacao
- `resolution.as_of`: data de corte informacional efetivamente aplicada
- `horizonte_anos`: horizonte anual efetivamente aplicado em consultas historicas FY

## `GET /analise/companhias/{codigo_cvm}/series/diagnostico`

Usa os mesmos filtros de `/series`, mas retorna uma explicação operacional de lacunas.

Parametros:

| Nome | Tipo | Descricao |
| --- | --- | --- |
| `metricas` | string | Lista CSV de metricas estaveis |
| `periodicidade` | string | `annual` ou `quarterly` |
| `base_periodo` | string | `fy`, `quarter` ou `ytd` |
| `escopo` | string | `consolidated` ou `individual` |
| `as_of` | string | Data de corte informacional em `AAAA-MM-DD` |
| `horizonte_anos` | integer | Horizonte anual maximo quando `periodicidade=annual` e `base_periodo=fy` |

```bash
curl -X GET "http://localhost:8007/analise/companhias/9512/series/diagnostico?metricas=receita_liquida&periodicidade=annual&base_periodo=fy&escopo=consolidated" \
  -H "Authorization: Bearer <token>"
```

Campos principais:

- `requested_metrics`: métricas solicitadas e reconhecidas
- `candidate_periods`: períodos candidatos encontrados no dado bruto para os filtros
- `returned_periods`: períodos que retornaram ao menos uma observação em `/series`
- `rejected_periods`: períodos com lacunas por métrica
- `unavailable_reasons`: indisponibilidades consolidadas do resolvedor

Cada item de `rejected_periods` informa:

- `returned_metrics`
- `rejected_metrics`
- `unavailable_reasons`
- `missing_accounts`
- `missing_forms`
- `scope_mismatch`
- `materialization_mismatch`
- `has_raw_data`
- `has_canonical_context`
- `has_canonical_facts`
- `has_materialized_metrics`
- `materialization_status`
- `materialization_execution_id`
- `latest_execution_id`
- `metrics_count`
- `unavailable_count`
- `metric_reasons`

Cada item de `metric_reasons` traz `metric_id`, `reason_code`, `reason_message`, `layer`, `remediation_code` e `remediation_message`.

`layer` indica onde a lacuna foi encontrada:

- `raw`
- `canonical_context`
- `canonical_fact`
- `metric_calculation`
- `materialization`
- `scope`
- `filter`

`reason_code` é estável para consumo da UI:

- `RAW_DATA_MISSING`
- `CANONICAL_CONTEXT_MISSING`
- `CANONICAL_FACTS_MISSING`
- `MATERIALIZATION_MISSING`
- `MATERIALIZATION_PENDING`
- `MATERIALIZATION_RUNNING`
- `MATERIALIZATION_FAILED`
- `SCOPE_MISMATCH`
- `PERIODICITY_MISMATCH`
- `BASE_PERIOD_MISMATCH`
- `METRIC_MAPPING_MISSING`
- `METRIC_INPUT_ACCOUNT_MISSING`
- `METRIC_CALCULATION_UNAVAILABLE`
- `INSUFFICIENT_SERIES_POINTS`

`remediation_code` informa a ação recomendada:

- `INGEST_SOURCE`
- `RUN_MATERIALIZATION`
- `WAIT_MATERIALIZATION`
- `REBUILD_CANONICAL_CONTEXT`
- `FIX_METRIC_MAPPING`
- `CHANGE_SCOPE`
- `CHANGE_PERIODICITY`
- `CHANGE_BASE_PERIOD`
- `SELECT_DIFFERENT_METRIC`

Exemplo de leitura para a UI: `FY2023` pode ter `has_raw_data=true`, `has_canonical_context=true`, `has_canonical_facts=false` e `metric_reasons[].reason_code=CANONICAL_FACTS_MISSING`. Nesse caso, a ação recomendada é executar repair/materialização para a companhia, escopo e período.

Quando o repair para o mesmo período, métrica e escopo retorna `NO_MISSING_METRICS`, o diagnóstico não recomenda `RUN_MATERIALIZATION`. Se uma observação materializada for excluída por filtros de consulta, o motivo aparece na camada `filter`.

Com isso, a UI pode explicar casos como: "o período existe no DFP bruto, mas a métrica não foi materializada" ou "há dado no escopo individual, mas não no consolidado solicitado".

## `GET /analise/companhias/{codigo_cvm}/comparacoes`

Retorna comparacoes analiticas prontas sobre as series resolvidas. O backend produz YoY, QoQ, CAGR, analise vertical e indice base 100 quando matematicamente definidos. Quando uma comparacao nao puder ser produzida, a resposta traz `status=unavailable` e `reason_code`.

As comparacoes reutilizam a mesma origem de resolucao declarada em `resolution`.

Parametros:

| Nome | Tipo | Descricao |
| --- | --- | --- |
| `metricas` | string | Lista CSV de metricas estaveis |
| `periodicidade` | string | `annual` ou `quarterly` |
| `base_periodo` | string | `fy`, `quarter` ou `ytd` |
| `escopo` | string | `consolidated` ou `individual` |
| `as_of` | string | Data de corte informacional em `AAAA-MM-DD` |
| `horizonte_anos` | integer | Horizonte anual maximo quando `periodicidade=annual` e `base_periodo=fy` |

Cada comparacao expõe:

- `metric_unit`: unidade dos valores `current_value` e `comparable_value`
- `comparison_unit`: unidade do resultado comparativo, como `ratio`, `percentage_point` ou `index`
- `horizonte_anos`: horizonte anual efetivamente aplicado em consultas historicas FY

## `GET /analise/companhias/{codigo_cvm}/qualidade`

Executa verificacoes auditaveis de completude, comparabilidade, consistencia e reapresentacoes.

Parametros:

| Nome | Tipo | Descricao |
| --- | --- | --- |
| `periodicidade` | string | `annual` ou `quarterly` |
| `escopo` | string | `consolidated` ou `individual` |
| `as_of` | string | Data de corte informacional em `AAAA-MM-DD` |

## `GET /analise/companhias/{codigo_cvm}/sinais`

Avalia regras deterministicas do backend e retorna o sinal com threshold, valor observado e evidencias.

Os sinais sao calculados sobre as series e comparaveis corretos para o `as_of` informado.

Parametros:

| Nome | Tipo | Descricao |
| --- | --- | --- |
| `escopo` | string | `consolidated` ou `individual` |
| `as_of` | string | Data de corte informacional em `AAAA-MM-DD` |

## `GET /analise/companhias/{codigo_cvm}/eventos`

Retorna a timeline analitica atual unificando IPE, reapresentacoes financeiras, alteracoes de capital e negociacoes relevantes.

Cada evento expoe `event_id`, identificador estavel adequado para chave de renderizacao, paginacao incremental e deep links.

## `GET /analise/companhias/{codigo_cvm}/restatements`

Compara versoes consecutivas de DFP e ITR no escopo solicitado e informa as contas alteradas, com valores antes/depois e impacto absoluto/relativo.

Parametros:

| Nome | Tipo | Descricao |
| --- | --- | --- |
| `escopo` | string | `consolidated` ou `individual` |
| `as_of` | string | Data de corte informacional em `AAAA-MM-DD` |

## `GET /analise/companhias/{codigo_cvm}/governanca`

Retorna observacoes temporais anuais de governanca, com corte `as_of` e horizonte historico explicito.

Parametros:

| Nome | Tipo | Descricao |
| --- | --- | --- |
| `escopo` | string | `consolidated` ou `individual` |
| `as_of` | string | Data de corte informacional em `AAAA-MM-DD` |
| `horizonte_anos` | integer | Horizonte anual maximo a retornar |

O contrato atual expõe, entre outras observacoes:

- `governanca_praticas_adotadas_ratio`
- `governanca_praticas_com_explicacao`

## `GET /analise/companhias/{codigo_cvm}/pessoas`

Retorna observacoes temporais anuais de pessoas e remuneracao, com corte `as_of` e horizonte historico explicito.

Parametros:

| Nome | Tipo | Descricao |
| --- | --- | --- |
| `escopo` | string | `consolidated` ou `individual` |
| `as_of` | string | Data de corte informacional em `AAAA-MM-DD` |
| `horizonte_anos` | integer | Horizonte anual maximo a retornar |

O contrato atual expõe, entre outras observacoes:

- `pessoas_remuneracao_total_orgao`
- `pessoas_empregados_total`

## `GET /analise/companhias/{codigo_cvm}/brief`

Retorna um brief analitico com:

- trimestre corrente
- trimestre anterior
- mesmo trimestre do ano anterior
- exercicio corrente
- exercicio anterior
- metricas, comparacoes, sinais, qualidade e eventos recentes

Parametros:

| Nome | Tipo | Descricao |
| --- | --- | --- |
| `escopo` | string | `consolidated` ou `individual` |
| `as_of` | string | Data de corte informacional em `AAAA-MM-DD` |
| `metricas` | string | Lista CSV opcional de metricas a priorizar |
| `incluir_eventos` | boolean | Controla a inclusao dos eventos recentes |

## `GET /analise/companhias/{codigo_cvm}/fundamentalista`

Retorna um relatório analítico fundamentalista consolidado estruturado em quatro etapas (pilares) para subsidiar a jornada do usuário. Esse endpoint unifica dados de séries temporais, comparações prontas, qualidade de dados, sinais e eventos para o recorte solicitado em uma única chamada.

O relatório canônico é servido por um read model persistido no PostgreSQL. O recorte padrão `annual`, `fy`, cinco anos, último conhecimento e sem `evidence_graph` é pré-compilado ao final de cada materialização bem-sucedida. Um recorte canônico diferente é compilado e persistido na primeira leitura. Quando ainda não existe materialização canônica, a resposta mantém `resolution.mode=runtime_fallback` e não é persistida como read model.

Parâmetros:

| Nome | Tipo | Padrão | Descrição |
| --- | --- | --- | --- |
| `escopo` | string | `consolidated` | `consolidated` ou `individual` |
| `periodicidade` | string | `annual` | `annual` ou `quarterly` |
| `base_periodo` | string | `fy` | `fy`, `quarter` ou `ytd` |
| `horizonte_anos` | integer | `5` | Horizonte anual máximo de pontos a retornar |
| `as_of` | string | ausente | Data de corte informacional em `AAAA-MM-DD` |
| `include` | string | ausente | Informar `evidence_graph` para incluir o grafo de proveniência no payload |

O payload de resposta contém:
- `report_id`: identificador determinístico único para o recorte
- `report_version`: versão do layout do relatório; campos novos são aditivos
- `companhia`, `contexto`, `qualidade`, `resolution`
- `etapas`: objeto com `ponto_partida`, `resultado_eficiencia`, `caixa_solidez` e `governanca_conclusao`
- `evidence_index`: mapa chave-valor de referências compactas para todas as evidências acionadas no relatório
- `evidence_graph`: grafo estruturado de arestas e nós expressando relações factuais de dados e documentos (quando `include=evidence_graph`)
- `event_buckets`: agrupamentos de eventos por ano ou mês, com contadores por família e severidade
- `evidence_dossier`: dossiê factual priorizado pelo backend para orientar a UI sem inferência no frontend

Campos adicionais em `etapas.caixa_solidez`:

- `ponte_caixa`: lista por período com itens de ponte de caixa. Cada item traz `metric_id`, `label`, `value`, `unit`, `role` (`opening`, `operating_cash`, `capex`, `adjustment` ou `free_cash`) e `evidence_ids`. Quando a ponte não é compatível com os componentes disponíveis, o período retorna `unavailable_reason`.
- `painel_posicao_financeira`: separa `monetary_series` de `ratio_series`, preservando o contrato completo de `AnaliseSeriesObservation`.

As contas de `changed_accounts` em reapresentações incluem metadados de exibição e linhagem factual: `account_label`, `statement_label`, `unit`, `display_rank`, `is_focus`, `reason_if_available` e `evidence_id`.

### Cache HTTP e origem da resposta

A resposta preserva o mesmo schema e inclui os seguintes headers:

| Header | Descrição |
| --- | --- |
| `ETag` | Hash do payload serializado. Pode ser enviado no próximo request em `If-None-Match`. |
| `Cache-Control` | Política privada de cache; o relatório é autenticado e não deve ser armazenado como resposta pública compartilhada. |
| `X-Analise-Source` | `redis_cache`, `redis_cache_wait`, `db_snapshot`, `compiled_canonical` ou `compiled_runtime`. |
| `X-Analise-Generation` | UUID da execução canônica vigente; retorna `runtime` quando não há materialização bem-sucedida. |

Quando `If-None-Match` coincide com o `ETag` vigente, o endpoint responde `304 Not Modified` sem corpo. Redis mantém uma cópia descartável e versionada do payload; falha de Redis degrada para o read model persistido ou para compilação pelo service.

Exemplos de uso:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "https://api.exemplo/analise/companhias/9512/fundamentalista?periodicidade=annual&base_periodo=fy&escopo=consolidated&horizonte_anos=5"

curl -H "Authorization: Bearer $TOKEN" \
  "https://api.exemplo/analise/companhias/9512/fundamentalista?periodicidade=quarterly&base_periodo=ytd&escopo=individual&as_of=2025-11-15"

curl -i -H "Authorization: Bearer $TOKEN" \
  -H 'If-None-Match: "ETAG_RECEBIDO"' \
  "https://api.exemplo/analise/companhias/9512/fundamentalista?periodicidade=annual&base_periodo=fy&escopo=consolidated&horizonte_anos=5"
```

## `GET /analise/companhias/{codigo_cvm}/fundamentalista/eventos`

Retorna a lista detalhada de eventos oficiais vinculados ao relatório fundamentalista. Use este endpoint para abrir um bucket retornado em `event_buckets` sem carregar todos os eventos no relatório principal.

Parâmetros:

| Nome | Tipo | Padrão | Descrição |
| --- | --- | --- | --- |
| `escopo` | string | `consolidated` | Mesmo recorte societário do relatório principal |
| `periodicidade` | string | `annual` | `annual` ou `quarterly` |
| `base_periodo` | string | `fy` | `fy`, `quarter` ou `ytd` |
| `horizonte_anos` | integer | `5` | Janela anual considerada |
| `as_of` | string | ausente | Data máxima de conhecimento informacional |
| `bucket` | string | ausente | Bucket específico em `YYYY` ou `YYYY-MM` |
| `familias` | array | ausente | Famílias de evento a retornar |
| `severidades` | array | ausente | Severidades a retornar |
| `cursor` | string | ausente | Cursor opaco de paginação |
| `limit` | integer | `25` | Tamanho da página, máximo 100 |

Resposta:

- `items`: lista de `AnaliseEvento`, ordenada do mais recente para o mais antigo e nunca após `as_of`
- `next_cursor`: cursor opaco para a próxima página, ou `null`

## `GET /analise/companhias/{codigo_cvm}/fundamentalista/evidencias/{evidence_id}/trilha`

Retorna uma trilha focal curta para uma evidência específica. O endpoint é recomendado para interações de drill-down na UI porque limita a profundidade e o volume da resposta.

Parâmetros:

| Nome | Tipo | Padrão | Descrição |
| --- | --- | --- | --- |
| `depth` | integer | `1` | Profundidade fixa do contrato atual |
| `limit` | integer | `12` | Limite máximo de nós |
| `types` | array | ausente | Filtra tipos: `observation`, `signal`, `event`, `document` ou `restatement` |

Resposta:

- `root_evidence_id`: evidência raiz solicitada
- `nodes`: nós factuais da trilha
- `edges`: relações factuais (`derivada_de`, `comparada_com`, `reportada_em`, `acionou_sinal`, `reapresentada_por`, `relacionada_a_evento`)
- `truncated`: indica se a resposta foi limitada por profundidade ou quantidade de nós

## `GET /analise/companhias/{codigo_cvm}/fundamentalista/evidencias/{evidence_id}`

Resolve os detalhes factuais sob demanda para uma determinada evidência da companhia. Permite fazer a rastreabilidade (audit trail) de qualquer dado exibido na tela, conectando o relatório aos arquivos e contas oficiais da CVM.

O endpoint valida se a evidência de fato pertence à companhia solicitada. Retorna:
- Métricas e fórmulas aplicadas (se aplicável)
- Contas CVM e demonstração de origem
- Metadados do documento/formulário entregue na CVM com link de download direto
- Relação com outras comparações, sinais ou reapresentações do relatório
