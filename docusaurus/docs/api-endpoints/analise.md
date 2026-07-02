---
title: Analise
sidebar_position: 7
---

# Analise

A superficie `/analise` mistura dois tipos de informacao:

1. informacao orientada ao usuario final de analise financeira:
   - leituras por companhia
   - series historicas
   - comparacoes
   - sinais
   - qualidade
   - eventos
   - brief analitico

2. informacao meta e operacional do proprio sistema:
   - materializacao canonica
   - filas, chunks e campanhas
   - gate operacional
   - retries e self-healing
   - observabilidade de processamento interno

Para evitar mistura entre consumo analitico e operacao da plataforma, a documentacao de analise foi separada em tres blocos.

## Estrutura desta secao

### 1. Visao geral de analise

Esta pagina explica a divisao conceitual da superficie `/analise`.

### 2. Analise por companhia

Use esta documentacao quando o interesse principal for o dado analitico consumido por usuarios de negocio, produtos financeiros ou telas de leitura.

Pagina:

- [Análise por Companhia](./analise-companhias.md)

Endpoints cobertos:

- `GET /analise/metricas`
- `GET /analise/companhias/{codigo_cvm}`
- `GET /analise/companhias/{codigo_cvm}/coverage`
- `GET /analise/companhias/{codigo_cvm}/series`
- `GET /analise/companhias/{codigo_cvm}/series/diagnostico`
- `GET /analise/companhias/{codigo_cvm}/comparacoes`
- `GET /analise/companhias/{codigo_cvm}/qualidade`
- `GET /analise/companhias/{codigo_cvm}/sinais`
- `GET /analise/companhias/{codigo_cvm}/eventos`
- `GET /analise/companhias/{codigo_cvm}/restatements`
- `GET /analise/companhias/{codigo_cvm}/governanca`
- `GET /analise/companhias/{codigo_cvm}/pessoas`
- `GET /analise/companhias/{codigo_cvm}/brief`

### 3. Materializacoes e operacao

Use esta documentacao quando o interesse principal for o funcionamento interno do sistema, monitoramento, retries operacionais, campanha/chunk, gate e observabilidade.

Pagina:

- [Materializações Analíticas](./analise-materializacoes.md)

Endpoints cobertos:

- `GET /analise/materializacoes`
- `GET /analise/materializacoes/companhias/{codigo_cvm}/status`
- `POST /analise/materializacoes/companhias/{codigo_cvm}/repair`
- `GET /analise/materializacoes/monitoramento`
- `GET /analise/materializacoes/controle`
- `POST /analise/materializacoes/controle/pause`
- `POST /analise/materializacoes/controle/resume`
- `POST /analise/materializacoes/recuperar-stale`
- `POST /analise/materializacoes/campanhas/{campanha_id}/recuperar`
- `POST /analise/materializacoes/campanhas/{campanha_id}/reativar`
- `POST /analise/materializacoes/recuperacao/trigger`
- `GET /analise/materializacoes/{execucao_id}`

## Como escolher a documentacao certa

### Se o foco for analise financeira

Leia:

- [Análise por Companhia](./analise-companhias.md)

Esse bloco cobre payloads orientados ao usuario e respostas com valor direto para leitura, comparacao e interpretacao financeira.

### Se o foco for processo interno do backend

Leia:

- [Materializações Analíticas](./analise-materializacoes.md)

Esse bloco cobre o que o sistema usa internamente para persistir, organizar, recuperar, monitorar e reprocessar a camada canonica.

## Distincao pratica

### Informacao orientada ao usuario

Exemplos:

- receita liquida, lucro liquido e margem
- comparacoes YoY, QoQ e CAGR
- sinais deterministas
- timeline de eventos
- observacoes de governanca
- brief analitico consolidado

### Informacao meta e operacional

Exemplos:

- campaign id
- chunk execucao id
- fila dedicada de materializacao
- stale chunk
- gate vermelho
- pending recovery
- self-healing
- retries operacionais

## Convencoes do contrato analitico

- datas e datetimes usam ISO 8601
- valores decimais sao serializados como string decimal canonica
- o escopo societario e explicito: `consolidated` ou `individual`
- `resolution.mode` distingue leitura canonica persistida de fallback em tempo de execucao
- `as_of` representa a data de corte informacional efetivamente aplicada
