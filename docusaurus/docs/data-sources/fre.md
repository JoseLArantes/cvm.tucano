---
title: Formulário de Referência (FRE)
sidebar_position: 5
---

# Formulário de Referência (FRE)

## O que é FRE

FRE é o Formulário de Referência das companhias abertas. Ele reúne informações estruturadas sobre a companhia, sua estrutura societária, capital, administração, remuneração, auditores, valores mobiliários, empregados, participações e relações declaradas.

No Tucano CVM, o FRE é uma das fontes mais amplas do catálogo. A ingestão reconhece muitos membros do pacote anual, promove os conjuntos já suportados para tabelas próprias e mantém separação entre quadros públicos ativos, histórico processado e datasets ainda sem mapeamento promovido.

## Por que esse conjunto existe

O FRE concentra informações que ajudam a contextualizar a companhia além das demonstrações financeiras. Ele registra quem responde pelo formulário, como o capital é declarado, como a posição acionária aparece no documento, quais remunerações são informadas, quais auditores foram reportados e quais relações relevantes foram declaradas.

Como o formulário pode ter versões e reapresentações, a leitura dos dados deve sempre considerar documento, versão e data de referência.

## Metadados técnicos

| Campo | Valor |
|-------|-------|
| Fonte no sistema | `fre` |
| Distribuição CVM | ZIP anual |
| Arquivo principal | `fre_cia_aberta_{ano}.zip` |
| Primeiro ano no registro da fonte | 2010 |
| Dependência | `cadastro` |
| Tabela documental | `fre_documentos` |
| Chaves de referência | `cnpj_companhia`, `codigo_cvm`, `id_documento`, `versao`, `data_referencia` |

## Arquivos e grupos de dados

O pacote anual contém um cabeçalho documental e diversos membros especializados. A relação abaixo resume os grupos que possuem promoção ou tratamento explícito no sistema.

| Grupo | Exemplos de membros | Situação no sistema |
|-------|---------------------|---------------------|
| Documento | `fre_cia_aberta_{ano}.csv` | Promovido para `fre_documentos`. |
| Auditoria | `fre_cia_aberta_auditor_{ano}.csv` | Promovido para `fre_auditores`. |
| Capital social | `fre_cia_aberta_capital_social_{ano}.csv` | Promovido para `fre_capital_social`. |
| Posição acionária | `fre_cia_aberta_posicao_acionaria_{ano}.csv` | Promovido para `fre_posicoes_acionarias`. |
| Remuneração | `fre_cia_aberta_remuneracao_total_orgao_{ano}.csv` e membros relacionados | Promovido para tabelas de remuneração suportadas. |
| Empregados | membros por posição, local, gênero, raça, faixa etária e PCD | Promovido para tabelas específicas quando suportado. |
| Participações e relações | participações em sociedades, relações familiares, subordinação e partes relacionadas | Promovido para tabelas específicas quando suportado. |
| Valores mobiliários e tesouraria | volumes, titulares, mercados estrangeiros, títulos no exterior, recompra e tesouraria | Promovido para tabelas específicas quando suportado. |
| Datasets sem mapeamento promovido | alguns quadros financeiros, dividendos, endividamento, obrigações e políticas | Catalogados na ingestão como pendentes de mapeamento promovido. |

## Estrutura no Tucano CVM

Os dados promovidos do FRE são organizados por tema, sempre mantendo o vínculo com o documento original.

| Área | Tabelas principais |
|------|--------------------|
| Documento e responsáveis | `fre_documentos`, `fre_responsaveis` |
| Auditoria | `fre_auditores` |
| Capital e distribuição | `fre_capital_social`, `fre_capital_social_classes_acoes`, `fre_capital_social_titulos_conversiveis`, `fre_distribuicao_capital`, `fre_distribuicao_capital_classes_acoes` |
| Posição acionária | `fre_posicoes_acionarias`, `fre_posicoes_acionarias_classes_acoes` |
| Remuneração | `fre_remuneracoes_totais_orgaos`, `fre_remuneracoes_maximas_minimas_medias`, `fre_remuneracoes_variaveis`, `fre_remuneracoes_acoes`, `fre_acoes_entregues` |
| Empregados | tabelas por posição, local, gênero, raça, faixa etária e PCD |
| Administração e relações | administradores, comitês, relações familiares, subordinação e partes relacionadas |
| Valores mobiliários | volumes, outros valores mobiliários, titulares, mercados estrangeiros, títulos no exterior, recompra e tesouraria |

## Endpoints principais

```bash
GET /fre/documentos?codigo_cvm=25224&ano_inicio=2020
GET /fre/auditores?codigo_cvm=25224
GET /fre/capital-social?codigo_cvm=25224
GET /fre/posicao-acionaria?codigo_cvm=25224
GET /fre/remuneracao/total-por-orgao?codigo_cvm=25224&ano_inicio=2024
GET /fre/participacoes-sociedades?codigo_cvm=25224
GET /fre/relacoes-familiares?codigo_cvm=25224
GET /fre/empregados/posicao-genero?codigo_cvm=25224
GET /fre/volume-valor-mobiliario?codigo_cvm=25224
GET /fre/plano-recompra?codigo_cvm=25224
```

A API também expõe endpoints mais específicos para classes de ações, distribuição de capital, remunerações detalhadas, empregados por local ou faixa, declarações de administradores e valores mobiliários em tesouraria.

## Quadros descontinuados pela CVM

Alguns membros do FRE foram explicitamente descontinuados pela CVM a partir do ano de referência de 2024. A API removeu esses quadros do catálogo público quando eles deixaram de ser exigidos, preservando suporte interno para histórico quando o dataset ainda existe em anos anteriores.

Famílias removidas do catálogo público:

- aumentos de capital
- desdobramentos e agrupamentos
- reduções de capital
- direitos e vantagens das ações

Rotas públicas removidas:

- `/fre/capital-social/aumentos`
- `/fre/capital-social/aumentos-classes-acoes`
- `/fre/capital-social/desdobramentos`
- `/fre/capital-social/desdobramentos-classes-acoes`
- `/fre/capital-social/reducoes`
- `/fre/capital-social/reducoes-classes-acoes`
- `/fre/direitos-acoes`

Quadros públicos ativos que permanecem como referência para leituras atuais de capital e distribuição:

- `/fre/capital-social`
- `/fre/capital-social-classes-acoes`
- `/fre/distribuicao-capital`
- `/fre/distribuicao-capital-classes-acoes`
- `/fre/posicao-acionaria`

## Como a ingestão trata a fonte

O membro principal é processado antes dos demais porque ele ancora os filhos pelo documento e pela versão. Cada membro é normalizado conforme o tipo de linha esperado e promovido para a tabela correspondente quando há suporte público.

O processo preserva arquivo, ano, linha e hash de origem. Quando um membro existe no pacote mas ainda não possui tabela pública promovida, ele pode ser reconhecido pelo catálogo de ingestão sem aparecer como endpoint de consulta.

## Como ler os dados

O FRE deve ser lido por documento, versão e data de referência. Quadros diferentes dentro do mesmo formulário podem responder a perguntas distintas: capital social não substitui posição acionária; remuneração total por órgão não substitui quadros de remuneração variável; informações de valores mobiliários no FRE não substituem VLMO.

Para análises históricas, mantenha o vínculo com o documento original e trate mudanças de catálogo da CVM como parte da série. Ausência de um quadro em um ano não significa necessariamente ausência do fato econômico ou societário; pode refletir mudança de exigência, estrutura do pacote ou suporte público da API.
