---
title: Fontes de Dados - Visão Geral
sidebar_position: 1
---

# Fontes de Dados - Visão Geral

## Contexto Regulatório

O serviço ingere dados públicos disponibilizados pela **Comissão de Valores Mobiliários (CVM)** através do [Portal de Dados Abertos](https://dados.cvm.gov.br/). Cada fonte possui periodicidade, granularidade e finalidade regulatória distintas.

## Matriz de Fontes

| Fonte | Nome Completo | Periodicidade CVM | Desde | Tabela Raiz | Endpoints Principais |
|-------|---------------|-------------------|-------|-------------|---------------------|
| `cadastro` | Cadastro de Companhias Abertas | Diária | Contínuo | `companhias` | `/companhias`, `/companhias/codigo-cvm/{id}` |
| `dfp` | Demonstrações Financeiras Padronizadas | Semanal/Anual | 2010 | `documentos_financeiros` | `/dfp/documentos`, `/dfp/balanco-patrimonial-ativo/{escopo}` |
| `itr` | Informações Trimestrais | Semanal/Trimestral | 2011 | `documentos_financeiros` | `/itr/documentos`, `/itr/demonstracao-resultado/{escopo}` |
| `fre` | Formulário de Referência | Semanal | 2010 | `fre_documentos` | `/fre/documentos`, `/fre/posicao-acionaria`, `/fre/remuneracao` |
| `fca` | Formulário Cadastral | Semanal | 2010 | `fca_documentos` | `/fca/documentos`, `/fca/geral`, `/fca/auditores` |
| `ipe` | Informações Periódicas e Eventuais | Semanal | 2003 | `ipe_documentos` | `/ipe/documentos` |
| `vlmo` | Valores Mobiliários Negociados e Detidos | Semanal | Últimos 5 anos | `vlmo_documentos` | `/vlmo/documentos`, `/vlmo/consolidado` |
| `cgvn` | Código de Governança Corporativa | Semanal | 2018 | `cgvn_documentos` | `/cgvn/documentos`, `/cgvn/praticas` |

## Padrão de Ingestão

Todas as fontes seguem o mesmo pipeline de duas fases:
1. **Aquisição**: Download ZIP → verificação SHA-256 → extração CSVs
2. **Processamento**: Stage → Validação → Resolução de Identidade → Promoção → Reconcile

## Normalização de Dados

Os dados brutos passam por:
- **Padronização monetária**: Conversão automática de escalas (`UNIDADE`, `MIL`, `MILHAO`)
- **Resolução de identidade**: Vinculação de CNPJ/Código CVM à tabela `companhias`
- **Tratamento de nulos**: Conversão de `N/A`, `N.D.`, `-` para `null`
- **Fallback de tipos**: Campos originalmente numéricos com texto livre são preservados como `Text`

## Auditoria e Rastreabilidade

Cada registro promovido contém metadados de origem:
```json
{
  "arquivo_origem": "dfp_cia_aberta_2024.csv",
  "ano_origem": 2024,
  "linha_origem": 142,
  "hash_origem": "sha256:...",
  "criado_em": "2026-05-15T10:00:00Z",
  "sincronizado_em": "2026-05-20T08:30:00Z",
  "alterado_em": "2026-05-20T08:30:00Z"
}
```

## Próximos Passos

Consulte a documentação específica de cada fonte:
- [Cadastro](./cadastro.md)
- [DFP](./dfp.md)
- [ITR](./itr.md)
- [FRE](./fre.md)
- [FCA](./fca.md)
- [IPE](./ipe.md)
- [VLMO](./vlmo.md)
- [CGVN](./cgvn.md)