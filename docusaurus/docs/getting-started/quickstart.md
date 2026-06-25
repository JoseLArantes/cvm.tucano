---
title: Inicio Rapido - Primeiras Consultas
sidebar_position: 3
---

# Inicio Rapido - Primeiras Consultas

Este guia mostra como realizar as primeiras consultas na API Tucano CVM após a instalação e autenticação.

## Pré-requisitos

1. Serviço rodando (consulte [Instalação](./installation.md))
2. Token de autenticação (consulte [Autenticação](./authentication.md))

## 1. Listar Companhias

Obter lista de companhias abertas cadastradas:

```bash
curl -X GET "http://localhost:8007/companhias?pagina=1&tamanho_pagina=10" \
  -H "Authorization: Bearer seu-token-aqui"
```

**Resposta:**

```json
{
  "dados": [
    {
      "id": "f4f6a9d8-7e26-45f2-b3fb-ec43a0f8a89a",
      "cnpj_companhia": "08773135000100",
      "codigo_cvm": 25224,
      "denominacao_social": "2W ECOBANK S.A. - EM RECUPERACAO JUDICIAL",
      "denominacao_comercial": "2W ECOBANK S.A.",
      "situacao_registro": "SUSPENSO(A) - DECISAO ADM",
      "data_registro": "2020-10-29",
      "setor_atividade": "Energia Eletrica",
      "tipo_mercado": "Novo Mercado",
      "criado_em": "2026-05-30T14:30:00Z",
      "sincronizado_em": "2026-05-30T14:30:00Z",
      "alterado_em": "2026-05-30T14:30:00Z"
    }
  ],
  "paginacao": {
    "pagina": 1,
    "tamanho_pagina": 10,
    "total": 1
  }
}
```

### Filtros Disponíveis

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `cnpj_companhia` | string | CNPJ (com ou sem pontuação) |
| `codigo_cvm` | integer | Código CVM da companhia |
| `nome` | string | Nome (razão social ou comercial) |
| `situacao_registro` | string | Situação do registro (ATIVO, SUSPENSO, etc.) |
| `ordenar` | string | Ordenação: `ativa_nome`, `nome`, `codigo_cvm` |

**Exemplo com filtros:**

```bash
curl -X GET "http://localhost:8007/companhias?nome=Petrobras&situacao_registro=ATIVO" \
  -H "Authorization: Bearer seu-token-aqui"
```

## 2. Obter Companhia Específica

### Por Código CVM

```bash
curl -X GET "http://localhost:8007/companhias/codigo-cvm/25224" \
  -H "Authorization: Bearer seu-token-aqui"
```

### Por CNPJ

```bash
curl -X GET "http://localhost:8007/companhias/08.773.135/0001-00" \
  -H "Authorization: Bearer seu-token-aqui"
```

## 3. Consultar Dados Financeiros (DFP)

### Listar Documentos DFP

```bash
curl -X GET "http://localhost:8007/dfp/documentos?codigo_cvm=25224&ano_inicio=2024" \
  -H "Authorization: Bearer seu-token-aqui"
```

### Consultar Balanço Patrimonial (Ativo - Consolidado)

```bash
curl -X GET "http://localhost:8007/dfp/balanco-patrimonial-ativo/consolidado?codigo_cvm=25224&ano_inicio=2024" \
  -H "Authorization: Bearer seu-token-aqui"
```

**Resposta:**

```json
{
  "dados": [
    {
      "id": "bbf228f5-5627-4fc5-a490-318b8ba31e43",
      "cnpj_companhia": "00000000000191",
      "codigo_cvm": 1023,
      "data_referencia": "2025-12-31",
      "versao": 1,
      "tipo_demonstracao": "balanco_patrimonial_ativo",
      "escopo_demonstracao": "consolidado",
      "codigo_conta": "1",
      "descricao_conta": "Ativo Total",
      "valor_conta": 740500000.0,
      "valor_conta_reportado": 740500.0,
      "escala_moeda": "MIL",
      "fator_escala_moeda": 1000,
      "ordem_exercicio": "ÚLTIMO"
    }
  ],
  "paginacao": {
    "pagina": 1,
    "tamanho_pagina": 100,
    "total": 1
  }
}
```

### Entendendo os Valores Monetários

| Campo | Descrição |
|-------|-----------|
| `valor_conta` | Valor monetário absoluto após aplicação da escala (ex: R$ 740.500.000,00) |
| `valor_conta_reportado` | Valor bruto como reportado pela CVM (ex: 740500) |
| `escala_moeda` | Escala informada pela CVM (UNIDADE, MIL, MILHAO) |
| `fator_escala_moeda` | Multiplicador aplicado (1, 1000, 1000000) |

**Fórmula:** `valor_conta = valor_conta_reportado × fator_escala_moeda`

## 4. Consultar Formulário de Referência (FRE)

### Listar Documentos FRE

```bash
curl -X GET "http://localhost:8007/fre/documentos?codigo_cvm=25224" \
  -H "Authorization: Bearer seu-token-aqui"
```

### Consultar Posição Acionária

```bash
curl -X GET "http://localhost:8007/fre/posicao-acionaria?codigo_cvm=25224" \
  -H "Authorization: Bearer seu-token-aqui"
```

### Consultar Remuneração de Administradores

```bash
curl -X GET "http://localhost:8007/fre/remuneracao/total-por-orgao?codigo_cvm=25224" \
  -H "Authorization: Bearer seu-token-aqui"
```

## 5. Consultar Informações Periódicas e Eventuais (IPE)

### Listar Documentos IPE

```bash
curl -X GET "http://localhost:8007/ipe/documentos?codigo_cvm=25224&categoria=Fato%20Relevante" \
  -H "Authorization: Bearer seu-token-aqui"
```

**Parâmetros de Filtro:**

| Parâmetro | Descrição |
|-----------|-----------|
| `categoria` | Categoria do documento (Fato Relevante, Aviso aos Acionistas, etc.) |
| `tipo` | Tipo do documento |
| `assunto` | Assunto do documento |
| `data_referencia_inicio` | Data inicial (YYYY-MM-DD) |
| `data_referencia_fim` | Data final (YYYY-MM-DD) |

## 6. Consulta Agregada (Master Endpoint)

Para obter todos os dados de uma companhia em uma única chamada:

```bash
curl -X GET "http://localhost:8007/companhias/mestre?codigo_cvm=25224&limite_por_endpoint=50" \
  -H "Authorization: Bearer seu-token-aqui"
```

**Resposta:**

```json
{
  "companhia": {
    "id": "...",
    "cnpj_companhia": "08773135000100",
    "codigo_cvm": 25224,
    "denominacao_social": "..."
  },
  "documentos_dfp": {
    "dados": [...],
    "paginacao": {...}
  },
  "documentos_itr": {
    "dados": [...],
    "paginacao": {...}
  },
  "demonstracoes": {
    "dfp_balanco_patrimonial_ativo_consolidado": {...},
    "dfp_demonstracao_resultado_consolidado": {...}
  },
  "fre_documentos": {...},
  "fre_posicao_acionaria": {...},
  "ipe_documentos": {...}
}
```

## 7. Consultar a API Analitica

### Manifesto analitico da companhia

```bash
curl -X GET "http://localhost:8007/analise/companhias/25224?escopo=consolidated" \
  -H "Authorization: Bearer seu-token-aqui"
```

### Series trimestrais normalizadas

```bash
curl -X GET "http://localhost:8007/analise/companhias/25224/series?metricas=receita_liquida,lucro_liquido&periodicidade=quarterly&base_periodo=quarter&escopo=consolidated" \
  -H "Authorization: Bearer seu-token-aqui"
```

### Comparacoes analiticas prontas

```bash
curl -X GET "http://localhost:8007/analise/companhias/25224/comparacoes?metricas=receita_liquida&periodicidade=quarterly&base_periodo=quarter" \
  -H "Authorization: Bearer seu-token-aqui"
```

## 7. Análise Financeira Consolidada

Para obter métricas financeiras com cálculos automáticos (YoY, QoQ, CAGR):

```bash
curl -X GET "http://localhost:8007/companhias/25224/analise/financeiro?horizonte=5a&periodicidade=anual" \
  -H "Authorization: Bearer seu-token-aqui"
```

**Resposta:**

```json
{
  "cnpj_companhia": "08773135000100",
  "codigo_cvm": 25224,
  "dados": [
    {
      "periodo_label": "2024",
      "ano": 2024,
      "trimestre": 0,
      "periodo_tipo": "ANUAL",
      "metrics": {
        "receita_liquida": {
          "valor_normalizado": 740500000.0,
          "valor_original": "740500",
          "yoy": 15.5,
          "cagr": 12.3,
          "proveniencia": {
            "fonte": "CVM",
            "dataset": "demonstracao_resultado",
            "data_referencia": "2024-12-31"
          }
        }
      }
    }
  ]
}
```

## 8. Exportação em Lote

Para exportar grandes volumes de dados:

```bash
curl -X GET "http://localhost:8007/exportacoes/dfp/balanco-patrimonial-ativo/consolidado?codigo_cvm=25224&ano_inicio=2020&ano_fim=2025&formato=csv" \
  -H "Authorization: Bearer seu-token-aqui" \
  -o exportacao.csv
```

**Parâmetros:**

| Parâmetro | Descrição |
|-----------|-----------|
| `fonte` | Fonte de dados (dfp, itr, fre, etc.) |
| `dataset` | Dataset específico ou alias (ex: `bpa_ind`) |
| `formato` | Formato de saída: `json` ou `csv` |
| `ano_inicio` | Ano inicial (inclusive) |
| `ano_fim` | Ano final (inclusive) |

**Limite:** Máximo de 100.000 registros por chamada.

## 9. Monitorar Sincronizações

### Listar Execuções de Sincronização

```bash
curl -X GET "http://localhost:8007/ingestion/sincronizacoes?pagina=1&tamanho_pagina=20" \
  -H "Authorization: Bearer seu-token-aqui"
```

### Dashboard de Execuções

```bash
curl -X GET "http://localhost:8007/ingestion/dashboard" \
  -H "Authorization: Bearer seu-token-aqui"
```

**Resposta:**

```json
{
  "total_execucoes": 150,
  "total_sucesso": 145,
  "total_sem_alteracao": 3,
  "total_falha": 2,
  "total_rejeitados": 15,
  "ultimas_execucoes": [...]
}
```

## 10. Exemplos Completos

### Exemplo Python: Análise de Companhia

```python
import httpx

# Configuração
BASE_URL = "http://localhost:8007"
TOKEN = "seu-token-aqui"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

# 1. Buscar companhia
response = httpx.get(
    f"{BASE_URL}/companhias/codigo-cvm/25224",
    headers=HEADERS
)
companhia = response.json()
print(f"Companhia: {companhia['denominacao_social']}")

# 2. Buscar DFP mais recente
response = httpx.get(
    f"{BASE_URL}/dfp/documentos",
    params={"codigo_cvm": 25224, "ordenar_por": "-data_referencia"},
    headers=HEADERS
)
dfp_docs = response.json()["dados"]
if dfp_docs:
    ultimo_dfp = dfp_docs[0]
    print(f"Último DFP: {ultimo_dfp['data_referencia']} (versão {ultimo_dfp['versao']})")

# 3. Buscar balanço patrimonial
response = httpx.get(
    f"{BASE_URL}/dfp/balanco-patrimonial-ativo/consolidado",
    params={
        "codigo_cvm": 25224,
        "data_referencia_inicio": "2024-01-01",
        "data_referencia_fim": "2024-12-31"
    },
    headers=HEADERS
)
balanco = response.json()["dados"]
for linha in balanco[:5]:
    print(f"{linha['descricao_conta']}: R$ {linha['valor_conta']:,.2f}")
```

### Exemplo JavaScript: Monitorar Eventos

```javascript
const BASE_URL = 'http://localhost:8007';
const TOKEN = 'seu-token-aqui';

// Buscar fatos relevantes recentes
const response = await fetch(
  `${BASE_URL}/ipe/documentos?categoria=Fato%20Relevante&data_referencia_inicio=2025-01-01`,
  { headers: { 'Authorization': `Bearer ${TOKEN}` } }
);

const { dados } = await response.json();
console.log(`Total de fatos relevantes: ${dados.length}`);

dados.slice(0, 5).forEach(doc => {
  console.log(`${doc.data_entrega} - ${doc.nome_companhia}: ${doc.assunto}`);
});
```

## Próximos Passos

Agora que você conhece o básico, explore:

1. **[Fontes de Dados](../data-sources/cadastro.md)** - Detalhes de cada fonte CVM
2. **[API Endpoints](../api-endpoints/auth.md)** - Referência completa da API
3. **[Pipeline de Ingestão](../concepts/ingestion-pipeline.md)** - Como funciona internamente
4. **[Monitoramento](../ingestion/monitoring.md)** - Como monitorar sincronizações
