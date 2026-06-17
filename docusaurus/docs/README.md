---
title: Guia da Documentacao
sidebar_position: 0
---

# Guia da Documentacao do Tucano CVM

O **Tucano CVM** e uma API e pipeline de ingestao voltados para transformar os arquivos publicos da CVM em dados consultaveis, consistentes e adequados para uso operacional. Em vez de depender diretamente de ZIPs, CSVs e layouts regulatorios heterogeneos, o projeto centraliza a captura, a normalizacao, a rastreabilidade e a exposicao desses dados por meio de endpoints HTTP e processos assincronos.

> **Nota de escopo:** neste momento, o projeto trata apenas dados da CVM relacionados a companhias.

## Intencao do Projeto

O objetivo do Tucano CVM e reduzir o custo tecnico de trabalhar com informacoes regulatorias de companhias abertas brasileiras. O projeto foi desenhado para:

- consolidar multiplas fontes da CVM em um modelo de dados mais estavel;
- permitir consultas por companhia, periodo, documento e categoria sem repetir a logica de parsing em cada consumidor;
- preservar proveniencia e historico de sincronizacao para auditoria, reprocessamento e investigacao de divergencias;
- oferecer uma base confiavel para produtos internos, integracoes, analises financeiras e operacoes de compliance.

## Publico-Alvo

Esta documentacao foi escrita principalmente para:

- **desenvolvedores** que integram clientes com a API ou evoluem o backend;
- **analistas financeiros** que precisam consultar DFP, ITR, FRE, FCA, IPE, VLMO e CGVN de forma estruturada;
- **times de dados e operacoes** que monitoram ingestao, quarentena e replay;
- **auditoria e compliance** que precisam de rastreabilidade sobre origem, alteracoes e cobertura dos dados.

## O Que Voce Encontra Aqui

Se estiver chegando agora ao projeto, comece por esta sequencia:

1. **[Introducao](./intro.md)** para entender o problema que o Tucano CVM resolve.
2. **[Instalacao e Configuracao](./getting-started/installation.md)** para subir o ambiente local.
3. **[Autenticacao](./getting-started/authentication.md)** para criar usuarios e obter tokens.
4. **[Inicio Rapido](./getting-started/quickstart.md)** para fazer as primeiras consultas.

Se o foco for uso funcional da API, os atalhos mais importantes sao:

- **[Companhias](./api-endpoints/companhias.md)** para busca cadastral e agregacao por companhia;
- **[Financeiro](./api-endpoints/financeiro.md)** para DFP e ITR;
- **[FRE](./api-endpoints/fre.md)** para estrutura acionaria, administracao e remuneracao;
- **[IPE](./api-endpoints/ipe.md)** para eventos e documentos periodicos/eventuais;
- **[Analise](./api-endpoints/analise.md)** para visoes consolidadas e metricas derivadas.

Se o foco for operacao da plataforma, va direto para:

- **[Visao Geral da Ingestao](./ingestion/overview.md)**;
- **[Disparo de Sincronizacoes](./ingestion/dispatch.md)**;
- **[Monitoramento](./ingestion/monitoring.md)**;
- **[Quarentena e Replay](./ingestion/quarantine.md)**;
- **[Reconstrucao de Identidade](./ingestion/identity.md)**.

## Visao Tecnica

No nivel tecnico, o projeto combina:

- **FastAPI** para a superficie HTTP e a exposicao do OpenAPI da instancia em execucao;
- **PostgreSQL** como armazenamento principal dos dados normalizados;
- **Celery + Redis** para execucao assincrona, paralelismo e retentativas;
- um pipeline de ingestao em fases, com staging, validacao, reconciliacao e promocao para tabelas de dominio;
- schemas e contratos consistentes para paginacao, filtros, erros e respostas agregadas.

As fontes documentadas incluem cadastro de companhias, demonstracoes financeiras, formularios cadastrais, formularios de referencia, informacoes periodicas e eventuais, movimentacoes de insiders e praticas de governanca.

## Estrutura da Documentacao

- **Primeiros Passos**: instalacao, autenticacao e uso inicial.
- **Conceitos**: pipeline, modelo de dados, identidade e quarentena.
- **Fontes de Dados**: detalhes de cada conjunto publico da CVM suportado.
- **API Endpoints**: referencia funcional da API.
- **Administracao da Ingestao**: operacao do pipeline.
- **Schemas**: contratos de request/response e modelos principais.
- **Referencia**: glossario, changelog e solucao de problemas.

## Detalhes Importantes

- O ambiente local documentado nesta base usa a API em `http://localhost:8007`.
- O endpoint de healthcheck real retorna `{"status": "ok"}`.
- O OpenAPI e o Swagger UI pertencem a **uma instancia em execucao da API**, normalmente em `/openapi.json` e `/docs`, e nao a este site estatico no GitHub Pages.

## Recursos Externos

- [Portal de Dados Abertos da CVM](https://dados.cvm.gov.br/)
- [Site oficial da CVM](https://www.gov.br/cvm/pt-br)
- [Repositorio do projeto](https://github.com/JoseLArantes/cvm.tucano)

## Contribuicao

Para ajustar a documentacao:

1. edite os arquivos Markdown em `docusaurus/docs/`;
2. valide localmente com `npm start` ou `npm run build`;
3. confirme se exemplos, portas, rotas e nomes batem com a implementacao real da API.
