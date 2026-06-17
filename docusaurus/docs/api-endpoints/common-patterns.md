---
title: Padrões Transversais da API
sidebar_position: 4
---

# Padrões Transversais da API

## Visão Geral

Todos os endpoints da API seguem um conjunto de padrões comuns para paginação, ordenação, tratamento de erros e autenticação. Este documento descreve esses padrões para que você possa aplicá-los consistentemente em qualquer endpoint.

---

## Autenticação

### Header Obrigatório

Todos os endpoints protegidos exigem:

```
Authorization: Bearer <access_token>
```

### Obtenção do Token

Consulte [Autenticação](./auth.md) para detalhes sobre `POST /auth/login`.

### Exceção

Apenas `/health` é público e não requer autenticação.

---

## Paginação Uniforme

### Formato de Resposta

Todas as listagens retornam o mesmo envelope:

```json
{
  "dados": [...],
  "paginacao": {
    "pagina": 1,
    "tamanho_pagina": 100,
    "total": 1250
  }
}
```

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `dados` | array | Lista de itens da página atual |
| `paginacao.pagina` | integer | Página atual (inicia em 1) |
| `paginacao.tamanho_pagina` | integer | Tamanho da página aplicado |
| `paginacao.total` | integer | Total de registros disponíveis para os filtros |

### Query Parameters Padrão

| Parâmetro | Tipo | Padrão | Limite | Descrição |
|-----------|------|--------|--------|-----------|
| `pagina` | integer | `1` | mín 1 | Número da página |
| `tamanho_pagina` | integer | `100` | máx **500** | Itens por página |

### Exemplo: Iterar Todas as Páginas (Python)

```python
import httpx

BASE_URL = "http://localhost:8007"
TOKEN = "seu-token"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

def iterar_todos(endpoint: str, params: dict = None):
    """Itera por todas as páginas de um endpoint paginado."""
    pagina = 1
    tamanho_pagina = 500  # máximo permitido
    
    while True:
        query = {**(params or {}), "pagina": pagina, "tamanho_pagina": tamanho_pagina}
        response = httpx.get(f"{BASE_URL}{endpoint}", headers=HEADERS, params=query)
        response.raise_for_status()
        
        body = response.json()
        yield from body["dados"]
        
        if pagina * tamanho_pagina >= body["paginacao"]["total"]:
            break
        pagina += 1

# Uso: listar todas as companhias ativas
for companhia in iterar_todos("/companhias", {"situacao_registro": "ATIVO"}):
    print(companhia["denominacao_social"])
```

### Exemplo: Iterar Todas as Páginas (JavaScript)

```javascript
async function* iterarTodos(endpoint, params = {}) {
  const BASE_URL = 'http://localhost:8007';
  const TOKEN = 'seu-token';
  let pagina = 1;
  const tamanho_pagina = 500;

  while (true) {
    const query = new URLSearchParams({
      ...params,
      pagina: pagina.toString(),
      tamanho_pagina: tamanho_pagina.toString()
    });

    const response = await fetch(`${BASE_URL}${endpoint}?${query}`, {
      headers: { 'Authorization': `Bearer ${TOKEN}` }
    });

    const body = await response.json();
    yield* body.dados;

    if (pagina * tamanho_pagina >= body.paginacao.total) break;
    pagina++;
  }
}

// Uso
for await (const companhia of iterarTodos('/companhias', { situacao_registro: 'ATIVO' })) {
  console.log(companhia.denominacao_social);
}
```

---

## Ordenação

### Sintaxe

O parâmetro `ordenar_por` aceita:

- **Nome do campo**: ordem ascendente
- **`-` + nome do campo**: ordem descendente

### Exemplos

```bash
# Ascendente por data de referência
GET /dfp/documentos?ordenar_por=data_referencia

# Descendente por data de referência (mais recente primeiro)
GET /dfp/documentos?ordenar_por=-data_referencia

# Por código da conta
GET /dfp/balanco-patrimonial-ativo/consolidado?ordenar_por=codigo_conta
```

### Campos Permitidos por Tipo de Endpoint

| Tipo de Endpoint | Campos Permitidos |
|------------------|-------------------|
| **Companhias** | `ativa_nome`, `nome`, `codigo_cvm` (via `ordenar`) |
| **Documentos (DFP/ITR/FRE/FCA/IPE/VLMO/CGVN)** | `data_referencia`, `versao`, `cnpj_companhia`, `codigo_cvm`, `data_recebimento`, `id_documento` |
| **Demonstrações Financeiras** | `data_referencia`, `versao`, `cnpj_companhia`, `codigo_conta`, `valor_conta` |
| **IPE** | `data_entrega`, `data_referencia`, `versao`, `cnpj_companhia`, `codigo_cvm`, `categoria` |
| **VLMO Consolidado** | `data_referencia`, `data_movimentacao`, `versao`, `cnpj_companhia`, `tipo_ativo`, `tipo_operacao`, `tipo_movimentacao`, `empresa` |

> **Importante:** Quando a ordenação usa `valor_conta`, o backend considera o valor monetário **ajustado por `ESCALA_MOEDA`**, não o valor bruto reportado.

### Erro de Ordenação Inválida

```json
{
  "detail": "Campo invalido para ordenacao: campo_invalido"
}
```

---

## Filtros Comuns

### Identificação de Companhia

Quase todos os endpoints aceitam:

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `cnpj_companhia` | string | CNPJ com ou sem pontuação (`08.773.135/0001-00` ou `08773135000100`) |
| `codigo_cvm` | integer | Código CVM da companhia (ex: `25224`) |

> **Dica:** Use apenas um dos dois. O backend normaliza automaticamente.

### Período de Referência

| Parâmetro | Tipo | Formato | Descrição |
|-----------|------|---------|-----------|
| `data_referencia_inicio` | date | `YYYY-MM-DD` | Data inicial (inclusive) |
| `data_referencia_fim` | date | `YYYY-MM-DD` | Data final (inclusive) |

### Ano de Origem

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `ano_origem` | integer | Ano do ZIP de origem |
| `ano_inicio` | integer | Ano inicial do intervalo (inclusive) |
| `ano_fim` | integer | Ano final do intervalo (inclusive) |

### Versão do Documento

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `versao` | integer | Versão específica do formulário |

> **Dica:** Para obter apenas a versão mais recente, use `ordenar_por=-versao&tamanho_pagina=1`.

---

## Tratamento de Erros

### Formato Padrão (HTTP 422 - Validation Error)

**Schema:** `HTTPValidationError`

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "password"],
      "msg": "Field required",
      "input": {"username": "admin"},
      "ctx": {}
    }
  ]
}
```

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `type` | string | Tipo do erro (ex: `missing`, `value_error`, `type_error`) |
| `loc` | array | Localização do erro (ex: `["body", "password"]`) |
| `msg` | string | Mensagem legível |
| `input` | any | Valor recebido que causou o erro |
| `ctx` | object | Contexto adicional (opcional) |

### Códigos HTTP Comuns

| Status | Significado | Quando Ocorre |
|--------|-------------|---------------|
| `200` | Sucesso | Requisição processada corretamente |
| `201` | Criado | Recurso criado com sucesso (ex: `POST /usuarios`) |
| `204` | Sem Conteúdo | Sucesso sem corpo (ex: `DELETE /usuarios/{id}`) |
| `400` | Bad Request | Requisição malformada (ex: execução não está no status esperado) |
| `401` | Unauthorized | Token ausente, inválido ou expirado |
| `403` | Forbidden | Permissão insuficiente (ex: operação admin com usuário não-admin) |
| `404` | Not Found | Recurso não encontrado |
| `409` | Conflict | Conflito de dados (ex: username já cadastrado, execução já finalizada) |
| `422` | Unprocessable Entity | Validação de payload falhou |

### Exemplo: Tratamento de Erro em Python

```python
import httpx

response = httpx.get(
    "http://localhost:8007/companhias/codigo-cvm/999999",
    headers={"Authorization": f"Bearer {TOKEN}"}
)

if response.status_code == 404:
    print("Companhia não encontrada")
elif response.status_code == 401:
    print("Token expirado - faça login novamente")
elif response.status_code == 422:
    errors = response.json()["detail"]
    for error in errors:
        print(f"Campo {error['loc']}: {error['msg']}")
else:
    response.raise_for_status()
```

---

## Datas e Timestamps

### Formato

Todos os campos de data/hora seguem **ISO 8601**:

- **Date**: `YYYY-MM-DD` (ex: `2025-12-31`)
- **DateTime**: `YYYY-MM-DDTHH:MM:SSZ` (ex: `2026-06-17T10:30:00Z`)

### Timezone

Todos os timestamps são em **UTC** (sufixo `Z`).

### Campos de Rastreabilidade

Quase todas as entidades de domínio possuem três timestamps:

| Campo | Descrição |
|-------|-----------|
| `criado_em` | Momento da primeira inserção no sistema |
| `sincronizado_em` | Última vez que o registro foi reencontrado na fonte CVM |
| `alterado_em` | Última vez que houve **mudança real de negócio** |

> **Importante para auditores:** `sincronizado_em` ≠ `alterado_em`. Reapresentação regulatória não é igual a alteração econômica.

---

## Valores Monetários

### Campos em Demonstrações Financeiras

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `valor_conta` | number | **Valor absoluto em reais** (já ajustado pela escala) |
| `valor_conta_reportado` | number | Valor bruto como reportado pela CVM |
| `escala_moeda` | string | `UNIDADE`, `MIL` ou `MILHAO` |
| `fator_escala_moeda` | integer | Multiplicador: `1`, `1000` ou `1000000` |

### Fórmula

```
valor_conta = valor_conta_reportado × fator_escala_moeda
```

### Exemplo

```json
{
  "valor_conta_reportado": 740500.0,
  "escala_moeda": "MIL",
  "fator_escala_moeda": 1000,
  "valor_conta": 740500000.0
}
```

> **Regra prática:** Para análises financeiras, sempre use `valor_conta`. Use `valor_conta_reportado` apenas para auditoria/traceabilidade.

---

## Formatos de CNPJ

A API aceita CNPJ **com ou sem pontuação**:

- ✅ `08.773.135/0001-00`
- ✅ `08773135000100`

O backend normaliza automaticamente para 14 dígitos.

---

## Limites e Quotas

| Limite | Valor | Aplicação |
|--------|-------|-----------|
| `tamanho_pagina` máximo | `500` | Todos os endpoints paginados |
| Registros por exportação | `100.000` | `/exportacoes/{fonte}/{dataset}` |
| `limite_por_endpoint` (mestre) | `500` | `/companhias/mestre` |
| TTL do token | `480` min (padrão) | Configurável via `ACCESS_TOKEN_TTL_MINUTES` |

---

## Content Types

### Request

- `application/json` (padrão para todos os endpoints)

### Response

- `application/json` (padrão)
- `text/csv` (quando `formato=csv` em `/exportacoes`)

---

## Versionamento

A API segue versionamento por URL. A versão atual é **v0.1.0** (indicada no OpenAPI).

Mudanças breaking serão comunicadas via:
- `docs/frontend_api_changelog.md`
- Headers de depreciação (quando aplicável)

---

## SDKs e Clientes

### OpenAPI Specification

A especificação completa está disponível em:

```
GET /openapi.json
```

### Geração de Clientes

Use o OpenAPI para gerar clientes em diversas linguagens:

```bash
# TypeScript/JavaScript (openapi-typescript-codegen)
npx openapi-typescript-codegen --input http://localhost:8007/openapi.json --output ./client

# Python (openapi-python-client)
openapi-python-client generate --url http://localhost:8007/openapi.json

# Go (openapi-generator)
openapi-generator generate -i http://localhost:8007/openapi.json -g go -o ./client
```

---

## Checklist de Integração

Antes de integrar sua aplicação, verifique:

- [ ] Obter token via `POST /auth/login`
- [ ] Armazenar token com segurança
- [ ] Implementar renovação automática ao receber `401`
- [ ] Usar paginação para listas grandes
- [ ] Tratar erros `422` com mensagens amigáveis
- [ ] Usar `valor_conta` (não `valor_conta_reportado`) para análises
- [ ] Respeitar limites de `tamanho_pagina` (máx 500)
- [ ] Usar HTTPS em produção