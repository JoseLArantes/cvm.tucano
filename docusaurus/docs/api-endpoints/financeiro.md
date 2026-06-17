---
title: Dados Financeiros (DFP/ITR)
sidebar_position: 8
---

# Dados Financeiros (DFP/ITR)

## Visão Geral

Os endpoints de dados financeiros cobrem as **Demonstrações Financeiras Padronizadas (DFP)** e as **Informações Trimestrais (ITR)**. Eles compartilham estrutura idêntica, diferenciando-se apenas pelo prefixo da rota (`/dfp/` vs `/itr/`).

## Endpoints Disponíveis

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/dfp/documentos` | Listar documentos DFP |
| `GET` | `/itr/documentos` | Listar documentos ITR |
| `GET` | `/dfp/composicao-capital` | Composição de capital DFP |
| `GET` | `/itr/composicao-capital` | Composição de capital ITR |
| `GET` | `/dfp/pareceres` | Pareceres DFP |
| `GET` | `/itr/pareceres` | Pareceres ITR |
| `GET` | `/dfp/balanco-patrimonial-ativo/{escopo}` | BPA (consolidado/individual) |
| `GET` | `/dfp/balanco-patrimonial-passivo/{escopo}` | BPP (consolidado/individual) |
| `GET` | `/dfp/demonstracao-resultado/{escopo}` | DRE (consolidado/individual) |
| `GET` | `/dfp/fluxo-caixa-metodo-direto/{escopo}` | DFC Direto (consolidado/individual) |
| `GET` | `/dfp/fluxo-caixa-metodo-indireto/{escopo}` | DFC Indireto (consolidado/individual) |
| `GET` | `/dfp/mutacoes-patrimonio-liquido/{escopo}` | DMPL (consolidado/individual) |
| `GET` | `/dfp/resultado-abrangente/{escopo}` | DRA (consolidado/individual) |
| `GET` | `/dfp/valor-adicionado/{escopo}` | DVA (consolidado/individual) |
| `GET` | `/itr/balanco-patrimonial-ativo/{escopo}` | BPA ITR |
| `GET` | `/itr/balanco-patrimonial-passivo/{escopo}` | BPP ITR |
| `GET` | `/itr/demonstracao-resultado/{escopo}` | DRE ITR |
| `GET` | `/itr/fluxo-caixa-metodo-direto/{escopo}` | DFC Direto ITR |
| `GET` | `/itr/fluxo-caixa-metodo-indireto/{escopo}` | DFC Indireto ITR |
| `GET` | `/itr/mutacoes-patrimonio-liquido/{escopo}` | DMPL ITR |
| `GET` | `/itr/resultado-abrangente/{escopo}` | DRA ITR |
| `GET` | `/itr/valor-adicionado/{escopo}` | DVA ITR |

> **Escopo:** todas as demonstrações aceitam `consolidado` ou `individual` como path parameter.

---

## Filtros Comuns

Todos os endpoints financeiros aceitam os seguintes filtros:

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `cnpj_companhia` | string | CNPJ com ou sem pontuação |
| `codigo_cvm` | integer | Código CVM da companhia |
| `data_referencia_inicio` | date | Data inicial (YYYY-MM-DD) |
| `data_referencia_fim` | date | Data final (YYYY-MM-DD) |
| `ano_origem` | integer | Ano do ZIP de origem |
| `ano_inicio` | integer | Ano inicial do intervalo |
| `ano_fim` | integer | Ano final do intervalo |
| `versao` | integer | Versão específica do formulário |
| `pagina` | integer | Número da página (padrão: 1) |
| `tamanho_pagina` | integer | Itens por página (padrão: 100, máx: 500) |

---

## `GET /dfp/documentos` e `GET /itr/documentos`

Retorna os documentos principais (cabeçalhos) de DFP ou ITR.

### Exemplo

```bash
curl -X GET "http://localhost:8007/dfp/documentos?codigo_cvm=25224&ano_inicio=2024&ordenar_por=-data_referencia" \
  -H "Authorization: Bearer <token>"
```

### Response 200

**Schema:** `ListaDocumentosFinanceirosResposta`

```json
{
  "dados": [
    {
      "id": "bbf228f5-5627-4fc5-a490-318b8ba31e43",
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
  ],
  "paginacao": {
    "pagina": 1,
    "tamanho_pagina": 100,
    "total": 1
  }
}
```

### Ordenação

| Campo | Descrição |
|-------|-----------|
| `data_referencia` | Data de referência |
| `versao` | Versão do formulário |
| `cnpj_companhia` | CNPJ |
| `codigo_cvm` | Código CVM |
| `data_recebimento` | Data de recebimento |
| `id_documento` | ID do documento |

Prefixe com `-` para ordem decrescente (ex: `-data_referencia`).

---

## Demonstracoes Financeiras (BPA, BPP, DRE, DFC, etc.)

### Endpoints de Demonstração

| Demonstração | Rota DFP | Rota ITR |
|--------------|----------|----------|
| Balanço Patrimonial Ativo | `/dfp/balanco-patrimonial-ativo/{escopo}` | `/itr/balanco-patrimonial-ativo/{escopo}` |
| Balanço Patrimonial Passivo | `/dfp/balanco-patrimonial-passivo/{escopo}` | `/itr/balanco-patrimonial-passivo/{escopo}` |
| Demonstração do Resultado | `/dfp/demonstracao-resultado/{escopo}` | `/itr/demonstracao-resultado/{escopo}` |
| Fluxo de Caixa (Método Direto) | `/dfp/fluxo-caixa-metodo-direto/{escopo}` | `/itr/fluxo-caixa-metodo-direto/{escopo}` |
| Fluxo de Caixa (Método Indireto) | `/dfp/fluxo-caixa-metodo-indireto/{escopo}` | `/itr/fluxo-caixa-metodo-indireto/{escopo}` |
| Mutações do Patrimônio Líquido | `/dfp/mutacoes-patrimonio-liquido/{escopo}` | `/itr/mutacoes-patrimonio-liquido/{escopo}` |
| Resultado Abrangente | `/dfp/resultado-abrangente/{escopo}` | `/itr/resultado-abrangente/{escopo}` |
| Valor Adicionado | `/dfp/valor-adicionado/{escopo}` | `/itr/valor-adicionado/{escopo}` |

> **`{escopo}`:** `consolidado` ou `individual`

### Exemplo: Balanço Patrimonial Ativo Consolidado

```bash
curl -X GET "http://localhost:8007/dfp/balanco-patrimonial-ativo/consolidado?codigo_cvm=25224&ano_inicio=2024" \
  -H "Authorization: Bearer <token>"
```

### Response 200

**Schema:** `ListaDemonstracoesFinanceirasResposta`

```json
{
  "dados": [
    {
      "id": "bbf228f5-5627-4fc5-a490-318b8ba31e43",
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
  ],
  "paginacao": {
    "pagina": 1,
    "tamanho_pagina": 100,
    "total": 1
  }
}
```

### Campos de Valores Monetários

| Campo | Descrição |
|-------|-----------|
| `valor_conta` | **Valor absoluto em reais** (já ajustado pela escala) |
| `valor_conta_reportado` | Valor bruto como reportado pela CVM |
| `escala_moeda` | `UNIDADE`, `MIL` ou `MILHAO` |
| `fator_escala_moeda` | Multiplicador: 1, 1000 ou 1000000 |

**Fórmula:** `valor_conta = valor_conta_reportado × fator_escala_moeda`

### Filtros Adicionais

| Parâmetro | Tipo | Descrição |
|-----------|------|-----------|
| `codigo_conta` | string | Código da conta contábil (ex: `3.01`) |

### Ordenação

| Campo | Descrição |
|-------|-----------|
| `data_referencia` | Data de referência |
| `versao` | Versão |
| `cnpj_companhia` | CNPJ |
| `codigo_conta` | Código da conta |
| `valor_conta` | Valor monetário (já ajustado por escala) |

---

## `GET /dfp/composicao-capital` e `GET /itr/composicao-capital`

Retorna dados de composição do capital extraídos de DFP/ITR.

### Exemplo

```bash
curl -X GET "http://localhost:8007/dfp/composicao-capital?codigo_cvm=25224&ano_inicio=2024" \
  -H "Authorization: Bearer <token>"
```

### Response 200

**Schema:** `ListaComposicoesCapitalResposta`

```json
{
  "dados": [
    {
      "id": "...",
      "tipo_formulario": "DFP",
      "cnpj_companhia": "08773135000100",
      "codigo_cvm": 25224,
      "data_referencia": "2025-12-31",
      "versao": 1,
      "denominacao_companhia": "EMPRESA A",
      "quantidade_acoes_ordinarias_capital_integralizado": 500000000,
      "quantidade_acoes_preferenciais_capital_integralizado": 300000000,
      "quantidade_total_acoes_capital_integralizado": 800000000,
      "quantidade_acoes_ordinarias_tesouraria": 10000000,
      "quantidade_acoes_preferenciais_tesouraria": 5000000,
      "quantidade_total_acoes_tesouraria": 15000000,
      "arquivo_origem": "dfp_cia_aberta_composicao_capital_2025.csv",
      "ano_origem": 2025,
      "linha_origem": 100,
      "criado_em": "2026-05-30T14:30:00Z",
      "sincronizado_em": "2026-05-30T14:30:00Z",
      "alterado_em": "2026-05-30T14:30:00Z"
    }
  ],
  "paginacao": { "pagina": 1, "tamanho_pagina": 100, "total": 1 }
}
```

### Ordenação

| Campo | Descrição |
|-------|-----------|
| `data_referencia` | Data de referência |
| `versao` | Versão |
| `cnpj_companhia` | CNPJ |

---

## `GET /dfp/pareceres` e `GET /itr/pareceres`

Retorna pareceres e declarações dos auditores.

### Exemplo

```bash
curl -X GET "http://localhost:8007/dfp/pareceres?codigo_cvm=25224&ano_inicio=2024" \
  -H "Authorization: Bearer <token>"
```

### Response 200

**Schema:** `ListaPareceresFinanceirosResposta`

```json
{
  "dados": [
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
      "linha_origem": 10,
      "criado_em": "2026-05-30T14:30:00Z",
      "sincronizado_em": "2026-05-30T14:30:00Z",
      "alterado_em": "2026-05-30T14:30:00Z"
    }
  ],
  "paginacao": { "pagina": 1, "tamanho_pagina": 100, "total": 1 }
}
```

### Ordenação

| Campo | Descrição |
|-------|-----------|
| `data_referencia` | Data de referência |
| `versao` | Versão |
| `cnpj_companhia` | CNPJ |

---

## Casos de Uso

### Caso 1: Série Histórica de Receita Líquida (YoY)

```bash
GET /dfp/demonstracao-resultado/consolidado?codigo_cvm=25224&codigo_conta=3.03&ano_inicio=2020&ano_fim=2025
```

### Caso 2: Comparar BPA Consolidado vs Individual

```bash
# Consolidado
GET /dfp/balanco-patrimonial-ativo/consolidado?codigo_cvm=25224&ano_inicio=2024

# Individual
GET /dfp/balanco-patrimonial-ativo/individual?codigo_cvm=25224&ano_inicio=2024
```

### Caso 3: Última Versão de um DFP

```bash
GET /dfp/documentos?codigo_cvm=25224&data_referencia_inicio=2024-01-01&data_referencia_fim=2024-12-31&ordenar_por=-versao&tamanho_pagina=1
```

### Caso 4: Python - Exportar DRE em CSV

```python
import httpx

def exportar_dre(codigo_cvm, ano, token):
    response = httpx.get(
        "http://localhost:8007/exportacoes/dfp/dre_con",
        params={"codigo_cvm": codigo_cvm, "ano_inicio": ano, "formato": "csv"},
        headers={"Authorization": f"Bearer {token}"},
        timeout=300.0
    )
    response.raise_for_status()
    with open(f"dre_{codigo_cvm}_{ano}.csv", "wb") as f:
        f.write(response.content)
```

---

## Notas Importantes

### Para Analistas Financeiros

- **Sempre use `valor_conta`** (não `valor_conta_reportado`) para análises comparativas
- **Prefira `consolidado`** para análise fundamentalista de holdings
- **Filtre por `versao`** para obter apenas a versão mais recente de cada documento
- **Use `ano_inicio` e `ano_fim`** para séries históricas

### Para Auditores

- **`valor_conta_reportado`** preserva o valor bruto da CVM para auditoria
- **`arquivo_origem` + `linha_origem`** permitem rastrear a origem exata de cada linha
- **`hash_origem`** garante idempotência e rastreabilidade
- **`versao`** identifica reapresentações

### Para Operadores de Backoffice

- **Use `/exportacoes/{fonte}/{dataset}`** para extrações em lote (até 100.000 registros)
- **Prefira `formato=csv`** para integração com ferramentas de BI
- **Monitore `/ingestion/dashboard`** para verificar status das sincronizações

### Regras de Negócio

1. **Deduplicação por Versão**: A CVM permite reapresentações. Para obter a versão mais recente, filtre por `MAX(versao)` para cada `(cnpj_companhia, data_referencia)`
2. **Escala da Moeda**: Valores são normalizados automaticamente. `valor_conta` já está em reais absolutos
3. **Consolidado vs Individual**: Priorize `consolidado` para análise de holdings; `individual` reflete apenas a holding-mãe
4. **Reapresentações**: Registros DFP/ITR ingeridos antes da correção do parser de decimais foram reparados via replay

---

## Próximos Passos

- [FRE](./fre.md) - Formulário de Referência
- [FCA](./fca.md) - Formulário Cadastral
- [Ingestion](../ingestion/monitoring.md) - Monitoramento de sincronizações