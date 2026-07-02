# Roadmap de Implementação do Model Context Protocol (MCP) no Tucano CVM

Este documento apresenta o plano detalhado de implementação de um servidor **Model Context Protocol (MCP)** para o projeto `tucano-cvm`. O objetivo é expor capacidades analíticas, operacionais e de diagnóstico do sistema diretamente para assistentes de IA (como Cursor, Claude Desktop e outros clientes habilitados para MCP), otimizando o fluxo de análise de dados corporativos da CVM e simplificando o monitoramento de pipelines de ingestão e materialização.

---

## 1. O que é o Model Context Protocol (MCP)?

O **Model Context Protocol (MCP)** é um padrão aberto que especifica como LLMs (Large Language Models) e assistentes inteligentes interagem com dados e ferramentas hospedadas em servidores externos. 

Em vez de construir integrações ad-hoc para cada API ou banco de dados, o MCP estabelece um protocolo uniforme (baseado em JSON-RPC 2.0 sobre Stdio ou WebSockets) com três primitivas principais:

1. **Tools (Ferramentas):** Funções executáveis que a IA pode invocar para realizar ações ou consultar dados (com esquemas de entrada validados por JSON Schema).
2. **Resources (Recursos):** Fontes de dados estáticas ou dinâmicas expostas ao modelo (como arquivos de log, esquemas de tabelas ou visualizações de dados).
3. **Prompts (Modelos de Instrução):** Modelos pré-definidos de prompts que guiam a IA na execução de tarefas complexas e repetitivas.

No ecossistema do `tucano-cvm`, o servidor MCP atuará como um **gateway inteligente** que traduz a semântica de negócios da CVM (busca de empresas, coleta de DFP/ITR, controle de materializações e monitoramento de filas Celery) em capacidades diretamente acionáveis por agentes de IA.

```
+------------------+         Stdio / HTTP         +--------------------+
|  Cliente MCP     | <------------------------->  |  Servidor MCP      |
|  (Cursor, etc.)  |                              |  (tucano-cvm)      |
+------------------+                              +--------------------+
                                                             |
                                         +-------------------+-------------------+
                                         |                   |                   |
                                         v                   v                   v
                                    [API/Routers]      [DB Session]       [Celery/Redis]
```

---

## 2. Motivações e Benefícios (Por que implementar?)

A introdução de um servidor MCP no `tucano-cvm` resolve diversos desafios operacionais e analíticos enfrentados por analistas e desenvolvedores:

### 2.1 Análise Financeira Avançada Sem Escrever Código
Atualmente, para realizar análises comparativas complexas ou consolidar dados de governança, o usuário ou o agente precisa fazer múltiplas chamadas HTTP ou interagir diretamente com o banco via SQL. Com as ferramentas MCP, uma IA pode receber instruções em linguagem natural (ex: *"Calcule a margem líquida consolidada da Petrobras para os últimos 3 anos"*) e orquestrar as consultas aos endpoints `/companhias` e `/analise` de forma autônoma e imediata.

### 2.2 Triage e Diagnóstico de Ingestão e Materialização
O pipeline de ingestão da CVM e a fila de materialização analítica (`analise_materializacao`) são fluxos complexos e sensíveis a falhas de rede ou inconsistências de dados de origem. Um operador assistido por IA poderá:
* Verificar rapidamente o estado do gate de materialização (se está pausado ou liberado).
* Analisar logs de erros de chunks stale ou execuções abortadas.
* Solicitar o reparo (`repair`) de dados de uma empresa específica diretamente pela interface de chat.

### 2.3 Produtividade do Desenvolvedor e Integração no Editor
Ao trabalhar dentro do repositório, o desenvolvedor ou o agente de codificação terá acesso a ferramentas que conectam a base de dados ativa aos seus prompts de desenvolvimento, reduzindo a necessidade de escrever scripts Python temporários (scratch scripts) para inspecionar estados do banco.

### 2.4 Padronização e Segurança
O protocolo centraliza as regras de negócio em um único ponto, garantindo que o acesso do LLM herde as regras de autenticação (como tokens de operador ou administrador) e respeite os limites de paginação e throttling configurados na aplicação FastAPI.

---

## 3. Sessões de Implementação (Fases)

O roadmap está estruturado em 4 sessões lógicas que evoluem o servidor MCP de uma base de infraestrutura para uma ferramenta madura de operação e análise.

### Sessão 1: Infraestrutura Base do Servidor MCP e Segurança
* **Foco:** Criação do servidor base, suporte ao protocolo JSON-RPC e integração do ciclo de vida com a aplicação.
* **Componentes:**
  * Uso do SDK oficial do MCP para Python (`mcp`).
  * Implementação de um ponto de entrada CLI para o servidor (ex: `python -m app.cli.mcp_server`).
  * Configuração de segurança: passagem de variáveis de ambiente para autenticação e mapeamento do ciclo de vida das sessões do banco de dados (SQLAlchemy) e Redis.
  * Compatibilidade com execução em ambientes locais e Docker.

### Sessão 2: Ferramentas Analíticas (Financial Analyst Toolset)
* **Foco:** Expor dados de companhias, demonstrações contábeis e indicadores históricos ao cliente de IA.
* **Ferramentas Expostas:**
  * `buscar_companhias`: busca parametrizada (CNPJ, código CVM, nome, situação cadastral).
  * `obter_indicadores_financeiros`: consulta à API financeira (/financeiro) e de séries analíticas (/analise/series).
  * `obter_brief_companhia`: retorna o resumo executivo de uma companhia cadastrada.
  * `obter_governanca_e_quarentena`: coleta dados estruturados de governança, membros de comitês (FCA/FRE) e alertas de qualidade de dados.

### Sessão 3: Ferramentas Operacionais e Controle (Ops & Ingestion Toolset)
* **Foco:** Permitir o monitoramento e o controle operacional do pipeline de ingestão e materialização de dados.
* **Ferramentas Expostas:**
  * `consultar_status_ingestao`: exibe o progresso de `ExecucaoSincronizacao` ou `IngestionRun` ativos.
  * `controlar_gate_materializacao`: permite pausar ou retomar a fila de processamento de materializações analíticas.
  * `obter_diagnostico_materializacao`: detalha chunks com erros ou status `stale`.
  * `solicitar_reparo_materializacao`: cria uma tarefa de reparo para reprocessar a camada analítica de uma companhia.

### Sessão 4: Integração de Recursos e Prompts Predefinidos (Rich Context)
* **Foco:** Enriquecer o contexto do LLM com recursos em tempo real e atalhos de prompt para problemas recorrentes.
* **Recursos (Resources):**
  * `resource://metadados/catalogo-metricas`: catálogo de métricas financeiras disponíveis no sistema.
  * `resource://status/fila-materializacao`: snapshot em tempo real do estado da fila e do gate.
* **Prompts:**
  * `diagnostico-erro-ingestao`: prompt estruturado para ajudar a IA a debugar uma falha de sincronização.
  * `analise-financeira-completa`: prompt template que orienta o modelo a extrair balanços, calcular indicadores e emitir parecer de governança da empresa de forma padronizada.

---

## 4. Planejamento de Tarefas de Alto Nível (Tasks)

As tarefas a seguir cobrem toda a implementação sem fatiamento excessivo, agrupando os entregáveis por blocos funcionais completos.

### Tarefa 1: Setup da Infraestrutura do Servidor MCP e Ciclo de Vida
* **Objetivo:** Estabelecer o servidor MCP executável, com controle de dependências, gerenciamento de sessões de banco de dados e testes locais de conectividade.
* **Escopo das Modificações:**
  * **Configuração:** Adicionar `mcp` (SDK da Anthropic) ao `pyproject.toml` e atualizar o `uv.lock`.
  * **Criação de Módulo:** Criar o diretório `app/mcp/` contendo:
    * `app/mcp/server.py`: definição do servidor, mapeamento inicial do protocolo e handlers de ciclo de vida.
    * `app/mcp/db.py`: gerenciamento seguro de sessões SQLAlchemy (utilizando `SessionLocal` da aplicação) para garantir que requisições do MCP não vazem conexões.
  * **Interface CLI:** Criar `app/cli/mcp.py` (ou integrar ao CLI existente) para iniciar o servidor via entrada/saída padrão (`stdio`). Exemplo: `tucano-cvm mcp-server`.
  * **Docker:** Atualizar o `docker-compose.yml` para expor opcionalmente uma forma de rodar o servidor MCP ou documentar o comando `docker compose run` correspondente.
* **Critérios de Aceitação:**
  * O servidor deve inicializar e responder ao aperto de mão (handshake) inicial do protocolo MCP via `stdio`.
  * O utilitário `mcp-cli-tester` ou o Claude Desktop devem conseguir se conectar ao servidor e listar uma lista vazia de ferramentas com sucesso.
  * O gerenciamento de conexão do banco de dados deve abrir e fechar sessões corretamente a cada invocação de ferramenta.

### Tarefa 2: Implementação do Toolset do Analista Financeiro
* **Objetivo:** Expor ferramentas de leitura e análise de companhias que permitam à IA consultar a base de dados normalizada da CVM.
* **Escopo das Modificações:**
  * **Desenvolvimento de Ferramentas (`app/mcp/tools/analise.py`):**
    * Registrar a ferramenta `buscar_companhias` acoplada aos filtros de `app/api/routers/companhias.py`.
    * Registrar a ferramenta `obter_demonstracoes_financeiras` integrando com os serviços de `app/services/analise.py` e consultas de balanço.
    * Registrar a ferramenta `obter_brief_companhia` (dados gerais, governança básica e indicadores recentes).
    * Registrar a ferramenta `obter_series_temporais` (coleta de métricas específicas em base anual ou trimestral).
  * **Tratamento de Dados:** Implementar serializadores específicos no MCP que convertam as respostas JSON dos schemas pydantic para formatos textuais limpos ou Markdown estruturado, reduzindo o consumo excessivo de tokens do LLM.
* **Critérios de Aceitação:**
  * O cliente MCP deve listar as ferramentas com os schemas JSON válidos e descrições detalhadas.
  * A IA deve ser capaz de buscar companhias pelo nome ou CNPJ e receber o objeto normalizado de resposta.
  * A chamada de `obter_brief_companhia` deve retornar dados consistentes e integrados com a base de dados PostgreSQL.

### Tarefa 3: Implementação do Toolset de Operação e Diagnóstico (Ops)
* **Objetivo:** Integrar os fluxos de controle da fila de materialização e do pipeline de ingestão ao servidor MCP, permitindo a gestão do estado do sistema pela IA.
* **Escopo das Modificações:**
  * **Desenvolvimento de Ferramentas (`app/mcp/tools/ops.py`):**
    * Registrar a ferramenta `obter_status_fila_materializacao` retornando dados do gate, fila Celery e progresso das campanhas.
    * Registrar a ferramenta `atualizar_gate_materializacao` com suporte a pausa/retomada.
    * Registrar a ferramenta `listar_erros_materializacao` retornando chunks stale ou execuções abortadas recentes.
    * Registrar a ferramenta `disparar_reparo_companhia` invocando `criar_repair_materializacao_companhia` para reprocessar a camada analítica.
    * Registrar a ferramenta `obter_status_sincronizacao` para acompanhar execuções do pipeline de ingestão de arquivos ZIP.
  * **Segurança:** Implementar validação do `admin_token` ou token de operador nas ferramentas que alteram estado (como disparar reparos ou pausar o gate).
* **Critérios de Aceitação:**
  * O operador de IA deve conseguir identificar falhas de materialização listando chunks com erros.
  * O comando para pausar ou retomar o gate de materialização deve alterar o estado no banco de dados com sucesso e respeitar a autenticação.
  * O disparo de reparos deve enfileirar a task Celery correspondente na fila `analise_materializacao`.

### Tarefa 4: Recursos (Resources) e Prompts Predefinidos
* **Objetivo:** Fornecer acesso direto a metadados do sistema e templates estruturados de prompts para agilizar fluxos de trabalho comuns.
* **Escopo das Modificações:**
  * **Desenvolvimento de Recursos (`app/mcp/resources.py`):**
    * Expor o catálogo completo de métricas financeiras suportadas (`/analise/metricas/catalogo`) através da URI `resource://metadados/catalogo-metricas`.
    * Expor o painel consolidado de integridade e quarentena de dados através da URI `resource://status/quarentena`.
  * **Desenvolvimento de Prompts (`app/mcp/prompts.py`):**
    * Criar o prompt `analise-financeira` aceitando o parâmetro `cnpj` ou `codigo_cvm`. O prompt instruirá a IA a buscar os balanços dos últimos 3 anos, o relatório de governança e calcular indicadores de rentabilidade de forma automática.
    * Criar o prompt `diagnostico-de-falha` que orientará a IA a verificar o status da sincronização, chunks stale e logs de erro para gerar um relatório de diagnóstico técnico.
* **Critérios de Aceitação:**
  * O cliente MCP deve reconhecer as URIs de recursos e carregá-las sob demanda.
  * Os prompts estruturados devem aparecer listados no cliente e funcionar corretamente ao receber argumentos, gerando o roteiro de execução de ferramentas esperado.

### Tarefa 5: Validação, Testes e Documentação Técnica
* **Objetivo:** Garantir a estabilidade do servidor MCP através de testes integrados e documentar as instruções de instalação e uso no Docusaurus.
* **Escopo das Modificações:**
  * **Testes unitários e integrados (`tests/mcp/`):**
    * Escrever testes que usem o cliente MCP simulado (`mcp.client`) para disparar requisições para as ferramentas implementadas, validando o comportamento com banco de dados SQLite de teste.
    * Garantir que as restrições de permissão falhem adequadamente se os tokens de autenticação não forem informados.
  * **Documentação Docusaurus:**
    * Criar página de documentação descrevendo como configurar o servidor MCP no Cursor, Claude Desktop e outros clientes.
    * Atualizar o `docs/frontend_api_changelog.md` registrando a introdução da interface MCP.
* **Critérios de Aceitação:**
  * Os testes do MCP devem rodar com sucesso via pytest.
  * A build do Docusaurus (`npm --prefix docusaurus run build`) deve passar sem erros.
  * O arquivo `docs/frontend_api_changelog.md` deve conter a seção correspondente ao lançamento do suporte ao MCP.
