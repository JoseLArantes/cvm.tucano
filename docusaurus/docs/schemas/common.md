---
title: Schemas Comuns e Tipos Base
sidebar_position: 7
---

# Schemas Comuns e Tipos Base

## `Paginacao`

Metadados de paginação presente em todas as listagens.

### Schema

```python
class Paginacao(BaseModel):
    pagina: int = Field(ge=1, description="Página atual considerada na resposta.")
    tamanho_pagina: int = Field(ge=1, le=500, description="Tamanho da página aplicado.")
    total: int = Field(ge=0, description="Total de registros disponíveis.")
```

### Exemplo JSON

```json
{
  "pagina": 1,
  "tamanho_pagina": 100,
  "total": 1250
}
```

### Validações

- `pagina`: mínimo 1
- `tamanho_pagina`: mínimo 1, máximo **500**
- `total`: mínimo 0

---

## `HTTPValidationError`

Schema de erro de validação (HTTP 422).

### Schema

```python
class HTTPValidationError(BaseModel):
    detail: List[ValidationError]

class ValidationError(BaseModel):
    loc: List[Union[str, int]]
    msg: str
    type: str
    input: Optional[Any]
    ctx: Optional[Dict[str, Any]]
```

### Exemplo JSON

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "password"],
      "msg": "Field required",
      "input": {"username": "admin"}
    }
  ]
}
```

### Campos

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `type` | string | Tipo do erro (ex: `missing`, `value_error`, `type_error`) |
| `loc` | array | Localização do erro (ex: `["body", "password"]`) |
| `msg` | string | Mensagem legível |
| `input` | any | Valor recebido que causou o erro |
| `ctx` | object | Contexto adicional (opcional) |

---

## Tipos de Dados Comuns

### UUID

```python
from uuid import UUID

id: UUID
```

**Formato:** `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`

**Exemplo:** `f4f6a9d8-7e26-45f2-b3fb-ec43a0f8a89a`

### Date

```python
from datetime import date

data_referencia: date
```

**Formato:** `YYYY-MM-DD` (ISO 8601)

**Exemplo:** `2025-12-31`

### DateTime

```python
from datetime import datetime

criado_em: datetime
```

**Formato:** `YYYY-MM-DDTHH:MM:SSZ` (UTC)

**Exemplo:** `2026-05-30T14:30:00Z`

### Optional Fields

Campos opcionais são representados com `Optional[T]` ou `T | None`:

```python
codigo_cvm: Optional[int]
denominacao_social: Optional[str]
```

No OpenAPI, isso é representado como:

```json
{
  "anyOf": [
    {"type": "integer"},
    {"type": "null"}
  ]
}
```

### Dict (Objetos Estruturados)

```python
endereco: Dict[str, Any]
responsavel: Dict[str, Any]
diagnostico: Optional[Dict[str, Any]]
```

**Exemplo:**

```json
{
  "endereco": {
    "tipo_endereco": "SEDE",
    "logradouro": "Avenida Dr. Chucri Zaidan, 1550",
    "bairro": "Chacara Santo Antoni",
    "municipio": "SAO PAULO",
    "uf": "SP"
  }
}
```

### List (Arrays)

```python
dados: List[CompanhiaResposta]
alertas: List[AlertaOverview]
header_columns: List[str]
```

---

## Validações de Campos

### CNPJ

```python
cnpj_companhia: str = Field(
    pattern=r"^[0-9./-]+$",
    description="CNPJ com ou sem pontuação"
)
```

**Aceita:**
- `08.773.135/0001-00` (com pontuação)
- `08773135000100` (sem pontuação)

### Username

```python
username: str = Field(
    min_length=3,
    max_length=150,
    pattern=r"^[a-zA-Z0-9_.@-]+$"
)
```

**Aceita:**
- `admin`
- `analista_financeiro`
- `usuario@email.com`
- `user-name`

### Senha

```python
password: str = Field(
    min_length=8,
    max_length=256
)
```

### Valores Monetários (Regex)

```python
valor: str = Field(
    pattern=r"^(?!^[-+.]*$)[+-]?0*\d*\.?\d*$",
    description="Valor numérico sem notação científica"
)
```

**Aceita:**
- `740500.0`
- `1234.56`
- `-100.00`

**Rejeita:**
- `1e10` (notação científica)
- `abc` (não numérico)

---

## Códigos HTTP Comuns

| Status | Descrição | Schema |
|--------|-----------|--------|
| `200` | Sucesso | Varies |
| `201` | Criado | `UsuarioResposta` |
| `204` | Sem Conteúdo | (vazio) |
| `400` | Bad Request | `{"detail": "..."}` |
| `401` | Unauthorized | `{"detail": "..."}` |
| `403` | Forbidden | `{"detail": "..."}` |
| `404` | Not Found | `{"detail": "..."}` |
| `409` | Conflict | `{"detail": "..."}` |
| `422` | Validation Error | `HTTPValidationError` |

---

## Exemplos de Erros

### 401 Unauthorized

```json
{
  "detail": "Usuario ou senha invalidos."
}
```

### 403 Forbidden

```json
{
  "detail": "Permissao administrativa requerida."
}
```

### 404 Not Found

```json
{
  "detail": "Companhia nao encontrada."
}
```

### 409 Conflict

```json
{
  "detail": "Username ja cadastrado."
}
```

### 422 Validation Error

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "password"],
      "msg": "Field required",
      "input": {"username": "admin"}
    }
  ]
}
```

---

## Content Types

### Request

- `application/json` (padrão para todos os endpoints)

### Response

- `application/json` (padrão)
- `text/csv` (quando `formato=csv` em `/exportacoes`)

---

## Geração de Clientes

### OpenAPI Specification

```
GET /openapi.json
```

### TypeScript/JavaScript

```bash
npx openapi-typescript-codegen \
  --input http://localhost:8007/openapi.json \
  --output ./client
```

### Python

```bash
openapi-python-client generate \
  --url http://localhost:8007/openapi.json
```

### Go

```bash
openapi-generator generate \
  -i http://localhost:8007/openapi.json \
  -g go \
  -o ./client
```

### Java

```bash
openapi-generator generate \
  -i http://localhost:8007/openapi.json \
  -g java \
  -o ./client
```

---

## Interfaces TypeScript (Exemplo)

```typescript
// Gerado automaticamente pelo openapi-typescript-codegen

export interface CompanhiaResposta {
  id: string;
  cnpj_companhia: string;
  codigo_cvm?: number;
  denominacao_social?: string;
  denominacao_comercial?: string;
  situacao_registro?: string;
  data_registro?: string;
  data_constituicao?: string;
  setor_atividade?: string;
  tipo_mercado?: string;
  endereco: Record<string, any>;
  responsavel: Record<string, any>;
  auditor?: string;
  cnpj_auditor?: string;
  criado_em: string;
  sincronizado_em: string;
  alterado_em: string;
}

export interface ListaCompanhiasResposta {
  dados: CompanhiaResposta[];
  paginacao: Paginacao;
}

export interface Paginacao {
  pagina: number;
  tamanho_pagina: number;
  total: number;
}

export interface LoginRequisicao {
  username: string;
  password: string;
}

export interface LoginResposta {
  access_token: string;
  token_type: string;
  expires_in: number;
}
```

---

## Pydantic Models (Python)

```python
# Importar schemas gerados

from client.models import CompanhiaResposta, ListaCompanhiasResposta

def listar_companhias():
    response = httpx.get(
        "http://localhost:8007/companhias",
        headers={"Authorization": f"Bearer {token}"}
    )
    data = response.json()
    
    # Validar com Pydantic
    lista = ListaCompanhiasResposta(**data)
    
    for companhia in lista.dados:
        print(f"{companhia.denominacao_social} - {companhia.codigo_cvm}")
```