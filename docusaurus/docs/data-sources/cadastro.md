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

Quando uma companhia já existe, o sistema compara campos de negócio antes de atualizar o registro. `sincronizado_em` indica que a linha foi reprocessada em uma execução recente; `alterado_em` muda apenas quando algum campo material foi modificado.

Os contadores operacionais da execução classificam cada linha válida do cadastro:

- `total_inseridos`: a linha criou um registro CVM ou vínculo de mercado que ainda não existia;
- `total_atualizados`: a linha encontrou o registro existente e modificou ao menos um campo de negócio;
- `total_inalterados`: a linha já estava representada com os mesmos valores de negócio;
- `total_rejeitados`: a linha não pôde ser promovida.

`total_registros_promovidos`, quando exposto pelo processamento interno, mede volume processado e não quantidade de inserções. Metadados de proveniência, como arquivo, linha e hash de origem, podem ser renovados sem transformar uma linha inalterada em atualização.

Também são independentes a mudança do artefato e o efeito no domínio. Um CSV pode ter SHA-256 diferente por ordenação, formatação ou alteração em campo não promovido e ainda produzir `total_inseridos=0` e `total_atualizados=0`. Nesse caso, os contadores demonstram que o novo artefato foi processado, mas não alterou o estado cadastral canônico.

Registros duplicados dentro do mesmo arquivo, linhas sem identificadores essenciais ou dados que não passam pela normalização não são promovidos silenciosamente. Eles ficam vinculados à execução para inspeção operacional.

## Validação e divergências de CNPJ

O CNPJ usado como identidade canônica passa pela validação dos dígitos verificadores. O valor original informado pela fonte continua associado ao registro CVM e à sua proveniência (arquivo, linha e hash). Uma divergência não altera o UUID interno da companhia quando ela pode ser reconciliada pelo código CVM.

Há uma correção explícita e restrita para o código CVM `80012` (`BRAZIL FAST FOOD CORP.`). O arquivo oficial [cad_cia_estrang.csv](https://dados.cvm.gov.br/dados/CIA_ESTRANG/CAD/DADOS/cad_cia_estrang.csv) publica `05.714.446/0004-00`, cujo dígito verificador é inválido. A regra só se aplica quando arquivo, código CVM, CNPJ de origem e denominação coincidem. O CNPJ canônico usado em `companhias` e nos identificadores ativos é `05.714.446/0001-00`, identificado para a mesma companhia no [Acórdão CARF nº 1402-002.180](https://acordaos.economia.gov.br/solr/acordaos2_shard7_replica_n101/browse?debugQuery=true&fq=ano_sessao_s%3A%222016%22&fq=decisao_txt%3A%22a%22&fq=decisao_txt%3A%22do%22&fq=decisao_txt%3A%22em%22&fq=decisao_txt%3A%22membros%22&fq=nome_relator_s%3A%22FERNANDO+BRASIL+DE+OLIVEIRA+PINTO%22&fq=secao_s%3A%22Primeira+Se%C3%A7%C3%A3o+de+Julgamento%22&q=). A [listagem pública da CVM](https://cvmweb.cvm.gov.br/swb/sistemas/scw/cpublica/ciaab/FormBuscaCiaAbOrdAlf.aspx?LetraInicial=B) confirma o nome, o código e o cancelamento em 23/12/2002, mas mostra `-` no campo CNPJ.

O valor de origem `05.714.446/0004-00` permanece no registro CVM, com arquivo e linha de origem; a correção não reescreve o dado publicado pela CVM. Cada divergência de dígitos verificadores gera o diagnóstico estruturado `cvm_registry_cnpj_source_mismatch`, com código CVM, arquivo, linha e apenas os quatro últimos dígitos dos valores. Para divergências sem regra respaldada por evidência, o processo não promove o valor inválido como CNPJ canônico. A correção duradoura é solicitar à CVM a retificação do arquivo cadastral, anexando a linha de origem e a evidência oficial; a regra local deve permanecer restrita até a fonte oficial ser corrigida.

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
