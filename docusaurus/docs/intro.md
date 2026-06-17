---
title: Tucano CVM - Documentação Técnica
sidebar_position: 1
---

# Tucano CVM - Documentação Técnica

## Visão Geral

Tucano CVM é um serviço FastAPI que baixa, normaliza, armazena e expõe dados públicos da CVM (Comissão de Valores Mobiliários) sobre companhias abertas brasileiras. O serviço transforma dados regulatórios brutos em APIs estruturadas e consultáveis.

> **Nota de escopo:** neste momento, o projeto trata apenas dados da CVM relacionados a companhias.

## Para Quem é Este Projeto

Esta documentação é destinada a:

- **Desenvolvedores de backend** que trabalham com ingestão, normalização e comportamento da API
- **Analistas financeiros profissionais** que precisam consultar dados financeiros e societários de emissores
- **Auditores** que precisam rastrear origem e alteração de cada linha contábil
- **Operadores de backoffice** que precisam automatizar sincronizações de dados regulatórios
- **Gerentes de compliance** que precisam monitorar eventos corporativos e mudanças regulatórias

## O Que Este Serviço Resolve

O consumo direto dos dados da CVM é operacionalmente caro devido a:

- Arquivos distribuídos em múltiplos conjuntos e anos
- Formatos ZIP/CSV com layouts complexos
- Necessidade de entender chaves naturais e relacionamentos entre documentos
- Reapresentações e versões de documentos
- Nomes de colunas técnicos e inconsistências de preenchimento
- Ausência de API pronta para consulta orientada a produto

O Tucano CVM faz a ponte entre o dado regulatório bruto e o dado de aplicação.

## Arquitetura do Sistema

```
┌─────────────────┐
│   CVM Dados     │
│    Abertos      │
└────────┬────────┘
         │
    ┌────▼────┐
    │  API    │ ← FastAPI (HTTP)
    │  HTTP   │
    └────┬────┘
         │
    ┌────▼────┐
    │ Celery  │ ← Workers assíncronos
    │ Workers │
    └────┬────┘
         │
    ┌────▼────┐
    │PostgreSQL│ ← Dados normalizados
    │   16    │
    └─────────┘
```

## Componentes Principais

| Componente | Descrição |
|------------|-----------|
| **API HTTP** | Servidor FastAPI que expõe endpoints REST |
| **Celery Workers** | Processam tarefas assíncronas de ingestão |
| **Celery Beat** | Agenda sincronizações periódicas |
| **Redis** | Broker de mensagens e backend de resultados |
| **PostgreSQL** | Banco de dados relacional principal |

## Fontes de Dados Suportadas

O sistema ingere dados de 8 fontes principais da CVM:

| Fonte | Descrição | Periodicidade | Desde |
|-------|-----------|---------------|-------|
| **Cadastro** | Cadastro de companhias abertas | Diária | Contínuo |
| **DFP** | Demonstrações Financeiras Padronizadas (anuais) | Semanal | 2010 |
| **ITR** | Informações Trimestrais | Semanal | 2011 |
| **FRE** | Formulário de Referência | Semanal | 2010 |
| **FCA** | Formulário Cadastral | Semanal | 2010 |
| **IPE** | Informações Periódicas e Eventuais | Semanal | 2003 |
| **VLMO** | Valores Mobiliários Negociados e Detidos | Semanal | Últimos 5 anos |
| **CGVN** | Código de Governança Corporativa | Semanal | 2018 |

## Como Usar Esta Documentação

Esta documentação está organizada em seções:

1. **Primeiros Passos** - Instalação, autenticação e uso básico
2. **Conceitos** - Pipeline de ingestão, modelo de dados, resolução de identidade
3. **Fontes de Dados** - Detalhes de cada fonte CVM suportada
4. **API Endpoints** - Referência completa de todos os endpoints
5. **Ingestão** - Monitoramento, quarentena, replay e troubleshooting
6. **Referência** - Códigos de erro, paginação, schemas

## Links Úteis

- [Portal de Dados Abertos da CVM](https://dados.cvm.gov.br/)
- [Site Oficial da CVM](https://www.gov.br/cvm/pt-br)
- [Consulta Cadastral de Companhias](https://www.gov.br/cvm/pt-br/assuntos/regulados/consultas/companhias)

## Suporte

Para questões técnicas, consulte as seções de troubleshooting ou abra uma issue no repositório do projeto.