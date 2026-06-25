---
title: Demonstrações Financeiras Padronizadas (DFP)
sidebar_position: 3
---

# Demonstrações Financeiras Padronizadas (DFP)

## O que é DFP

DFP é o conjunto anual de demonstrações financeiras padronizadas entregue por companhias abertas à CVM. Ele reúne o cabeçalho documental, as demonstrações contábeis, a composição do capital e os pareceres relacionados ao exercício social.

No Tucano CVM, DFP é tratada como uma fonte financeira anual. Os dados são promovidos para tabelas comuns de documentos, demonstrações, composição de capital e pareceres, compartilhando a mesma estrutura usada por ITR quando os conceitos são equivalentes.

## Por que esse conjunto existe

A DFP organiza a visão anual das informações financeiras reportadas pelas companhias. Ela permite acompanhar balanço patrimonial, resultado, caixa, mutações do patrimônio líquido, valor adicionado e resultado abrangente com a granularidade das contas publicadas pela CVM.

Como os arquivos podem ser reapresentados, a versão do documento é parte importante da leitura. A ingestão mantém a relação entre documento, versão, data de referência, escopo e arquivo de origem.

## Metadados técnicos

| Campo | Valor |
|-------|-------|
| Fonte no sistema | `dfp` |
| Distribuição CVM | ZIP anual |
| Arquivo principal | `dfp_cia_aberta_{ano}.zip` |
| Primeiro ano no registro da fonte | 2010 |
| Dependência | `cadastro` |
| Tabelas promovidas | `documentos_financeiros`, `demonstracoes_financeiras`, `composicoes_capital`, `pareceres_financeiros` |
| Chaves de referência | `cnpj_companhia`, `codigo_cvm`, `id_documento`, `versao`, `data_referencia` |

## Arquivos do pacote anual

Cada ZIP anual contém um arquivo principal e arquivos especializados por quadro contábil. O prefixo `con` indica demonstração consolidada; `ind` indica demonstração individual.

```text
dfp_cia_aberta_{ano}.csv
dfp_cia_aberta_BPA_con_{ano}.csv
dfp_cia_aberta_BPA_ind_{ano}.csv
dfp_cia_aberta_BPP_con_{ano}.csv
dfp_cia_aberta_BPP_ind_{ano}.csv
dfp_cia_aberta_DFC_MD_con_{ano}.csv
dfp_cia_aberta_DFC_MD_ind_{ano}.csv
dfp_cia_aberta_DFC_MI_con_{ano}.csv
dfp_cia_aberta_DFC_MI_ind_{ano}.csv
dfp_cia_aberta_DMPL_con_{ano}.csv
dfp_cia_aberta_DMPL_ind_{ano}.csv
dfp_cia_aberta_DRA_con_{ano}.csv
dfp_cia_aberta_DRA_ind_{ano}.csv
dfp_cia_aberta_DRE_con_{ano}.csv
dfp_cia_aberta_DRE_ind_{ano}.csv
dfp_cia_aberta_DVA_con_{ano}.csv
dfp_cia_aberta_DVA_ind_{ano}.csv
dfp_cia_aberta_composicao_capital_{ano}.csv
dfp_cia_aberta_parecer_{ano}.csv
```

## Estrutura no Tucano CVM

| Área | Tabela | Conteúdo |
|------|--------|----------|
| Documento | `documentos_financeiros` | Cabeçalho do formulário, companhia, versão, datas e situação documental. |
| Demonstrações | `demonstracoes_financeiras` | Linhas de contas contábeis, escopo, moeda, escala e valores reportados. |
| Capital | `composicoes_capital` | Composição de ações ou quotas declarada no formulário. |
| Pareceres | `pareceres_financeiros` | Informações de parecer, auditoria e declarações vinculadas ao documento. |

Nas demonstrações, a leitura principal passa por:

- `tipo_demonstracao`, como balanço patrimonial ativo, passivo ou demonstração do resultado
- `escopo`, com valores como `consolidado` ou `individual`
- `codigo_conta` e `descricao_conta`
- `valor_conta_reportado`
- `moeda` e `escala_moeda`
- `valor_conta`, quando a normalização aplica o fator de escala
- `ordem_exercicio`, preservando a posição do exercício no arquivo da CVM

## Endpoints principais

```bash
GET /dfp/documentos?codigo_cvm=25224&ano_inicio=2020
GET /dfp/balanco-patrimonial-ativo/consolidado?codigo_cvm=25224&ano_inicio=2023
GET /dfp/balanco-patrimonial-passivo/individual?codigo_cvm=25224&ano_inicio=2023
GET /dfp/demonstracao-resultado/consolidado?codigo_cvm=25224&ano_inicio=2023
GET /dfp/fluxo-caixa-metodo-indireto/consolidado?codigo_cvm=25224&ano_inicio=2023
GET /dfp/composicao-capital?codigo_cvm=25224&ano_inicio=2020
GET /dfp/pareceres?codigo_cvm=25224&ano_inicio=2020
```

## Como a ingestão trata a fonte

O arquivo principal é processado antes dos membros dependentes porque ele ancora o documento financeiro e sua versão. As linhas das demonstrações, composição de capital e pareceres são vinculadas a esse cabeçalho por identificadores do próprio pacote.

O processo preserva metadados de origem, como arquivo, ano, linha e hash. Quando o pacote anual é substituído pela CVM, a ingestão usa o pacote como unidade de reconciliação para manter o estado promovido compatível com a entrega mais recente processada.

## Como ler os dados

A DFP é anual e deve ser comparada por `data_referencia`, `tipo_demonstracao`, `escopo`, `codigo_conta` e `versao`. Para análises entre companhias, a escala monetária precisa ser observada; quando disponível, use o valor já normalizado em vez do valor textual ou reportado no arquivo.

Reapresentações fazem parte do ciclo regulatório. Em leituras históricas, a versão e os metadados documentais devem acompanhar qualquer conclusão baseada nos números.
