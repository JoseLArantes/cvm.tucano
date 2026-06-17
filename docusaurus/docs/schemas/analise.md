---
title: Schemas de Análise Estratégica
sidebar_position: 5
---

# Schemas de Análise Estratégica

## `OverviewAnaliseResposta`

Visão geral da companhia: cobertura, frescor e alertas.

### Schema

```python
class OverviewAnaliseResposta(BaseModel):
    cnpj_companhia: str
    codigo_cvm: int
    denominacao_social: str
    situacao_registro: str
    status_ativo: bool
    data_freshness: Optional[datetime]
    cobertura: Dict[str, List[str]]
    periodos_disponiveis: Dict[str, List[str]]
    alertas: List[AlertaOverview]
    anos_comparacao_disponiveis: List[int]
```

### Exemplo JSON

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
    "2023": ["DFP", "ITR", "FRE", "FCA", "IPE"]
  },
  "periodos_disponiveis": {
    "DFP": ["2024-12-31", "2023-12-31"],
    "ITR": ["2024-09-30", "2024-06-30"]
  },
  "alertas": [
    {
      "tipo": "SITUACAO_REGISTRO",
      "descricao": "Companhia com registro suspenso",
      "severidade": "WARNING"
    }
  ],
  "anos_comparacao_disponiveis": [2024, 2023, 2022]
}
```

---

## `AlertaOverview`

Schema de alerta individual.

### Schema

```python
class AlertaOverview(BaseModel):
    tipo: str = Field(description="Tipo do alerta (ex: SITUACAO_REGISTRO, ATRASO_FILING)")
    descricao: str = Field(description="Descrição amigável do alerta")
    severidade: str = Field(description="Nível de severidade: INFO, WARNING, CRITICAL")
```

### Tipos de Alerta

| Tipo | Descrição | Severidade Típica |
|------|-----------|-------------------|
| `SITUACAO_REGISTRO` | Problema com registro na CVM | WARNING/CRITICAL |
| `ATRASO_FILING` | Entrega após prazo regulatório | INFO/WARNING |
| `REAPRESENTACAO` | Documento reapresentado | INFO |
| `AUDITOR_RESSALVA` | Parecer com ressalvas | WARNING |

---

## `FinanceiroAnaliseResposta`

Métricas financeiras com cálculos YoY/QoQ/CAGR e proveniência.

### Schema

```python
class FinanceiroAnaliseResposta(BaseModel):
    cnpj_companhia: str
    codigo_cvm: int
    dados: List[PeriodoFinanceiro]
```

### `PeriodoFinanceiro`

```python
class PeriodoFinanceiro(BaseModel):
    periodo_label: str  # "2024" ou "2024-3T"
    ano: int
    trimestre: int  # 0 para anual, 1-4 para trimestral
    periodo_tipo: str  # "ANUAL" ou "TRIMESTRAL"
    metrics: Dict[str, MetricaFinanceira]
```

### `MetricaFinanceira`

```python
class MetricaFinanceira(BaseModel):
    valor_normalizado: Optional[float]  # Valor absoluto em reais
    valor_original: Optional[str]  # Valor como reportado
    yoy: Optional[float]  # Variação ano contra ano (%)
    qoq: Optional[float]  # Variação trimestre contra trimestre (%)
    cagr: Optional[float]  # Taxa de crescimento anual composta (%)
    proveniencia: Optional[ReferenciaProveniencia]
```

### `ReferenciaProveniencia`

```python
class ReferenciaProveniencia(BaseModel):
    fonte: str = Field(default="CVM")
    dataset: str
    documento_id: Optional[int]
    linha_id: Optional[str]  # UUID da linha original
    data_referencia: Optional[date]
    data_entrega: Optional[date]
    link_download: Optional[str]
```

### Exemplo JSON

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
          "cagr": 6.5
        }
      }
    }
  ]
}
```

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

---

## `ComparativoAnaliseResposta`

Comparação entre dois anos específicos.

### Schema

```python
class ComparativoAnaliseResposta(BaseModel):
    ano_base: int
    ano_comparacao: int
    financeiro: Dict[str, DeltaComparativo]
    capital: Dict[str, DeltaComparativo]
    governanca: Dict[str, DeltaComparativo]
    pessoas: Dict[str, DeltaComparativo]
    mercado: Dict[str, DeltaComparativo]
    eventos_ipe: Optional[DeltaComparativo]
```

### `DeltaComparativo`

```python
class DeltaComparativo(BaseModel):
    valor_base: Optional[float]
    valor_comparacao: Optional[float]
    delta_absoluto: Optional[float]  # Base - Comparação
    delta_percentual: Optional[float]
```

### Exemplo JSON

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
    }
  },
  "capital": {
    "quantidade_total_acoes": {
      "valor_base": 1000000000,
      "valor_comparacao": 1000000000,
      "delta_absoluto": 0,
      "delta_percentual": 0.0
    }
  }
}
```

---

## `EventoLinhaTempo`

Evento na timeline unificada.

### Schema

```python
class EventoLinhaTempo(BaseModel):
    data_evento: date
    familia_evento: str  # IPE, FRE, VLMO, CGVN, FCA, FINANCEIRO
    tipo_evento: str
    severidade: str  # INFO, WARNING, CRITICAL
    titulo: str
    explicacao: str
    link_documento: Optional[str]
    periodo_afetado: Optional[str]  # "2024" ou "2024-3T"
```

### Exemplo JSON

```json
{
  "data_evento": "2026-05-15",
  "familia_evento": "IPE",
  "tipo_evento": "Fato Relevante",
  "severidade": "INFO",
  "titulo": "Resultado do 1T26",
  "explicacao": "Divulgação dos resultados do primeiro trimestre de 2026",
  "link_documento": "https://dados.cvm.gov.br/...",
  "periodo_afetado": "2026-1T"
}
```

---

## `PessoasRemuneracaoResposta`

Estatísticas anuais de remuneração e diversidade.

### Schema

```python
class PessoasRemuneracaoResposta(BaseModel):
    cnpj_companhia: str
    codigo_cvm: int
    dados: List[PessoasRemuneracaoAno]
```

### `PessoasRemuneracaoAno`

```python
class PessoasRemuneracaoAno(BaseModel):
    ano: int
    total_remuneracao_conselho: Optional[float]
    membros_conselho: Optional[int]
    remuneracao_media_conselho: Optional[float]
    total_remuneracao_diretoria: Optional[float]
    membros_diretoria: Optional[int]
    remuneracao_media_diretoria: Optional[float]
    yoy_remuneracao_total: Optional[float]
    proporcao_feminino_conselho: Optional[float]
    proporcao_feminino_diretoria: Optional[float]
    relacoes_familiares_total: int = 0
```

### Exemplo JSON

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
    }
  ]
}
```

---

## `MercadoInsidersResposta`

Movimentações de insiders, tesouraria e governança.

### Schema

```python
class MercadoInsidersResposta(BaseModel):
    cnpj_companhia: str
    codigo_cvm: int
    movimentacoes: List[Dict[str, Any]]
    concentracao_cargo: Dict[str, float]
    tesouraria: List[Dict[str, Any]]
    capital_alteracoes: List[Dict[str, Any]]
    governanca_resumo: Dict[str, int]
```

### Exemplo JSON

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

## `AnaliseConsolidadaResposta`

Endpoint estratégico que agrega todos os blocos de análise.

### Schema

```python
class AnaliseConsolidadaResposta(BaseModel):
    companhia: Dict[str, Any]
    periodos_disponiveis: Dict[str, List[str]]
    cobertura: Dict[str, List[str]]
    financeiro: List[PeriodoFinanceiro]
    eventos: List[EventoLinhaTempo]
    governanca: Dict[str, Any]
    pessoas_remuneracao: List[PessoasRemuneracaoAno]
    mercado_insiders: Dict[str, Any]
    proveniencia: Dict[str, Any]
```

### Exemplo de Uso

```bash
GET /companhias/{codigo_cvm}/analise?horizonte=5a&ano_base=2024&ano_comparacao=2023
```

### Parâmetros

| Parâmetro | Tipo | Padrão | Descrição |
|-----------|------|--------|-----------|
| `horizonte` | string | `5a` | Horizonte temporal: `5a`, `10a`, `todos` |
| `periodicidade` | string | `anual` | Periodicidade: `anual`, `trimestral`, `todos` |
| `ano_base` | integer | `2025` | Ano base para comparação |
| `ano_comparacao` | integer | `2024` | Ano de comparação |