---
title: Fontes e Datasets
sidebar_position: 6
---

# Fontes e Datasets

## Visão Geral

A API expõe o **catálogo interno de fontes CVM** suportadas, permitindo que clientes descubram quais datasets estão disponíveis, sua cobertura temporal e status de suporte.

## Endpoints

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/fontes` | Listar todas as fontes CVM disponíveis |
| `GET` | `/fontes/{fonte}/datasets` | Listar datasets de uma fonte específica |
| `GET` | `/exportacoes/{fonte}/{dataset}` | Exportação em lote (streaming) |

---

## `GET /fontes`

Retorna todas as fontes de dados da CVM registradas no sistema.

### Exemplo

```bash
curl -X GET "http://localhost:8007/fontes" \
  -H "Authorization: Bearer <token>"
```

### Response 200

**Schema:** Array de `FonteResposta`

```json
[
  {
    "fonte": "cadastro",
    "descricao": "Cadastro de companhias abertas",
    "tipo_distribuicao": "csv_unico",
    "primeiro_ano": null,
    "ultimo_ano": null,
    "status_suporte": "suportado"
  },
  {
    "fonte": "dfp",
    "descricao": "Demonstrações Financeiras Padronizadas (anuais)",
    "tipo_distribuicao": "zip_anual",
    "primeiro_ano": 2010,
    "ultimo_ano": 2026,
    "status_suporte": "suportado"
  },
  {
    "fonte": "itr",
    "descricao": "Informações Trimestrais",
    "tipo_distribuicao": "zip_anual",
    "primeiro_ano": 2011,
    "ultimo_ano": 2026,
    "status_suporte": "suportado"
  },
  {
    "fonte": "fre",
    "descricao": "Formulário de Referência",
    "tipo_distribuicao": "zip_anual",
    "primeiro_ano": 2010,
    "ultimo_ano": 2026,
    "status_suporte": "suportado"
  },
  {
    "fonte": "fca",
    "descricao": "Formulário Cadastral",
    "tipo_distribuicao": "zip_anual",
    "primeiro_ano": 2010,
    "ultimo_ano": 2026,
    "status_suporte": "suportado"
  },
  {
    "fonte": "ipe",
    "descricao": "Informações Periódicas e Eventuais",
    "tipo_distribuicao": "zip_anual",
    "primeiro_ano": 2003,
    "ultimo_ano": 2026,
    "status_suporte": "suportado"
  },
  {
    "fonte": "vlmo",
    "descricao": "Valores Mobiliários Negociados e Detidos",
    "tipo_distribuicao": "zip_anual",
    "primeiro_ano": 2018,
    "ultimo_ano": 2026,
    "status_suporte": "suportado"
  },
  {
    "fonte": "cgvn",
    "descricao": "Código de Governança Corporativa",
    "tipo_distribuicao": "zip_anual",
    "primeiro_ano": 2018,
    "ultimo_ano": 2026,
    "status_suporte": "suportado"
  }
]
```

### Campos da Resposta

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `fonte` | string | Chave canônica (ex: `dfp`, `fre`) |
| `descricao` | string | Descrição funcional da fonte |
| `tipo_distribuicao` | string | `csv_unico` ou `zip_anual` |
| `primeiro_ano` | integer \| null | Primeiro ano disponível |
| `ultimo_ano` | integer \| null | Último ano disponível |
| `status_suporte` | string | Status de suporte (`suportado`, `parcial`, `pendente`) |

---

## `GET /fontes/{fonte}/datasets`

Retorna todos os datasets/tabelas mapeados no catálogo para uma fonte específica.

### Path Parameters

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `fonte` | string | Chave canônica da fonte (ex: `fre`, `dfp`) |

### Exemplo

```bash
curl -X GET "http://localhost:8007/fontes/fre/datasets" \
  -H "Authorization: Bearer <token>"
```

### Response 200

**Schema:** Array de `DatasetResposta`

```json
[
  {
    "dataset": "documentos",
    "descricao": "Cabeçalho documental do FRE",
    "obrigatorio": true,
    "status_suporte": "suportado",
    "exportavel": true
  },
  {
    "dataset": "auditores",
    "descricao": "Auditores independentes",
    "obrigatorio": true,
    "status_suporte": "suportado",
    "exportavel": true
  },
  {
    "dataset": "capital_social",
    "descricao": "Capital social declarado",
    "obrigatorio": true,
    "status_suporte": "suportado",
    "exportavel": true
  },
  {
    "dataset": "posicao_acionaria",
    "descricao": "Posição acionária detalhada",
    "obrigatorio": true,
    "status_suporte": "suportado",
    "exportavel": true
  },
  {
    "dataset": "remuneracao_total_orgao",
    "descricao": "Remuneração total por órgão",
    "obrigatorio": true,
    "status_suporte": "suportado",
    "exportavel": true
  },
  {
    "dataset": "empregados_posicao_genero",
    "descricao": "Empregados por posição e gênero",
    "obrigatorio": true,
    "status_suporte": "suportado",
    "exportavel": true
  }
]
```

### Campos da Resposta

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `dataset` | string | Nome do dataset/tabela |
| `descricao` | string | Descrição do conteúdo |
| `obrigatorio` | boolean | Se é de preenchimento obrigatório |
| `status_suporte` | string | Status de suporte no sistema |
| `exportavel` | boolean | Se possui endpoint de exportação em lote |

### Códigos de Erro

| Status | Descrição |
|--------|-----------|
| `422` | Fonte inválida |

---

## `GET /exportacoes/{fonte}/{dataset}`

**Exportação em lote** de dados CVM por streaming. Suporta resolução automática de aliases curtos.

### Comportamento

- Executa consulta dinâmica e transmite por streaming em formato estruturado (JSON ou CSV)
- Suporta aliases curtos (ex: `bpa_ind` → `demonstracao_balanco_patrimonial_ativo_individual`)
- Nos datasets financeiros, `valor_conta` já é ajustado por `ESCALA_MOEDA`
- Datasets FRE explicitamente descontinuados pela CVM não aparecem no catálogo público e retornam `404` quando solicitados por exportação
- **Limite:** 100.000 registros por chamada

### Path Parameters

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `fonte` | string | Chave canônica da fonte |
| `dataset` | string | Nome do dataset ou alias curto |

### Query Parameters

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `cnpj_companhia` | string | CNPJ da companhia (com ou sem pontuação) |
| `codigo_cvm` | integer | Código CVM da companhia |
| `ano_inicio` | integer | Ano inicial (inclusive) |
| `ano_fim` | integer | Ano final (inclusive) |
| `formato` | string | `json` (padrão) ou `csv` |

### Exemplos

#### Exportar DFP consolidado em CSV

```bash
curl -X GET "http://localhost:8007/exportacoes/dfp/bpa_con?codigo_cvm=25224&ano_inicio=2020&ano_fim=2025&formato=csv" \
  -H "Authorization: Bearer <token>" \
  -o bpa_consolidado.csv
```

#### Exportar usando alias curto

```bash
# bpa_ind é alias para demonstracao_balanco_patrimonial_ativo_individual
curl -X GET "http://localhost:8007/exportacoes/dfp/bpa_ind?codigo_cvm=25224&ano_inicio=2024" \
  -H "Authorization: Bearer <token>" \
  -o bpa_individual.json
```

#### Exportar FRE de posição acionária

```bash
curl -X GET "http://localhost:8007/exportacoes/fre/posicao_acionaria?codigo_cvm=25224&ano_inicio=2023" \
  -H "Authorization: Bearer <token>" \
  -o posicao_acionaria.json
```

#### Dataset FRE descontinuado pela CVM

```bash
curl -X GET "http://localhost:8007/exportacoes/fre/capital_social_aumento?formato=json" \
  -H "Authorization: Bearer <token>"
```

Resposta esperada: `404`, com orientação para consultar `capital_social`, `capital_social_classe_acao` e `distribuicao_capital`.

### Response 200

**Content-Type:** `application/json` ou `text/csv`

#### JSON

```json
[
  {
    "cnpj_companhia": "08773135000100",
    "codigo_cvm": 25224,
    "data_referencia": "2025-12-31",
    "codigo_conta": "1",
    "descricao_conta": "Ativo Total",
    "valor_conta": 740500000.0,
    "valor_conta_reportado": 740500.0,
    "escala_moeda": "MIL",
    "fator_escala_moeda": 1000
  }
]
```

#### CSV

```csv
cnpj_companhia,codigo_cvm,data_referencia,codigo_conta,descricao_conta,valor_conta,valor_conta_reportado,escala_moeda,fator_escala_moeda
08773135000100,25224,2025-12-31,1,Ativo Total,740500000.0,740500.0,MIL,1000
```

### Aliases Comuns

| Alias | Dataset Completo |
|-------|------------------|
| `bpa_con` | `demonstracao_balanco_patrimonial_ativo_consolidado` |
| `bpa_ind` | `demonstracao_balanco_patrimonial_ativo_individual` |
| `bpp_con` | `demonstracao_balanco_patrimonial_passivo_consolidado` |
| `bpp_ind` | `demonstracao_balanco_patrimonial_passivo_individual` |
| `dre_con` | `demonstracao_resultado_consolidado` |
| `dre_ind` | `demonstracao_resultado_individual` |
| `dfc_con` | `demonstracao_fluxos_caixa_consolidado` |
| `dva_con` | `demonstracao_valor_adicionado_consolidado` |

### Códigos de Erro

| Status | Descrição |
|--------|-----------|
| `422` | Fonte ou dataset inválido, ou parâmetros inválidos |

---

## Casos de Uso

### Caso 1: Descobrir Datasets Disponíveis

```bash
# Listar todas as fontes
GET /fontes

# Listar datasets do FRE
GET /fontes/fre/datasets

# Listar datasets do DFP
GET /fontes/dfp/datasets
```

### Caso 2: Exportar Dados para Análise Externa

```bash
# Exportar DRE consolidado de todas as companhias em 2024
GET /exportacoes/dfp/dre_con?ano_inicio=2024&ano_fim=2024&formato=csv

# Exportar posição acionária de uma companhia específica
GET /exportacoes/fre/posicao_acionaria?codigo_cvm=25224&ano_inicio=2020&formato=json
```

### Caso 3: Python - Download Automatizado

```python
import httpx
from pathlib import Path

def exportar_dataset(fonte, dataset, params, token, output_path):
    """Exporta dataset em lote para arquivo local."""
    base_url = "http://localhost:8007"
    formato = params.get("formato", "json")
    
    response = httpx.get(
        f"{base_url}/exportacoes/{fonte}/{dataset}",
        params=params,
        headers={"Authorization": f"Bearer {token}"},
        timeout=300.0
    )
    response.raise_for_status()
    
    Path(output_path).write_bytes(response.content)
    print(f"Exportado: {output_path} ({len(response.content)} bytes)")

# Uso
exportar_dataset(
    fonte="dfp",
    dataset="dre_con",
    params={"codigo_cvm": 25224, "ano_inicio": 2020, "formato": "csv"},
    token="seu-token",
    output_path="dre_consolidado.csv"
)
```

---

## Notas Técnicas

### Streaming

O endpoint de exportação usa **streaming HTTP** para transmitir grandes volumes de dados sem consumir memória excessiva no servidor. Para datasets muito grandes, considere:

- Filtrar por `codigo_cvm` ou `cnpj_companhia`
- Limitar o intervalo de anos (`ano_inicio` / `ano_fim`)
- Usar paginação via endpoints regulares (não streaming)

### Limites

| Limite | Valor |
|--------|-------|
| Registros por exportação | 100.000 |
| Timeout recomendado | 300 segundos |

### Performance

- Para consultas interativas, use os endpoints regulares com paginação
- Para extrações em lote (ETL, relatórios), use `/exportacoes`
- Prefira `formato=csv` para integração com ferramentas de BI

---

## Próximos Passos

- [Análise](./analise.md) - Endpoints estratégicos de análise consolidada
- [Ingestion](../ingestion/monitoring.md) - Monitoramento de sincronizações
