---
title: Informações Trimestrais (ITR)
sidebar_position: 4
---

# Informações Trimestrais (ITR)

## O que é ITR

ITR é o conjunto de informações financeiras trimestrais entregue por companhias abertas à CVM. Ele usa uma estrutura próxima à DFP, mas representa períodos intermediários do exercício social.

No Tucano CVM, ITR e DFP compartilham as tabelas financeiras promovidas. A diferença principal está na natureza temporal da fonte: ITR acompanha trimestres e períodos acumulados; DFP representa o encerramento anual.

## Por que esse conjunto existe

O ITR permite observar a evolução financeira ao longo do ano, antes da demonstração anual completa. Ele é usado para acompanhar receitas, resultado, caixa, patrimônio, composição de capital e pareceres em datas intermediárias.

Como as companhias podem reapresentar informações trimestrais, a versão do documento e a data de referência são elementos essenciais da leitura.

## Metadados técnicos

| Campo | Valor |
|-------|-------|
| Fonte no sistema | `itr` |
| Distribuição CVM | ZIP anual |
| Arquivo principal | `itr_cia_aberta_{ano}.zip` |
| Primeiro ano no registro da fonte | 2010 |
| Dependência | `cadastro` |
| Tabelas promovidas | `documentos_financeiros`, `demonstracoes_financeiras`, `composicoes_capital`, `pareceres_financeiros` |
| Chaves de referência | `cnpj_companhia`, `codigo_cvm`, `id_documento`, `versao`, `data_referencia` |

## Arquivos do pacote anual

O pacote anual ITR segue o mesmo padrão de membros da fonte financeira. Cada arquivo especializado representa um quadro contábil e um escopo.

```text
itr_cia_aberta_{ano}.csv
itr_cia_aberta_BPA_con_{ano}.csv
itr_cia_aberta_BPA_ind_{ano}.csv
itr_cia_aberta_BPP_con_{ano}.csv
itr_cia_aberta_BPP_ind_{ano}.csv
itr_cia_aberta_DFC_MD_con_{ano}.csv
itr_cia_aberta_DFC_MD_ind_{ano}.csv
itr_cia_aberta_DFC_MI_con_{ano}.csv
itr_cia_aberta_DFC_MI_ind_{ano}.csv
itr_cia_aberta_DMPL_con_{ano}.csv
itr_cia_aberta_DMPL_ind_{ano}.csv
itr_cia_aberta_DRA_con_{ano}.csv
itr_cia_aberta_DRA_ind_{ano}.csv
itr_cia_aberta_DRE_con_{ano}.csv
itr_cia_aberta_DRE_ind_{ano}.csv
itr_cia_aberta_DVA_con_{ano}.csv
itr_cia_aberta_DVA_ind_{ano}.csv
itr_cia_aberta_composicao_capital_{ano}.csv
itr_cia_aberta_parecer_{ano}.csv
```

## Diferenças em relação à DFP

| Aspecto | DFP | ITR |
|---------|-----|-----|
| Período | Exercício anual | Períodos intermediários do exercício |
| Uso típico | Fechamento anual | Acompanhamento trimestral |
| Estrutura no sistema | Tabelas financeiras comuns | Tabelas financeiras comuns |
| Campos de leitura | Documento, versão, data de referência, escopo e conta | Documento, versão, data de referência, escopo e conta |
| Reapresentações | Possíveis | Possíveis |

## Estrutura no Tucano CVM

| Área | Tabela | Conteúdo |
|------|--------|----------|
| Documento | `documentos_financeiros` | Cabeçalho do ITR, companhia, versão, datas e situação documental. |
| Demonstrações | `demonstracoes_financeiras` | Linhas de contas contábeis por quadro, escopo e data de referência. |
| Capital | `composicoes_capital` | Composição de capital declarada no pacote. |
| Pareceres | `pareceres_financeiros` | Pareceres e informações relacionadas ao documento. |

## Endpoints principais

```bash
GET /itr/documentos?codigo_cvm=25224&ano_inicio=2024
GET /itr/balanco-patrimonial-ativo/consolidado?codigo_cvm=25224&ano_inicio=2024
GET /itr/demonstracao-resultado/consolidado?codigo_cvm=25224&ano_inicio=2024
GET /itr/fluxo-caixa-metodo-direto/individual?codigo_cvm=25224&ano_inicio=2024
GET /itr/composicao-capital?codigo_cvm=25224&ano_inicio=2024
GET /itr/pareceres?codigo_cvm=25224&ano_inicio=2024
```

## Como a ingestão trata a fonte

O cabeçalho documental é processado antes dos quadros financeiros. As demais linhas do pacote são promovidas somente depois de vinculadas ao documento correspondente. A ingestão mantém arquivo, ano, linha e hash de origem para cada registro promovido.

Como a distribuição é anual, o pacote de um ano contém os documentos daquele ano de referência. O sistema usa a mesma política de reconciliação por pacote anual aplicada à família financeira.

## Como ler os dados

O ITR deve ser lido pela combinação de companhia, data de referência, versão, escopo e conta. Algumas linhas representam valores acumulados no período; por isso, comparações trimestrais exigem atenção à semântica do quadro original e à data de referência.

Para séries históricas, mantenha DFP e ITR separados quando a periodicidade for relevante. A aproximação estrutural entre as fontes facilita consultas, mas não elimina a diferença regulatória entre fechamento anual e informação intermediária.
