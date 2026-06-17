---
title: Quarentena e Replay
sidebar_position: 4
---

# Quarentena e Replay

## Visão Geral

Endpoints para gerenciar a fila de reparo da quarentena e reprocessar itens rejeitados.

---

## `GET /ingestion/quarentena`

Lista paginada da fila de reparo da quarentena.

### Query Parameters

| Parâmetro | Tipo | Padrão | Descrição |
|-----------|------|--------|-----------|
| `pagina` | integer | `1` | Número da página |
| `tamanho_pagina` | integer | `100` | Itens por página (máx: 500) |
| `motivo_codigo` | string | - | Filtrar por código do motivo |
| `arquivo_origem` | string | - | Filtrar por arquivo de origem |
| `status` | string | - | Filtrar por status |
| `ano_origem` | integer | - | Filtrar por ano de origem |

### Códigos de Motivo (`motivo_codigo`)

| Código | Descrição | Reparável |
|--------|-----------|-----------|
| `normalizacao_invalida` | Erro de conversão/parse ou falha de BD | Não |
| `companhia_nao_encontrada` | Empresa não encontrada no grafo | Sim |
| `companhia_ambigua` | CNPJ e CVM conflitantes | Sim |
| `chave_natural_duplicada_conflitante` | Chave duplicada com dados divergentes | Sim |
| `schema_inesperado` | Colunas obrigatórias ausentes | Sim* |
| `denominacao_social_ausente` | Não foi possível extrair denominação | Não |
| `identidade_ausente` | Nem CNPJ nem CVM disponíveis | Não |

*`schema_inesperado` é tratado em nível de membro, não explode em milhares de itens.

### Exemplo

```bash
curl -X GET "http://localhost:8007/ingestion/quarentena?motivo_codigo=companhia_nao_encontrada&status=pendente" \
  -H "Authorization: Bearer <token-admin>"
```

### Response 200

**Schema:** `ListaQuarantineItems`

```json
{
  "dados": [
    {
      "id": "0ebc5c67-25a4-4e0c-ab25-66eaf4af4ced",
      "ingestion_run_id": "6a31c7f8-1c89-4f3d-87db-7e6a8e196999",
      "ingestion_row_id": "9b3a4f45-b7ab-4de6-a93d-95f85913df71",
      "arquivo_origem": "itr_cia_aberta_2021.csv",
      "ano_origem": 2021,
      "linha_origem": 1692,
      "row_kind": "itr_documento",
      "status": "pendente",
      "motivo_codigo": "companhia_nao_encontrada",
      "severidade": "error",
      "reparavel": true,
      "tentativas_reprocessamento": 1,
      "diagnostico": {
        "codigo_cvm": 3,
        "denominacao_companhia": "EMPRESA FINANCEIRA",
        "resolution_method": "none"
      }
    }
  ],
  "paginacao": {
    "pagina": 1,
    "tamanho_pagina": 100,
    "total": 1
  }
}
```

---

## `GET /ingestion/quarentena/resumo`

Retorna métricas agregadas e consolidadas de erros na quarentena.

### Query Parameters

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `status` | string | Filtrar por status específico |
| `ingestion_run_id` | UUID | Filtrar por ID de run |
| `execucao_sincronizacao_id` | UUID | Filtrar por ID de execução |

### Exemplo

```bash
curl -X GET "http://localhost:8007/ingestion/quarentena/resumo" \
  -H "Authorization: Bearer <token-admin>"
```

### Response 200

**Schema:** `QuarentenaResumoResposta`

```json
{
  "total": 42,
  "por_status": {
    "pendente": 35,
    "resolvido_auto": 5,
    "resolvido_manual": 2
  },
  "por_erro": [
    {"motivo_codigo": "companhia_nao_encontrada", "quantidade": 28},
    {"motivo_codigo": "normalizacao_invalida", "quantidade": 10},
    {"motivo_codigo": "chave_natural_duplicada_conflitante", "quantidade": 4}
  ],
  "por_arquivo": [
    {"arquivo_origem": "itr_cia_aberta_2021.csv", "quantidade": 15},
    {"arquivo_origem": "dfp_cia_aberta_2022.csv", "quantidade": 12}
  ],
  "por_arquivo_e_erro": [
    {
      "arquivo_origem": "itr_cia_aberta_2021.csv",
      "motivo_codigo": "companhia_nao_encontrada",
      "quantidade": 10
    }
  ]
}
```

---

## `POST /ingestion/replay/quarentena`

Executa replay sobre itens pendentes da quarentena.

### Request Body

**Schema:** `ReplayQuarantineRequisicao`

```json
{
  "reason_code": "companhia_nao_encontrada",
  "arquivo_origem": "itr_cia_aberta_2021.csv",
  "ano": 2021
}
```

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `reason_code` | string | Filtrar por motivo (opcional) |
| `arquivo_origem` | string | Filtrar por arquivo (opcional) |
| `ano` | integer | Filtrar por ano (opcional) |

> **Nota:** Quando nenhum filtro é enviado, todos os itens `pendente` são considerados.

### Exemplo

```bash
curl -X POST "http://localhost:8007/ingestion/replay/quarentena" \
  -H "Authorization: Bearer <token-admin>" \
  -H "Content-Type: application/json" \
  -d '{
    "reason_code": "companhia_nao_encontrada"
  }'
```

### Response 200

**Schema:** `ReplayResposta`

```json
{
  "status": "sucesso",
  "detalhe": {
    "total": 10,
    "promovidos": 8,
    "inalterados": 1,
    "falhas": 1,
    "items": [
      {"row_id": "...", "status": "promovido"},
      {"row_id": "...", "status": "falha", "erro": "..."}
    ]
  }
}
```

### Comportamento Resiliente

O replay é resiliente no nível da linha individual:
- Se uma linha falhar, registra erro mas continua processando as demais
- Erros de BD capturados por `safe_promote_chunk` mantêm o item na quarentena com erro atualizado
- Não aborta o lote por falha individual

---

## `POST /ingestion/runs/{run_id}/replay`

Executa replay administrativo de uma run completa.

### Path Parameters

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `run_id` | UUID | ID da run |

### Exemplo

```bash
curl -X POST "http://localhost:8007/ingestion/runs/6a31c7f8-1c89-4f3d-87db-7e6a8e196999/replay" \
  -H "Authorization: Bearer <token-admin>"
```

### Response 200

```json
{
  "status": "sucesso",
  "detalhe": {...}
}
```

### Comportamento

- Reconstrói processamento a partir do payload bruto retido (`IngestionFileMemberPayload`)
- Não depende da permanência das linhas bem-sucedidas em staging
- Passa novamente por `stage`, `promote` e `reconcile`
- Útil quando correção de parser ou regra de reparo precisa ser aplicada em lote

---

## Casos de Uso

### Caso 1: Resolver Companhias Não Encontradas

```bash
# 1. Ver resumo da quarentena
GET /ingestion/quarentena/resumo

# 2. Sincronizar cadastro (se desatualizado)
POST /ingestion/sincronizacoes/cadastro

# 3. Reconstruir grafo de identidade
POST /ingestion/identity/rebuild

# 4. Replay da quarentena
POST /ingestion/replay/quarentena
{
  "reason_code": "companhia_nao_encontrada"
}

# 5. Verificar resultado
GET /ingestion/quarentena/resumo
```

### Caso 2: Corrigir Erros de Normalização

```bash
# 1. Identificar padrões
GET /ingestion/quarentena?motivo_codigo=normalizacao_invalida

# 2. Analisar diagnóstico
# (Ver campo "diagnostico" de cada item)

# 3. Se for bug no normalizador:
#    - Corrigir código
#    - Deploy
#    - Replay de run completa
POST /ingestion/runs/{run_id}/replay
```

### Caso 3: Python - Monitoramento de Quarentena

```python
import httpx

def monitorar_quarentena(base_url, token):
    """Monitora quarentena e alerta se acumular muitos itens."""
    headers = {"Authorization": f"Bearer {token}"}
    
    response = httpx.get(
        f"{base_url}/ingestion/quarentena/resumo",
        headers=headers
    )
    response.raise_for_status()
    
    resumo = response.json()
    
    if resumo["total"] > 100:
        print(f"⚠️ Quarentena acumulando: {resumo['total']} itens")
        
        # Top 3 erros
        for erro in resumo["por_erro"][:3]:
            print(f"  - {erro['motivo_codigo']}: {erro['quantidade']}")
    
    return resumo

# Uso
resumo = monitorar_quarentena("http://localhost:8007", "seu-token")
```

---

## Notas para Usuários

### Para Operadores de Backoffice

- Monitore `/quarentena/resumo` diariamente
- Priorize erros com `reparavel=true`
- Use replay seletivo por `reason_code`

### Para Auditores

- Analise `diagnostico` para entender causa raiz
- Documente replay de quarentena para auditoria
- Use `/runs/{run_id}/replay` para correções em lote

### Para Compliance

- Monitore `normalizacao_invalida` para detectar bugs
- Valide `companhia_nao_encontrada` após sincronização de cadastro
- Documente todos os replays para rastreabilidade

---

## Próximos Passos

- [Identidade e Auditoria](./identity.md) - Reconstrução e auditoria