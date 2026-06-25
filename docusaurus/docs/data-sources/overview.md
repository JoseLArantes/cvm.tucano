---
title: Fontes de Dados - Visão Geral
sidebar_position: 1
---

# Fontes de Dados - Visão Geral

## Contexto

O Tucano CVM ingere dados públicos disponibilizados pela Comissão de Valores Mobiliários no Portal de Dados Abertos. Cada fonte possui uma finalidade própria: algumas identificam companhias, outras registram documentos financeiros, formulários estruturados, eventos corporativos ou práticas de governança.

As páginas desta seção descrevem como cada fonte é entendida no projeto, quais arquivos entram na ingestão, quais dados são promovidos para consulta e quais cuidados de leitura devem acompanhar o uso da informação.

## Matriz de fontes

| Fonte | Conteúdo principal | Distribuição | Raiz de consulta |
|-------|--------------------|--------------|------------------|
| `cadastro` | Identidade e situação cadastral das companhias | CSV corrente | `/companhias` |
| `dfp` | Demonstrações financeiras anuais | ZIP anual | `/dfp/documentos` |
| `itr` | Demonstrações financeiras trimestrais | ZIP anual | `/itr/documentos` |
| `fre` | Formulário de Referência | ZIP anual | `/fre/documentos` |
| `fca` | Formulário Cadastral | ZIP anual | `/fca/documentos` |
| `ipe` | Informações periódicas e eventuais | ZIP anual | `/ipe/documentos` |
| `vlmo` | Valores mobiliários negociados e detidos | ZIP anual | `/vlmo/documentos` |
| `cgvn` | Informe de governança corporativa | ZIP anual | `/cgvn/documentos` |

## Relação entre as fontes

O cadastro é a base de identidade. DFP e ITR formam a família financeira. FRE e FCA descrevem formulários estruturados com finalidades diferentes. IPE registra comunicações e eventos documentais. VLMO trata posições e movimentações de valores mobiliários. CGVN registra práticas de governança declaradas.

Essas fontes não substituem umas às outras. Elas formam camadas complementares em torno da companhia e dos documentos enviados à CVM.

## Processo de ingestão

A ingestão preserva a origem dos dados e busca promover somente registros que passam por normalização e vínculo de identidade. O processamento inclui:

- aquisição do arquivo publicado pela CVM
- verificação de metadados remotos e hash do artefato
- leitura dos CSVs
- normalização de tipos, datas, textos e identificadores
- resolução da companhia pelo cadastro
- promoção para tabelas de domínio quando há suporte
- registro de quarentena para linhas inválidas ou não vinculadas
- reconciliação do pacote processado com o estado promovido

## Rastreabilidade

Os registros promovidos mantêm metadados de origem, como arquivo, ano, linha e hash. Esses campos ajudam a explicar de onde veio um dado e qual execução o processou.

Em fontes documentais, versão, protocolo, data de referência e data de entrega são parte da interpretação. Em fontes financeiras, tipo de demonstração, escopo, conta, moeda e escala também devem acompanhar a leitura.

## Documentos desta seção

- [Cadastro](./cadastro.md)
- [DFP](./dfp.md)
- [ITR](./itr.md)
- [FRE](./fre.md)
- [FCA](./fca.md)
- [IPE](./ipe.md)
- [VLMO](./vlmo.md)
- [CGVN](./cgvn.md)
