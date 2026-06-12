# Ingestao de Dados CVM

## 1. Visao Geral

O servico de ingestao e o pipeline de dados do Tucano-CVM. Ele substitui o sistema legado
de "sincronizacao v1" e e responsavel por:

- Baixar arquivos do portal de dados abertos da CVM (`https://dados.cvm.gov.br/dados`)
- Fazer parsing de CSV e ZIP
- Validar schemas, normalizar campos e deduplicar registros
- Resolver a identidade das companhias (CNPJ / codigo CVM)
- Promover os dados para as tabelas de dominio
- Manter uma trilha de auditoria e quarentena para itens com falha

O pipeline opera sobre **8 fontes de dados** publicas da CVM, cada uma com um conjunto
de arquivos CSV organizados em pacotes anuais (ZIP) ou arquivos unicos (cadastro).

---

## 2. Arquitetura do Sistema

### Stack Tecnologica

| Componente | Tecnologia |
|---|---|
| API HTTP | FastAPI (Python 3.12+) |
| Fila de tarefas assincronas | Celery 5.4+ |
| Broker / Result backend | Redis 7 |
| Banco de dados relacional | PostgreSQL 16 |
| ORM | SQLAlchemy 2.x |
| Migracoes | Alembic |

### Processos em Execucao

| Processo | Descricao |
|---|---|
| `cvm_api` | Servidor HTTP (uvicorn) que expoe endpoints REST, incluindo admin de ingestion |
| `cvm_worker` | Celery worker (concurrency=4) que consome as tarefas de ingestion |
| `cvm_scheduler` | Celery beat que dispara sincronizacoes periodicas (diarias) |

### Visao da Arquitetura

```
  CVM Dados Abertos
         |
    [HTTP Download]
         |
  +-----+------+
  |   Worker   |  (Celery)
  |  ingestion |
  +-----+------+
         |
    [Staging: ingestion_rows]
         |
    [Validacao + Resolucao + Promocao]
         |
  +------+-------+
  |  PostgreSQL  |
  |  Tabelas de  |
  |   Dominio    |
  +--------------+
```

---

## 3. Fontes de Dados

Definidas em `app/services/ingestion/source_registry.py`.

| Fonte | Familia | Tipo | Anos | Depende de | Descricao |
|---|---|---|---|---|---|
| `cadastro` | cadastro_cvm | csv_unico | todos | -- | Cadastro de companhias abertas + emissor estrangeiro |
| `dfp` | documentos_financeiros | zip_anual | 2010+ | cadastro | Demonstracoes Financeiras Padronizadas (anuais) |
| `itr` | documentos_financeiros | zip_anual | 2010+ | cadastro | Informacoes Trimestrais |
| `fre` | formulario_referencia | zip_anual | 2010+ | cadastro | Formulario de Referencia |
| `fca` | formulario_cadastral | zip_anual | 2010+ | cadastro | Formulario Cadastral |
| `ipe` | informacoes_periodicas_eventuais | zip_anual | 2003+ | cadastro | Informacoes Periodicas e Eventuais |
| `vlmo` | valores_mobiliarios_negociados_detidos | zip_anual | 2018+ | cadastro | Valores Mobiliarios Negociados e Detidos |
| `cgvn` | governanca | zip_anual | 2018+ | cadastro | Codigo de Governanca Corporativa |

### Estrutura de uma Fonte (`FonteRegistry`)

Cada fonte possui:

- `fonte`: identificador unico (`FonteChave`)
- `familia`: agrupamento logico
- `tipo_distribuicao`: `csv_unico` (arquivo unico) ou `zip_anual` (pacote ZIP com varios CSVs)
- `dataset_path_template`: URL template para download
- `arquivo_principal_template`: nome do arquivo principal
- `primeiro_ano` / `ultimo_ano`: periodo de cobertura
- `dependencias`: fontes que precisam ser processadas antes
- `datasets`: lista de `DatasetFonte` descrevendo cada CSV dentro do ZIP

### Estrutura de um Dataset (`DatasetFonte`)

| Campo | Descricao |
|---|---|
| `dataset` | Nome logico do dataset |
| `member_name_template` | Template do nome do arquivo CSV dentro do ZIP |
| `row_kind` | Tipo de linha (ex: `dfp_documento`, `fre_auditor`) |
| `destino_promovido` | Tabela de dominio alvo |
| `normalizador` | Nome da funcao normalizadora |
| `chaves_relacao` | Campos usados para relacao entre datasets |
| `obrigatorio` | Se o arquivo deve obrigatoriamente existir no ZIP |

---

## 4. Modelo de Dados (Pipeline)

Oito tabelas principais em `app/models/ingestion.py`:

### `IngestionRun`

Representa uma execucao do pipeline para uma fonte/ano.

| Coluna | Tipo | Descricao |
|---|---|---|
| `id` | UUID | Chave primaria |
| `execucao_sincronizacao_id` | UUID (FK) | Referencia a `execucoes_sincronizacao` (legado) |
| `tipo_fonte` | String(50) | Fonte sendo processada |
| `ano` | Integer | Ano de referencia |
| `status` | String(32) | Status atual da execucao |
| `phase` | String(32) | Fase atual do pipeline |
| `requested_by_task_id` | String(64) | ID da tarefa Celery que solicitou |
| `message` | Text | Mensagem de status ou erro |
| `quality_summary` | JSON | Resumo consolidado de qualidade |
| `started_at` | DateTime | Inicio da execucao |
| `finished_at` | DateTime | Termino da execucao |

### `IngestionFile`

Arquivo baixado (ZIP ou CSV).

| Coluna | Descricao |
|---|---|
| `source_url` | URL de origem |
| `source_filename` | Nome do arquivo |
| `content_sha256` | Hash SHA-256 do conteudo |
| `content_length_bytes` | Tamanho em bytes |
| `http_status_code` | Status HTTP do download |
| `etag` / `last_modified` | Metadados HTTP |
| `is_zip` | Se o arquivo e um pacote ZIP |
| `already_seen_success` | Se ja foi processado com sucesso antes |

### `IngestionFileMember`

Membro dentro de um ZIP (ou CSV unico).

| Coluna | Descricao |
|---|---|
| `member_name` | Nome do CSV |
| `member_sha256` | Hash do conteudo |
| `member_size_bytes` | Tamanho |
| `encoding` | Encoding detectado (utf-8-sig / latin1) |
| `delimiter` | Delimitador (padrao `;`) |
| `header` | Lista de colunas (JSON) |
| `row_count` | Quantidade de linhas |
| `schema_status` | Status da validacao do schema |
| `schema_message` | Mensagem de validacao |

### `IngestionRow`

Uma linha de CSV parseada e armazenada.

| Coluna | Descricao |
|---|---|
| `raw_data` | Dados brutos (JSON) |
| `raw_hash` | Hash dos dados brutos |
| `normalized_data` | Dados normalizados (JSON) |
| `normalized_hash` | Hash dos dados normalizados |
| `row_kind` | Tipo de linha (ex: `dfp_documento`) |
| `natural_key` | Chave natural para dedup (JSON) |
| `validation_status` | Status da validacao |
| `validation_reason_code` | Codigo do motivo de rejeicao |
| `validation_details` | Detalhes da validacao (JSON) |
| `resolved_companhia_id` | FK para `companhias` |
| `resolution_method` | Metodo de resolucao usado |
| `resolution_confidence` | Confianca da resolucao |
| `promoted_entity` | Entidade de dominio promovida |
| `promoted_entity_id` | ID da entidade promovida |

### `IngestionRowEvent`

Auditoria do ciclo de vida de cada linha.

| Coluna | Descricao |
|---|---|
| `event_type` | `validated`, `quarantined`, `resolved`, `replayed`, etc. |
| `event_payload` | Dados do evento (JSON) |
| `created_by` | Identificador de quem criou |

### `IngestionAttempt`

Rastreamento de tentativas de operacoes (download, processamento).

| Coluna | Descricao |
|---|---|
| `operation` | Nome da operacao |
| `attempt_number` | Numero da tentativa |
| `error_type` | Tipo do erro |
| `error_message` | Mensagem de erro |
| `next_retry_at` | Proxima tentativa agendada |

### `QuarantineItem`

Linhas rejeitadas que aguardam reparo ou replay.

| Coluna | Descricao |
|---|---|
| `motivo_codigo` | Codigo do motivo (`companhia_nao_encontrada`, `chave_natural_duplicada_conflitante`, `schema_inesperado`) |
| `severidade` | `error` ou `warning` |
| `reparavel` | Se pode ser automaticamente reparado via replay |
| `tentativas_reprocessamento` | Contagem de tentativas de reprocessamento |
| `resolvido_em` / `resolvido_por` | Quando e por quem foi resolvido |

### `IngestionFileMemberPayload`

Armazenamento binario de payloads de membros extraidos (para dispatch assincrono).

---

## 5. Pipeline de Ingestao

O pipeline opera em **duas fases** para todas as fontes. A separacao permite que o sistema
sobreviva a restart entre as fases.

### 5.1 Fluxo Cadastro (CSV Unico)

A fonte `cadastro` e especial: sao dois CSV baixados diretamente (sem ZIP) e processados
de forma integrada.

#### Fase 1 — Pre-processo (`pre_processar_cadastro`)

1. Download de `cad_cia_aberta.csv` e `cad_cia_estrang.csv` do portal CVM
2. Computacao de SHA-256 de cada arquivo + hash composto
3. Verificacao de duplicidade via `buscar_execucao_hash_existente`
4. Se ja processado (hash igual): status = `skipped`, limpeza de disco
5. Se novo: criacao de `IngestionRun`, `IngestionFile` (2), `IngestionFileMember` (2)
6. Deteccao de encoding/delimiter, leitura de header e contagem de linhas
7. Status: `aguardando_ingestao`

#### Fase 2 — Ingestao (`ingerir_cadastro`)

1. Leitura dos CSV do disco
2. Normalizacao linha a linha:
   - `normalizar_linha_cadastro_aberta` (50 campos: CNPJ, CD_CVM, denominacao, endereco, responsavel, etc.)
   - `normalizar_linha_cadastro_estrangeira` (estrutura similar, sem tipo_mercado)
3. Agrupamento por identidade (CNPJ ou codigo CVM)
4. Selecao do registro canonico por grupo:
   - Prioridade: situacao ATIVO > sem cancelamento > data inicio mais recente > data registro mais recente > fonte aberta > linha origem
5. Upsert em 4 tabelas de dominio:
   - `Companhia` (registro mestre)
   - `CompanhiaRegistroCvm` (cada linha de cadastro historico)
   - `CompanhiaMercado` (tipo de mercado, quando presente)
   - `CompanhiaIdentificador` (CNPJ + codigo CVM normalizados)
6. Limpeza dos arquivos em disco

### 5.2 Fluxo ZIP (dfp, itr, fre, fca, ipe, vlmo, cgvn)

#### Fase 1 — Pre-processo (`pre_processar_sincronizacao_zip`)

1. Download do ZIP: `{fonte}_cia_aberta_{ano}.zip`
2. Criacao de `ExecucaoSincronizacao` pai com `tipo_execucao="arquivo_zip"`
3. Criacao de `IngestionRun` e `IngestionFile` (is_zip=True)
4. Computacao de hash SHA-256 do ZIP
5. Verificacao de duplicidade (skipped se ja processado)
6. Extracao dos membros CSV do ZIP em ordem definida pelo `source_registry`
7. Para cada membro:
   - Extracao do CSV para disco
   - Computacao de hash do membro
   - Se ja foi processado com sucesso antes (`member_has_successful_match`):
     - Cria `ExecucaoSincronizacao` filho com `status=skipped`
     - Cria `IngestionRun` filho com `status=skipped`
   - Se novo:
     - Cria `ExecucaoSincronizacao` filho com `tipo_execucao="arquivo_membro"` e `status=aguardando_ingestao`
     - Cria `IngestionRun` filho
     - Detecta encoding/delimiter, le header e conta linhas
     - Registra `IngestionFileMember`
8. Pai atualizado para `aguardando_ingestao`

#### Fase 2 — Ingestao (`ingerir_sincronizacao_zip`)

1. Carrega caches do resolver de identidade
2. Verifica se o grafo de identidade esta pronto (`ensure_identity_graph_ready`)
3. Separa membros em duas categorias:
   - **Document headers**: arquivo principal `{fonte}_cia_aberta_{ano}.csv` (processado primeiro)
   - **Dependentes**: demais arquivos (processados apos os headers)
4. Dispara `sincronizar_member_task` para cada membro (execucao sincrona `is_eager=True`):
   - Stage do CSV via `stage_csv_payload_streaming_from_disk` (batch de 5000 linhas)
   - Determinacao do `row_kind` via `get_row_kind`
   - Reconstrucao do `header_map` a partir de linhas ja resolvidas
   - Processamento especifico por tipo de fonte:
     - `dfp`/`itr`: `_process_financeiro_member`
     - `fre`: `_process_fre_member`
     - `fca`: `_process_fca_rows`
     - `ipe`: `_process_ipe_rows`
     - `vlmo`: `_process_vlmo_rows`
     - `cgvn`: `_process_cgvn_rows`
5. Agregacao dos resultados filhos no pai
6. Quality gate: se algum filho falhou, pai falha
7. Limpeza dos arquivos em disco

#### Processamento Interno de Membro (`sincronizar_member_task`)

Para cada membro, o pipeline interno e:

```
stage (CSV -> ingestion_rows)
  -> validate header (colunas obrigatorias)
  -> normalize (domain-specific normalizer)
  -> validate rows (natural key, dedup)
  -> resolve (company identity)
  -> promote (domain tables)
  -> quality gate
```

---

## 6. Fases e Status

### Fases do Pipeline (`phase`)

| Fase | Descricao |
|---|---|
| `acquire` | Download do arquivo da CVM |
| `stage` | Parsing do CSV e insercao em `ingestion_rows` |
| `validate` | Validacao de header, normalizacao e dedup |
| `resolve` | Resolucao de identidade da companhia |
| `promote` | Escrita nas tabelas de dominio |
| `complete` | Pipeline finalizado |

### Status de Execucao

| Status | Descricao |
|---|---|
| `em_execucao` | Pipeline em andamento |
| `aguardando_ingestao` | Pre-processo concluido, aguardando ingestao |
| `sucesso` | Processado com sucesso |
| `sucesso_com_alerta` | Processado com alertas (ex: erros de schema) |
| `skipped` | Ignorado (arquivo ja processado, hash identico) |
| `falha` | Falha no processamento |
| `falha_qualidade` | Falha no quality gate (ex: muitas companhias nao encontradas) |

---

## 7. Validacao e Qualidade

### Validacao de Schema (`validation.py`)

Cada `row_kind` possui um conjunto de colunas obrigatorias definidas em
`_REQUIRED_COLUMNS_BY_ROW_KIND`. Exemplos:

| row_kind | Colunas Obrigatorias |
|---|---|
| `dfp_documento` | `CNPJ_CIA`, `DT_REFER`, `VERSAO`, `ID_DOC` |
| `fre_documento` | `CNPJ_CIA`, `DT_REFER`, `VERSAO`, `ID_DOC` |
| `fre_auditor` | `CNPJ_Companhia`, `Data_Referencia`, `Versao`, `ID_Documento`, `ID_Auditor` |
| `vlmo_consolidado` | `CNPJ_Companhia`, `Nome_Companhia`, `Data_Referencia`, `Versao`, `Tipo_Empresa`, etc. (17 colunas) |

Resultados da validacao:

- `valid` — todos os requisitos atendidos
- `invalid` com `schema_inesperado` — colunas obrigatorias ausentes (reparavel = true)

### Construcao de Chave Natural

Cada `row_kind` possui um builder de chave natural especifico. Exemplos:

- `dfp_documento`: `{tipo_formulario, id_documento, versao, data_referencia}`
- `dfp_demonstracao`: `{tipo_formulario, tipo_demonstracao, escopo_demonstracao, cnpj_companhia, ..., codigo_conta}`
- `fre_auditor`: `{id_documento, versao, data_referencia, cnpj_companhia, id_auditor}`

### Classificacao de Duplicatas

`classify_duplicate()` compara a chave natural + hash normalizado:

| Resultado | Descricao |
|---|---|
| `new` | Primeira ocorrencia da chave natural |
| `ignored_duplicate` | Mesma chave natural + mesmo hash (registro identico) |
| `chave_natural_duplicada_conflitante` | Mesma chave natural, hash diferente (conflito, reparavel) |

### Quality Gate (`quality.py`)

Aplicado ao final do processamento de cada membro. Verifica:

- Razo de `companhia_nao_encontrada` < `INGESTION_COMPANY_MISSING_MAX_RATIO` (padrao 1%)
- Erros de schema produzem `sucesso_com_alerta`
- Violacao do limite produz `falha_qualidade`

---

## 8. Resolucao de Identidade (`resolver.py`)

### Estrategia em Cascata

A resolucao da companhia para cada linha segue 5 estrategias em ordem de precedencia:

1. **Identificador exato** (cache na sessao):
   - Busca por CNPJ em `CompanhiaIdentificador` (tipo="cnpj")
   - Busca por codigo CVM em `CompanhiaIdentificador` (tipo="codigo_cvm")
   - Se ambos encontrados e convergem para mesma companhia: confianca **alta**
   - Se apenas um encontrado: confianca **alta**

2. **Header de documento**:
   - Para linhas filhas (demonstracoes, auditores, etc.), usa a companhia ja resolvida do documento header
   - Cache em `header_map` (dict na memoria, chave = tipo_formulario + id_documento + versao + data_referencia)
   - Confianca: **media**

3. **Regras de reparo** (`RepairRule`):
   - Regras manuais do tipo `identity_exact`
   - Match por payload (campos especificos mapeados para companhia_id)
   - Confianca: **media**

4. **Tabela legada `Companhia`**:
   - Cache carregado no inicio da sessao
   - Busca por CNPJ e/ou codigo CVM
   - Confianca: **alta**

5. **Criacao provisoria** (feature flag `INGESTION_PROVISIONAL_COMPANY_ENABLED`):
   - Cria `Companhia` com `tipo_emissor="provisorio"`, `qualidade_identidade="baixa"`
   - CNPJ = `PROV{codigo_cvm:010d}` se codigo CVM disponivel
   - Atualiza caches em memoria para uso imediato
   - Confianca: **baixa**

### Resultados

| Status | Confianca | Descricao |
|---|---|---|
| `RESOLVED` | alta / media | Companhia encontrada |
| `AMBIGUOUS` | -- | Identificador aponta para multiplas companhias |
| `NOT_FOUND` | -- | Nenhuma estrategia resolveu |
| `PROVISIONAL_CREATED` | baixa | Companhia provisoria criada |

---

## 9. Quarentena e Replay

### Quarentena (`quarantine.py`)

Linhas invalidas sao registradas em `QuarantineItem` com:

| Campo | Descricao |
|---|---|
| `motivo_codigo` | Codigo estavel do motivo |
| `severidade` | `error` ou `warning` |
| `reparavel` | Se o item pode ser automaticamente reparado |
| `tentativas_reprocessamento` | Numero de tentativas de reprocessamento |
| `ultimo_erro` | Mensagem do ultimo erro |

Principais codigos de motivo:

| Codigo | Descricao | Reparavel |
|---|---|---|
| `companhia_nao_encontrada` | Empresa nao encontrada no grafo de identidade | Sim |
| `chave_natural_duplicada_conflitante` | Chave natural duplicada com dados divergentes | Sim |
| `schema_inesperado` | Colunas obrigatorias ausentes | Sim |
| `denominacao_social_ausente` | Nao foi possivel extrair a denominacao social | Nao |
| `identidade_ausente` | Nem CNPJ nem codigo CVM disponiveis | Nao |

### Replay (`replay.py`)

Tres niveis de replay:

1. **Linha individual** (`replay_ingestion_row`):
   - Renormaliza, re-resolve, re-promote uma unica linha
   - Usa o `raw_data` armazenado originalmente

2. **Run completa** (`replay_ingestion_run`):
   - Replay de todas as linhas de uma `IngestionRun`
   - Preserva a estrutura de membros original

3. **Lote de quarentena** (`replay_quarantine`):
   - Replay de todos os itens pendentes na quarentena
   - Filtros opcionais: `reason_code`, `arquivo_origem`, `ano`

---

## 10. Deduplicacao

A deduplicacao opera em tres niveis:

| Nivel | Mecanismo | Descricao |
|---|---|---|
| Arquivo | SHA-256 do conteudo | `buscar_execucao_hash_existente` compara hash contra execucoes anteriores |
| Membro CSV | SHA-256 do conteudo | `member_has_successful_match` verifica se mesmo hash ja foi processado com sucesso |
| Linha | Chave natural + hash normalizado | `classify_duplicate` detecta registros identicos ou conflitantes |

---

## 11. Gatilhos de Execucao

### 11.1 Celery Beat (Agendamento Diario)

Definido em `app/worker/celery_app.py`:

```python
# Cadastro — 01:00
"sincronizar-cadastro-diario": crontab(hour=1, minute=0)

# Fontes anuais — a partir de 02:00 com offsets de 5 min
# Para cada fonte configurada em anos_iniciais_*
"sincronizar-{fonte}-{ano}-diario": crontab(hour=2+, minute=offset)
```

### 11.2 Bootstrap (Sincronizacao Inicial)

Em `app/worker/bootstrap.py`: na inicializacao do scheduler, verifica se existem
execucoes validas. Se nao, dispara tarefas para cadastro e todas as fontes/anos
configurados.

### 11.3 Admin API

Seis endpoints em `app/api/routers/admin.py`:

| Metodo | Rota | Descricao |
|---|---|---|
| `GET` | `/admin/ingestion/runs` | Lista paginada de runs |
| `GET` | `/admin/ingestion/runs/{run_id}` | Detalhe de uma run |
| `GET` | `/admin/ingestion/quarantine` | Lista paginada da quarentena |
| `POST` | `/admin/ingestion/replay/quarantine` | Replay de itens da quarentena |
| `POST` | `/admin/ingestion/runs/{run_id}/replay` | Replay de uma run completa |
| `POST` | `/admin/ingestion/identity/rebuild` | Reconstroi o grafo de identidade |

### 11.4 Tasks Avulsas

Duas tarefas para operacao manual em duas fases:

- `pre_processar_sincronizacao_task` — apenas download + stage
- `ingerir_sincronizacao_task` — apenas validacao + resolucao + promocao

### 11.5 Tarefas Celery

| Nome da Task | Funcao | Gatilho |
|---|---|---|
| `sincronizar_cadastro_companhias_task` | `sincronizar_cadastro_companhias` | Beat + Bootstrap |
| `sincronizar_dfp_task` | `_coordenar_sincronizacao_zip("dfp", ano)` | Beat + Bootstrap |
| `sincronizar_itr_task` | `_coordenar_sincronizacao_zip("itr", ano)` | Beat + Bootstrap |
| `sincronizar_fre_task` | `_coordenar_sincronizacao_zip("fre", ano)` | Beat + Bootstrap |
| `sincronizar_fca_task` | `_coordenar_sincronizacao_zip("fca", ano)` | Beat + Bootstrap |
| `sincronizar_ipe_task` | `_coordenar_sincronizacao_zip("ipe", ano)` | Beat + Bootstrap |
| `sincronizar_vlmo_task` | `_coordenar_sincronizacao_zip("vlmo", ano)` | Beat + Bootstrap |
| `sincronizar_cgvn_task` | `_coordenar_sincronizacao_zip("cgvn", ano)` | Beat + Bootstrap |
| `sincronizar_member_task` | Processamento de membro individual | Disparada por `ingerir_sincronizacao_zip` |
| `pre_processar_sincronizacao_task` | Fase 1 manual | Admin / API |
| `ingerir_sincronizacao_task` | Fase 2 manual | Admin / API |

Todas as tarefas usam `autoretry_for` com: `RetryableIngestionError`,
`RetryableHttpStatus`, `DependencyNotReady`, `httpx.TimeoutException`,
`httpx.TransportError`, `sqlalchemy.exc.OperationalError`,
`sqlalchemy.exc.InterfaceError`.

---

## 12. Processadores por Dominio

Cada fonte possui um modulo especifico em `app/services/ingestion/` que implementa
a normalizacao, validacao e promocao para as tabelas de dominio.

### `cadastro.py` (~870 linhas)

Processa o cadastro de companhias abertas e estrangeiras.

- Normalizadores: `normalizar_linha_cadastro_aberta`, `normalizar_linha_cadastro_estrangeira`
- Promocao: `promover_registros_cadastro` → upsert em `Companhia`, `CompanhiaRegistroCvm`, `CompanhiaMercado`, `CompanhiaIdentificador`

### `financeiro.py` (~1198 linhas)

Processa DFP e ITR.

- Datasets: documento, demonstracoes financeiras (multiplos tipos como BPA, BPP, DRE, DFC, etc.), composicao de capital, parecer
- Normalizador compartilhado: `normalizar_financeiro_row`
- Promocao: `DocumentoFinanceiro`, `DemonstracaoFinanceira`, `ComposicaoCapital`, `ParecerFinanceiro`
- Ordem: documento header primeiro, depois demonstracoes, composicao, parecer

### `fre.py` (~1362 linhas)

Processa o Formulario de Referencia.

- 22 datasets no total, sendo 9 promovidos no MVP e 13 pendentes de mapeamento
- Datasets promovidos: documento, auditor, capital_social, posicao_acionaria, remuneracao_total_orgao, empregado_posicao_genero, responsavel + classes/titulos relacionados
- Normalizador: `normalizar_fre_row`
- Promocao: `FreDocumento`, `FreAuditor`, `FreCapitalSocial`, `FrePosicaoAcionaria`, `FreRemuneracaoTotalOrgao`, `FreEmpregadoPosicaoGenero`, `FreResponsavel`, etc.

### `fca.py` (~957 linhas)

Processa o Formulario Cadastral.

- 12 datasets, 5 promovidos, 5 apenas em staging (escriturador, canal_divulgacao, departamento_acionistas, pais_estrangeiro_negociacao)
- Promovidos: documento, geral, endereco, dri, auditor, valor_mobiliario
- Normalizador: `normalizar_fca_row`

### `ipe.py` (~621 linhas)

Processa Informacoes Periodicas e Eventuais.

- 1 dataset (documento principal)
- Normalizador: `normalizar_ipe_row`
- Promocao: `IpeDocumento`

### `vlmo.py` (~707 linhas)

Processa Valores Mobiliarios Negociados e Detidos.

- 2 datasets: documento + consolidado
- Normalizador: `normalizar_vlmo_row`
- Promocao: `VlmoDocumento`, `VlmoConsolidado`

### `cgvn.py` (~650 linhas)

Processa o Codigo de Governanca Corporativa.

- 2 datasets: documento + praticas
- Normalizador: `normalizar_cgvn_row`
- Promocao: `CgvnDocumento`, `CgvnPratica`

---

## 13. Metricas e Monitoramento

Definidas em `app/services/ingestion/metrics.py` (Prometheus):

| Metrica | Tipo | Labels |
|---|---|---|
| `cvm_ingestion_rows_total` | Counter | `source`, `status`, `reason` |
| `cvm_ingestion_run_duration_seconds` | Histogram | `source`, `phase` |
| `cvm_ingestion_retries_total` | Counter | `operation`, `error_type` |
| `cvm_ingestion_quarantine_total` | Gauge | `reason` |
| `cvm_ingestion_resolution_total` | Counter | `method`, `confidence` |

Helpers: `RunTimer` (context manager), `observe_row()`, `observe_retry()`,
`observe_resolution()`, `set_quarantine_total()`.

---

## 14. Configuracao

Definida em `app/core/config.py` (variaveis de ambiente com prefixo `INGESTION_`):

| Variavel | Padrao | Descricao |
|---|---|---|
| `INGESTION_PROMOTE_ENABLED` | `true` | Habilita/desabilita promocao para tabelas de dominio (dark launch) |
| `INGESTION_PROVISIONAL_COMPANY_ENABLED` | `false` | Cria companhias provisorias quando identidade nao encontrada |
| `INGESTION_MAX_RETRIES` | `5` | Maximo de retentativas para tarefas Celery |
| `INGESTION_RETRY_BACKOFF_MAX_SECONDS` | `600` | Backoff maximo entre retentativas |
| `INGESTION_COMPANY_MISSING_MAX_RATIO` | `0.01` | Razo maxima de companhias nao encontradas (quality gate) |
| `INGESTION_STAGE_BATCH_SIZE` | `5000` | Linhas por batch durante stage |
| `INGESTION_PROMOTE_BATCH_SIZE` | `5000` | Linhas por batch durante promocao |
| `STORAGE_DIR` | `data/storage` | Diretorio para arquivos temporarios |

Anos iniciais por fonte (environment vars):

| Variavel | Descricao |
|---|---|
| `ANOS_INICIAIS_DFP` | Anos para sincronizar DFP (ex: "2010,2011,...,2024") |
| `ANOS_INICIAIS_ITR` | Anos para sincronizar ITR |
| `ANOS_INICIAIS_FRE` | Anos para sincronizar FRE |
| `ANOS_INICIAIS_FCA` | Anos para sincronizar FCA |
| `ANOS_INICIAIS_IPE` | Anos para sincronizar IPE |
| `ANOS_INICIAIS_VLMO` | Anos para sincronizar VLMO |
| `ANOS_INICIAIS_CGVN` | Anos para sincronizar CGVN |

---

## 15. Estrutura de Arquivos

### Servico Principal (28 modulos)

```
app/services/ingestion/
  __init__.py
  acquisition.py       # Download HTTP com retry e registro de tentativas
  audit.py             # Auditoria de datasets, consistencia e analise
  backfill.py          # Orquestracao de backfill para anos historicos
  cadastro.py          # Normalizacao e upsert do cadastro de companhias
  cgvn.py              # Processamento CGVN
  dedup.py             # Verificacao de duplicidade por hash
  dependencies.py      # Verificacao de prontidao do grafo de identidade
  engine.py            # Core: ZipIngestionSpec, process_zip_members
  fca.py               # Processamento FCA
  file_manager.py      # IO em disco: download, SHA256, extracao ZIP, deteccao encoding
  financeiro.py        # Processamento DFP/ITR
  fre.py               # Processamento FRE
  ipe.py               # Processamento IPE
  metrics.py           # Metricas Prometheus
  normalizers.py       # Utilitarios de normalizacao (CNPJ, codigo CVM, texto)
  quality.py           # Quality gate
  quarantine.py        # Gerenciamento de quarentena
  repair_rules.py      # CRUD de regras de reparo de identidade
  replay.py            # Replay de linhas, runs e quarentena
  resolver.py          # Resolucao de identidade de companhias
  retry.py             # Taxonomia de erros (RetryableIngestionError, etc.)
  source_registry.py   # Catalogo de fontes de dados (1172 linhas)
  staging.py           # Pipeline de stage: criacao de run, file, member, rows
  summary.py           # Agregacao de contadores de qualidade
  validation.py        # Validacao de linhas e chaves naturais
  vlmo.py              # Processamento VLMO
```

### Modelos

```
app/models/ingestion.py        # 8 tabelas do pipeline
app/models/sincronizacao.py    # Modelos legados (ExecucaoSincronizacao, etc.)
app/models/companhia.py        # Compania (registro mestre)
app/models/identidade.py       # CompanhiaIdentificador, CompanhiaRegistroCvm, etc.
app/models/financeiro.py       # DocumentoFinanceiro, DemonstracaoFinanceira, etc.
app/models/fre.py              # 16 modelos FRE
app/models/fca.py              # 6 modelos FCA
app/models/ipe.py              # IpeDocumento
app/models/vlmo.py             # VlmoDocumento, VlmoConsolidado
app/models/cgvn.py             # CgvnDocumento, CgvnPratica
```

### Worker / Tasks

```
app/worker/tasks.py            # Todas as tarefas Celery (1045 linhas)
app/worker/celery_app.py       # Configuracao do Celery + beat schedule
app/worker/bootstrap.py        # Sincronizacao inicial no startup
```

### API

```
app/api/routers/admin.py       # Endpoints de ingestion (linhas 1291-1497)
app/schemas/admin.py           # Schemas Pydantic (linhas 300-420)
```

### Configuracao

```
app/core/config.py             # Settings com prefixo INGESTION_ (linhas 29-46)
```

### Migracoes Alembic

```
alembic/versions/0006_stop_syncs.py
alembic/versions/0007_ingestion_v2_staging.py
alembic/versions/0008_ingestion_v2_identity.py
alembic/versions/0009_ingestion_v2_quarantine.py
alembic/versions/b1f0c8f4b7aa_rename_ingestion_v2_runtime_to_ingestion.py
alembic/versions/f484cf28f893_split_zip_ingestion.py
```

### Testes (16 arquivos)

```
tests/unit/test_ingestion_v2_cadastro.py
tests/unit/test_ingestion_v2_financeiro.py
tests/unit/test_ingestion_v2_fre.py
tests/unit/test_ingestion_v2_fca.py
tests/unit/test_ingestion_v2_ipe.py
tests/unit/test_ingestion_v2_vlmo.py
tests/unit/test_ingestion_v2_cgvn.py
tests/unit/test_ingestion_v2_validation.py
tests/unit/test_ingestion_v2_staging.py
tests/unit/test_ingestion_v2_resolver.py
tests/unit/test_ingestion_v2_hierarchy.py
tests/unit/test_ingestion_v2_audit.py
tests/unit/test_ingestion_v2_quarantine_replay.py
tests/unit/test_ingestion_v2_ops.py
tests/unit/test_ingestion_v2_retry.py
tests/unit/test_two_phase_ingestion.py
tests/scripts/benchmark_ingestion_stage.py
```
