---
title: Glossário
sidebar_position: 2
---

# Glossário de Termos

Este glossário define termos técnicos e de negócio usados na documentação do Tucano CVM.

## Termos de Negócio

### CVM (Comissão de Valores Mobiliários)
Autarquia federal vinculada ao Ministério da Fazenda, responsável por disciplinar, fiscalizar e desenvolver o mercado de capitais no Brasil.

### Companhia Aberta
Empresa que possui valores mobiliários (ações, debêntures, etc.) negociados em bolsa de valores ou no mercado de balcão organizado.

### Código CVM
Identificador numérico único atribuído pela CVM a cada companhia aberta registrada.

### CNPJ (Cadastro Nacional da Pessoa Jurídica)
Número de 14 dígitos que identifica empresas no Brasil. Formato: `XX.XXX.XXX/XXXX-XX`.

### DFP (Demonstrações Financeiras Padronizadas)
Documentos contábeis anuais auditados das companhias abertas. Incluem balanço patrimonial, DRE, fluxo de caixa, etc.

### ITR (Informações Trimestrais)
Documentos contábeis trimestrais das companhias abertas. Versão simplificada das DFPs.

### FRE (Formulário de Referência)
Documento abrangente com informações sobre a companhia: estrutura acionária, governança, remuneração, fatores de risco, etc.

### FCA (Formulário Cadastral)
Documento com informações cadastrais completas da companhia: endereços, DRI, auditores, valores mobiliários.

### IPE (Informações Periódicas e Eventuais)
Metadados de documentos não estruturados: fatos relevantes, avisos aos acionistas, assembleias, etc.

### VLMO (Valores Mobiliários Negociados e Detidos)
Informações sobre negociações e posições de insiders (administradores, controladores).

### CGVN (Código de Governança Corporativa)
Informe sobre adoção de práticas de governança corporativa recomendadas ("pratique ou explique").

### Fato Relevante
Comunicado obrigatório ao mercado sobre eventos que podem influenciar o preço dos valores mobiliários.

### Insider
Administrador, conselheiro, controlador ou pessoa com acesso a informações privilegiadas.

### Reapresentação
Correção de documento já entregue à CVM. Cada reapresentação incrementa o campo `VERSAO`.

### Consolidado
Demonstrações financeiras que incluem a holding e todas as suas controladas (grupo econômico).

### Individual
Demonstrações financeiras apenas da holding-mãe, sem consolidar controladas.

## Termos Técnicos

### Pipeline de Ingestão
Sequência de etapas para baixar, validar, normalizar e persistir dados da CVM.

### Fase 1 (Pré-processamento)
Download do arquivo, extração de metadados, persistência de payloads brutos.

### Fase 2 (Ingestão)
Leitura dos dados, normalização, resolução de identidade, promoção para tabelas de domínio.

### Remote Probe
Sondagem remota (HTTP HEAD, CKAN) para detectar alterações antes do download.

### SHA-256
Hash criptográfico usado para verificar integridade de arquivos e evitar reprocessamento.

### Staging
Tabela temporária (`ingestion_rows`) onde linhas são carregadas antes da promoção.

### Promoção
Escrita de dados normalizados nas tabelas de domínio permanentes.

### Reconcile
Remoção de linhas obsoletas das tabelas de domínio após atualização de dados.

### Quarentena
Fila de linhas rejeitadas por erro real, aguardando correção ou replay.

### Replay
Reprocessamento de itens em quarentena ou runs completas.

### Grafo de Identidade
Estrutura em memória que mapeia CNPJs e códigos CVM para companhias.

### Resolução de Identidade
Processo de vincular cada linha de dados a uma companhia registrada.

### Quality Gate
Verificação de qualidade ao final do processamento (ex: máximo 1% de companhias não encontradas).

### Change Tracking
Rastreamento de mudanças estruturais entre execuções (membros adicionados/removidos, headers alterados).

### Self-healing
Capacidade de reconstruir arquivos CSV a partir de payloads brutos persistidos no banco.

### Safe Promote Chunk
Mecanismo resiliente de promoção que usa savepoints para isolar falhas por linha.

### Celery
Framework de processamento assíncrono baseado em filas de mensagens.

### Celery Beat
Agendador de tarefas periódicas do Celery.

### Broker
Servidor de mensagens (Redis) que distribui tarefas para workers.

### Worker
Processo que consome e executa tarefas da fila.

### Task
Unidade de trabalho assíncrona executada por um worker.

### Chord
Padrão do Celery para executar tarefas em paralelo e agregar resultados.

### Chain
Padrão do Celery para executar tarefas em sequência.

### Alembic
Ferramenta de migração de banco de dados para SQLAlchemy.

### Pydantic
Biblioteca de validação de dados usando type hints do Python.

### FastAPI
Framework web moderno para construção de APIs REST com Python.

### SQLAlchemy
ORM (Object-Relational Mapping) para Python.

### PostgreSQL
Banco de dados relacional open-source.

### Redis
Banco de dados em memória usado como broker de mensagens.

### Docker Compose
Ferramenta para definir e executar aplicações multi-container.

### OpenAPI
Especificação para descrever APIs REST.

### Swagger UI
Interface interativa para explorar APIs OpenAPI.

## Termos de API

### Endpoint
URL específica da API que aceita requisições HTTP.

### Request
Requisição HTTP enviada pelo cliente à API.

### Response
Resposta HTTP retornada pela API ao cliente.

### Header
Metadados HTTP enviados na requisição ou resposta.

### Bearer Token
Token de autenticação enviado no header `Authorization: Bearer <token>`.

### JWT (JSON Web Token)
Token compacto e autônomo que contém claims JSON assinadas.

### Paginação
Técnica para dividir resultados em páginas menores.

### Query Parameter
Parâmetro passado na URL para filtrar ou modificar a resposta.

### Path Parameter
Parâmetro passado na URL como parte do caminho.

### Schema
Definição da estrutura de dados (request/response).

### Validation Error
Erro retornado quando os dados de entrada não atendem às validações.

### HTTP Status Code
Código numérico que indica o resultado da requisição (200, 404, 500, etc.).

### Idempotência
Propriedade de uma operação que pode ser executada múltiplas vezes sem mudar o resultado.

### Streaming
Técnica para transmitir grandes volumes de dados gradualmente.

### Alias
Nome curto para um dataset ou endpoint (ex: `bpa_ind` para `demonstracao_balanco_patrimonial_ativo_individual`).

## Termos de Dados

### Dataset
Conjunto de dados estruturados (tabela, arquivo CSV).

### Member
Arquivo CSV dentro de um pacote ZIP da CVM.

### Row Kind
Tipo interno de linha (ex: `dfp_documento`, `fre_auditor`).

### Natural Key
Chave de negócio única que identifica um registro (ex: `CNPJ + DT_REFER + VERSAO`).

### Hash Origem
Hash criptográfico dos dados brutos para idempotência.

### Valor Contábil
Valor monetário de uma linha de demonstração financeira.

### Escala Moeda
Multiplicador aplicado ao valor contábil (UNIDADE=1, MIL=1000, MILHAO=1000000).

### Valor Normalizado
Valor contábil já ajustado pela escala (valor absoluto em reais).

### Valor Reportado
Valor bruto como informado pela CVM (antes da aplicação da escala).

### Proveniência
Metadados que rastreiam a origem de cada dado (fonte, dataset, linha, documento).

### YoY (Year over Year)
Variação percentual em relação ao mesmo período do ano anterior.

### QoQ (Quarter over Quarter)
Variação percentual em relação ao trimestre anterior.

### CAGR (Compound Annual Growth Rate)
Taxa de crescimento anual composta ao longo de múltiplos anos.

## Siglas e Abreviações

| Sigla | Significado |
|-------|-------------|
| API | Application Programming Interface |
| BPA | Balanço Patrimonial do Ativo |
| BPP | Balanço Patrimonial do Passivo |
| DRE | Demonstração do Resultado do Exercício |
| DFC | Demonstração de Fluxos de Caixa |
| DMPL | Demonstração das Mutações do Patrimônio Líquido |
| DRA | Demonstração de Resultado Abrangente |
| DVA | Demonstração de Valor Adicionado |
| EBITDA | Earnings Before Interest, Taxes, Depreciation and Amortization |
| ESG | Environmental, Social and Governance |
| FK | Foreign Key (Chave Estrangeira) |
| HTTP | HyperText Transfer Protocol |
| JSON | JavaScript Object Notation |
| OPA | Oferta Pública de Aquisição |
| ORM | Object-Relational Mapping |
| PCD | Pessoa com Deficiência |
| PLR | Participação nos Lucros e Resultados |
| REST | Representational State Transfer |
| RI | Relações com Investidores |
| ROA | Return on Assets |
| ROE | Return on Equity |
| SHA | Secure Hash Algorithm |
| SLA | Service Level Agreement |
| SQL | Structured Query Language |
| UUID | Universally Unique Identifier |

## Exemplos de Uso

### Exemplo 1: Reapresentação
```
Petrobras enviou DFP 2024 três vezes:
- Versão 1: Entrega original em 2025-03-15
- Versão 2: Correção em 2025-04-10
- Versão 3: Correção final em 2025-05-20

Para obter os dados mais recentes, filtre por VERSAO=3.
```

### Exemplo 2: Escala Moeda
```json
{
  "valor_conta_reportado": 740500.0,
  "escala_moeda": "MIL",
  "fator_escala_moeda": 1000,
  "valor_conta": 740500000.0  // 740500 × 1000
}
```

### Exemplo 3: Resolução de Identidade
```
Linha com CNPJ=08773135000100 e COD_CVM=25224
→ Busca no grafo de identidade
→ Encontrada: "2W ECOBANK S.A."
→ Status: RESOLVED (confiança alta)
```

### Exemplo 4: Quarentena
```
Linha com CNPJ=99999999999999 (inexistente)
→ Busca no grafo de identidade
→ Não encontrada
→ Status: NOT_FOUND
→ Enviada para quarentena com motivo: "companhia_nao_encontrada"
```