---
title: Informações Periódicas e Eventuais (IPE)
sidebar_position: 7
---

# Informações Periódicas e Eventuais (IPE)

## O que é IPE

IPE é a fonte de Informações Periódicas e Eventuais das companhias abertas. Ela reúne metadados de documentos divulgados ao mercado, como comunicados, fatos relevantes, avisos, atas, assembleias, estatutos e outros eventos corporativos classificados pela CVM.

No Tucano CVM, IPE é promovida principalmente como catálogo documental. A fonte não transforma o conteúdo integral dos anexos em campos analíticos; ela organiza os metadados necessários para localizar, filtrar e acompanhar os documentos publicados.

## Por que esse conjunto existe

Enquanto DFP e ITR descrevem demonstrações financeiras e FRE/FCA descrevem formulários estruturados, IPE registra comunicações associadas a eventos corporativos. A fonte ajuda a acompanhar quando a companhia divulgou algo, qual categoria foi usada, qual assunto foi informado e onde está o documento original.

Essa fonte é relevante para montar uma linha do tempo de publicações e cruzar eventos com dados cadastrais, financeiros ou societários.

## Metadados técnicos

| Campo | Valor |
|-------|-------|
| Fonte no sistema | `ipe` |
| Distribuição CVM | ZIP anual |
| Arquivo principal | `ipe_cia_aberta_{ano}.zip` |
| Membro promovido | `ipe_cia_aberta_{ano}.csv` |
| Primeiro ano no registro da fonte | 2003 |
| Dependência | `cadastro` |
| Tabela promovida | `ipe_documentos` |
| Chaves de referência | `cnpj_companhia`, `codigo_cvm`, `protocolo_entrega` |

## O que entra na fonte

O pacote anual possui um membro principal com os metadados dos documentos. Entre os campos tratados pela API estão:

- companhia e código CVM
- categoria do documento
- tipo
- espécie
- assunto
- data de referência
- data de entrega
- protocolo de entrega
- versão
- situação ou status do documento
- link de download, quando informado pela origem

## Estrutura no Tucano CVM

| Tabela | Conteúdo |
|--------|----------|
| `ipe_documentos` | Registros documentais com classificação, datas, protocolo, versão e vínculo com a companhia. |

Os dados são mantidos como documentos porque a semântica principal da fonte está na publicação e na classificação do evento, não em quadros financeiros ou societários tabulares.

## Endpoints principais

```bash
GET /ipe/documentos?codigo_cvm=25224
GET /ipe/documentos?categoria=Fato%20Relevante
GET /ipe/documentos?assunto=Assembleia
GET /ipe/documentos?data_referencia_inicio=2025-01-01&data_referencia_fim=2025-06-30
GET /ipe/documentos/agregados?codigo_cvm=25224
```

## Como a ingestão trata a fonte

A ingestão processa o pacote anual, valida o membro principal, normaliza datas, identificadores e textos, e promove os registros para `ipe_documentos`. Cada linha mantém a referência ao arquivo, ano, linha e hash de origem.

Como o IPE pode conter retificações, cancelamentos ou versões diferentes de uma mesma comunicação, a leitura deve preservar protocolo, versão e status sempre que essas dimensões forem relevantes.

## Como ler os dados

`data_referencia` indica a data associada ao fato ou documento. `data_entrega` indica quando a informação foi entregue à CVM. A diferença entre essas datas pode ser relevante para análises de tempestividade.

Use categoria, tipo e assunto como filtros complementares. A taxonomia da CVM pode variar conforme o tipo de documento e o período, por isso comparações muito rígidas por texto devem considerar normalização ou agrupamentos próprios.
