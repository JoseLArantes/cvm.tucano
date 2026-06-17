---
title: Valores Mobiliários Negociados e Detidos (VLMO)
sidebar_position: 8
---

# Valores Mobiliários Negociados e Detidos (VLMO)

## Visão Geral

Registro de operações e posições de insiders (administradores, conselheiros, controladores) e grandes acionistas.

## Metadados Técnicos

| Campo | Valor |
|-------|-------|
| **Fonte CVM** | `vlmo` |
| **Arquivo ZIP** | `vlmo_companhias_abertas_{ano}.zip` |
| **Periodicidade** | Semanal |
| **Cobertura** | Últimos 5 anos |
| **Tabelas Alvo** | `vlmo_documentos`, `vlmo_consolidado` |

## Endpoints Principais

```bash
GET /vlmo/documentos?codigo_cvm=25224
GET /vlmo/consolidado?codigo_cvm=25224&tipo_cargo=Diretor
GET /vlmo/consolidado?tipo_movimentacao=Compra&ano=2024
```

## Campos Principais (`vlmo_consolidado`)

| Campo | Descrição |
|-------|-----------|
| `tipo_empresa` | Controladora, Controlada, Coligada |
| `tipo_cargo` | Diretor, Conselheiro, Fiscal, Acionista Controlador |
| `nome` | Nome do insider |
| `cpf_cnpj` | Documento |
| `tipo_ativo` | Ação Ordinária, Preferencial, Opção, Debênture |
| `tipo_movimentacao` | Compra, Venda, Doação, Exercício de Opção |
| `quantidade` | Quantidade negociada/detida |
| `preco_unitario` | Preço médio |
| `volume` | `quantidade * preco_unitario` |
| `data_operacao` | Data da negociação |
| `data_comunicacao` | Data de reporte à CVM |

## Regras de Processamento

1. **Consolidação**: Dados são agrupados por insider + ativo + data
2. **Insider Trading Monitoring**: `data_operacao` vs `data_comunicacao` expõe atrasos de reporte
3. **Valores Monetários**: `preco_unitario` e `volume` são normalizados
4. **Retificações**: Movimentações canceladas são marcadas com status adequado

## Exemplo: Rastreamento de Insiders

```bash
GET /vlmo/consolidado?codigo_cvm=25224&tipo_cargo=Conselheiro&tipo_movimentacao=Venda&ano_inicio=2024
```

## Notas para Compliance

- Fundamental para políticas de `blackout periods` e prevenção de insider trading
- Use `data_comunicacao - data_operacao` para SLA de reporte
- Cruze com `ipe/documentos` para verificar se houve fato relevante prévio