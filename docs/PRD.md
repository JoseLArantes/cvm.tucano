# Product Requirements Document (PRD): Tucano CVM

## 1. Visão Geral e Propósito
O **Tucano CVM** é uma plataforma de dados (Data Product) projetada para atuar como uma camada intermediária confiável entre os arquivos regulatórios brutos da Comissão de Valores Mobiliários (CVM) e os consumidores finais (analistas, auditores, sistemas de backoffice).

**O Problema:** Os dados abertos da CVM são essenciais para o mercado financeiro, mas seu consumo direto impõe um alto custo operacional. As informações estão fragmentadas em arquivos ZIP anuais, CSVs com layouts heterogêneos, escalas monetárias variáveis e identificadores desencontrados (CNPJ vs. Código CVM), exigindo que cada equipe de dados reimplemente rotinas complexas de extração, limpeza, reconciliação de identidade e auditoria.

**A Solução:** Um serviço centralizado que ingere, normaliza, armazena e expõe esses dados via APIs RESTful consistentes, garantindo **rastreabilidade total** (do JSON da API até a linha exata do CSV original na CVM).

## 2. Escopo do Produto
*   **In-Scope (Escopo Atual):** Dados regulatórios da CVM referentes estritamente a **Companhias Abertas Brasileiras**.
*   **Fontes de Dados Cobertas (8 fontes):**
    1.  `cadastro` (Identidade e situação cadastral)
    2.  `dfp` (Demonstrações Financeiras Padronizadas - Anuais)
    3.  `itr` (Informações Trimestrais)
    4.  `fre` (Formulário de Referência)
    5.  `fca` (Formulário Cadastral)
    6.  `ipe` (Informações Periódicas e Eventuais / Fatos Relevantes)
    7.  `vlmo` (Valores Mobiliários negociados e detidos por insiders)
    8.  `cgvn` (Código de Governança Corporativa)
*   **Out-of-Scope (Fora do Escopo):** Fundos de investimento, participantes de mercado (corretoras/distribuidoras), processos sancionadores e outros domínios regulatórios.

## 3. Personas e Casos de Uso
| Persona | Necessidade Principal | Como o Tucano CVM atende |
| :--- | :--- | :--- |
| **Analista Financeiro** | Construir modelos de valuation, séries históricas (YoY, QoQ) e dashboards fundamentalistas. | API Analítica (`/analise/*`) com métricas canônicas, comparações prontas e endpoint `/companhias/mestre` para visão consolidada. |
| **Auditor / Compliance** | Validar a origem de um dado, auditar reapresentações (restatements) e justificar números para órgãos reguladores. | Rastreabilidade nativa (`arquivo_origem`, `linha_origem`, `hash`), separação entre `sincronizado_em` e `alterado_em`, e endpoints de quarentena. |
| **Engenheiro de Dados** | Integrar dados da CVM em Data Lakes/Warehouses sem lidar com a complexidade dos ZIPs da CVM. | API REST paginada, suporte a exportação CSV, webhooks/filas de atualização e OpenAPI (Swagger) para geração de SDKs. |
| **Operador de Backoffice** | Monitorar a saúde da base, tratar falhas de ingestão e aprovar mudanças estruturais. | Dashboard operacional, Serviço de Atualizações (detecção prévia) e fluxo de *Quarantine & Replay*. |

---

## 4. Requisitos Funcionais (Core Features)

### 4.1. Pipeline de Ingestão (ETL/ELT)
O pipeline deve operar em **duas fases estruturadas** para garantir resiliência e *self-healing*:
*   **Fase 1: Pré-processamento (Aquisição)**
    *   **Sondagem Remota (Remote Probe):** Verificar `ETag`/`Last-Modified` via HTTP HEAD antes de baixar, evitando tráfego desnecessário.
    *   **Integridade:** Validação de downloads via SHA-256.
    *   **Persistência de Payloads:** Armazenar o conteúdo bruto dos CSVs no banco (como `LargeBinary`) para permitir *replay* sem necessidade de novo download e auditoria forense.
*   **Fase 2: Ingestão (Processamento)**
    *   **Staging de Alta Performance:** Utilizar o protocolo `COPY` do PostgreSQL para carregar CSVs em tabelas temporárias (`ingestion_rows`) em *chunks* (ex: 5.000 linhas).
    *   **Promoção Resiliente:** Falhas em linhas individuais não devem abortar o lote inteiro. Linhas válidas são promovidas para as tabelas de domínio; linhas inválidas vão para a Quarentena.
    *   **Reconciliação:** Remoção automática de registros que não existem mais nas fontes oficiais (obsoletos).

### 4.2. Serviço de Atualizações (Detection-First Workflow)
A ingestão **não deve ser cega/automática** por padrão. O sistema deve seguir um fluxo de descoberta:
1.  **Scanning:** Job diário que detecta mudanças nos metadados remotos dos ZIPs da CVM.
2.  **Deep Analysis:** Baixa temporariamente o pacote, compara hashes dos membros CSVs internos e gera um relatório de "drift" (o que mudou a nível de linha/coluna).
3.  **Disparo Controlado:** O operador (ou um gatilho automatizado configurável) revisa o impacto e autoriza a ingestão física.

### 4.3. Resolução de Identidade (Identity Resolution)
Como a CVM usa CNPJ, Código CVM e nomes de forma inconsistente entre as fontes, o sistema deve implementar um **Grafo de Identidade** com estratégia em cascata (5 níveis) para vincular qualquer linha à entidade raiz `Companhia`:
1.  Identificador Exato (Alta confiança)
2.  Header do Documento (Média confiança)
3.  Regras de Reparo (Mapeamentos manuais criados por operadores)
4.  Tabela Legada
5.  Criação Provisória (Baixa confiança - Fallback)

### 4.4. Gestão de Erros: Quarentena e Replay
*   **Quarentena:** Linhas que falham na normalização, violam schemas, possuem ambiguidade de identidade ou chaves duplicadas devem ser isoladas na tabela `quarantine_items` com o motivo exato (`reason_code`).
*   **Replay:** Capacidade de reprocessar itens da quarentena em 3 níveis (Linha individual, Filtro de Quarentena, ou *Run* inteira) utilizando os *payloads brutos* salvos na Fase 1, sem recarregar os arquivos da CVM.

### 4.5. Superfície HTTP (API REST)
A API deve ser altamente padronizada, prevendo:
*   **Entidade Raiz:** Todas as rotas (exceto catálogos) orbitam a `Companhia` (identificada por `cnpj_companhia` ou `codigo_cvm`).
*   **Endpoint Mestre (`/companhias/mestre`):** Um endpoint agregador estratégico que retorna, em uma única chamada, o cadastro, documentos, balanços, DREs e formulários (FRE/FCA) de uma companhia.
*   **Padrões Comuns:**
    *   *Paginação:* Baseada em `pagina` e `tamanho_pagina` (limite rígido de 500 itens).
    *   *Ordenação:* Via parâmetro `ordenar_por` (suporte a ordem decrescente com prefixo `-`).
    *   *Filtros:* Aceite de CNPJ com ou sem pontuação, intervalos de datas (`data_referencia_inicio/fim`) e anos.
*   **Semântica Monetária:** Exposição de dois campos para valores financeiros:
    *   `valor_conta`: Valor absoluto em Reais (já multiplicado pelo `fator_escala_moeda`). *Focado em análise.*
    *   `valor_conta_reportado`: Valor bruto exato do CSV da CVM. *Focado em auditoria.*
*   **Semântica Temporal (Rastreabilidade):**
    *   `sincronizado_em`: Última vez que o sistema "viu" o registro na CVM (confirmação de existência).
    *   `alterado_em`: Última vez que houve mudança real de negócio (ignora meras reapresentações sem alteração de valores).

### 4.6. Camada Analítica (Analytics Engine)
O sistema deve possuir um motor de análise materializada assíncrono:
*   **Catálogo de Métricas:** Definição versionada de métricas (ex: Receita Líquida, EBITDA) com fórmulas e contas CVM candidatas.
*   **Fila de Materialização:** Processamento em *chunks* via workers (Celery) para gerar séries históricas canônicas.
*   **Gate de Admissão:** O motor analítico deve "pausar" (ficar vermelho) automaticamente se houver uma ingestão de dados ativa, evitando contenção de recursos no banco e garantindo que as métricas não sejam calculadas sobre dados incompletos.
*   **Time-Travel:** Suporte ao parâmetro `as_of` (data de corte informacional) para saber o que era conhecido sobre a companhia em uma data específica no passado, lidando com *restatements* (reapresentações).
*   **Endpoints Analíticos:** Séries, Comparações (YoY, CAGR), Sinais (alertas determinísticos), Qualidade de Dados e Governança.

---

## 5. Requisitos Não-Funcionais e Arquitetura

### 5.1. Modelo de Dados
O banco de dados (PostgreSQL) deve ser estritamente segregado em dois domínios:
1.  **Tabelas de Domínio:** Dados de negócio limpos e normalizados (`companhias`, `demonstracoes_financeiras`, `fre_documentos`, etc.).
2.  **Tabelas Operacionais:** Suporte ao pipeline (`ingestion_runs`, `ingestion_rows`, `quarantine_items`, `pending_updates`).

### 5.2. Observabilidade e Métricas
*   Exposição de métricas no formato **Prometheus**.
*   Métricas obrigatórias:
    *   `cvm_ingestion_resolution_total` (por método e confiança).
    *   `cvm_ingestion_quarantine_total` (por `reason_code`).
    *   `cvm_ingestion_rows_total` (por fonte e status).
*   Endpoints de saúde (`/health`) e dashboards operacionais (`/ingestion/dashboard`).

### 5.3. Segurança e Acesso
*   Autenticação obrigatória via **Bearer Tokens** (JWT) em todos os endpoints (exceto saúde).
*   TTL de token configurável.
*   Controle de acesso baseado em roles (ex: usuários padrão vs. administradores que podem disparar *replays* e *rebuilds* de identidade).

---

## 6. Matriz de Rastreabilidade (Audit Trail)
Para atender requisitos de auditoria (como SOX ou regras do BACEN/CVM), **nenhum dado pode ser inserido nas tabelas de domínio sem as seguintes colunas de metadados**:
*   `arquivo_origem` (ex: `dfp_cia_aberta_2025.csv`)
*   `ano_origem` (ex: `2025`)
*   `linha_origem` (número da linha no CSV original)
*   `id_documento` / `versao` (controle de reapresentações da CVM)
*   Hashes de validação do pacote ZIP baixado.

---

## 7. Critérios de Aceite (Definition of Done)
1.  **Cobertura de Fontes:** O pipeline processa com sucesso as 8 fontes (Cadastro, DFP, ITR, FRE, FCA, IPE, VLMO, CGVN).
2.  **Resiliência:** Uma falha de parsing em 1 linha de um CSV de 500.000 linhas resulta em 1 item na quarentena e 499.999 linhas promovidas.
3.  **Performance:** A API suporta paginação de 500 itens e exportação de até 100.000 registros por requisição.
4.  **Documentação:** A API possui especificação OpenAPI 3.0 (`/openapi.json`) completa, permitindo a geração automática de clientes em Python, TypeScript e Go.
5.  **Auditoria:** É possível pegar um valor monetário retornado pela API (`/dfp/demonstracao-resultado`) e, via UI/DB, clicar e abrir o CSV original da CVM na exata linha que originou aquele número.

---

### Insights do Arquiteto
*   **A genialidade do `updates-service`:** O sistema não tenta "adivinhar" se deve rodar o pipeline. Ele age como um sistema de *Change Data Capture (CDC)* em nível de arquivo HTTP, criando uma "caixa de entrada" (`pending_updates`) que exige aprovação. Isso evita que a CVM derrube o servidor da aplicação com downloads acidentais em loop.
*   **O Gate Analítico:** A separação entre a "Ingestão" (foco em I/O e integridade) e a "Materialização Analítica" (foco em CPU/Memória e matemática financeira) com um *Gate* que interrompe a análise quando a ingestão está rodando é uma escolha de arquitetura madura para evitar *locks* no banco e cálculos baseados em estados inconsistentes.
*   **Foco no Auditor:** A distinção entre `sincronizado_em` (o robô rodou hoje e viu que o documento ainda existe) e `alterado_em` (a companhia mudou o valor do ativo no balanço) é uma "feature" que a maioria dos scrapers de dados ignora, mas que é o Santo Graal para produtos de dados financeiros sérios.
