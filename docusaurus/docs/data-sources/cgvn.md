---
title: Código de Governança Corporativa (CGVN)
sidebar_position: 9
---

# Código de Governança Corporativa (CGVN)

## O que é CGVN

CGVN é a fonte de informes relacionados ao Código Brasileiro de Governança Corporativa. Ela registra o documento entregue pela companhia e as práticas declaradas, incluindo a adoção ou não adoção de recomendações e as explicações apresentadas.

No Tucano CVM, a fonte é dividida em cabeçalho documental e práticas. Isso permite consultar tanto a entrega do informe quanto o conteúdo item a item.

## Por que esse conjunto existe

O CGVN organiza informações qualitativas sobre práticas de governança. Diferente de DFP e ITR, que têm foco financeiro, ou de IPE, que registra eventos documentais, CGVN descreve como a companhia responde às práticas recomendadas no código.

Essa fonte deve ser lida como uma declaração estruturada da companhia em uma data e versão específicas.

## Metadados técnicos

| Campo | Valor |
|-------|-------|
| Fonte no sistema | `cgvn` |
| Distribuição CVM | ZIP anual |
| Arquivo principal | `cgvn_cia_aberta_{ano}.zip` |
| Membros promovidos | `cgvn_cia_aberta_{ano}.csv`, `cgvn_cia_aberta_praticas_{ano}.csv` |
| Primeiro ano no registro da fonte | 2018 |
| Dependência | `cadastro` |
| Tabelas promovidas | `cgvn_documentos`, `cgvn_praticas` |
| Chaves de referência | `cnpj_companhia`, `codigo_cvm`, `id_documento`, `versao`, `id_item` |

## Arquivos do pacote anual

```text
cgvn_cia_aberta_{ano}.csv
cgvn_cia_aberta_praticas_{ano}.csv
```

O primeiro arquivo contém o cabeçalho documental. O segundo contém os itens de prática e as respostas associadas.

## Estrutura no Tucano CVM

| Dataset | Tabela | Conteúdo |
|---------|--------|----------|
| Documento | `cgvn_documentos` | Companhia, documento, versão, data de referência e metadados da entrega. |
| Práticas | `cgvn_praticas` | Itens do código, prática recomendada, resposta declarada e explicação textual. |

Nos registros de práticas, a leitura normalmente passa por:

- `id_item`, que identifica o item do código
- prática recomendada
- prática adotada ou resposta equivalente
- explicação informada pela companhia
- seção ou agrupamento temático, quando disponível na origem
- data de referência e versão do documento

## Endpoints principais

```bash
GET /cgvn/documentos?codigo_cvm=25224
GET /cgvn/praticas?codigo_cvm=25224&ano=2024
```

## Como a ingestão trata a fonte

O cabeçalho documental é processado antes das práticas. As práticas são promovidas depois de vinculadas ao documento, preservando linha de origem, arquivo, ano e hash.

O vínculo com `cadastro` resolve a companhia antes da promoção dos registros. Quando a linha não pode ser vinculada ou não passa pela normalização, o processo registra a falha operacional em vez de promover dados incompletos.

## Como ler os dados

CGVN é uma fonte declaratória. A resposta de uma prática deve ser interpretada junto com a explicação textual, a versão do documento e a data de referência. Para comparações entre anos, acompanhe o mesmo `id_item` e considere mudanças na redação ou estrutura do informe.

Indicadores agregados podem ser calculados fora da API a partir dos itens de prática, mas a documentação da fonte prioriza os campos oficiais e a rastreabilidade do documento.
