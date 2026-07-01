---
title: Quarentena e Replay
sidebar_position: 4
---

# Quarentena e Replay

## Escopo

A quarentena e a fila de reparo de excecoes persistidas da ingestao.

Cada item da quarentena representa uma linha que nao conseguiu ser promovida com sucesso e ficou registrada com:

- `motivo_codigo`
- `status`
- `severidade`
- `reparavel`
- `tentativas_reprocessamento`
- `diagnostico`

Quando `status` nao e enviado nos endpoints de listagem e resumo, o filtro implicito e `pendente`.

## `GET /ingestion/quarentena`

Lista paginada da fila de reparo.

Filtros:

| Parametro | Uso |
| --- | --- |
| `motivo_codigo` | filtrar por motivo |
| `arquivo_origem` | filtrar por member/arquivo |
| `status` | `pendente` por default; use `all` para historico |
| `ano_origem` | filtrar por ano |

Campos centrais por item:

| Campo | Uso |
| --- | --- |
| `motivo_codigo` | chave de agrupamento e filtro |
| `status` | fila aberta ou historico resolvido/ignorado |
| `reparavel` | habilitar replay automatico ou assistido |
| `tentativas_reprocessamento` | exibir insistencia do replay |
| `diagnostico` | payload tecnico para suporte |

Exemplo:

```bash
curl -X GET "http://localhost:8007/ingestion/quarentena?motivo_codigo=companhia_nao_encontrada" \
  -H "Authorization: Bearer <token-admin>"
```

## Motivos mais comuns

| `motivo_codigo` | Significado |
| --- | --- |
| `normalizacao_invalida` | erro de parse, validacao ou promote individual |
| `companhia_nao_encontrada` | nao foi possivel resolver a companhia |
| `companhia_ambigua` | mais de uma companhia elegivel para a linha |
| `chave_natural_duplicada_conflitante` | conflito entre linhas com a mesma chave natural |
| `schema_inesperado` | header/schema do member nao bateu com o esperado |
| `denominacao_social_ausente` | faltou informacao minima de denominacao |
| `identidade_ausente` | faltaram identificadores minimos para resolucao |

## `GET /ingestion/quarentena/resumo`

Agregado da fila de reparo.

Campos principais:

- `total`
- `por_status`
- `por_erro`
- `por_arquivo`
- `por_arquivo_e_erro`
- `total_pendentes`
- `total_resolvidos`
- `total_historico`

Filtros:

| Parametro | Uso |
| --- | --- |
| `status` | `pendente` por default; use `all` para historico |
| `ingestion_run_id` | drill-down por run |
| `execucao_sincronizacao_id` | drill-down por execucao administrativa |

Exemplo:

```bash
curl -X GET "http://localhost:8007/ingestion/quarentena/resumo?status=all" \
  -H "Authorization: Bearer <token-admin>"
```

## `POST /ingestion/replay/quarentena`

Replay de itens pendentes da quarentena.

Body aceito:

```json
{
  "reason_code": "companhia_nao_encontrada",
  "arquivo_origem": "itr_cia_aberta_2021.csv",
  "ano": 2021
}
```

Regras:

- quando nenhum filtro e enviado, o replay considera todos os itens `pendente`;
- cada linha e reprocessada de forma independente;
- se uma linha falhar novamente, ela permanece na quarentena com diagnostico atualizado.

## `POST /ingestion/runs/{run_id}/replay`

Replay completo da run.

Use quando:

- houve correcao de regra de negocio;
- houve correcao de parser;
- houve correcao de identidade;
- o escopo correto e a run inteira, nao apenas a fila de excecoes.

O replay da run reavalia o artefato retido da run, passa novamente pelas fases operacionais aplicaveis e pode produzir:

- novos itens de quarentena;
- novos promotes;
- novo reconcile;
- novo reuso de members elegiveis.

## `POST /ingestion/runs/{run_id}/recover`

Recover administrativo de run stale ou com erro recuperavel.

Quando usar:

- `state=stale`;
- `state=failed` com `last_error.retryable=true`;
- `next_action=recover`.

## Fluxo operacional recomendado

### Caso 1: erro de identidade

1. consultar `GET /ingestion/quarentena/resumo`
2. identificar volume de `companhia_nao_encontrada`
3. sincronizar cadastro se necessario
4. executar `POST /ingestion/identity/rebuild`
5. executar `POST /ingestion/replay/quarentena`

### Caso 2: problema em um member especifico

1. localizar a run em `GET /ingestion/runs`
2. abrir `GET /ingestion/runs/{run_id}/members`
3. confirmar o member alvo
4. decidir entre `POST /ingestion/sincronizacoes/reprocessar-arquivo` e `POST /ingestion/runs/{run_id}/replay`

### Caso 3: run stale

1. localizar a run em `GET /ingestion/runs`
2. confirmar `next_action=recover`
3. abrir `GET /ingestion/runs/{run_id}/phases`
4. executar `POST /ingestion/runs/{run_id}/recover`
