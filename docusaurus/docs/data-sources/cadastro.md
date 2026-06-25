---
title: Cadastro de Companhias Abertas
sidebar_position: 2
---

# Cadastro de Companhias Abertas

## O que é o cadastro

O cadastro é a base de identificação das companhias acompanhadas pelo projeto. Ele reúne os dados cadastrais publicados pela CVM para companhias abertas e, na malha de ingestão, também considera o cadastro de emissores estrangeiros quando ele é necessário para resolver documentos vinculados a esse universo.

Essa fonte não descreve demonstrações, eventos ou práticas de governança. Ela informa quem é a companhia, qual é o seu código CVM, qual CNPJ a identifica, qual é sua situação de registro e quais dados institucionais estavam vigentes na última publicação oficial.

## Por que esse conjunto existe

As demais fontes da CVM referenciam companhias por identificadores como `CNPJ_CIA`, `CD_CVM` ou campos equivalentes. Antes de interpretar um documento financeiro, um formulário cadastral, um informe eventual ou um relatório de governança, o sistema precisa resolver a identidade da companhia de forma consistente.

Por isso, o cadastro funciona como a raiz de identidade do domínio. Ele permite que documentos de anos diferentes, fontes diferentes e formatos diferentes sejam associados à mesma companhia quando os identificadores oficiais apontam para ela.

## Metadados técnicos

| Campo | Valor |
|-------|-------|
| Fonte no sistema | `cadastro` |
| Distribuição CVM | CSV único |
| Arquivo principal | `cad_cia_aberta.csv` |
| Arquivo complementar no catálogo | `cad_cia_estrang.csv` |
| Tabela promovida | `companhias` |
| Chaves de referência | `cnpj_companhia`, `codigo_cvm` |
| Periodicidade | Retrato corrente publicado pela CVM |
| Dependências | Nenhuma |

## O que entra no cadastro

O arquivo principal contém um registro por companhia aberta presente no cadastro publicado pela CVM. A normalização preserva a identidade oficial e organiza campos institucionais que aparecem em formatos variados no arquivo de origem.

Entre os dados tratados estão:

- CNPJ da companhia
- código CVM
- denominação social
- denominação comercial
- situação de registro
- data de registro
- data de constituição
- data de cancelamento, quando houver
- motivo de cancelamento, quando houver
- setor de atividade
- tipo de mercado
- categoria de registro
- situação do emissor
- controle acionário
- endereço
- responsável cadastral
- auditor e CNPJ do auditor, quando informados

## Estrutura no Tucano CVM

O cadastro é promovido para a tabela `companhias`. Cada registro mantém os campos normalizados e os metadados de origem necessários para auditoria operacional.

| Campo de saída | Origem conceitual | Observação |
|----------------|-------------------|------------|
| `cnpj_companhia` | CNPJ da companhia | Normalizado sem máscara. |
| `codigo_cvm` | Código CVM | Identificador numérico usado em várias fontes. |
| `denominacao_social` | Denominação social | Texto oficial informado no cadastro. |
| `denominacao_comercial` | Denominação comercial | Pode estar ausente. |
| `situacao_registro` | Situação de registro | Mantém a descrição normalizada a partir da fonte. |
| `data_registro` | Data de registro | Data oficial de registro na CVM. |
| `data_cancelamento` | Data de cancelamento | Preenchida quando aplicável. |
| `setor_atividade` | Setor de atividade | Mantido conforme a classificação informada. |
| `tipo_mercado` | Tipo de mercado | Segmento ou mercado informado pela CVM. |
| `endereco` | Campos de endereço | Agrupado como estrutura. |
| `responsavel` | Campos do responsável | Agrupado como estrutura. |
| `arquivo_origem`, `linha_origem`, `hash_origem` | Metadados de ingestão | Usados para rastreabilidade. |

## Como a ingestão trata a fonte

A ingestão do cadastro é sensível porque alterações nessa base afetam a resolução das demais fontes. O processo calcula o hash do arquivo, registra a execução, normaliza linha a linha e separa registros inválidos em quarentena.

Quando uma companhia já existe, o sistema compara campos de negócio antes de atualizar o registro. `sincronizado_em` indica que a linha foi reprocessada em uma execução recente; `alterado_em` muda apenas quando algum campo material foi modificado. Alterações relevantes são registradas em histórico de campos.

Registros duplicados dentro do mesmo arquivo, linhas sem identificadores essenciais ou dados que não passam pela normalização não são promovidos silenciosamente. Eles ficam vinculados à execução para inspeção operacional.

## Endpoints principais

```bash
GET /companhias?pagina=1&tamanho_pagina=100
GET /companhias?nome=petrobras
GET /companhias?situacao_registro=ATIVO
GET /companhias/codigo-cvm/{codigo_cvm}
GET /companhias/{cnpj_companhia}
```

## Como ler os dados

O cadastro representa o estado cadastral conhecido na última sincronização, não uma série histórica completa de todos os estados passados da companhia. Para entender mudanças observadas pelo pipeline, use os metadados de sincronização e o histórico de alterações registrado pela ingestão.

O CNPJ e o código CVM devem ser lidos como identificadores oficiais complementares. Em integrações com DFP, ITR, FRE, FCA, IPE, VLMO e CGVN, o código CVM costuma ser o elo mais frequente para consultas, enquanto o CNPJ é importante para consolidação cadastral e rastreabilidade.
