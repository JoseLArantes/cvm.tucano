---
title: Demonstrações Financeiras Padronizadas (DFP)
sidebar_position: 3
---

# Demonstrações Financeiras Padronizadas (DFP)

## Visão Geral

Demonstrações financeiras anuais padronizadas, equivalentes às demonstrações contábeis auditadas exigidas pela Lei 6.404/76 e resoluções CVM.

## Metadados Técnicos

| Campo | Valor |
|-------|-------|
| **Fonte CVM** | `dfp` |
| **Arquivo ZIP** | `dfp_companhias_abertas_{ano}.zip` |
| **Periodicidade** | Anual (publicação) / Sincronização Semanal |
| **Desde** | 2010 |
| **Tabelas Alvo** | `documentos_financeiros`, `demonstracoes_financeiras`, `composicoes_capital`, `pareceres_financeiros` |
| **Chaves Naturais** | `(tipo_formulario, id_documento, versao, data_referencia)` |

## Estrutura de Arquivos

Cada ano gera múltiplos membros CSV:

```
dfp_cia_aberta_{ano}.csv              # Header documental
dfp_cia_aberta_BPA_con_{ano}.csv      # Balanço Patrimonial Ativo - Consolidado
dfp_cia_aberta_BPA_ind_{ano}.csv      # Balanço Patrimonial Ativo - Individual
dfp_cia_aberta_BPP_con_{ano}.csv      # Balanço Patrimonial Passivo - Consolidado
dfp_cia_aberta_BPP_ind_{ano}.csv      # Balanço Patrimonial Passivo - Individual
dfp_cia_aberta_DRE_con_{ano}.csv      # Demonstração do Resultado - Consolidado
dfp_cia_aberta_DRE_ind_{ano}.csv      # Demonstração do Resultado - Individual
dfp_cia_aberta_DFC_MI_con_{ano}.csv   # Fluxo de Caixa (Método Indireto) - Consolidado
dfp_cia_aberta_DFC_DI_con_{ano}.csv   # Fluxo de Caixa (Método Direto) - Consolidado
dfp_cia_aberta_DMPL_con_{ano}.csv     # Mutações do Patrimônio Líquido - Consolidado
dfp_cia_aberta_DRA_con_{ano}.csv      # Resultado Abrangente - Consolidado
dfp_cia_aberta_DVA_con_{ano}.csv      # Valor Adicionado - Consolidado
dfp_cia_aberta_composicao_capital_{ano}.csv
dfp_cia_aberta_parecer_{ano}.csv
```

## Mapeamento de Campos (Demonstrações)

| Campo CVM | Tabela | Campo | Observação |
|-----------|--------|-------|------------|
| `COD_CVM` | `demonstracoes_financeiras` | `codigo_cvm` | Resolvido via grafo |
| `DT_REF` | `demonstracoes_financeiras` | `data_referencia` | `YYYY-MM-DD` |
| `MOEDA` | `demonstracoes_financeiras` | `moeda` | Ex: `REAL` |
| `ESCALA_MOEDA` | `demonstracoes_financeiras` | `escala_moeda` | `UNIDADE`, `MIL`, `MILHAO` |
| `CD_CONTA` | `demonstracoes_financeiras` | `codigo_conta` | Ex: `1.01`, `3.03` |
| `DS_CONTA` | `demonstracoes_financeiras` | `descricao_conta` | Mantido original |
| `VL_CONTA` | `demonstracoes_financeiras` | `valor_conta_reportado` | Bruto da CVM |
| `FATOR_ESCALA` | (calculado) | `fator_escala_moeda` | 1, 1000, 1000000 |
| (calculado) | `demonstracoes_financeiras` | `valor_conta` | `valor_conta_reportado * fator` |

## Endpoints Principais

### Listar Documentos
```bash
GET /dfp/documentos?codigo_cvm=25224&ano_inicio=2020
```

### Balanço Patrimonial (Ativo/Passivo)
```bash
GET /dfp/balanco-patrimonial-ativo/{escopo}?codigo_cvm=25224&ano_inicio=2023
# escopo: consolidado ou individual
```

### Demonstração de Resultado
```bash
GET /dfp/demonstracao-resultado/{escopo}?codigo_cvm=25224&ano_inicio=2023
```

### Composição do Capital
```bash
GET /dfp/composicao-capital?codigo_cvm=25224&ano_inicio=2020
```

### Pareceres de Auditoria
```bash
GET /dfp/pareceres?codigo_cvm=25224&ano_inicio=2020
```

## Regras de Processamento

1. **Reapresentações**: A CVM republica arquivos anuais com nova `versao`. O pipeline mantém todas as versões, mas expõe a mais recente por padrão
2. **Escopo de Moeda**: Valores são normalizados automaticamente. Sempre use `valor_conta` para análises comparativas
3. **Contas Fixas**: Campo `conta_fixa` indica se a conta é obrigatória ou discricionária
4. **Ordem de Exercício**: `ÚLTIMO`, `PENÚLTIMO`, etc. são preservados para análises YoY

## Exemplo: Série Histórica YoY

```bash
GET /dfp/demonstracao-resultado/consolidado?codigo_cvm=25224&codigo_conta=3.03&ano_inicio=2020
```

**Lógica de Cálculo (cliente):**
```python
def yoy_atual(valores):
    return [(valores[i]/valores[i-1])-1 for i in range(1, len(valores))]
```

## Notas para Analistas

- DFP reflete o exercício social encerrado em 31/12
- Use `data_referencia` para alinhar com calendários fiscais
- Reapresentações são comuns nos primeiros trimestres do ano seguinte
- Para auditoria, sempre compare `versao` e `hash_origem`