---
title: Código de Governança Corporativa (CGVN)
sidebar_position: 9
---

# Código de Governança Corporativa (CGVN)

## Visão Geral

Declaração anual de práticas de governança adotadas pela companhia, conforme modelo CVM.

## Metadados Técnicos

| Campo | Valor |
|-------|-------|
| **Fonte CVM** | `cgvn` |
| **Arquivo ZIP** | `cgvn_companhias_abertas_{ano}.zip` |
| **Periodicidade** | Anual |
| **Desde** | 2018 |
| **Tabelas Alvo** | `cgvn_documentos`, `cgvn_praticas` |

## Endpoints Principais

```bash
GET /cgvn/documentos?codigo_cvm=25224
GET /cgvn/praticas?codigo_cvm=25224&ano=2024
```

## Campos Principais (`cgvn_praticas`)

| Campo | Descrição |
|-------|-----------|
| `id_item` | Código da prática (ex: `1.1.1`, `2.3.4`) |
| `pratica_recomendada` | Texto da recomendação CVM |
| `pratica_adotada` | `Sim`, `Não`, `Parcialmente`, `Não se Aplica` |
| `explicacao` | Justificativa quando não adotada ou parcialmente |
| `secao` | Área temática (ex: Conselho de Administração, Auditoria, Remuneração) |

## Regras de Processamento

1. **Estrutura Hierárquica**: `id_item` segue padrão `secao.subsecao.item`
2. **Compliance Score**: Pode ser calculado pelo cliente: `adotadas / (total - nao_se_aplica)`
3. **Explicações Obrigatórias**: `pratica_adotada != 'Sim'` geralmente exige `explicacao`
4. **Comparativo Ano-a-Ano**: Útil para tracking de maturidade de governança

## Exemplo: Score de Governança

```bash
GET /cgvn/praticas?codigo_cvm=25224&ano=2024
```

**Cálculo sugerido:**
```python
total = len(praticas)
nao_aplica = sum(1 for p in praticas if p['pratica_adotada'] == 'Não se Aplica')
adotadas = sum(1 for p in praticas if p['pratica_adotada'] == 'Sim')
score = adotadas / (total - nao_aplica) * 100
```

## Notas para Auditores e Compliance

- CGVN complementa FRE na análise de governança
- Use para scoring ESG/Corporate Governance em matrizes de risco
- `explicacao` contém detalhes qualitativos valiosos
- Cruze com `fre_relativas_familiares` e `fre_auditores` para visão 360°