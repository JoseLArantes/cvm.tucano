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
| `GET` | `/analise/companhias/{codigo_cvm}/series` | Series normalizadas por metrica e periodo |
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

Retorna o manifesto analítico da companhia: contexto padrão, períodos disponíveis, resumo de qualidade e links para os demais blocos.

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
