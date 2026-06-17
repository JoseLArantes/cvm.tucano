---
title: Changelog da API
sidebar_position: 3
---

# Changelog da API

Este documento registra mudanças significativas na API do Tucano CVM.

## Versão 0.1.0 (Atual)

**Data**: Junho 2026

### Funcionalidades Principais

#### Autenticação e Usuários
- `POST /auth/login` - Login com username e senha
- `GET /auth/me` - Obter usuário autenticado
- `GET /usuarios` - Listar usuários (admin)
- `POST /usuarios` - Criar usuário (admin)
- `PATCH /usuarios/{id}` - Atualizar usuário (admin)
- `DELETE /usuarios/{id}` - Excluir usuário (admin)

#### Companhias
- `GET /companhias` - Listar companhias com filtros
- `GET /companhias/codigo-cvm/{codigo_cvm}` - Buscar por código CVM
- `GET /companhias/{cnpj_companhia}` - Buscar por CNPJ
- `GET /companhias/mestre` - Consulta agregada (master endpoint)

#### Análise Estratégica
- `GET /companhias/{codigo_cvm}/analise/overview` - Visão geral
- `GET /companhias/{codigo_cvm}/analise/financeiro` - Métricas financeiras com YoY/CAGR
- `GET /companhias/{codigo_cvm}/analise/comparativo` - Comparação anual
- `GET /companhias/{codigo_cvm}/analise/eventos` - Timeline de eventos
- `GET /companhias/{codigo_cvm}/analise/pessoas-remuneracao` - Remuneração e diversidade
- `GET /companhias/{codigo_cvm}/analise/mercado-insiders` - Insider trading
- `GET /companhias/{codigo_cvm}/analise` - Análise consolidada

#### Dados Financeiros (DFP/ITR)
- `GET /dfp/documentos` - Listar documentos DFP
- `GET /itr/documentos` - Listar documentos ITR
- `GET /dfp/composicao-capital` - Composição de capital DFP
- `GET /itr/composicao-capital` - Composição de capital ITR
- `GET /dfp/pareceres` - Pareceres DFP
- `GET /itr/pareceres` - Pareceres ITR
- `GET /dfp/balanco-patrimonial-ativo/{escopo}` - BPA consolidado/individual
- `GET /dfp/balanco-patrimonial-passivo/{escopo}` - BPP consolidado/individual
- `GET /dfp/demonstracao-resultado/{escopo}` - DRE consolidado/individual
- `GET /dfp/fluxo-caixa-metodo-direto/{escopo}` - DFC direto
- `GET /dfp/fluxo-caixa-metodo-indireto/{escopo}` - DFC indireto
- `GET /dfp/mutacoes-patrimonio-liquido/{escopo}` - DMPL
- `GET /dfp/resultado-abrangente/{escopo}` - DRA
- `GET /dfp/valor-adicionado/{escopo}` - DVA
- (Mesmos endpoints para ITR)

#### Formulário de Referência (FRE)
- `GET /fre/documentos` - Listar documentos FRE
- `GET /fre/auditores` - Auditores independentes
- `GET /fre/capital-social` - Capital social
- `GET /fre/posicao-acionaria` - Posição acionária
- `GET /fre/remuneracao/total-por-orgao` - Remuneração por órgão
- `GET /fre/empregados/posicao-genero` - Empregados por gênero
- `GET /fre/participacoes-sociedades` - Participações em sociedades
- `GET /fre/relacoes-familiares` - Relações familiares
- (Mais de 40 endpoints FRE no total)

#### Formulário Cadastral (FCA)
- `GET /fca/documentos` - Listar documentos FCA
- `GET /fca/geral` - Dados gerais
- `GET /fca/enderecos` - Endereços
- `GET /fca/dri` - Diretor de RI
- `GET /fca/auditores` - Auditores
- `GET /fca/valores-mobiliarios` - Valores mobiliários
- `GET /fca/departamento-acionistas` - Departamento de acionistas

#### Informações Periódicas e Eventuais (IPE)
- `GET /ipe/documentos` - Listar documentos IPE
- `GET /ipe/documentos/agregados` - Contagem agrupada

#### Valores Mobiliários (VLMO)
- `GET /vlmo/documentos` - Listar documentos VLMO
- `GET /vlmo/consolidado` - Negociações de insiders

#### Governança Corporativa (CGVN)
- `GET /cgvn/documentos` - Listar documentos CGVN
- `GET /cgvn/praticas` - Práticas adotadas

#### Fontes e Exportação
- `GET /fontes` - Listar fontes CVM
- `GET /fontes/{fonte}/datasets` - Listar datasets de uma fonte
- `GET /exportacoes/{fonte}/{dataset}` - Exportação em lote (streaming)

#### Ingestion Admin
- `POST /ingestion/sincronizacoes/cadastro` - Sincronizar cadastro
- `POST /ingestion/sincronizacoes/dfp/{ano}` - Sincronizar DFP
- `POST /ingestion/sincronizacoes/itr/{ano}` - Sincronizar ITR
- `POST /ingestion/sincronizacoes/fre/{ano}` - Sincronizar FRE
- `POST /ingestion/sincronizacoes/fca/{ano}` - Sincronizar FCA
- `POST /ingestion/sincronizacoes/ipe/{ano}` - Sincronizar IPE
- `POST /ingestion/sincronizacoes/vlmo/{ano}` - Sincronizar VLMO
- `POST /ingestion/sincronizacoes/cgvn/{ano}` - Sincronizar CGVN
- `POST /ingestion/sincronizacoes/tudo/{ano}` - Sincronizar todas as fontes
- `POST /ingestion/sincronizacoes/reprocessar-arquivo` - Reprocessamento seletivo
- `POST /ingestion/sincronizacoes/pre-processar/cadastro` - Fase 1 do cadastro
- `POST /ingestion/sincronizacoes/pre-processar/{tipo_fonte}/{ano}` - Fase 1 de fonte anual
- `POST /ingestion/sincronizacoes/{id_execucao}/ingerir` - Fase 2
- `POST /ingestion/sincronizacoes/cancelar` - Cancelar sincronização
- `GET /ingestion/sincronizacoes` - Listar execuções
- `GET /ingestion/sincronizacoes/{id_execucao}` - Detalhar execução
- `GET /ingestion/runs` - Listar runs
- `GET /ingestion/runs/{run_id}` - Detalhar run
- `GET /ingestion/dashboard` - Dashboard consolidado
- `GET /ingestion/alteracoes` - Histórico de alterações
- `GET /ingestion/quarentena` - Listar quarentena
- `GET /ingestion/quarentena/resumo` - Resumo da quarentena
- `POST /ingestion/replay/quarentena` - Replay de quarentena
- `POST /ingestion/runs/{run_id}/replay` - Replay de run
- `POST /ingestion/identity/rebuild` - Reconstruir identidade
- `GET /ingestion/fontes` - Listar fontes registradas
- `GET /ingestion/fontes/{fonte}` - Detalhar fonte
- `POST /ingestion/fontes/auditar` - Auditar fontes

### Características Técnicas

#### Paginação Uniforme
Todas as listagens retornam:
```json
{
  "dados": [...],
  "paginacao": {
    "pagina": 1,
    "tamanho_pagina": 100,
    "total": 1250
  }
}
```

#### Valores Monetários
- `valor_conta`: Valor absoluto em reais (ajustado por escala)
- `valor_conta_reportado`: Valor bruto da CVM
- `escala_moeda`: UNIDADE, MIL ou MILHAO
- `fator_escala_moeda`: 1, 1000 ou 1000000

#### Campos de Rastreabilidade
Todos os registros incluem:
- `arquivo_origem`: CSV de origem
- `ano_origem`: Ano do ZIP
- `linha_origem`: Linha no CSV
- `criado_em`: Timestamp de criação
- `sincronizado_em`: Última sincronização
- `alterado_em`: Última alteração real

#### Autenticação
- Tokens Bearer JWT
- TTL padrão: 480 minutos (8 horas)
- Header: `Authorization: Bearer <token>`

#### Limites
- `tamanho_pagina`: máximo 500
- Exportações: máximo 100.000 registros
- `limite_por_endpoint` (mestre): máximo 500

### Breaking Changes

Nenhum breaking change nesta versão inicial.

### Deprecations

Nenhuma deprecation nesta versão inicial.

### Melhorias Futuras Planejadas

#### Versão 0.2.0 (Planejada)
- Suporte completo para todos os 48 datasets do FRE
- Endpoints de busca full-text
- Webhooks para eventos de sincronização
- Rate limiting por usuário
- Métricas Prometheus expostas via API

#### Versão 0.3.0 (Planejada)
- Suporte a GraphQL
- Endpoints de agregação customizável
- Exportação em Parquet
- Cache distribuído (Redis)
- Multi-tenancy

#### Versão 1.0.0 (Planejada)
- Estabilização da API
- SLA garantido
- Documentação OpenAPI completa
- SDKs oficiais (Python, JavaScript, Go)
- Sandbox para testes

## Histórico de Mudanças

### 2026-06-17
- Documentação inicial completa
- 100+ endpoints documentados
- Guias de troubleshooting e glossário

### 2026-06-15
- Implementação do pipeline de ingestão v2
- Suporte a 8 fontes CVM
- Sistema de quarentena e replay

### 2026-06-10
- Implementação da resolução de identidade em 5 estratégias
- Grafo de identidade em memória
- Regras de reparo configuráveis

### 2026-06-05
- Implementação da Fase 1 e Fase 2 do pipeline
- Self-healing com payloads brutos
- Reconcile set-based

### 2026-06-01
- Implementação do Celery Beat para sincronizações diárias
- Bootstrap automático de dados iniciais
- Sistema de retries com backoff exponencial

### 2026-05-28
- Implementação dos endpoints de análise estratégica
- Cálculos YoY, QoQ e CAGR
- Sistema de proveniência

### 2026-05-25
- Implementação dos endpoints FRE (48 datasets)
- Normalização de dados de diversidade
- Suporte a remuneração executiva

### 2026-05-20
- Implementação dos endpoints FCA
- Suporte a valores mobiliários
- Integração com auditores

### 2026-05-15
- Implementação dos endpoints IPE
- Suporte a fatos relevantes
- Sistema de agregação

### 2026-05-10
- Implementação dos endpoints VLMO
- Suporte a insider trading
- Monitoramento de negociações

### 2026-05-05
- Implementação dos endpoints CGVN
- Suporte a práticas de governança
- Sistema de scoring

### 2026-05-01
- Implementação dos endpoints financeiros (DFP/ITR)
- Suporte a todas as demonstrações contábeis
- Normalização de escala monetária

### 2026-04-25
- Implementação dos endpoints de companhias
- Suporte a busca por CNPJ e código CVM
- Endpoint mestre agregado

### 2026-04-20
- Implementação do sistema de autenticação
- CRUD de usuários
- Tokens JWT

### 2026-04-15
- Implementação do modelo de dados
- Migrações Alembic
- Tabelas de domínio e operacionais

### 2026-04-10
- Configuração inicial do projeto
- Docker Compose para desenvolvimento
- Estrutura base do FastAPI

## Convenções de Versionamento

Este projeto segue [Semantic Versioning](https://semver.org/lang/pt-BR/):

- **MAJOR** (X.0.0): Mudanças incompatíveis na API
- **MINOR** (0.X.0): Novas funcionalidades compatíveis
- **PATCH** (0.0.X): Correções de bugs compatíveis

## Política de Deprecation

- Endpoints depreciados são mantidos por pelo menos 6 meses
- Deprecations são anunciadas no changelog
- Alternativas são documentadas
- Headers de deprecation são adicionados às responses

## Como Assinar para Atualizações

Para receber notificações de mudanças na API:
1. Watch o repositório no GitHub
2. Assine o changelog via RSS (quando disponível)
3. Entre em contato com a equipe para atualizações prioritárias

## Contato

Para questões sobre a API:
- Abra uma issue no GitHub
- Consulte a documentação
- Entre em contato com a equipe de desenvolvimento