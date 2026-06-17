---
title: Informações Trimestrais (ITR)
sidebar_position: 4
---

# Informações Trimestrais (ITR)

## Visão Geral

Demonstrações financeiras trimestrais, equivalentes a relatórios de acompanhamento financeiro. Podem ser revisadas ou limitadas.

## Metadados Técnicos

| Campo | Valor |
|-------|-------|
| **Fonte CVM** | `itr` |
| **Arquivo ZIP** | `itr_companhias_abertas_{ano}.zip` |
| **Periodicidade** | Trimestral (Q1, Q2, Q3) + Anual |
| **Desde** | 2011 |
| **Tabelas Alvo** | `documentos_financeiros`, `demonstracoes_financeiras` |
| **Chaves Naturais** | `(tipo_formulario, id_documento, versao, data_referencia)` |

## Estrutura de Arquivos

```
itr_cia_aberta_{ano}.csv
itr_cia_aberta_BPA_con_{ano}.csv
itr_cia_aberta_BPA_ind_{ano}.csv
itr_cia_aberta_BPP_con_{ano}.csv
itr_cia_aberta_BPP_ind_{ano}.csv
itr_cia_aberta_DRE_con_{ano}.csv
itr_cia_aberta_DRE_ind_{ano}.csv
itr_cia_aberta_DFC_MI_con_{ano}.csv
itr_cia_aberta_DMPL_con_{ano}.csv
itr_cia_aberta_DVA_con_{ano}.csv
```

## Diferenças para DFP

| Aspecto | DFP | ITR |
|---------|-----|-----|
| **Periodicidade** | Anual | Trimestral + Acumulado |
| **Auditoria** | Obrigatória (completa) | Revisada/Limitada (geralmente) |
| **Abrangência** | Todas demonstrações | Principalmente BPA, BPP, DRE, DFC, DVA |
| **Data Referência** | `31/12/{ano}` | `31/03`, `30/06`, `30/09`, `31/12` |
| **Tabela** | `dfp_*` | `itr_*` (mesma estrutura `demonstracoes_financeiras`) |

## Mapeamento de Campos

Idêntico ao DFP, com adição de:
- `trimestre`: `1`, `2`, `3`, ou `4` (acumulado)
- `tipo_revisao`: `REVISADA`, `LIMITADA` ou `N/A`

## Endpoints Principais

### Listar Documentos
```bash
GET /itr/documentos?codigo_cvm=25224&ano_inicio=2024
```

### Balanço Trimestral
```bash
GET /itr/balanco-patrimonial-ativo/{escopo}?codigo_cvm=25224&ano_inicio=2024
```

### Filtro por Trimestre
```bash
GET /itr/demonstracao-resultado/consolidado?codigo_cvm=25224&ano=2024&trimestre=2
```

## Regras de Processamento

1. **Acumulado vs Trimestral**: ITRs do Q4 são acumulados (Jan-Dez). ITRs Q1-Q3 são acumulados até o trimestre
2. **Moeda e Escala**: Mesma normalização do DFP
3. **Reapresentações**: Comuns quando há reclassificação de contas ou erros de arredondamento
4. **Vínculo com DFP**: Não há vínculo direto de chaves, mas `codigo_cvm` e `cnpj_companhia` mantêm a coerência

## Exemplo: Consulta Trimestral

```bash
curl -X GET "http://localhost:8007/itr/demonstracao-resultado/consolidado?codigo_cvm=25224&ano=2025&trimestre=2" \
  -H "Authorization: Bearer seu-token"
```

## Notas para Compliance

- ITRs não substituem DFPs para fins de auditoria formal
- Use `tipo_revisao` para avaliar confiabilidade
- Revisões tardias podem gerar múltiplas versões com mesma `data_referencia`