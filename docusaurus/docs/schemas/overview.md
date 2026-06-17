---
title: Schemas - Visão Geral
sidebar_position: 1
---

# Schemas e Tipos de Dados - Visão Geral

## Visão Geral

A API Tucano CVM utiliza **Pydantic v2** para validação e serialização de dados. Todos os schemas estão definidos no módulo `app/schemas/` e são automaticamente expostos via OpenAPI em `/openapi.json`.

## Especificação OpenAPI

A especificação completa está disponível em:

```
GET /openapi.json
```

Ou via interface interativa:

- **Swagger UI**: `/docs`
- **ReDoc**: `/redoc`

## Organização dos Schemas

Os schemas estão organizados por domínio:

| Categoria | Localização | Descrição |
|-----------|-------------|-----------|
| **Auth** | `app/schemas/auth.py` | Login, tokens, usuários |
| **Companhias** | `app/schemas/companhias.py` | Entidade raiz do domínio |
| **Financeiro** | `app/schemas/financeiro.py` | DFP/ITR (documentos, demonstrações) |
| **FRE** | `app/schemas/fre.py` | Formulário de Referência (48 datasets) |
| **FCA** | `app/schemas/fca.py` | Formulário Cadastral |
| **IPE** | `app/schemas/ipe.py` | Informações Periódicas e Eventuais |
| **VLMO** | `app/schemas/vlmo.py` | Valores Mobiliários Negociados |
| **CGVN** | `app/schemas/cgvn.py` | Governança Corporativa |
| **Análise** | `app/schemas/analise.py` | Endpoints estratégicos de análise |
| **Ingestion** | `app/schemas/ingestion.py` | Pipeline de ingestão |
| **Fontes** | `app/schemas/fontes.py` | Catálogo de fontes CVM |
| **Comuns** | `app/schemas/common.py` | Paginação, erros, tipos base |

## Convenções de Nomenclatura

### Schemas de Requisição

Terminam com `Requisicao` ou `Criacao`/`Atualizacao`:

- `LoginRequisicao`
- `UsuarioCriacao`
- `UsuarioAtualizacao`
- `ReplayQuarantineRequisicao`
- `AuditoriaFontesRequisicao`

### Schemas de Resposta

Terminam com `Resposta`:

- `CompanhiaResposta`
- `ListaCompanhiasResposta`
- `LoginResposta`
- `IngestionRunResumo`

### Schemas de Lista

Prefixados com `Lista` e contêm `dados` + `paginacao`:

- `ListaCompanhiasResposta`
- `ListaDocumentosFinanceirosResposta`
- `ListaQuarantineItems`

## Padrão de Resposta Paginada

Todas as listagens seguem o envelope:

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

**Schema:** `Paginacao`

```python
class Paginacao(BaseModel):
    pagina: int = Field(ge=1, description="Página atual")
    tamanho_pagina: int = Field(ge=1, le=500, description="Tamanho da página")
    total: int = Field(ge=0, description="Total de registros")
```

## Campos Transversais

Vários schemas compartilham campos de rastreabilidade:

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `id` | UUID | Identificador interno |
| `cnpj_companhia` | string | CNPJ com 14 dígitos |
| `codigo_cvm` | integer | Código CVM |
| `data_referencia` | date | Data de referência (YYYY-MM-DD) |
| `versao` | integer | Versão do documento |
| `arquivo_origem` | string | CSV de origem |
| `ano_origem` | integer | Ano do ZIP |
| `linha_origem` | integer | Linha no CSV |
| `criado_em` | datetime | Timestamp de criação (UTC) |
| `sincronizado_em` | datetime | Última sincronização (UTC) |
| `alterado_em` | datetime | Última alteração real (UTC) |

## Valores Monetários

Campos financeiros seguem o padrão:

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `valor_conta` | number | Valor absoluto em reais (ajustado por escala) |
| `valor_conta_reportado` | number | Valor bruto da CVM |
| `escala_moeda` | string | `UNIDADE`, `MIL`, `MILHAO` |
| `fator_escala_moeda` | integer | Multiplicador (1, 1000, 1000000) |

**Fórmula:** `valor_conta = valor_conta_reportado × fator_escala_moeda`

## Datas e Timestamps

- **Date**: `YYYY-MM-DD` (ISO 8601)
- **DateTime**: `YYYY-MM-DDTHH:MM:SSZ` (UTC)
- **Timezone**: Todos os timestamps em UTC (sufixo `Z`)

## Nullable Fields

Campos opcionais são representados com `anyOf` no OpenAPI:

```json
{
  "anyOf": [
    {"type": "string"},
    {"type": "null"}
  ]
}
```

Em Python, isso é representado como `Optional[str]` ou `str | None`.

## Validações Comuns

### CNPJ

```python
cnpj_companhia: str = Field(
    pattern=r"^[0-9./-]+$",
    description="CNPJ com ou sem pontuação"
)
```

### Username

```python
username: str = Field(
    min_length=3,
    max_length=150,
    pattern=r"^[a-zA-Z0-9_.@-]+$"
)
```

### Senha

```python
password: str = Field(
    min_length=8,
    max_length=256
)
```

### Valores Numéricos

```python
# Valores monetários com regex para evitar notação científica
valor: str = Field(
    pattern=r"^(?!^[-+.]*$)[+-]?0*\d*\.?\d*$"
)
```

## Próximos Passos

- [Schemas de Autenticação](./auth.md)
- [Schemas de Companhias](./companhias.md)
- [Schemas Financeiros](./financeiro.md)
- [Schemas de Análise](./analise.md)
- [Schemas de Ingestion](./ingestion.md)