---
title: Schemas Financeiros (DFP/ITR)
sidebar_position: 4
---

# Schemas Financeiros (DFP/ITR)

## `DocumentoFinanceiroResposta`

Cabeçalho documental de DFP/ITR.

### Schema

```python
class DocumentoFinanceiroResposta(BaseModel):
    id: UUID
    companhia_id: Optional[UUID]
    tipo_formulario: str  # "DFP" ou "ITR"
    cnpj_companhia: str
    codigo_cvm: Optional[int]
    data_referencia: date
    versao: int
    denominacao_companhia: Optional[str]
    categoria_documento: Optional[str]
    id_documento: int
    data_recebimento: Optional[date]
    link_documento: Optional[str]
    arquivo_origem: str
    ano_origem: Optional[int]
    linha_origem: Optional[int]
    criado_em: datetime
    sincronizado_em: datetime
    alterado_em: datetime
```

### Exemplo JSON

```json
{
  "id": "bbf228f5-5627-4fc5-a490-318b8ba31e43",
  "companhia_id": "f4f6a9d8-7e26-45f2-b3fb-ec43a0f8a89a",
  "tipo_formulario": "DFP",
  "cnpj_companhia": "08773135000100",
  "codigo_cvm": 25224,
  "data_referencia": "2025-12-31",
  "versao": 1,
  "denominacao_companhia": "EMPRESA A",
  "categoria_documento": "DFP",
  "id_documento": 123,
  "data_recebimento": "2026-01-01",
  "link_documento": "http://exemplo",
  "arquivo_origem": "dfp_cia_aberta_2025.csv",
  "ano_origem": 2025,
  "linha_origem": 2,
  "criado_em": "2026-05-30T14:30:00Z",
  "sincronizado_em": "2026-05-30T14:30:00Z",
  "alterado_em": "2026-05-30T14:30:00Z"
}
```

---

## `DemonstracaoFinanceiraResposta`

Linhas contábeis de DFP/ITR (BPA, BPP, DRE, DFC, DMPL, DRA, DVA).

### Schema

```python
class DemonstracaoFinanceiraResposta(BaseModel):
    companhia_id: Optional[UUID]
    tipo_formulario: str  # "DFP" ou "ITR"
    tipo_demonstracao: str  # "balanco_patrimonial_ativo", "demonstracao_resultado", etc.
    escopo_demonstracao: str  # "consolidado" ou "individual"
    cnpj_companhia: str
    codigo_cvm: Optional[int]
    data_referencia: date
    versao: int
    denominacao_companhia: Optional[str]
    grupo_demonstracao: Optional[str]
    moeda: Optional[str]
    escala_moeda: Optional[str]  # "UNIDADE", "MIL", "MILHAO"
    fator_escala_moeda: int  # 1, 1000, 1000000
    ordem_exercicio: Optional[str]  # "ÚLTIMO", "PENÚLTIMO", etc.
    data_inicio_exercicio: Optional[date]
    data_fim_exercicio: Optional[date]
    codigo_conta: Optional[str]
    coluna_df: str  # Eixo COLUNA_DF (vazio quando não aplicável)
    descricao_conta: Optional[str]
    valor_conta: Optional[float]  # Valor ajustado por escala
    valor_conta_reportado: Optional[float]  # Valor bruto da CVM
    conta_fixa: Optional[bool]
    arquivo_origem: str
    ano_origem: Optional[int]
    linha_origem: Optional[int]
    criado_em: datetime
    sincronizado_em: datetime
    alterado_em: datetime
```

### Exemplo JSON

```json
{
  "id": "bbf228f5-5627-4fc5-a490-318b8ba31e43",
  "companhia_id": "f4f6a9d8-7e26-45f2-b3fb-ec43a0f8a89a",
  "tipo_formulario": "DFP",
  "tipo_demonstracao": "demonstracao_resultado",
  "escopo_demonstracao": "individual",
  "cnpj_companhia": "00000000000191",
  "codigo_cvm": 1023,
  "data_referencia": "2025-12-31",
  "versao": 1,
  "denominacao_companhia": "BCO BRASIL S.A.",
  "grupo_demonstracao": "DF Individual - Demonstração do Resultado",
  "moeda": "REAL",
  "escala_moeda": "MIL",
  "fator_escala_moeda": 1000,
  "ordem_exercicio": "ÚLTIMO",
  "data_inicio_exercicio": "2025-01-01",
  "data_fim_exercicio": "2025-12-31",
  "codigo_conta": "3.03",
  "coluna_df": "",
  "descricao_conta": "Receita Líquida",
  "valor_conta": 740500000.0,
  "valor_conta_reportado": 740500.0,
  "conta_fixa": true,
  "arquivo_origem": "dfp_cia_aberta_DRE_ind_2025.csv",
  "ano_origem": 2025,
  "linha_origem": 2960,
  "criado_em": "2026-05-30T14:30:00Z",
  "sincronizado_em": "2026-05-30T14:30:00Z",
  "alterado_em": "2026-05-30T14:30:00Z"
}
```

### Campos de Valores Monetários

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `valor_conta` | float \| null | **Valor absoluto em reais** (ajustado por escala) |
| `valor_conta_reportado` | float \| null | Valor bruto como reportado pela CVM |
| `escala_moeda` | string \| null | `UNIDADE`, `MIL` ou `MILHAO` |
| `fator_escala_moeda` | integer | Multiplicador: 1, 1000 ou 1000000 |

**Fórmula:** `valor_conta = valor_conta_reportado × fator_escala_moeda`

### Tipos de Demonstração

| `tipo_demonstracao` | Descrição |
|---------------------|-----------|
| `balanco_patrimonial_ativo` | Balanço Patrimonial - Ativo |
| `balanco_patrimonial_passivo` | Balanço Patrimonial - Passivo |
| `demonstracao_resultado` | Demonstração do Resultado |
| `fluxo_caixa_metodo_direto` | Fluxo de Caixa - Método Direto |
| `fluxo_caixa_metodo_indireto` | Fluxo de Caixa - Método Indireto |
| `mutacoes_patrimonio_liquido` | Mutações do Patrimônio Líquido |
| `resultado_abrangente` | Resultado Abrangente |
| `valor_adicionado` | Valor Adicionado |

---

## `ComposicaoCapitalResposta`

Composição do capital social extraída de DFP/ITR.

### Schema

```python
class ComposicaoCapitalResposta(BaseModel):
    id: UUID
    companhia_id: Optional[UUID]
    tipo_formulario: str
    cnpj_companhia: str
    codigo_cvm: Optional[int]
    data_referencia: date
    versao: int
    denominacao_companhia: Optional[str]
    quantidade_acoes_ordinarias_capital_integralizado: Optional[str]
    quantidade_acoes_preferenciais_capital_integralizado: Optional[str]
    quantidade_total_acoes_capital_integralizado: Optional[str]
    quantidade_acoes_ordinarias_tesouraria: Optional[str]
    quantidade_acoes_preferenciais_tesouraria: Optional[str]
    quantidade_total_acoes_tesouraria: Optional[str]
    arquivo_origem: str
    ano_origem: Optional[int]
    linha_origem: Optional[int]
    criado_em: datetime
    sincronizado_em: datetime
    alterado_em: datetime
```

### Exemplo JSON

```json
{
  "id": "...",
  "tipo_formulario": "DFP",
  "cnpj_companhia": "08773135000100",
  "codigo_cvm": 25224,
  "data_referencia": "2025-12-31",
  "versao": 1,
  "denominacao_companhia": "EMPRESA A",
  "quantidade_acoes_ordinarias_capital_integralizado": "500000000",
  "quantidade_acoes_preferenciais_capital_integralizado": "300000000",
  "quantidade_total_acoes_capital_integralizado": "800000000",
  "quantidade_acoes_ordinarias_tesouraria": "10000000",
  "quantidade_acoes_preferenciais_tesouraria": "5000000",
  "quantidade_total_acoes_tesouraria": "15000000",
  "arquivo_origem": "dfp_cia_aberta_composicao_capital_2025.csv",
  "ano_origem": 2025,
  "linha_origem": 100
}
```

---

## `ParecerFinanceiroResposta`

Pareceres e declarações dos auditores.

### Schema

```python
class ParecerFinanceiroResposta(BaseModel):
    companhia_id: Optional[UUID]
    tipo_formulario: str
    cnpj_companhia: str
    codigo_cvm: Optional[int]
    data_referencia: date
    versao: int
    denominacao_companhia: Optional[str]
    tipo_relatorio_auditor: Optional[str]
    tipo_parecer_declaracao: Optional[str]
    numero_item_parecer_declaracao: Optional[str]
    texto_parecer_declaracao: Optional[str]
    arquivo_origem: str
    ano_origem: Optional[int]
    linha_origem: Optional[int]
    criado_em: datetime
    sincronizado_em: datetime
    alterado_em: datetime
```

### Exemplo JSON

```json
{
  "id": "...",
  "tipo_formulario": "DFP",
  "cnpj_companhia": "08773135000100",
  "codigo_cvm": 25224,
  "data_referencia": "2025-12-31",
  "versao": 1,
  "denominacao_companhia": "EMPRESA A",
  "tipo_relatorio_auditor": "OPINIAO_SEM_RESSALVAS",
  "tipo_parecer_declaracao": "PARECER",
  "numero_item_parecer_declaracao": "1",
  "texto_parecer_declaracao": "Os exames que procedemos...",
  "arquivo_origem": "dfp_cia_aberta_parecer_2025.csv",
  "ano_origem": 2025,
  "linha_origem": 10
}
```

---

## Schemas de Lista

### `ListaDocumentosFinanceirosResposta`

```python
class ListaDocumentosFinanceirosResposta(BaseModel):
    dados: List[DocumentoFinanceiroResposta]
    paginacao: Paginacao
```

### `ListaDemonstracoesFinanceirasResposta`

```python
class ListaDemonstracoesFinanceirasResposta(BaseModel):
    dados: List[DemonstracaoFinanceiraResposta]
    paginacao: Paginacao
```

### `ListaComposicoesCapitalResposta`

```python
class ListaComposicoesCapitalResposta(BaseModel):
    dados: List[ComposicaoCapitalResposta]
    paginacao: Paginacao
```

### `ListaPareceresFinanceirosResposta`

```python
class ListaPareceresFinanceirosResposta(BaseModel):
    dados: List[ParecerFinanceiroResposta]
    paginacao: Paginacao
```

---

## Filtros Comuns

### Documentos (DFP/ITR)

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `cnpj_companhia` | string | CNPJ com ou sem pontuação |
| `codigo_cvm` | integer | Código CVM |
| `data_referencia_inicio` | date | Data inicial (YYYY-MM-DD) |
| `data_referencia_fim` | date | Data final (YYYY-MM-DD) |
| `ano_origem` | integer | Ano do ZIP de origem |
| `ano_inicio` | integer | Ano inicial do intervalo |
| `ano_fim` | integer | Ano final do intervalo |
| `versao` | integer | Versão específica |
| `id_documento` | integer | ID do documento CVM |
| `ordenar_por` | string | Campo de ordenação (prefixe com `-` para desc.) |
| `pagina` | integer | Número da página (padrão: 1) |
| `tamanho_pagina` | integer | Itens por página (padrão: 100, máx: 500) |

### Demonstrações Financeiras

Mesmos filtros de documentos, mais:

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `codigo_conta` | string | Código da conta contábil (ex: `3.01`) |

### Ordenação Permitida

**Documentos:**
- `data_referencia`
- `versao`
- `cnpj_companhia`
- `codigo_cvm`
- `data_recebimento`
- `id_documento`

**Demonstrações:**
- `data_referencia`
- `versao`
- `cnpj_companhia`
- `codigo_conta`
- `valor_conta` (considera valor ajustado por escala)

**Composição de Capital / Pareceres:**
- `data_referencia`
- `versao`
- `cnpj_companhia`