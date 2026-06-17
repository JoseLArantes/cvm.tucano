---
title: Análise Estratégica
sidebar_position: 7
---

# Análise Estratégica

## Visão Geral

Os endpoints de análise fornecem **visões consolidadas e enriquecidas** dos dados CVM, com cálculos automáticos de indicadores financeiros (YoY, QoQ, CAGR), proveniência e alertas. São ideais para dashboards executivos e análises rápidas.

## Endpoints

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/companhias/{codigo_cvm}/analise/overview` | Visão geral da companhia |
| `GET` | `/companhias/{codigo_cvm}/analise/financeiro` | Análise financeira com proveniência |
| `GET` | `/companhias/{codigo_cvm}/analise/comparativo` | Comparativo anual |
| `GET` | `/companhias/{codigo_cvm}/analise/eventos` | Timeline de eventos |
| `GET` | `/companhias/{codigo_cvm}/analise/pessoas-remuneracao` | Estrutura de administração e remuneração |
| `GET` | `/companhias/{codigo_cvm}/analise/mercado-insiders` | Insider trading e inteligência de mercado |
| `GET` | `/companhias/{codigo_cvm}/analise` | Análise consolidada (endpoint estratégico) |

---

## `GET /companhias/{codigo_cvm}/analise/overview`

Retorna **cobertura anual de dados**, frescor das fontes e alertas cadastrais.

### Path Parameters

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `codigo_cvm` | integer | Código CVM da companhia |

### Exemplo

```bash
curl -X GET "http://localhost:8007/companhias/25224/analise/overview" \
  -H "Authorization: Bearer <token>"
```

### Response 200

**Schema:** `OverviewAnaliseResposta`

```json
{
  "cnpj_companhia": "08773135000100",
  "codigo_cvm": 25224,
  "denominacao_social": "2W ECOBANK S.A. - EM RECUPERACAO JUDICIAL",
  "situacao_registro": "SUSPENSO(A) - DECISAO ADM",
  "status_ativo": false,
  "data_freshness": "2026-06-15T08:00:00Z",
  "cobertura": {
    "2024": ["DFP", "FRE", "FCA", "IPE"],
    "2023": ["DFP", "ITR", "FRE", "FCA", "IPE"],
    "2022": ["DFP", "ITR", "FRE", "FCA", "IPE"]
  },
  "periodos_disponiveis": {
    "DFP": ["2024-12-31", "2023-12-31", "2022-12-31"],
    "ITR": ["2024-09-30", "2024-06-30", "2024-03-31"]
  },
  "alertas": [
    {
      "tipo": "SITUACAO_REGISTRO",
      "descricao": "Companhia com registro suspenso",
      "severidade": "WARNING"
    },
    {
      "tipo": "ATRASO_FILING",
      "descricao": "DFP 2024 entregue após prazo regulatório",
      "severidade": "INFO"
    }
  ],
  "anos_comparacao_disponiveis": [2024, 2023, 2022, 2021, 2020]
}
```

### Campos da Resposta

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `cnpj_companhia` | string | CNPJ da companhia |
| `codigo_cvm` | integer | Código CVM |
| `denominacao_social` | string | Razão social |
| `situacao_registro` | string | Situação atual |
| `status_ativo` | boolean | Se está ativa |
| `data_freshness` | datetime | Timestamp da última sincronização geral |
| `cobertura` | object | Mapeamento de ano para famílias de dados disponíveis |
| `periodos_disponiveis` | object | Períodos disponíveis por tipo documental |
| `alertas` | array | Lista de alertas de conformidade ou operacionais |
| `anos_comparacao_disponiveis` | array | Anos com DFP disponível para comparação |

### Tipos de Alerta

| Tipo | Descrição | Severidade Típica |
|------|-----------|-------------------|
| `SITUACAO_REGISTRO` | Problema com registro na CVM | WARNING/CRITICAL |
| `ATRASO_FILING` | Entrega após prazo regulatório | INFO/WARNING |
| `REAPRESENTACAO` | Documento reapresentado | INFO |
| `AUDITOR_RESSALVA` | Parecer com ressalvas | WARNING |

---

## `GET /companhias/{codigo_cvm}/analise/financeiro`

Retorna **métricas financeiras anuais e trimestrais normalizadas** com variação YoY/QoQ/CAGR e proveniência.

### Query Parameters

| Parâmetro | Tipo | Padrão | Descrição |
|-----------|------|--------|-----------|
| `horizonte` | string | `5a` | Horizonte de anos: `5a`, `10a`, `todos` |
| `periodicidade` | string | `anual` | Tipo de formulários: `anual`, `trimestral`, `todos` |

### Exemplo

```bash
curl -X GET "http://localhost:8007/companhias/25224/analise/financeiro?horizonte=5a&periodicidade=anual" \
  -H "Authorization: Bearer <token>"
```

### Response 200

**Schema:** `FinanceiroAnaliseResposta`

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
          "qoq": null,
          "cagr": 12.3,
          "proveniencia": {
            "fonte": "CVM",
            "dataset": "demonstracao_resultado",
            "documento_id": 123456,
            "linha_id": "bbf228f5-5627-4fc5-a490-318b8ba31e43",
            "data_referencia": "2024-12-31",
            "data_entrega": "2025-03-15",
            "link_download": "https://dados.cvm.gov.br/..."
          }
        },
        "lucro_liquido": {
          "valor_normalizado": 85000000.0,
          "valor_original": "85000",
          "yoy": 8.2,
          "cagr": 6.5,
          "proveniencia": { "..." }
        },
        "ativo_total": {
          "valor_normalizado": 1200000000.0,
          "valor_original": "1200000",
          "yoy": 5.1,
          "cagr": 4.8,
          "proveniencia": { "..." }
        }
      }
    },
    {
      "periodo_label": "2023",
      "ano": 2023,
      "trimestre": 0,
      "periodo_tipo": "ANUAL",
      "metrics": { "..." }
    }
  ]
}
```

### Campos da Métrica

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `valor_normalizado` | number | Valor absoluto em reais (ajustado por escala) |
| `valor_original` | string | Valor exatamente como reportado pela CVM |
| `yoy` | number | Variação ano contra ano (%) |
| `qoq` | number | Variação trimestre contra trimestre anterior (%) |
| `cagr` | number | Taxa de crescimento anual composta (%) |
| `proveniencia` | object | Metadados de proveniência do dado contábil |

### Métricas Disponíveis

- `receita_liquida`
- `lucro_liquido`
- `ativo_total`
- `patrimonio_liquido`
- `divida_liquida`
- `ebitda`
- `margem_liquida`
- `roe`
- `roa`

### Códigos de Erro

| Status | Descrição |
|--------|-----------|
| `404` | Companhia não encontrada |
| `422` | Parâmetro inválido |

---

## `GET /companhias/{codigo_cvm}/analise/comparativo`

Compara o desempenho financeiro, composição de capital e governança entre **dois anos específicos**.

### Query Parameters

| Parâmetro | Tipo | Obrigatório | Descrição |
|-----------|------|-------------|-----------|
| `ano_base` | integer | Sim | Ano base da comparação |
| `ano_comparacao` | integer | Sim | Ano a ser comparado |

### Exemplo

```bash
curl -X GET "http://localhost:8007/companhias/25224/analise/comparativo?ano_base=2024&ano_comparacao=2023" \
  -H "Authorization: Bearer <token>"
```

### Response 200

**Schema:** `ComparativoAnaliseResposta`

```json
{
  "ano_base": 2024,
  "ano_comparacao": 2023,
  "financeiro": {
    "receita_liquida": {
      "valor_base": 740500000.0,
      "valor_comparacao": 641000000.0,
      "delta_absoluto": 99500000.0,
      "delta_percentual": 15.5
    },
    "lucro_liquido": {
      "valor_base": 85000000.0,
      "valor_comparacao": 78500000.0,
      "delta_absoluto": 6500000.0,
      "delta_percentual": 8.2
    }
  },
  "capital": {
    "quantidade_total_acoes": {
      "valor_base": 1000000000,
      "valor_comparacao": 1000000000,
      "delta_absoluto": 0,
      "delta_percentual": 0.0
    }
  },
  "governanca": {
    "numero_conselheiros": {
      "valor_base": 7,
      "valor_comparacao": 6,
      "delta_absoluto": 1,
      "delta_percentual": 16.7
    }
  },
  "pessoas": {
    "total_empregados": {
      "valor_base": 15000,
      "valor_comparacao": 14200,
      "delta_absoluto": 800,
      "delta_percentual": 5.6
    }
  },
  "mercado": {
    "volume_negociacao_insiders": {
      "valor_base": 5000000.0,
      "valor_comparacao": 3200000.0,
      "delta_absoluto": 1800000.0,
      "delta_percentual": 56.3
    }
  },
  "eventos_ipe": {
    "valor_base": 45,
    "valor_comparacao": 38,
    "delta_absoluto": 7,
    "delta_percentual": 18.4
  }
}
```

### Campos do Delta

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `valor_base` | number | Valor no ano base |
| `valor_comparacao` | number | Valor no ano de comparação |
| `delta_absoluto` | number | Diferença absoluta (Base - Comparação) |
| `delta_percentual` | number | Variação percentual |

---

## `GET /companhias/{codigo_cvm}/analise/eventos`

Retorna uma **linha do tempo unificada** de fatos relevantes (IPE), reapresentações financeiras e grandes negociações.

### Exemplo

```bash
curl -X GET "http://localhost:8007/companhias/25224/analise/eventos" \
  -H "Authorization: Bearer <token>"
```

### Response 200

**Schema:** Array de `EventoLinhaTempo`

```json
[
  {
    "data_evento": "2026-05-15",
    "familia_evento": "IPE",
    "tipo_evento": "Fato Relevante",
    "severidade": "INFO",
    "titulo": "Resultado do 1T26",
    "explicacao": "Divulgação dos resultados do primeiro trimestre de 2026",
    "link_documento": "https://dados.cvm.gov.br/...",
    "periodo_afetado": "2026-1T"
  },
  {
    "data_evento": "2026-04-20",
    "familia_evento": "FINANCEIRO",
    "tipo_evento": "Reapresentação",
    "severidade": "WARNING",
    "titulo": "DFP 2025 reapresentado",
    "explicacao": "Reclassificação de contas contábeis",
    "link_documento": null,
    "periodo_afetado": "2025"
  },
  {
    "data_evento": "2026-03-10",
    "familia_evento": "VLMO",
    "tipo_evento": "Negociação de Insider",
    "severidade": "INFO",
    "titulo": "Diretor adquiriu 50.000 ações",
    "explicacao": "Compra de ações ordinárias por membro da diretoria",
    "link_documento": null,
    "periodo_afetado": null
  }
]
```

### Campos do Evento

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `data_evento` | date | Data da publicação/entrega |
| `familia_evento` | string | Família de origem: `IPE`, `FRE`, `VLMO`, `CGVN`, `FCA`, `FINANCEIRO` |
| `tipo_evento` | string | Tipo específico (ex: Fato Relevante, Reapresentação) |
| `severidade` | string | `INFO`, `WARNING`, `CRITICAL` |
| `titulo` | string | Título do evento |
| `explicacao` | string | Descrição resumida |
| `link_documento` | string \| null | Link para download do documento |
| `periodo_afetado` | string \| null | Período correspondente (ex: 2024, 2024-3T) |

---

## `GET /companhias/{codigo_cvm}/analise/pessoas-remuneracao`

Retorna **estatísticas anuais de remuneração** de órgãos, número de membros e diversidade de gênero.

### Exemplo

```bash
curl -X GET "http://localhost:8007/companhias/25224/analise/pessoas-remuneracao" \
  -H "Authorization: Bearer <token>"
```

### Response 200

**Schema:** `PessoasRemuneracaoResposta`

```json
{
  "cnpj_companhia": "08773135000100",
  "codigo_cvm": 25224,
  "dados": [
    {
      "ano": 2024,
      "total_remuneracao_conselho": 2500000.0,
      "membros_conselho": 7,
      "remuneracao_media_conselho": 357142.86,
      "total_remuneracao_diretoria": 8000000.0,
      "membros_diretoria": 5,
      "remuneracao_media_diretoria": 1600000.0,
      "yoy_remuneracao_total": 12.5,
      "proporcao_feminino_conselho": 0.286,
      "proporcao_feminino_diretoria": 0.2,
      "relacoes_familiares_total": 2
    },
    {
      "ano": 2023,
      "total_remuneracao_conselho": 2200000.0,
      "membros_conselho": 6,
      "remuneracao_media_conselho": 366666.67,
      "total_remuneracao_diretoria": 7200000.0,
      "membros_diretoria": 5,
      "remuneracao_media_diretoria": 1440000.0,
      "yoy_remuneracao_total": 8.3,
      "proporcao_feminino_conselho": 0.167,
      "proporcao_feminino_diretoria": 0.2,
      "relacoes_familiares_total": 1
    }
  ]
}
```

### Campos por Ano

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `ano` | integer | Ano de referência |
| `total_remuneracao_conselho` | number | Remuneração anual total do Conselho |
| `membros_conselho` | integer | Quantidade de membros no Conselho |
| `remuneracao_media_conselho` | number | Remuneração média por membro |
| `total_remuneracao_diretoria` | number | Remuneração anual total da Diretoria |
| `membros_diretoria` | integer | Quantidade de membros na Diretoria |
| `remuneracao_media_diretoria` | number | Remuneração média por membro |
| `yoy_remuneracao_total` | number | Variação YoY da remuneração total |
| `proporcao_feminino_conselho` | number | Proporção de mulheres no Conselho |
| `proporcao_feminino_diretoria` | number | Proporção de mulheres na Diretoria |
| `relacoes_familiares_total` | integer | Quantidade de relações familiares reportadas |

---

## `GET /companhias/{codigo_cvm}/analise/mercado-insiders`

Retorna **movimentações de insiders**, ações em tesouraria, alterações de capital social e governança.

### Exemplo

```bash
curl -X GET "http://localhost:8007/companhias/25224/analise/mercado-insiders" \
  -H "Authorization: Bearer <token>"
```

### Response 200

**Schema:** `MercadoInsidersResposta`

```json
{
  "cnpj_companhia": "08773135000100",
  "codigo_cvm": 25224,
  "movimentacoes": [
    {
      "ano_mes": "2026-05",
      "total_compras": 1500000.0,
      "total_vendas": 800000.0,
      "volume_liquido": 700000.0,
      "quantidade_operacoes": 12
    }
  ],
  "concentracao_cargo": {
    "Diretor": 0.45,
    "Conselheiro": 0.35,
    "Acionista Controlador": 0.20
  },
  "tesouraria": [
    {
      "data": "2026-05-31",
      "quantidade_acoes": 5000000,
      "percentual_capital": 0.5
    }
  ],
  "capital_alteracoes": [
    {
      "data": "2026-04-15",
      "tipo": "Aumento",
      "valor": 100000000.0,
      "descricao": "Aumento de capital por subscrição pública"
    }
  ],
  "governanca_resumo": {
    "Adotada": 45,
    "Nao Adotada": 12,
    "Parcialmente": 8,
    "Nao se Aplica": 5
  }
}
```

---

## `GET /companhias/{codigo_cvm}/analise`

**Endpoint estratégico** que retorna **todos os blocos de análise consolidados** em um único payload estruturado.

### Query Parameters

| Parâmetro | Tipo | Padrão | Descrição |
|-----------|------|--------|-----------|
| `horizonte` | string | `5a` | Horizonte temporal: `5a`, `10a`, `todos` |
| `periodicidade` | string | `anual` | Periodicidade: `anual`, `trimestral`, `todos` |
| `ano_base` | integer | `2025` | Ano base para comparação |
| `ano_comparacao` | integer | `2024` | Ano de comparação |

### Exemplo

```bash
curl -X GET "http://localhost:8007/companhias/25224/analise?horizonte=5a&ano_base=2024&ano_comparacao=2023" \
  -H "Authorization: Bearer <token>"
```

### Response 200

**Schema:** `AnaliseConsolidadaResposta`

```json
{
  "companhia": {
    "cnpj_companhia": "08773135000100",
    "codigo_cvm": 25224,
    "denominacao_social": "2W ECOBANK S.A."
  },
  "periodos_disponiveis": {
    "DFP": ["2024-12-31", "2023-12-31"],
    "ITR": ["2024-09-30"]
  },
  "cobertura": {
    "2024": ["DFP", "FRE", "FCA", "IPE"],
    "2023": ["DFP", "ITR", "FRE", "FCA", "IPE"]
  },
  "financeiro": [
    {
      "periodo_label": "2024",
      "ano": 2024,
      "trimestre": 0,
      "periodo_tipo": "ANUAL",
      "metrics": { "..." }
    }
  ],
  "eventos": [
    { "..." }
  ],
  "governanca": {
    "praticas_adotadas": 45,
    "praticas_nao_adotadas": 12,
    "score_governanca": 78.9
  },
  "pessoas_remuneracao": [
    { "..." }
  ],
  "mercado_insiders": {
    "movimentacoes": [...],
    "concentracao_cargo": {...},
    "tesouraria": [...],
    "capital_alteracoes": [...],
    "governanca_resumo": {...}
  },
  "proveniencia": {
    "fontes_utilizadas": ["DFP", "ITR", "FRE", "FCA", "IPE", "VLMO", "CGVN"],
    "ultima_atualizacao": "2026-06-15T08:00:00Z"
  }
}
```

---

## Casos de Uso

### Caso 1: Dashboard Executivo

Use o endpoint consolidado para obter todos os dados em uma única chamada:

```bash
GET /companhias/{codigo_cvm}/analise?horizonte=5a
```

### Caso 2: Análise de Governança

Combine `pessoas-remuneracao` com `mercado-insiders` para avaliar qualidade da gestão:

```bash
GET /companhias/25224/analise/pessoas-remuneracao
GET /companhias/25224/analise/mercado-insiders
```

### Caso 3: Monitoramento de Eventos

Use `eventos` para criar alertas em tempo real:

```python
import httpx

def verificar_eventos_criticos(codigo_cvm, token):
    response = httpx.get(
        f"http://localhost:8007/companhias/{codigo_cvm}/analise/eventos",
        headers={"Authorization": f"Bearer {token}"}
    )
    eventos = response.json()
    
    criticos = [e for e in eventos if e["severidade"] == "CRITICAL"]
    if criticos:
        print(f"⚠️ {len(criticos)} eventos críticos encontrados!")
        for evento in criticos:
            print(f"  - {evento['titulo']} ({evento['data_evento']})")
```

### Caso 4: Comparação Anual

Use `comparativo` para análises YoY:

```bash
GET /companhias/25224/analise/comparativo?ano_base=2024&ano_comparacao=2023
```

---

## Notas para Usuários

### Para Analistas Financeiros
- Use `financeiro` para séries históricas com cálculos automáticos de YoY/CAGR
- Use `comparativo` para análises rápidas entre dois exercícios
- A proveniência permite rastrear cada métrica até o documento original

### Para Auditores
- Use `overview` para verificar cobertura e frescor dos dados
- Use `eventos` para identificar reapresentações e atrasos
- Os alertas ajudam a priorizar áreas de risco

### Para Compliance
- Use `mercado-insiders` para monitorar negociações de insiders
- Use `pessoas-remuneracao` para avaliar conformidade com políticas de remuneração
- Use `eventos` para rastrear fatos relevantes e comunicados obrigatórios

### Para Operadores de Backoffice
- Use o endpoint consolidado (`/analise`) para dashboards executivos
- Use `overview` para verificar status de sincronização
- Os alertas indicam problemas operacionais que precisam de atenção

---

## Próximos Passos

- [Financeiro](./financeiro.md) - Endpoints detalhados de DFP/ITR
- [FRE](./fre.md) - Endpoints do Formulário de Referência
- [Ingestion](../ingestion/monitoring.md) - Monitoramento de sincronizações