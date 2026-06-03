# Tucano CVM

![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.x-D71F00?logo=sqlalchemy&logoColor=white)
![Alembic](https://img.shields.io/badge/Alembic-1.13+-222222)
![Celery](https://img.shields.io/badge/Celery-5.4+-37814A?logo=celery&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-7+-DC382D?logo=redis&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)

Serviço FastAPI para baixar, normalizar, armazenar e expor dados públicos da CVM sobre companhias abertas brasileiras.

Este repositório é voltado para desenvolvedores de backend e plataforma que trabalham com ingestão, normalização e comportamento da API.

## Visão geral

- Serviço orientado a API, construído com FastAPI.
- A raiz do domínio é `companhias`; dados de DFP, ITR e FRE se vinculam a uma companhia sempre que possível.
- A ingestão assíncrona usa Celery com Redis como broker/backend.
- A persistência usa SQLAlchemy + Alembic sobre PostgreSQL.
- O desenvolvimento local usa Docker Compose.

## O que está no escopo

- API pública para dados normalizados da CVM.
- Tarefas assíncronas de sincronização para cadastro, DFP, ITR e FRE.
- Ingestão idempotente com rastreamento de alterações.

## Modelo de execução

- `api`: expõe tráfego HTTP.
- `worker`: consome jobs do Celery.
- `beat`: agenda tarefas recorrentes do Celery.
- `postgres`: banco relacional principal.
- `redis`: broker/backend de tarefas.

## Desenvolvimento local

### Requisitos

- Python `3.12+`
- Docker + Docker Compose

### Ambiente

Use `.env` ou `.env.example` como fonte de variáveis no ambiente local.

Variáveis importantes:

- `DATABASE_URL`
- `REDIS_URL`
- `TUCANO_CVM_TOKEN`
- `CVM_BASE_URL`
- `LOG_LEVEL`
- `AMBIENTE`
- `ANOS_INICIAIS_DFP`
- `ANOS_INICIAIS_ITR`
- `ANOS_INICIAIS_FRE`

### Execução local

```bash
docker compose up --build
```

Comandos úteis depois disso:

```bash
docker compose run --rm cvm_api alembic upgrade head
docker compose run --rm cvm_api pytest
```

## API e autenticação

- `/health` é intencionalmente público para liveness/readiness probe.
- `POST /auth/login` aceita JSON com `username` e `password` e retorna `access_token` + `token_type`.
- Configure `TUCANO_CVM_USERNAME`, `TUCANO_CVM_PASSWORD` e `TUCANO_CVM_TOKEN` para o login do frontend.
- Todas as rotas protegidas de negócio/admin exigem `Authorization: Bearer <TUCANO_CVM_TOKEN>`.

## Testes e qualidade

```bash
pytest
ruff check .
mypy .
```

Observações:

- O repositório está configurado com mypy estrito.
- Os fixtures de teste usam SQLite em memória quando apropriado.

## Documentos principais

- Referência funcional/comportamental: `docs/prd_app_cvm_fastapi.md`
- Notas de mapeamento das fontes CVM: `ref_cvm.md`
- Guia detalhado sobre a CVM, suas fontes e o racional de negócio: `CVM.md`

## Versões usadas

<details>
<summary>Versões de linguagem e framework</summary>

- Python: `>=3.12`
- FastAPI: `>=0.115.0,<1.0.0`
- SQLAlchemy: `>=2.0.36,<3.0.0`
- Alembic: `>=1.13.2,<2.0.0`
- Celery: `>=5.4.0,<6.0.0`
- Uvicorn: `>=0.32.0,<1.0.0`
- Pydantic Settings: `>=2.6.0,<3.0.0`
- httpx: `>=0.28.0,<1.0.0`
- psycopg: `>=3.2.0,<4.0.0`
- Prometheus client: `>=0.21.0,<1.0.0`

</details>

<details>
<summary>Versões de infraestrutura</summary>

- PostgreSQL: `16` no Compose local
- Redis: `7` no Compose local
- Imagem base Docker: `python:3.12-slim`
- API do chart Helm: `v2`

</details>

<details>
<summary>Versões de ferramentas de desenvolvimento</summary>

- pytest: `>=8.3.0,<9.0.0`
- pytest-asyncio: `>=0.24.0,<1.0.0`
- ruff: `>=0.7.0,<1.0.0`
- mypy: `>=1.13.0,<2.0.0`

</details>

## Diretrizes de desenvolvimento

- Use `pyproject.toml` como fonte de verdade para dependências.
- Prefira corrigir problemas de ingestão, autenticação e deploy na causa raiz, sem camadas desnecessárias de workaround.
- Preserve `/health` como endpoint público, a menos que a estratégia de probe também mude.

## Detalhes adicionais sobre o projeto
> Consulte o documento [CVM.md](CVM.md) para uma explicação detalhada sobre o domínio CVM.

## 1. Tabelas principais do projeto

## 1.1 `companhias`

É a tabela raiz do domínio.

Campos principais:

- `id`: identificador interno estável;
- `cnpj_companhia`: chave principal de identificação do emissor;
- `codigo_cvm`: identificador regulatório da CVM;
- `denominacao_social`, `denominacao_comercial`: nomes do emissor;
- `situacao_registro`, `situacao_emissor`, `categoria_registro`: status regulatório;
- `data_registro`, `data_constituicao`, `data_cancelamento`: datas relevantes;
- `setor_atividade`, `tipo_mercado`, `controle_acionario`: classificação de negócio e mercado;
- `endereco`: bloco estrutural de endereço;
- `responsavel`: responsável cadastral;
- `auditor`, `cnpj_auditor`: auditor cadastral.

Campos de rastreabilidade:

- `arquivo_origem`, `ano_origem`, `linha_origem`, `hash_origem`;
- `criado_em`, `sincronizado_em`, `alterado_em`.

### Papel de negócio

Sem `companhias`, o restante vira dado documental sem identidade operacional.

## 1.2 `documentos_financeiros`

Representa o cabeçalho documental de DFP e ITR.

Campos principais:

- `tipo_formulario`: DFP ou ITR;
- `cnpj_companhia`, `codigo_cvm`, `companhia_id`;
- `data_referencia`, `versao`, `id_documento`;
- `categoria_documento`;
- `data_recebimento`;
- `link_documento`.

### Papel de negócio

Permite rastrear a existência do documento, sua versão e seu vínculo com o emissor.

## 1.3 `demonstracoes_financeiras`

Tabela mais importante para linhas contábeis.

Campos principais:

- `tipo_formulario`: DFP ou ITR;
- `tipo_demonstracao`: BPA, BPP, DRE, DFC etc.;
- `escopo_demonstracao`: consolidado ou individual, conforme a origem;
- `data_referencia`, `versao`;
- `grupo_demonstracao`;
- `moeda`, `escala_moeda`;
- `data_inicio_exercicio`, `data_fim_exercicio`;
- `codigo_conta`, `descricao_conta`, `valor_conta`;
- `conta_fixa`: sinaliza conta fixa ou não fixa.

### Papel de negócio

É a base para consultas financeiras granulares e para séries históricas por conta contábil.

## 1.4 `composicoes_capital`

Concentra dados de composição do capital extraídos de DFP/ITR.

Campos principais:

- quantidades de ações ordinárias, preferenciais e total;
- segregação entre capital integralizado e tesouraria;
- `data_referencia`, `versao`, `tipo_formulario`.

### Papel de negócio

Suporta análises de estrutura acionária e reconciliação societária em conjunto com FRE.

## 1.5 `pareceres_financeiros`

Guarda pareceres, relatórios e declarações ligados a DFP/ITR.

Campos principais:

- `tipo_relatorio_auditor`;
- `tipo_parecer_declaracao`;
- `numero_item_parecer_declaracao`;
- `texto_parecer_declaracao`.

### Papel de negócio

Preserva conteúdo textual regulatório que contextualiza a qualidade e a formalidade da informação financeira.

## 1.6 `fre_documentos`

Cabeçalho documental do FRE.

Campos principais:

- `id_documento`, `versao`, `data_referencia`;
- `cnpj_companhia`, `codigo_cvm`, `companhia_id`;
- `categoria_documento`, `data_recebimento`, `link_documento`.

### Papel de negócio

É o ponto de entrada para os subarquivos do Formulário de Referência.

## 1.7 `fre_auditores`

Informações de auditoria no contexto do FRE.

Campos principais:

- identificação do auditor (`id_auditor`, nome, CPF/CNPJ, código CVM);
- tipo/origem do auditor;
- datas de contratação e prestação;
- serviço contratado;
- remuneração;
- justificativa de substituição e razões apresentadas.

### Papel de negócio

Útil para governança, risco, continuidade do relacionamento com auditor e análises de independência.

## 1.8 `fre_capital_social`

Informações de capital social declaradas no FRE.

Campos principais:

- `tipo_capital`;
- `data_autorizacao_aprovacao`;
- `valor_capital`;
- `prazo_integralizacao`;
- quantidades de ações ordinárias, preferenciais e total.

### Papel de negócio

Complementa a visão societária do emissor e ajuda a explicar sua estrutura formal de capital.

## 1.9 `fre_posicoes_acionarias`

Informações de posição acionária do FRE.

Campos principais:

- identificação do acionista;
- tipo de pessoa;
- CPF/CNPJ;
- relações com outros acionistas;
- quantidades e percentuais por classe de ação;
- nacionalidade, UF, residência no exterior;
- representante legal;
- sinalizadores de controle e acordo de acionistas.

### Papel de negócio

Suporta análise de concentração, controle, dispersão acionária e governança.

## 1.10 `fre_remuneracoes_totais_orgaos`

Informações de remuneração por órgão de administração.

Campos principais:

- período do exercício social;
- órgão de administração;
- total de remuneração;
- número de membros e membros remunerados;
- parcelas fixas, variáveis, bônus, participação em resultados;
- remuneração baseada em ações;
- benefícios pós-emprego e cessação de cargo;
- observações.

### Papel de negócio

Permite análises de incentivo, governança e estrutura de remuneração executiva.

## 1.11 `fre_empregados_posicao_genero`

Informações agregadas de empregados por posição e gênero.

Campos principais:

- `posicao`;
- `quantidade_feminino`;
- `quantidade_masculino`;
- `quantidade_nao_binario`;
- `quantidade_outros`;
- `quantidade_sem_resposta`.

### Papel de negócio

Suporta leitura de diversidade e composição de força de trabalho dentro do emissor.

## 1.12 Tabelas operacionais de sincronização

### `execucoes_sincronizacao`

Registra cada execução de ingestão.

Campos principais:

- `tipo_fonte`, `ano`, `arquivo`, `url`;
- `hash_arquivo`;
- `iniciada_em`, `finalizada_em`, `status`;
- contadores de linhas lidas, inseridas, atualizadas, inalteradas e rejeitadas;
- `mensagem_erro`.

### `historico_alteracoes_campos`

Registra alteração campo a campo.

Campos principais:

- `entidade`, `entidade_id`, `companhia_id`;
- `campo`;
- `valor_anterior`, `valor_novo`;
- `alterado_em`;
- `execucao_sincronizacao_id`.

### `registros_quarentena`

Guarda registros rejeitados para análise posterior.

Campos principais:

- `execucao_sincronizacao_id`;
- `arquivo_origem`, `ano_origem`, `linha_origem`;
- `motivo`;
- `dados_originais`;
- `criado_em`.

### Papel de negócio

Essas tabelas existem para auditoria, confiabilidade operacional e explicabilidade.

## 2 Campos transversais importantes

Há um conjunto de campos que aparece em várias tabelas porque ele resolve problemas reais de operação:

- `companhia_id`: vínculo explícito com a entidade raiz;
- `arquivo_origem`: identifica o CSV específico da CVM;
- `ano_origem`: identifica o lote anual;
- `linha_origem`: permite rastrear a linha bruta;
- `hash_origem`: ajuda a implementar idempotência;
- `criado_em`: momento de inserção interna;
- `sincronizado_em`: última vez em que o registro foi reencontrado na fonte;
- `alterado_em`: última vez em que houve mudança real de negócio.

Esse desenho é importante porque reapresentação regulatória não é igual a alteração econômica. A aplicação precisa saber a diferença.

## 3. Frequência de sincronização esperada no produto

Embora a periodicidade oficial da CVM seja diária para cadastro e semanal para os demais conjuntos citados, o produto precisa decidir sua própria cadência operacional.

Uma estratégia típica é:

- cadastro: sincronização diária;
- DFP: sincronização semanal;
- ITR: sincronização semanal;
- FRE: sincronização semanal.

Em cenários mais exigentes, pode haver reprocessamento orientado por monitoramento de alteração do arquivo.

## 4. O que torna este domínio difícil

Há vários pontos que tornam o domínio mais difícil do que uma ingestão simples de CSV:

- reapresentações de documentos;
- versões diferentes do mesmo documento;
- múltiplos arquivos por tipo documental;
- relacionamento por CNPJ ou código CVM;
- dados textuais e contábeis convivendo no mesmo domínio;
- evolução regulatória do layout ao longo do tempo;
- necessidade de diferenciar atualização técnica de alteração material.

## 5. Por que isso é valioso para o negócio

Uma aplicação como esta serve para:

- construir APIs de dados financeiros e societários;
- alimentar painéis internos de análise e supervisão;
- apoiar produtos de inteligência de mercado;
- reduzir custo operacional de ingestão regulatória;
- aumentar a confiabilidade de analytics sobre emissores;
- dar auditabilidade a decisões baseadas em dados públicos.

Em outras palavras: o valor não está apenas em “baixar dados da CVM”. O valor está em transformar uma obrigação regulatória pública em um ativo de dados utilizável por produto, analytics e operação.
