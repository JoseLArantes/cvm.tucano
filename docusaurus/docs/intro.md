---
title: Introdução
sidebar_position: 1
---

# Tucano CVM

O **Tucano CVM** transforma dados públicos da Comissão de Valores Mobiliários (CVM) sobre companhias abertas brasileiras em uma base consultável, organizada e rastreável. Em vez de cada pessoa ou sistema precisar baixar arquivos ZIP, abrir CSVs, entender layouts regulatórios e reconciliar versões, o serviço centraliza esse trabalho e expõe as informações por APIs consistentes.

> **Escopo atual:** o projeto trata dados da CVM relacionados a companhias abertas. Ele não cobre, neste momento, fundos de investimento, participantes de mercado, processos sancionadores ou outros domínios regulatórios fora desse recorte.

## Contexto e propósito

Os dados abertos da CVM são essenciais para análise financeira, acompanhamento societário, auditoria, produtos de dados e rotinas de compliance. Ainda assim, o uso direto desses arquivos costuma exigir esforço recorrente:

- localizar a fonte correta para cada pergunta;
- baixar pacotes por ano, documento e tipo de informação;
- lidar com layouts diferentes entre Cadastro, DFP, ITR, FRE, FCA, IPE, VLMO e CGVN;
- identificar a companhia correta a partir de CNPJ, código CVM e documentos reapresentados;
- normalizar datas, valores monetários, escalas, textos e campos ausentes;
- acompanhar alterações, falhas de ingestão e reapresentações;
- repetir a mesma preparação de dados em cada planilha, integração ou aplicação.

O Tucano CVM reduz esse custo operacional. Ele atua como uma camada confiável entre os arquivos regulatórios brutos e os consumidores que precisam consultar, comparar, auditar ou incorporar esses dados em outros produtos.

## Público

Esta documentação atende públicos diferentes, não apenas desenvolvedores:

- **analistas financeiros** que precisam consultar demonstrações, séries históricas, estrutura de capital, remuneração, governança e eventos corporativos;
- **auditoria e compliance** que precisam rastrear origem, data de recebimento, versões, alterações e qualidade dos dados;
- **times de dados e produtos** que precisam alimentar painéis, modelos, rotinas operacionais e integrações internas;
- **operações** que precisam monitorar sincronizações, aprovar atualizações, tratar quarentena e acompanhar falhas;
- **desenvolvedores** que integram sistemas com a API ou evoluem o backend.

Se o seu objetivo é entender o que a plataforma entrega, esta introdução é o ponto de partida. Se o objetivo é integrar ou operar a API, as próximas seções da documentação entram nos detalhes.

## Cobertura funcional

O serviço organiza a informação pública da CVM em torno da entidade central **companhia**. A partir dela, os demais conjuntos de dados podem ser consultados por identificadores como código CVM, CNPJ, período, tipo de documento, versão, categoria ou escopo.

Na prática, o Tucano CVM oferece:

- **cadastro consolidado de companhias abertas**, com situação regulatória, setor, responsáveis, auditor e dados de contato;
- **demonstrações financeiras DFP e ITR**, incluindo documentos, contas contábeis, composição de capital e pareceres;
- **dados do Formulário de Referência (FRE)** sobre capital social, posição acionária, administradores, remuneração, empregados, valores mobiliários e informações relacionadas;
- **dados do Formulário Cadastral (FCA)** sobre dados gerais, endereços, DRI, auditores e valores mobiliários;
- **documentos IPE** para acompanhamento de eventos periódicos e eventuais;
- **VLMO** para valores mobiliários negociados e detidos por administradores, controladores e pessoas vinculadas;
- **CGVN** para práticas declaradas no Código Brasileiro de Governança Corporativa;
- **camada analítica** com métricas, séries, comparações, qualidade, sinais, eventos, reapresentações e resumos por companhia;
- **monitoramento de ingestão e atualizações**, com histórico operacional, quarentena, replay, auditoria de fontes e aprovação de mudanças detectadas.

## Fontes de dados

| Fonte | O que representa | Uso comum |
| --- | --- | --- |
| **Cadastro** | Cadastro de companhias abertas | Identificação da companhia, situação de registro, setor, auditor e responsáveis |
| **DFP** | Demonstrações financeiras anuais | Análise anual, contas contábeis, pareceres e composição de capital |
| **ITR** | Informações trimestrais | Acompanhamento trimestral e evolução intra-anual |
| **FRE** | Formulário de Referência | Estrutura societária, administração, remuneração, empregados e valores mobiliários |
| **FCA** | Formulário Cadastral | Dados cadastrais complementares, DRI, auditores e instrumentos emitidos |
| **IPE** | Informações periódicas e eventuais | Fatos relevantes, avisos, assembleias, políticas e outros documentos divulgados |
| **VLMO** | Valores mobiliários negociados e detidos | Movimentações e posições de administradores, controladores e pessoas vinculadas |
| **CGVN** | Código de Governança Corporativa | Práticas de governança declaradas pelas companhias |

Cada fonte mantém sua finalidade regulatória original, mas o Tucano CVM padroniza a forma de consulta e preserva metadados de origem para rastreabilidade.

## Fluxo da informação

O ciclo de dados começa nas fontes oficiais da CVM e termina em respostas estruturadas para consulta:

1. O serviço verifica os arquivos públicos disponíveis.
2. Quando há dados a processar, os arquivos são baixados, identificados e preparados.
3. As linhas passam por validação, normalização e resolução de identidade da companhia.
4. Registros válidos são promovidos para as tabelas de domínio.
5. Alterações, falhas, itens em quarentena e execuções ficam disponíveis para monitoramento.
6. A camada analítica pode materializar resultados canônicos para acelerar consultas e preservar o histórico conhecido em cada data.

Esse fluxo permite responder não só “qual é o dado atual?”, mas também “de onde ele veio?”, “quando foi sincronizado?”, “qual versão do documento foi usada?” e “o que era conhecido em determinada data?”.

## Rastreabilidade e qualidade

A plataforma foi desenhada para preservar contexto operacional. Sempre que possível, os dados carregam referências ao arquivo de origem, ano, linha, versão documental, data de recebimento, momento de sincronização e momento de alteração real.

Isso é importante porque dados regulatórios mudam. Companhias reapresentam documentos, arquivos podem ganhar novas versões, campos podem chegar incompletos e algumas linhas podem exigir tratamento manual. O Tucano CVM não tenta esconder esses casos: ele registra falhas, separa itens problemáticos em quarentena, permite replay e oferece painéis de acompanhamento da ingestão.

## Camada analítica

Além de expor os dados normalizados, o projeto possui endpoints analíticos em `/analise/companhias/...`. Essa camada organiza métricas, séries históricas, comparações, diagnósticos de qualidade, sinais determinísticos, eventos e reapresentações por companhia.

As respostas analíticas deixam explícito se o resultado veio da camada canônica materializada ou de uma resolução em tempo de consulta. Também indicam unidades, escopo societário, base temporal e cortes informacionais quando aplicável. Isso ajuda consumidores a interpretar corretamente valores, variações e comparações históricas.

## Operação e atualizações

A ingestão é tratada como uma operação crítica. O sistema mantém registros de execuções, etapas do pipeline, alterações detectadas, status de arquivos, itens em quarentena e histórico de reprocessamento.

O serviço de atualizações separa a detecção de mudanças da ingestão física. Primeiro ele identifica alterações nas fontes públicas; depois uma operação autorizada pode analisar, aprovar e disparar a importação. Essa separação evita reprocessamentos desnecessários e dá mais controle sobre quando dados novos entram na base.

## Navegação recomendada

Use esta sequência se estiver conhecendo o projeto:

1. **Primeiros passos**: instalação, autenticação e primeira consulta.
2. **Conceitos**: modelo de dados, pipeline de ingestão, identidade e quarentena.
3. **Fontes de dados**: explicação de cada fonte CVM coberta.
4. **Endpoints da API**: rotas disponíveis para consulta, análise, ingestão e administração.
5. **Schemas**: contratos de resposta e formatos de dados.
6. **Referência**: glossário, troubleshooting e changelog.

Para uso funcional, comece por **Companhias**, **Financeiro**, **FRE**, **IPE** e **Análise**. Para operação da plataforma, priorize **Administração da ingestão**, **Monitoramento**, **Quarentena** e **Serviço de atualizações**.

## Recursos externos

- [Portal de Dados Abertos da CVM](https://dados.cvm.gov.br/)
- [Site oficial da CVM](https://www.gov.br/cvm/pt-br)
- [Consulta Cadastral de Companhias](https://www.gov.br/cvm/pt-br/assuntos/regulados/consultas/companhias)
