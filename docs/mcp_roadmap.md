# Roadmap de Implementação do Model Context Protocol (MCP) no Tucano CVM

Este documento apresenta o plano detalhado de implementação de um servidor **Model Context Protocol (MCP)** para o projeto `tucano-cvm`. O objetivo do primeiro corte é expor capacidades **analíticas read-only** diretamente para assistentes de IA (como Cursor, Claude Desktop e outros clientes habilitados para MCP), otimizando o fluxo de análise de dados corporativos da CVM sem criar uma segunda superfície operacional.

O MCP nasce como adaptador de leitura sobre a camada analítica canônica. Ele não executa ingestão, não dispara materialização, não controla filas e não altera estado da aplicação neste roadmap.

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

No ecossistema do `tucano-cvm`, o servidor MCP atuará como um **adaptador semântico local** que traduz a linguagem de negócio da CVM (busca de empresas, séries financeiras, cobertura canônica, diagnóstico analítico e disponibilidade de dados) em capacidades de leitura diretamente acionáveis por agentes de IA.

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
                                    [Services]        [DB Session]       [Schemas]
```

---

## 1.1 Fontes Técnicas e Decisões de Base

Este roadmap assume como referência a especificação atual do MCP e o SDK oficial Python do projeto `modelcontextprotocol`. As decisões de base são:

1. **Começar por `stdio`**: é o caminho mais simples e interoperável para uso local em Cursor, Claude Desktop e outros clientes de desenvolvimento.
2. **Adiar Streamable HTTP**: só deve entrar quando houver necessidade real de servidor remoto, autenticação HTTP, sessões concorrentes e operação multiusuário.
3. **Usar application services compartilhados obrigatoriamente**: ferramentas MCP não podem implementar regras de negócio próprias. REST e MCP devem chamar o mesmo service/query de aplicação.
4. **Manter o primeiro corte read-only**: o roadmap atual não inclui ferramentas que alteram estado, disparam Celery, controlam gate, cancelam runs ou fazem repair.
5. **Retornar contexto compacto**: respostas MCP devem ser menores que os payloads HTTP completos, com campos essenciais, diagnóstico acionável e links/ids para aprofundamento.
6. **Preparar auditabilidade futura sem habilitar mutações**: qualquer capacidade mutável futura exigirá novo desenho, escopos próprios, confirmação explícita e auditoria antes de entrar no MCP.

Regra obrigatória de manutenção:

```text
REST Router
  -> Application Service compartilhado
     -> DB

MCP Tool
  -> mesmo Application Service compartilhado
     -> DB
```

É proibido manter a mesma regra de negócio duplicada em router REST e tool MCP. Quando a regra atual estiver presa em um router FastAPI, a implementação do MCP deve primeiro extrair essa lógica para um service/query compartilhado e então fazer o router e a tool chamarem esse mesmo ponto. Esta regra é bloqueante: nenhuma ferramenta MCP deve ser implementada copiando query, filtro, cálculo, decisão operacional ou regra de diagnóstico de um router.

A duplicação aceitável é apenas de adaptação de transporte:

- REST: query params, autenticação HTTP, response model e status code.
- MCP: tool args, perfil MCP, compactação para LLM e erro estruturado.

Referências técnicas:

- Especificação de transportes MCP: `https://modelcontextprotocol.io/specification/2025-11-25/basic/transports`
- SDK Python oficial: `https://github.com/modelcontextprotocol/python-sdk`

---

## 2. Motivações e Benefícios (Por que implementar?)

A introdução de um servidor MCP no `tucano-cvm` resolve desafios analíticos enfrentados por analistas e desenvolvedores:

### 2.1 Análise Financeira Avançada Sem Escrever Código
Atualmente, para realizar análises comparativas complexas ou consolidar dados de governança, o usuário ou o agente precisa fazer múltiplas chamadas HTTP ou interagir diretamente com o banco via SQL. Com as ferramentas MCP, uma IA pode receber instruções em linguagem natural (ex: *"Calcule a margem líquida consolidada da Petrobras para os últimos 3 anos"*) e orquestrar as consultas aos endpoints `/companhias` e `/analise` de forma autônoma e imediata.

### 2.2 Diagnóstico Analítico de Lacunas
O projeto possui uma camada canônica de análise com cobertura, séries, diagnósticos e status derivado de materialização. Um analista assistido por IA poderá:
* verificar se uma companhia possui dados canônicos para períodos específicos;
* entender por que uma métrica não aparece em um gráfico;
* diferenciar ausência de dado bruto, ausência de contexto canônico, ausência de fato canônico, métrica indisponível ou filtro incompatível;
* receber uma recomendação operacional textual sem que o MCP execute a ação.

### 2.3 Produtividade do Desenvolvedor e Integração no Editor
Ao trabalhar dentro do repositório, o desenvolvedor ou o agente de codificação terá acesso a ferramentas que conectam a base de dados ativa aos seus prompts de desenvolvimento, reduzindo a necessidade de escrever scripts Python temporários (scratch scripts) para inspecionar estados do banco.

### 2.4 Padronização e Segurança
O protocolo centraliza as regras de consulta em uma superfície controlada. O MCP deve reutilizar serviços de aplicação já existentes e não deve assumir que a autenticação FastAPI se aplica automaticamente ao transporte `stdio`. Tokens usados na API REST não concedem acesso ao MCP automaticamente. Permissões, perfis, escopos, limites de paginação e timeouts precisam ser explicitamente modelados no servidor MCP.

### 2.5 Diagnóstico Explicável Para Dados Ausentes
O projeto já possui endpoints de diagnóstico canônico, cobertura analítica e disponibilidade de datasets FRE. O MCP deve transformar esses sinais em respostas mais úteis para análise assistida, por exemplo:

* explicar por que uma série histórica não retorna FY2021-FY2023;
* indicar se falta ingestão, contexto canônico, fatos canônicos, métrica materializada ou apenas ajuste de filtro;
* diferenciar arquivo CVM ausente de falha de promoção em FRE;
* sugerir a próxima ação operacional sem executá-la.

---

## 2.6 Princípios de Segurança e Governança

O MCP dá ao assistente acesso semântico ao domínio. Mesmo no modo read-only, o servidor deve nascer com limites explícitos:

1. **Modo exclusivamente read-only neste roadmap**: ferramentas de escrita não fazem parte do escopo.
2. **Perfis separados**:
   - `analyst`: busca companhias, séries, coverage, diagnósticos e briefs.
   - perfis `operator` e `admin` ficam reservados para roadmap futuro, fora do escopo deste documento.
3. **Escopo MCP explícito**: token REST não libera MCP por padrão. O token usado no MCP precisa trazer escopo/perfil explícito, como `mcp:analyst`, ou ser configurado por variável de ambiente própria em instalação local controlada.
4. **Separação de credenciais**: a implementação pode reaproveitar o mesmo mecanismo de validação de tokens da API, mas deve distinguir escopo REST de escopo MCP. Um token `api:admin` não deve implicar acesso MCP sem escopo explícito.
5. **Sem SQL arbitrário**: o MCP não deve expor ferramenta genérica de SQL. Consultas precisam passar por serviços/queries explicitamente modelados.
6. **Sem logs brutos volumosos**: respostas devem retornar resumo analítico, ids, reason codes e próximos passos, com limites defensivos.
7. **Redação de segredos**: tokens, URLs com credenciais, variáveis sensíveis e connection strings devem ser mascarados em qualquer resposta.
8. **Timeouts e limites**: toda ferramenta deve ter limite de linhas, limite de anos, timeout e paginação defensiva.

### 2.6.1 Credenciais e Escopos

O servidor MCP deve tratar autenticação como uma superfície própria:

```text
Token REST
  -> escopos REST: api:read, api:admin

Token MCP
  -> escopos MCP: mcp:analyst
```

Regras obrigatórias:

- tokens REST não concedem acesso MCP automaticamente;
- tokens MCP não precisam conceder acesso REST;
- ferramentas analíticas read-only exigem `mcp:analyst` ou perfil local explicitamente configurado;
- não há ferramentas operacionais ou mutáveis neste roadmap;
- em ambiente local `stdio`, o perfil `analyst` pode ser permitido por configuração controlada.

---

## 2.7 MVP Recomendado

O primeiro corte deve ser pequeno e comprovadamente útil:

1. Servidor `stdio` inicializável por Docker e por ambiente local.
2. Healthcheck MCP e listagem de ferramentas.
3. Tool read-only `buscar_companhias`.
4. Tool read-only `obter_diagnostico_series`, usando `/analise/companhias/{codigo_cvm}/series/diagnostico` ou o serviço equivalente.
5. Tool read-only `obter_coverage_companhia`, usando a matriz canônica de cobertura.
6. Tool read-only `obter_disponibilidade_fre_dataset`, usando o diagnóstico de disponibilidade FRE.
7. Documentação de configuração no Docusaurus.

Ferramentas operacionais, mutáveis ou de administração ficam fora do escopo deste roadmap.

---

## 3. Sessões de Implementação (Fases)

O roadmap está estruturado em 3 sessões lógicas. Todas são read-only e analíticas.

### Sessão 1: Infraestrutura Base do Servidor MCP
* **Foco:** Criação do servidor base, suporte ao protocolo JSON-RPC e integração segura com a aplicação.
* **Componentes:**
  * Uso do SDK oficial Python do Model Context Protocol (`mcp`).
  * Implementação de um ponto de entrada CLI para o servidor (ex: `python -m app.cli.mcp_server`).
  * Configuração de segurança por ambiente: `MCP_PROFILE`, `MCP_TOOL_TIMEOUT_SECONDS`, `MCP_MAX_ROWS`, `MCP_TOKEN` e escopo `mcp:analyst`.
  * Mapeamento do ciclo de vida das sessões do banco de dados (SQLAlchemy).
  * Compatibilidade com execução em ambientes locais e Docker.
* **Regra bloqueante:**
  * nenhum handler MCP pode consultar modelos ORM diretamente quando existir regra equivalente em router REST;
  * antes de criar a ferramenta, a regra deve estar em service/query compartilhado.

### Sessão 2: Extração de Services Compartilhados
* **Foco:** Remover dependência de regras presas nos routers antes de expor as ferramentas MCP.
* **Extrações necessárias:**
  * `companhias`: mover busca por companhia, serialização compacta e resolução de logo para service/query compartilhado.
  * `fre`: mover diagnóstico de disponibilidade de datasets FRE para service/query compartilhado.
  * `analise`: confirmar que coverage, séries, diagnóstico de séries e brief usam funções de service sem lógica complementar no router.
* **Critérios de Aceitação:**
  * routers REST e tools MCP chamam os mesmos services;
  * testes cobrem a semântica do service compartilhado;
  * nenhuma query, filtro, regra de fallback ou cálculo é duplicado no MCP.

### Sessão 3: Ferramentas Read-Only de Diagnóstico e Análise
* **Foco:** Expor dados de companhias, cobertura canônica, séries analíticas e disponibilidade de datasets sem alterar estado.
* **Ferramentas Expostas:**
  * `buscar_companhias`: busca parametrizada por CNPJ, código CVM, nome e situação cadastral.
  * `obter_coverage_companhia`: retorna matriz de cobertura por período, escopo, periodicidade e base.
  * `obter_diagnostico_series`: explica lacunas de séries com reason/remediation codes.
  * `obter_series_temporais`: retorna séries materializadas em formato compacto.
  * `obter_brief_companhia`: retorna resumo executivo determinístico de uma companhia cadastrada.
  * `obter_disponibilidade_fre_dataset`: explica se um endpoint FRE está vazio por ausência de pacote, CSV membro, linha, promoção ou endpoint público.
  * `listar_metricas_analise`: retorna catálogo compacto das métricas financeiras suportadas.
* **Fora de escopo:**
  * status de filas Celery;
  * gate de materialização;
  * cancelamento de ingestão;
  * reprocessamento seletivo;
  * repair de materialização;
  * SQL arbitrário;
  * resources/prompts operacionais.

---

## 4. Planejamento de Tarefas de Alto Nível (Tasks)

As tarefas a seguir cobrem a implementação do MCP analítico read-only sem fatiamento excessivo.

### Tarefa 1: Setup da Infraestrutura do Servidor MCP e Ciclo de Vida
* **Objetivo:** Estabelecer o servidor MCP executável, com controle de dependências, gerenciamento de sessões de banco de dados e testes locais de conectividade.
* **Escopo das Modificações:**
  * **Configuração:** Adicionar `mcp` ao `pyproject.toml` e atualizar o lockfile usado pelo projeto.
  * **Criação de Módulo:** Criar o diretório `app/mcp/` contendo:
    * `app/mcp/server.py`: definição do servidor, mapeamento inicial do protocolo e handlers de ciclo de vida.
    * `app/mcp/db.py`: gerenciamento seguro de sessões SQLAlchemy (utilizando `SessionLocal` da aplicação) para garantir que requisições do MCP não vazem conexões.
    * `app/mcp/settings.py`: leitura de perfil, timeouts, limites e escopo `mcp:analyst`.
    * `app/mcp/security.py`: validação de perfil, checagem de permissão e mascaramento de segredos.
    * `app/mcp/serialization.py`: serialização compacta para respostas orientadas a LLM.
    * `app/mcp/adapters.py`: adaptadores finos que convertem argumentos MCP para chamadas aos application services compartilhados, sem regras de negócio próprias.
  * **Interface CLI:** Criar `app/cli/mcp.py` (ou integrar ao CLI existente) para iniciar o servidor via entrada/saída padrão (`stdio`). Exemplo: `tucano-cvm mcp-server`.
  * **Docker:** Atualizar o `docker-compose.yml` para expor opcionalmente uma forma de rodar o servidor MCP ou documentar o comando `docker compose run` correspondente.
* **Critérios de Aceitação:**
  * O servidor deve inicializar e responder ao aperto de mão (handshake) inicial do protocolo MCP via `stdio`.
  * O utilitário `mcp-cli-tester` ou o Claude Desktop devem conseguir se conectar ao servidor e listar uma lista vazia de ferramentas com sucesso.
  * O gerenciamento de conexão do banco de dados deve abrir e fechar sessões corretamente a cada invocação de ferramenta.
  * Token REST sem escopo MCP deve ser rejeitado pelo servidor MCP.
  * Token MCP com `mcp:analyst` deve acessar apenas ferramentas read-only analíticas.
  * Respostas de erro devem ser estruturadas, sem stack trace ou segredo.
  * Nenhuma ferramenta MCP deve chamar diretamente um handler FastAPI nem duplicar regra existente em router.

### Tarefa 2: Extração de Services Compartilhados Para o MVP
* **Objetivo:** Garantir que o MCP não implemente regra própria nem dependa de handlers REST.
* **Escopo das Modificações:**
  * Criar ou completar service/query de companhias para busca e obtenção por `codigo_cvm`/CNPJ.
  * Extrair o diagnóstico de disponibilidade FRE para service/query compartilhado.
  * Revisar os endpoints analíticos usados pelo MCP e mover qualquer lógica residual de router para service.
  * Manter os schemas HTTP como contrato público, mas permitir serialização MCP compacta em camada própria.
* **Critérios de Aceitação:**
  * REST e MCP chamam os mesmos services para cada capacidade exposta.
  * Os services possuem testes próprios de regra de negócio.
  * O MCP não possui query SQL/ORM duplicada para comportamento já existente na API.

### Tarefa 3: Implementação do Toolset do Analista Financeiro
* **Objetivo:** Expor ferramentas de leitura e análise de companhias que permitam à IA consultar a base de dados normalizada da CVM.
* **Escopo das Modificações:**
  * **Desenvolvimento de Ferramentas (`app/mcp/tools/analise.py`):**
    * Registrar a ferramenta `buscar_companhias` reutilizando queries ou services da camada de companhias.
    * Registrar a ferramenta `obter_coverage_companhia`, alinhada ao contrato de `/analise/companhias/{codigo_cvm}/coverage`.
    * Registrar a ferramenta `obter_diagnostico_series`, alinhada ao contrato de `/analise/companhias/{codigo_cvm}/series/diagnostico`.
    * Registrar a ferramenta `obter_brief_companhia` (dados gerais, governança básica e indicadores recentes).
    * Registrar a ferramenta `obter_series_temporais` (coleta de métricas específicas em base anual ou trimestral).
    * Registrar a ferramenta `obter_disponibilidade_fre_dataset`, alinhada ao contrato de `/fre/datasets/disponibilidade`.
    * Registrar a ferramenta `listar_metricas_analise`, alinhada ao catálogo de métricas de análise.
  * **Tratamento de Dados:** Implementar serializadores específicos no MCP que convertam as respostas JSON dos schemas pydantic para formatos textuais limpos ou Markdown estruturado, reduzindo o consumo excessivo de tokens do LLM.
* **Critérios de Aceitação:**
  * O cliente MCP deve listar as ferramentas com os schemas JSON válidos e descrições detalhadas.
  * A IA deve ser capaz de buscar companhias pelo nome ou CNPJ e receber o objeto normalizado de resposta.
  * A chamada de `obter_brief_companhia` deve retornar dados consistentes e integrados com a base de dados PostgreSQL.
  * Para uma mesma companhia/período/métrica, `obter_coverage_companhia` e `obter_diagnostico_series` devem retornar period IDs e escopo compatíveis.
  * Quando um endpoint FRE estiver vazio, `obter_disponibilidade_fre_dataset` deve indicar se a causa é fonte ausente, member ausente, member vazio ou promoção ausente.
  * Se a lógica de uma ferramenta ainda estiver implementada dentro de um router REST, a tarefa só é considerada concluída depois da extração para service/query compartilhado.

### Tarefa 4: Resources e Prompts Analíticos
* **Objetivo:** Fornecer acesso direto a metadados do sistema e templates estruturados de prompts para agilizar fluxos de trabalho comuns.
* **Escopo das Modificações:**
  * **Desenvolvimento de Recursos (`app/mcp/resources.py`):**
    * Expor o catálogo completo de métricas financeiras suportadas (`/analise/metricas/catalogo`) através da URI `resource://metadados/catalogo-metricas`.
    * Expor um resumo estático de fontes e datasets suportados através da URI `resource://metadados/catalogo-fontes`.
  * **Desenvolvimento de Prompts (`app/mcp/prompts.py`):**
    * Criar o prompt `analise-financeira` aceitando o parâmetro `cnpj` ou `codigo_cvm`. O prompt instruirá a IA a buscar os balanços dos últimos 3 anos, o relatório de governança e calcular indicadores de rentabilidade de forma automática.
    * Criar o prompt `diagnostico-lacuna-serie` que orientará a IA a verificar coverage, diagnóstico de séries e disponibilidade de datasets para explicar lacunas de gráfico.
* **Critérios de Aceitação:**
  * O cliente MCP deve reconhecer as URIs de recursos e carregá-las sob demanda.
  * Os prompts estruturados devem aparecer listados no cliente e funcionar corretamente ao receber argumentos, gerando o roteiro de execução de ferramentas esperado.

### Tarefa 5: Validação, Testes e Documentação Técnica
* **Objetivo:** Garantir a estabilidade do servidor MCP através de testes integrados e documentar as instruções de instalação e uso no Docusaurus.
* **Escopo das Modificações:**
  * **Testes unitários e integrados (`tests/unit/test_mcp_*.py` ou `tests/mcp/`):**
    * Escrever testes que usem o cliente MCP simulado (`mcp.client`) para disparar requisições para as ferramentas implementadas, validando o comportamento com banco de dados SQLite de teste.
    * Garantir que as restrições de permissão falhem adequadamente se os tokens de autenticação não forem informados.
    * Testar limites de paginação, timeout e mascaramento de segredos.
    * Testar consistência entre services, REST e MCP para coverage, diagnóstico de séries e disponibilidade FRE.
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
| `obter_brief_companhia` | `analyst` | Não | Brief determinístico de análise | Resumo financeiro e analítico, sem geração AI no backend |
| `obter_disponibilidade_fre_dataset` | `analyst` | Não | Diagnóstico FRE | Causa de endpoint FRE vazio por dataset/ano |
| `listar_metricas_analise` | `analyst` | Não | Catálogo de métricas | Métricas disponíveis, unidades, periodicidades e descrições |

---

## 6. Riscos e Mitigações

| Risco | Impacto | Mitigação |
|-------|---------|-----------|
| Ferramenta MCP retornar payload HTTP completo demais | Consumo excessivo de tokens e respostas ruins do LLM | Serializadores compactos por ferramenta, com `include_raw=false` por padrão |
| Escopo crescer para ações operacionais sem desenho próprio | MCP passa a alterar estado sem auditoria, confirmação e governança | Manter este roadmap read-only; qualquer mutação futura exige novo ADR/plano e services compartilhados |
| Token REST liberar MCP automaticamente | Um token pensado para frontend/API ganha poder de agente e amplia impacto de vazamento | Exigir escopo MCP explícito (`mcp:analyst`) e rejeitar tokens apenas REST |
| Divergência entre API HTTP e MCP | Dois contratos passam a responder coisas diferentes | MCP deve chamar services/queries compartilhados e ter testes de consistência com schemas HTTP críticos |
| Duplicação de regra de negócio entre REST e MCP | Cada mudança passa a exigir duas manutenções e aumenta risco de comportamento inconsistente | Regra obrigatória: extrair lógica de routers para application services compartilhados antes de expor a mesma capacidade no MCP |
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
