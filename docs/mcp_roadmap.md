# Roadmap de Implementação do Model Context Protocol (MCP) no Tucano CVM

Este documento apresenta o plano detalhado de implementação de um servidor **Model Context Protocol (MCP)** para o projeto `tucano-cvm`. O objetivo é expor capacidades analíticas, operacionais e de diagnóstico do sistema diretamente para assistentes de IA (como Cursor, Claude Desktop e outros clientes habilitados para MCP), otimizando o fluxo de análise de dados corporativos da CVM e simplificando o monitoramento de pipelines de ingestão e materialização.

---

## 1. O que é o Model Context Protocol (MCP)?

O **Model Context Protocol (MCP)** é um padrão aberto que especifica como LLMs (Large Language Models) e assistentes inteligentes interagem com dados e ferramentas hospedadas em servidores externos. 

Em vez de construir integrações ad-hoc para cada API ou banco de dados, o MCP estabelece um protocolo uniforme baseado em JSON-RPC 2.0. Os transportes padrão relevantes para este projeto são:

- **stdio**: recomendado para integração local com editores e clientes desktop, com o servidor rodando como processo filho do cliente MCP.
- **Streamable HTTP**: recomendado para uma etapa posterior, quando houver necessidade de acesso remoto, múltiplas sessões, observabilidade HTTP e controle de autenticação fora do processo local.

O transporte SSE antigo não deve ser tratado como alvo principal. WebSocket também não deve ser assumido como transporte padrão do roadmap.

O protocolo expõe três primitivas principais:

1. **Tools (Ferramentas):** Funções executáveis que a IA pode invocar para realizar ações ou consultar dados (com esquemas de entrada validados por JSON Schema).
2. **Resources (Recursos):** Fontes de dados estáticas ou dinâmicas expostas ao modelo (como arquivos de log, esquemas de tabelas ou visualizações de dados).
3. **Prompts (Modelos de Instrução):** Modelos pré-definidos de prompts que guiam a IA na execução de tarefas complexas e repetitivas.

No ecossistema do `tucano-cvm`, o servidor MCP atuará como um **adaptador semântico local** que traduz a linguagem de negócio da CVM (busca de empresas, coleta de DFP/ITR, diagnóstico analítico, controle de materializações e monitoramento de filas Celery) em capacidades diretamente acionáveis por agentes de IA.

O MCP não deve substituir a API HTTP pública, nem criar um segundo modelo de domínio. Ele deve reutilizar os serviços, schemas e contratos já existentes, retornando respostas mais compactas e orientadas a uso por LLM.

```
+------------------+  stdio agora / Streamable HTTP futuro  +--------------------+
|  Cliente MCP     | <------------------------->  |  Servidor MCP      |
|  (Cursor, etc.)  |                              |  (tucano-cvm)      |
+------------------+                              +--------------------+
                                                             |
                                         +-------------------+-------------------+
                                         |                   |                   |
                                         v                   v                   v
                                    [Services]        [DB Session]       [Celery/Redis]
```

---

## 1.1 Fontes Técnicas e Decisões de Base

Este roadmap assume como referência a especificação atual do MCP e o SDK oficial Python do projeto `modelcontextprotocol`. As decisões de base são:

1. **Começar por `stdio`**: é o caminho mais simples e interoperável para uso local em Cursor, Claude Desktop e outros clientes de desenvolvimento.
2. **Adiar Streamable HTTP**: só deve entrar quando houver necessidade real de servidor remoto, autenticação HTTP, sessões concorrentes e operação multiusuário.
3. **Usar services antes de routers**: ferramentas MCP devem chamar preferencialmente funções de serviço ou consultas de domínio, não handlers FastAPI. Routers continuam sendo a superfície HTTP; MCP vira uma segunda superfície controlada sobre a mesma lógica de domínio.
4. **Separar leitura de escrita**: ferramentas analíticas read-only devem ser habilitadas por padrão; ferramentas operacionais que alteram estado precisam de configuração explícita.
5. **Retornar contexto compacto**: respostas MCP devem ser menores que os payloads HTTP completos, com campos essenciais, diagnóstico acionável e links/ids para aprofundamento.
6. **Preservar auditabilidade**: qualquer ferramenta que altere estado deve registrar origem `mcp`, nome da ferramenta, argumentos principais, usuário/token operacional e resultado.

Referências técnicas:

- Especificação de transportes MCP: `https://modelcontextprotocol.io/specification/2025-11-25/basic/transports`
- SDK Python oficial: `https://github.com/modelcontextprotocol/python-sdk`

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
O protocolo centraliza as regras de negócio em uma superfície controlada. O MCP deve reutilizar políticas já existentes de operador/admin quando fizer sentido, mas não deve assumir que a autenticação FastAPI se aplica automaticamente ao transporte `stdio`. Permissões, perfis, limites de paginação e timeouts precisam ser explicitamente modelados no servidor MCP.

### 2.5 Diagnóstico Explicável Para Dados Ausentes
O projeto já possui endpoints de diagnóstico canônico, cobertura analítica, status de materialização e disponibilidade de datasets FRE. O MCP deve transformar esses sinais em respostas mais úteis para análise assistida, por exemplo:

* explicar por que uma série histórica não retorna FY2021-FY2023;
* indicar se falta ingestão, contexto canônico, fatos canônicos, métrica materializada ou apenas ajuste de filtro;
* diferenciar arquivo CVM ausente de falha de promoção em FRE;
* sugerir o próximo comando operacional sem executá-lo automaticamente quando a ferramenta for destrutiva.

---

## 2.6 Princípios de Segurança e Governança

O MCP dá poder operacional ao assistente. Por isso, o servidor deve nascer com limites explícitos:

1. **Modo padrão read-only**: ferramentas de escrita ficam desabilitadas até `MCP_ENABLE_MUTATING_TOOLS=true`.
2. **Perfis separados**:
   - `analyst`: busca companhias, séries, coverage, diagnósticos e briefs.
   - `operator`: inclui status de ingestão/materialização e reparos.
   - `admin`: inclui pausa/retomada de gate e disparos operacionais sensíveis.
3. **Confirmação em duas etapas para mutações**: ferramentas como pausar gate, retomar gate, disparar ingestão ou repair devem aceitar `dry_run=true` por padrão e exigir `confirm=true` para executar.
4. **Sem SQL arbitrário**: o MCP não deve expor ferramenta genérica de SQL. Consultas precisam passar por serviços/queries explicitamente modelados.
5. **Sem logs brutos volumosos por padrão**: retornar resumo, erro principal, ids e próximos passos; logs completos só via ferramenta específica com limite de linhas.
6. **Redação de segredos**: tokens, URLs com credenciais, variáveis sensíveis e connection strings devem ser mascarados em qualquer resposta.
7. **Timeouts e limites**: toda ferramenta deve ter limite de linhas, limite de anos, timeout e paginação defensiva.

---

## 2.7 MVP Recomendado

O primeiro corte deve ser pequeno e comprovadamente útil:

1. Servidor `stdio` inicializável por Docker e por ambiente local.
2. Healthcheck MCP e listagem de ferramentas.
3. Tool read-only `buscar_companhias`.
4. Tool read-only `obter_diagnostico_series`, usando `/analise/companhias/{codigo_cvm}/series/diagnostico` ou o serviço equivalente.
5. Tool read-only `obter_coverage_companhia`, usando a matriz canônica de cobertura.
6. Tool read-only `obter_disponibilidade_fre_dataset`, usando o diagnóstico de disponibilidade FRE.
7. Tool read-only `obter_status_materializacao_companhia`.
8. Documentação de configuração no Docusaurus.

Ferramentas mutáveis entram apenas depois desse MVP estar testado em cliente real.

---

## 3. Sessões de Implementação (Fases)

O roadmap está estruturado em 5 sessões lógicas que evoluem o servidor MCP de uma base local read-only para uma ferramenta madura de operação e análise.

### Sessão 1: Infraestrutura Base do Servidor MCP e Segurança
* **Foco:** Criação do servidor base, suporte ao protocolo JSON-RPC e integração do ciclo de vida com a aplicação.
* **Componentes:**
  * Uso do SDK oficial Python do Model Context Protocol (`mcp`).
  * Implementação de um ponto de entrada CLI para o servidor (ex: `python -m app.cli.mcp_server`).
  * Configuração de segurança por ambiente: `MCP_PROFILE`, `MCP_ENABLE_MUTATING_TOOLS`, `MCP_TOOL_TIMEOUT_SECONDS`, `MCP_MAX_ROWS` e token operacional quando necessário.
  * Mapeamento do ciclo de vida das sessões do banco de dados (SQLAlchemy) e Redis.
  * Compatibilidade com execução em ambientes locais e Docker.

### Sessão 2: Ferramentas Read-Only de Diagnóstico e Análise
* **Foco:** Expor dados de companhias, cobertura canônica, séries analíticas e disponibilidade de datasets sem alterar estado.
* **Ferramentas Expostas:**
  * `buscar_companhias`: busca parametrizada (CNPJ, código CVM, nome, situação cadastral).
  * `obter_coverage_companhia`: retorna matriz de cobertura por período, escopo, periodicidade e base.
  * `obter_diagnostico_series`: explica lacunas de séries com reason/remediation codes.
  * `obter_series_temporais`: retorna séries materializadas em formato compacto.
  * `obter_brief_companhia`: retorna resumo executivo determinístico de uma companhia cadastrada.
  * `obter_disponibilidade_fre_dataset`: explica se um endpoint FRE está vazio por ausência de pacote, CSV membro, linha, promoção ou endpoint público.
  * `obter_governanca_e_quarentena`: coleta dados estruturados de governança, membros de comitês (FCA/FRE) e alertas de qualidade de dados.

### Sessão 3: Ferramentas Operacionais Read-Only
* **Foco:** Permitir monitoramento operacional do pipeline de ingestão e materialização sem executar ações.
* **Ferramentas Expostas:**
  * `consultar_status_ingestao`: exibe o progresso de `ExecucaoSincronizacao` ou `IngestionRun` ativos.
  * `obter_status_fila_materializacao`: retorna estado do gate, campanhas, chunks e filas.
  * `obter_diagnostico_materializacao`: detalha chunks com erros ou status `stale`.
  * `obter_diagnostico_ingestao`: resume execução pai/filhos, fase atual, heartbeat, throughput e último erro.

### Sessão 4: Ferramentas Operacionais Mutáveis
* **Foco:** Permitir controle operacional explícito e auditável para operadores/admins.
* **Ferramentas Expostas:**
  * `controlar_gate_materializacao`: permite pausar ou retomar a fila de processamento de materializações analíticas.
  * `solicitar_reparo_materializacao`: cria uma tarefa de reparo para reprocessar a camada analítica de uma companhia.
  * `reprocessar_member_ingestao`: agenda reprocessamento seletivo de um CSV membro.
  * `cancelar_ingestao`: solicita cancelamento de execução pai ou membro.
* **Regras:**
  * `dry_run=true` por padrão.
  * `confirm=true` obrigatório para alteração real.
  * perfil mínimo `operator` para repair/reprocessamento/cancelamento.
  * perfil mínimo `admin` para pausar/retomar gate.

### Sessão 5: Integração de Recursos e Prompts Predefinidos (Rich Context)
* **Foco:** Enriquecer o contexto do LLM com recursos em tempo real e atalhos de prompt para problemas recorrentes.
* **Recursos (Resources):**
  * `resource://metadados/catalogo-metricas`: catálogo de métricas financeiras disponíveis no sistema.
  * `resource://metadados/catalogo-fontes`: catálogo de fontes e datasets suportados.
  * `resource://status/fila-materializacao`: snapshot em tempo real do estado da fila e do gate.
  * `resource://status/ingestao-ativa`: snapshot de ingestões em andamento.
* **Prompts:**
  * `diagnostico-erro-ingestao`: prompt estruturado para ajudar a IA a debugar uma falha de sincronização.
  * `analise-financeira-completa`: prompt template que orienta o modelo a extrair balanços, calcular indicadores e emitir parecer de governança da empresa de forma padronizada.

---

## 4. Planejamento de Tarefas de Alto Nível (Tasks)

As tarefas a seguir cobrem toda a implementação sem fatiamento excessivo, agrupando os entregáveis por blocos funcionais completos.

### Tarefa 1: Setup da Infraestrutura do Servidor MCP e Ciclo de Vida
* **Objetivo:** Estabelecer o servidor MCP executável, com controle de dependências, gerenciamento de sessões de banco de dados e testes locais de conectividade.
* **Escopo das Modificações:**
  * **Configuração:** Adicionar `mcp` ao `pyproject.toml` e atualizar o lockfile usado pelo projeto.
  * **Criação de Módulo:** Criar o diretório `app/mcp/` contendo:
    * `app/mcp/server.py`: definição do servidor, mapeamento inicial do protocolo e handlers de ciclo de vida.
    * `app/mcp/db.py`: gerenciamento seguro de sessões SQLAlchemy (utilizando `SessionLocal` da aplicação) para garantir que requisições do MCP não vazem conexões.
    * `app/mcp/settings.py`: leitura de perfil, timeouts, limites e habilitação de ferramentas mutáveis.
    * `app/mcp/security.py`: validação de perfil, checagem de permissão e mascaramento de segredos.
    * `app/mcp/serialization.py`: serialização compacta para respostas orientadas a LLM.
  * **Interface CLI:** Criar `app/cli/mcp.py` (ou integrar ao CLI existente) para iniciar o servidor via entrada/saída padrão (`stdio`). Exemplo: `tucano-cvm mcp-server`.
  * **Docker:** Atualizar o `docker-compose.yml` para expor opcionalmente uma forma de rodar o servidor MCP ou documentar o comando `docker compose run` correspondente.
* **Critérios de Aceitação:**
  * O servidor deve inicializar e responder ao aperto de mão (handshake) inicial do protocolo MCP via `stdio`.
  * O utilitário `mcp-cli-tester` ou o Claude Desktop devem conseguir se conectar ao servidor e listar uma lista vazia de ferramentas com sucesso.
  * O gerenciamento de conexão do banco de dados deve abrir e fechar sessões corretamente a cada invocação de ferramenta.
  * `MCP_ENABLE_MUTATING_TOOLS=false` deve impedir o registro ou execução das ferramentas que alteram estado.
  * Respostas de erro devem ser estruturadas, sem stack trace ou segredo.

### Tarefa 2: Implementação do Toolset do Analista Financeiro
* **Objetivo:** Expor ferramentas de leitura e análise de companhias que permitam à IA consultar a base de dados normalizada da CVM.
* **Escopo das Modificações:**
  * **Desenvolvimento de Ferramentas (`app/mcp/tools/analise.py`):**
    * Registrar a ferramenta `buscar_companhias` reutilizando queries ou serviços da camada de companhias, sem chamar diretamente o handler HTTP.
    * Registrar a ferramenta `obter_demonstracoes_financeiras` integrando com os serviços de análise e consultas de balanço.
    * Registrar a ferramenta `obter_coverage_companhia`, alinhada ao contrato de `/analise/companhias/{codigo_cvm}/coverage`.
    * Registrar a ferramenta `obter_diagnostico_series`, alinhada ao contrato de `/analise/companhias/{codigo_cvm}/series/diagnostico`.
    * Registrar a ferramenta `obter_brief_companhia` (dados gerais, governança básica e indicadores recentes).
    * Registrar a ferramenta `obter_series_temporais` (coleta de métricas específicas em base anual ou trimestral).
    * Registrar a ferramenta `obter_disponibilidade_fre_dataset`, alinhada ao contrato de `/fre/datasets/disponibilidade`.
  * **Tratamento de Dados:** Implementar serializadores específicos no MCP que convertam as respostas JSON dos schemas pydantic para formatos textuais limpos ou Markdown estruturado, reduzindo o consumo excessivo de tokens do LLM.
* **Critérios de Aceitação:**
  * O cliente MCP deve listar as ferramentas com os schemas JSON válidos e descrições detalhadas.
  * A IA deve ser capaz de buscar companhias pelo nome ou CNPJ e receber o objeto normalizado de resposta.
  * A chamada de `obter_brief_companhia` deve retornar dados consistentes e integrados com a base de dados PostgreSQL.
  * Para uma mesma companhia/período/métrica, `obter_coverage_companhia` e `obter_diagnostico_series` devem retornar period IDs e escopo compatíveis.
  * Quando um endpoint FRE estiver vazio, `obter_disponibilidade_fre_dataset` deve indicar se a causa é fonte ausente, member ausente, member vazio ou promoção ausente.

### Tarefa 3: Implementação do Toolset de Operação e Diagnóstico (Ops)
* **Objetivo:** Integrar os fluxos de observabilidade da fila de materialização e do pipeline de ingestão ao servidor MCP, sem alterar estado no primeiro corte.
* **Escopo das Modificações:**
  * **Desenvolvimento de Ferramentas (`app/mcp/tools/ops.py`):**
    * Registrar a ferramenta `obter_status_fila_materializacao` retornando dados do gate, fila Celery e progresso das campanhas.
    * Registrar a ferramenta `listar_erros_materializacao` retornando chunks stale ou execuções abortadas recentes.
    * Registrar a ferramenta `obter_status_sincronizacao` para acompanhar execuções do pipeline de ingestão de arquivos ZIP.
    * Registrar a ferramenta `obter_diagnostico_execucao_ingestao` para uma run ou execução específica, incluindo fase, heartbeat, throughput, filhos e último erro.
  * **Segurança:** limitar resultados por paginação e ocultar segredos.
* **Critérios de Aceitação:**
  * O operador de IA deve conseguir identificar falhas de materialização listando chunks com erros.
  * O operador de IA deve conseguir explicar se uma ingestão está avançando, presa por heartbeat stale ou aguardando janela de concorrência.
  * Nenhuma ferramenta desta tarefa deve alterar banco, Redis ou Celery.

### Tarefa 4: Implementação das Ferramentas Operacionais Mutáveis
* **Objetivo:** Adicionar ações operacionais com confirmação explícita e auditoria.
* **Escopo das Modificações:**
  * **Desenvolvimento de Ferramentas (`app/mcp/tools/mutations.py`):**
    * Registrar `atualizar_gate_materializacao` com suporte a pausa/retomada.
    * Registrar `disparar_reparo_companhia` invocando o serviço de repair de materialização.
    * Registrar `reprocessar_member_ingestao` reutilizando o fluxo de reprocessamento seletivo.
    * Registrar `cancelar_ingestao` reutilizando a infraestrutura de cancelamento.
  * **Segurança e Auditoria:**
    * Exigir `MCP_ENABLE_MUTATING_TOOLS=true`.
    * Exigir perfil mínimo por ferramenta.
    * Exigir `dry_run=false` e `confirm=true` para executar a mutação.
    * Registrar evento operacional com ferramenta, argumentos principais, resultado e correlação com execução/campanha quando aplicável.
* **Critérios de Aceitação:**
  * Sem `confirm=true`, ferramentas mutáveis retornam apenas plano de ação.
  * Sem perfil suficiente, ferramentas mutáveis retornam erro de permissão.
  * O disparo de reparos deve enfileirar a task Celery correspondente na fila `analise_materializacao`.
  * Pausar/retomar gate deve alterar o estado esperado e aparecer no monitoramento.

### Tarefa 5: Recursos (Resources) e Prompts Predefinidos
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

### Tarefa 6: Validação, Testes e Documentação Técnica
* **Objetivo:** Garantir a estabilidade do servidor MCP através de testes integrados e documentar as instruções de instalação e uso no Docusaurus.
* **Escopo das Modificações:**
  * **Testes unitários e integrados (`tests/unit/test_mcp_*.py` ou `tests/mcp/`):**
    * Escrever testes que usem o cliente MCP simulado (`mcp.client`) para disparar requisições para as ferramentas implementadas, validando o comportamento com banco de dados SQLite de teste.
    * Garantir que as restrições de permissão falhem adequadamente se os tokens de autenticação não forem informados.
    * Testar limites de paginação, timeout, mascaramento de segredos e `dry_run` das mutações.
  * **Documentação Docusaurus:**
    * Criar página de documentação descrevendo como configurar o servidor MCP no Cursor, Claude Desktop e outros clientes.
    * Criar uma página de referência de ferramentas, argumentos, permissões e exemplos.
    * Registrar a introdução da superfície MCP no changelog técnico apropriado. O `docs/frontend_api_changelog.md` só deve ser atualizado se consumidores frontend forem afetados; MCP, por si só, não é contrato frontend.
* **Critérios de Aceitação:**
  * Os testes do MCP devem rodar com sucesso via pytest.
  * A build do Docusaurus (`npm --prefix docusaurus run build`) deve passar sem erros.
  * A documentação deve incluir comandos de execução local, configuração de cliente, perfis de segurança e lista de ferramentas.

---

## 5. Matriz Inicial de Ferramentas

| Ferramenta | Perfil mínimo | Mutável | Fonte interna recomendada | Resultado esperado |
|------------|---------------|---------|---------------------------|--------------------|
| `buscar_companhias` | `analyst` | Não | Serviço/query de companhias | Lista compacta com `codigo_cvm`, CNPJ, nome e situação |
| `obter_coverage_companhia` | `analyst` | Não | Serviço de análise canônica | Matriz por período com raw/context/facts/series |
| `obter_diagnostico_series` | `analyst` | Não | Diagnóstico de séries | Períodos retornados/rejeitados e reason/remediation codes |
| `obter_series_temporais` | `analyst` | Não | Serviço de séries analíticas | Observações compactas por métrica/período |
| `obter_brief_companhia` | `analyst` | Não | Brief determinístico de análise | Resumo financeiro e operacional, sem geração AI no backend |
| `obter_disponibilidade_fre_dataset` | `analyst` | Não | Diagnóstico FRE | Causa de endpoint FRE vazio por dataset/ano |
| `obter_status_materializacao_companhia` | `operator` | Não | Status de materialização por companhia | Estado por período, métricas e execução |
| `obter_status_fila_materializacao` | `operator` | Não | Monitoramento de materialização | Gate, campanhas, chunks e pendências |
| `obter_status_sincronizacao` | `operator` | Não | Estado de ingestão | Execuções pai/filhas, fases, heartbeat e erros |
| `disparar_reparo_companhia` | `operator` | Sim | Serviço de repair de materialização | Campanha aceita/rejeitada, ids e reason codes |
| `reprocessar_member_ingestao` | `operator` | Sim | Reprocessamento seletivo | Execução agendada e correlação com task |
| `cancelar_ingestao` | `operator` | Sim | Serviço de cancelamento | Solicitação de cancelamento e escopo afetado |
| `controlar_gate_materializacao` | `admin` | Sim | Controle de materialização | Gate pausado/retomado com auditoria |

---

## 6. Riscos e Mitigações

| Risco | Impacto | Mitigação |
|-------|---------|-----------|
| Ferramenta MCP retornar payload HTTP completo demais | Consumo excessivo de tokens e respostas ruins do LLM | Serializadores compactos por ferramenta, com `include_raw=false` por padrão |
| Agente executar mutação operacional indevida | Pausa de pipeline, repair desnecessário ou cancelamento acidental | Mutating tools desabilitadas por padrão, `dry_run=true`, `confirm=true`, perfil mínimo e auditoria |
| Divergência entre API HTTP e MCP | Dois contratos passam a responder coisas diferentes | MCP deve chamar services/queries compartilhados e ter testes de consistência com schemas HTTP críticos |
| Exposição de segredo em logs ou respostas | Vazamento de token/connection string | Redação centralizada em `app/mcp/security.py` e testes específicos |
| Ferramenta read-only causar carga alta | Degradação do banco durante ingestão/materialização | Limites de linhas/anos, timeouts, paginação e preferência por tabelas materializadas |
| Cliente MCP variar suporte a resources/prompts | Funcionalidade inconsistente entre Cursor, Claude Desktop e outros | MVP baseado em tools; resources/prompts entram como camada adicional |
| Acoplamento direto aos routers FastAPI | Reuso difícil, testes frágeis e necessidade de simular HTTP internamente | Ferramentas chamam services; routers e MCP compartilham lógica de domínio, não handlers |

---

## 7. Comandos de Validação Esperados

Além da validação padrão do projeto, a implementação MCP deve rodar:

```bash
docker compose run --rm cvm_api mypy .
docker compose run --rm cvm_api ruff check . --ignore E501
docker compose run --rm cvm_api python -m pytest -q
npm --prefix docusaurus run build
```

Para o servidor MCP, adicionar um teste de inicialização equivalente a:

```bash
docker compose run --rm cvm_api python -m app.cli.mcp --help
docker compose run --rm cvm_api python -m app.cli.mcp smoke-test
```

O comando `smoke-test` deve validar pelo menos inicialização do servidor, listagem de ferramentas read-only e execução de uma ferramenta simples contra banco de teste ou fixture controlada.
