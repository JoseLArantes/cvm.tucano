# Ingestion V2 Plan

## Purpose

Ingestion v2 must move CVM import from "parse and reject" to "acquire, stage, validate, resolve, repair, replay".

Current ingestion already has useful foundations: idempotent upserts, source file hashes, execution counters, history rows, and quarantine. Main weakness is that deterministic data-shape issues are treated as terminal row rejections. Retry can help network failures, but it cannot fix official-source identity gaps, duplicated regulatory rows, or schema drift.

This plan describes how to build v2 with high consistency, low rejection, repairability, and operational safety.

## Target Outcomes

Primary outcomes:

- Reduce deterministic row rejection from identity issues to near zero.
- Preserve every source row, including rows not promoted to domain tables.
- Make quarantine repairable and replayable.
- Support official CVM identity reality: open companies, foreign companies, repeated CNPJ, repeated market rows, historical CVM codes.
- Add retries only where retries make sense: network, temporary HTTP, transient CVM/service failures.
- Keep domain API behavior stable while improving internals.
- Keep `/health` unauthenticated.
- Keep dependencies in `pyproject.toml`.

Initial measurable targets:

- `companhia_nao_encontrada`:
  - DFP 2021: current sample `9711` rows, target `0`.
  - FRE 2021: current sample `1432` rows, target `0`.
  - ITR 2021: current sample `18875` rows, target `<= 1` before provisional issuer fallback, target `0` after fallback.
- `chave_natural_duplicada_no_arquivo` in cadastro:
  - current sample `147` rows, target `0` hard rejects.
  - same `CD_CVM` with different `TP_MERC`: store as multiple market memberships.
  - same CNPJ with different `CD_CVM`: store as multiple CVM registration identities under one canonical company.
- Retry policy:
  - retry transient acquisition failures.
  - never retry deterministic validation failures.
  - never hide persistent failures behind infinite retry loops.

## Non-goals

- Do not rewrite API routers unless required for identity lookups.
- Do not introduce in-cluster Postgres or Redis templates.
- Do not reintroduce migration jobs in the Helm chart.
- Do not hide official-source conflicts by overwriting source rows.
- Do not use fuzzy name matching as an automatic high-confidence resolver in v2. Fuzzy matching can suggest repairs, but must not silently bind rows unless strict confidence rules are met.

## Evidence From Current Research

Research date: 2026-06-03.

Official sources inspected:

- Open company cadastro: `https://dados.cvm.gov.br/dataset/cia_aberta-cad`
- Open company cadastro data: `https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv`
- Foreign company cadastro: `https://dados.cvm.gov.br/dataset/cia_estrang-cad`
- Foreign company cadastro data: `https://dados.cvm.gov.br/dados/CIA_ESTRANG/CAD/DADOS/cad_cia_estrang.csv`
- DFP data directory: `https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/`
- ITR data directory: `https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS/`
- FRE data directory: `https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/FRE/DADOS/`

Measured current files:

- `cad_cia_aberta.csv`: `2675` rows.
- duplicate CNPJ buckets: `140`.
- duplicate rows after first row: `147`, about `5.50%`.
- duplicate categories:
  - `110` rows: same `CD_CVM`, different `TP_MERC` only.
  - `37` rows: same CNPJ, different `CD_CVM` and registration lifecycle.

Measured 2021 document parent resolution:

| File group | Rows | Missing with current open-company cadastro only | Missing after open + foreign cadastro |
| --- | ---: | ---: | ---: |
| DFP 2021 | `1237654` | `9711` | `0` |
| ITR 2021 | `3643850` | `18875` | `1` |
| FRE 2021 | `185667` | `1432` | `0` |

The remaining ITR row is `EMPRESA FINANCEIRA`, `CD_CVM=3`, `CNPJ=33066408000115`. This should be handled by a low-confidence provisional issuer or a manual identity rule, not by repeated retry.

Current local code pressure points:

- Cadastro duplicate CNPJ rejection happens in `app/services/sincronizacao_cadastro.py`.
- DFP/ITR parent lookup relies on in-memory maps from `companhias`.
- FRE parent lookup queries `companhias` row by row.
- `companhias.cnpj_companhia` and `companhias.codigo_cvm` are unique columns, but CVM source identity is not that simple.
- `RegistroQuarentena` stores raw rejected rows, but there is no repair state, resolution state, replay state, or automated redrive.
- Celery tasks have no `autoretry_for`, retry backoff, retry taxonomy, or dependency deferral.

## Core Design Principles

1. Raw data is never lost.
   Every file, zip member, line number, raw payload, normalized payload, and validation result must be traceable.

2. Rejection must mean "cannot safely promote now", not "throw away".
   Rejected rows live in repairable quarantine with reason codes and replay paths.

3. Official identity must be modeled, not forced into one CNPJ plus one CVM code.
   CVM has foreign companies, historical registrations, multiple markets, repeated codes in cadastro rows, and same CNPJ with different CVM codes.

4. Resolver must be deterministic and auditable.
   Every promoted row must carry enough metadata to explain how `companhia_id` was selected.

5. Retries must be cause-based.
   Retry transport and temporary remote failures. Do not retry bad rows.

6. Staging and promotion must be separate.
   Parsing source files and writing domain tables are different responsibilities.

7. V2 must be deployable gradually.
   Existing v1 API can stay stable while v2 tables and jobs are introduced behind new service boundaries.

## Target Pipeline

Pipeline stages:

1. Acquire source file.
2. Register file and hash.
3. Expand ZIP members when needed.
4. Stage raw rows.
5. Normalize staged rows.
6. Validate staged rows.
7. Build or update issuer identity graph.
8. Resolve document rows to `companhia_id`.
9. Promote valid normalized rows to domain tables.
10. Write metrics, row events, and repair queue items.
11. Replay repaired rows or full files when identity/schema fixes land.

Flow:

```text
CVM HTTP source
  -> acquisition attempt
  -> ingestion_files
  -> ingestion_file_members
  -> ingestion_rows
  -> normalized rows
  -> validation results
  -> identity graph
  -> resolver
  -> domain upsert
  -> metrics + repair queue
```

## New Data Model

### `ingestion_runs`

One row per requested sync operation.

Purpose:

- Replaces relying only on `execucoes_sincronizacao` for detailed v2 state.
- Can coexist with current `execucoes_sincronizacao` during migration.
- Tracks phase-level state.

Columns:

- `id`: UUID primary key.
- `execucao_sincronizacao_id`: nullable FK to current execution table.
- `tipo_fonte`: `cadastro_aberta`, `cadastro_estrangeira`, `dfp`, `itr`, `fre`.
- `ano`: nullable integer.
- `status`: `em_execucao`, `sucesso`, `sem_alteracao`, `falha`, `cancelada`, `bloqueada_dependencia`.
- `phase`: `acquire`, `stage`, `normalize`, `validate`, `identity`, `promote`, `complete`.
- `started_at`, `finished_at`.
- `requested_by_task_id`.
- `message`.
- `quality_summary`: JSON.
- `created_at`, `updated_at`.

Indexes:

- `(tipo_fonte, ano, status)`.
- `(requested_by_task_id)`.
- `(started_at)`.

### `ingestion_files`

One row per remote file payload.

Columns:

- `id`: UUID primary key.
- `ingestion_run_id`: FK.
- `source_url`: text.
- `source_filename`: string.
- `content_sha256`: string.
- `content_length_bytes`: integer.
- `http_status_code`: nullable integer.
- `etag`: nullable string.
- `last_modified`: nullable string/date.
- `downloaded_at`.
- `is_zip`: boolean.
- `already_seen_success`: boolean.

Unique constraints:

- `(source_url, content_sha256)`.

Indexes:

- `(source_filename)`.
- `(content_sha256)`.

### `ingestion_file_members`

One row per CSV inside a ZIP, or one synthetic member for plain CSV.

Columns:

- `id`: UUID primary key.
- `ingestion_file_id`: FK.
- `member_name`: string.
- `member_sha256`: string.
- `member_size_bytes`: integer.
- `encoding`: `utf-8-sig`, `latin1`, or detected value.
- `delimiter`: string, usually `;`.
- `header`: JSON array.
- `row_count`: integer.
- `schema_status`: `ok`, `missing_expected_column`, `unexpected_layout`, `unsupported`.
- `schema_message`: text.

Unique constraints:

- `(ingestion_file_id, member_name)`.

Indexes:

- `(member_name)`.
- `(member_sha256)`.

### `ingestion_rows`

One row per source CSV row.

Columns:

- `id`: UUID primary key.
- `ingestion_run_id`: FK.
- `ingestion_file_member_id`: FK.
- `arquivo_origem`: string.
- `ano_origem`: nullable integer.
- `linha_origem`: integer.
- `raw_data`: JSON.
- `raw_hash`: string.
- `normalized_data`: JSON nullable.
- `normalized_hash`: string nullable.
- `row_kind`: `cadastro_aberta`, `cadastro_estrangeira`, `dfp_documento`, `dfp_demonstracao`, `dfp_composicao`, `dfp_parecer`, `itr_*`, `fre_*`.
- `natural_key`: JSON nullable.
- `validation_status`: `pending`, `valid`, `warning`, `quarantine`, `ignored_duplicate`, `conflict`.
- `validation_reason_code`: nullable string.
- `validation_details`: JSON.
- `resolved_companhia_id`: nullable UUID.
- `resolution_method`: nullable string.
- `resolution_confidence`: nullable numeric/string.
- `promoted_entity`: nullable string.
- `promoted_entity_id`: nullable UUID.
- `created_at`, `updated_at`.

Unique constraints:

- `(ingestion_file_member_id, linha_origem)`.

Indexes:

- `(arquivo_origem, ano_origem)`.
- `(row_kind)`.
- `(validation_status, validation_reason_code)`.
- `(resolved_companhia_id)`.
- `(natural_key)` with JSON support where available.
- `(raw_hash)`.

### `ingestion_row_events`

Append-only events for row state transitions.

Columns:

- `id`: UUID primary key.
- `ingestion_row_id`: FK.
- `event_type`: `normalized`, `validated`, `resolved`, `promoted`, `quarantined`, `replayed`, `manual_override`.
- `event_payload`: JSON.
- `created_at`.
- `created_by`: nullable string.

Purpose:

- Explain why row moved to a state.
- Preserve repair history.
- Support audit/debug without changing domain tables.

### `companhia_registros_cvm`

Official CVM registration rows after semantic merge.

Purpose:

- Model CVM registration identity separately from canonical `companhias`.
- Handle same CNPJ with different `CD_CVM`.
- Handle open and foreign cadastro sources.
- Handle lifecycle and regulatory status history.

Columns:

- `id`: UUID primary key.
- `companhia_id`: FK to `companhias`.
- `fonte_cadastro`: `cad_cia_aberta`, `cad_cia_estrang`, `documento_provisorio`.
- `cnpj_companhia`: nullable string(14).
- `codigo_cvm`: nullable integer.
- `denominacao_social`: nullable string.
- `denominacao_comercial`: nullable string.
- `pais_origem`: nullable string.
- `situacao_registro`: nullable string.
- `data_registro`: nullable date.
- `data_constituicao`: nullable date.
- `data_cancelamento`: nullable date.
- `motivo_cancelamento`: nullable string.
- `data_inicio_situacao`: nullable date.
- `setor_atividade`: nullable string.
- `categoria_registro`: nullable string.
- `data_inicio_categoria`: nullable date.
- `situacao_emissor`: nullable string.
- `data_inicio_situacao_emissor`: nullable date.
- `controle_acionario`: nullable string.
- `endereco`: JSON.
- `responsavel`: JSON.
- `auditor`: nullable string.
- `cnpj_auditor`: nullable string.
- `source_ingestion_row_id`: FK nullable.
- `hash_sem_mercado`: string.
- `hash_origem`: string.
- `arquivo_origem`: string.
- `linha_origem`: nullable integer.
- `created_at`, `updated_at`.

Unique constraints:

- Prefer `(fonte_cadastro, codigo_cvm, cnpj_companhia, data_registro, data_cancelamento, hash_sem_mercado)` or another deterministic official-row key.
- Do not require global uniqueness on `cnpj_companhia` or `codigo_cvm` here.

Indexes:

- `(cnpj_companhia)`.
- `(codigo_cvm)`.
- `(companhia_id)`.
- `(fonte_cadastro)`.
- `(situacao_registro)`.

### `companhia_mercados`

Market memberships from cadastro rows.

Purpose:

- Fix `110` current duplicate rows caused only by different `TP_MERC`.
- Avoid losing `BALCAO ORGANIZADO`, `BALCAO NAO ORGANIZADO`, `BOLSA`, and blank market values.

Columns:

- `id`: UUID primary key.
- `companhia_registro_cvm_id`: FK.
- `tipo_mercado`: nullable string.
- `source_ingestion_row_id`: FK nullable.
- `arquivo_origem`: string.
- `linha_origem`: nullable integer.
- `hash_origem`: string.
- `created_at`.

Unique constraints:

- `(companhia_registro_cvm_id, tipo_mercado)`.

### `companhia_identificadores`

Fast resolver index.

Purpose:

- Resolve documents by CNPJ, CVM code, and future aliases.
- Keep confidence and source.
- Preserve historical identifiers without forcing uniqueness into `companhias`.

Columns:

- `id`: UUID primary key.
- `companhia_id`: FK.
- `tipo`: `cnpj`, `codigo_cvm`, `denominacao_social`, `documento_id`.
- `valor`: string.
- `valor_normalizado`: string.
- `fonte`: `cad_cia_aberta`, `cad_cia_estrang`, `dfp_documento`, `itr_documento`, `fre_documento`, `manual`.
- `confianca`: `alta`, `media`, `baixa`.
- `ativo`: boolean.
- `valid_from`: nullable date.
- `valid_to`: nullable date.
- `source_ingestion_row_id`: nullable FK.
- `created_at`, `updated_at`.

Constraints:

- Do not make `(tipo, valor_normalizado)` globally unique.
- Use non-unique indexes and resolver logic because same CNPJ or name can appear in historical contexts.

Indexes:

- `(tipo, valor_normalizado)`.
- `(companhia_id, tipo)`.
- `(fonte)`.

### `quarantine_items_v2`

Repairable quarantine.

Purpose:

- Replace dead-end quarantine with lifecycle-managed repair queue.
- Can be populated from `ingestion_rows` with `validation_status='quarantine'`.

Columns:

- `id`: UUID primary key.
- `ingestion_row_id`: FK.
- `execucao_sincronizacao_id`: nullable FK for current admin compatibility.
- `arquivo_origem`: string.
- `ano_origem`: nullable integer.
- `linha_origem`: nullable integer.
- `motivo_codigo`: stable reason code.
- `motivo_detalhe`: text.
- `severity`: `info`, `warning`, `error`, `critical`.
- `status`: `pendente`, `resolvido_auto`, `resolvido_manual`, `ignorado`, `bloqueado`.
- `repair_strategy`: nullable string.
- `repair_payload`: JSON nullable.
- `attempt_count`: integer.
- `last_attempt_at`: nullable datetime.
- `resolved_at`: nullable datetime.
- `resolved_by`: nullable string.
- `created_at`, `updated_at`.

Stable reason codes:

- `normalizacao_invalida`.
- `schema_inesperado`.
- `companhia_nao_encontrada`.
- `companhia_ambigua`.
- `chave_natural_duplicada_identica`.
- `chave_natural_duplicada_conflitante`.
- `arquivo_esperado_ausente`.
- `dependencia_cadastro_ausente`.
- `erro_promocao_integridade`.
- `erro_transiente_aquisicao`.

### `repair_rules`

Manual and automatic repair rules.

Purpose:

- Keep fixes explicit and auditable.
- Avoid hardcoding one-off fixes inside parser code.

Columns:

- `id`: UUID primary key.
- `rule_type`: `identity_map`, `ignore_duplicate`, `schema_alias`, `value_override`, `manual_company_bind`.
- `enabled`: boolean.
- `match_payload`: JSON.
- `action_payload`: JSON.
- `reason`: text.
- `created_by`: string.
- `created_at`, `updated_at`.

Examples:

- Bind `CD_CVM=3` and `CNPJ=33066408000115` to a provisional/manual issuer if no official cadastro row exists.
- Treat a new CVM column alias as equivalent after schema drift.
- Mark exact duplicate source rows as ignored.

### `ingestion_attempts`

Attempt log for acquisition and task retry.

Columns:

- `id`: UUID primary key.
- `ingestion_run_id`: nullable FK.
- `task_id`: nullable string.
- `operation`: `download`, `stage`, `promote`, `replay`.
- `attempt_number`: integer.
- `started_at`, `finished_at`.
- `status`: `success`, `retryable_failure`, `terminal_failure`.
- `error_type`: nullable string.
- `error_message`: nullable text.
- `next_retry_at`: nullable datetime.

## Existing Table Changes

### `companhias`

Keep `companhias` as canonical issuer table, but stop treating it as the full official identity model.

Recommended changes:

- Keep current fields for API compatibility.
- Add `tipo_emissor`: `aberta`, `estrangeira`, `provisorio`, nullable at first.
- Add `fonte_identidade_principal`: `cad_cia_aberta`, `cad_cia_estrang`, `documento_provisorio`, `manual`.
- Add `qualidade_identidade`: `alta`, `media`, `baixa`.
- Consider removing strict uniqueness on `codigo_cvm` in a later migration if it blocks historical data. Keep for phase 1 if canonical row stores only preferred code.
- Keep `cnpj_companhia` unique only if canonical policy remains "one canonical company per CNPJ". If later evidence shows multiple true companies share CNPJ at same time, move CNPJ uniqueness fully into `companhia_identificadores`.

Canonical field policy:

- `cnpj_companhia`: preferred/current or best official CNPJ.
- `codigo_cvm`: preferred/current or best official CVM code.
- `tipo_mercado`: legacy display only, derived from `companhia_mercados`.
- `hash_origem`: hash of canonical chosen registration row, not all identity facts.

### `registros_quarentena`

Keep existing table for API compatibility during phase 1.

Bridge behavior:

- v2 writes both `quarantine_items_v2` and legacy `registros_quarentena` until admin API is migrated.
- Legacy `motivo` should use reason code plus short detail.
- After admin v2 endpoints exist, legacy writes can stop or become compatibility view.

### `execucoes_sincronizacao`

Keep as high-level execution summary.

Add later if useful:

- `quality_summary`: JSON.
- `retry_count`: integer.
- `phase`: string.

Do not block v2 on these additions because `ingestion_runs` can carry detailed state.

## Normalization Strategy

### Shared Normalization Rules

Move common helpers into a v2 normalizer module:

- `normalizar_texto`.
- `normalizar_cnpj`.
- `normalizar_data`.
- `normalizar_inteiro`.
- `normalizar_decimal_cvm`.
- `normalizar_booleano`.
- `gerar_hash_canonico`.
- `normalizar_header`.
- `normalizar_chave_natural`.

Additional v2 rules:

- `normalizar_cnpj_opcional`: returns `None` for blank, validates only when present.
- `normalizar_codigo_cvm`: accepts zero-padded strings like `057886`, stores integer `57886`, stores raw string in normalized metadata if useful.
- `normalizar_nome_emissor`: uppercases only for matching key, preserves display text.
- `normalizar_tipo_mercado`: preserves official text, maps blank to `None`.

### Open Company Cadastro

Source:

- `CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv`.

Important source columns:

- `CNPJ_CIA`.
- `CD_CVM`.
- `DENOM_SOCIAL`.
- `DENOM_COMERC`.
- `SIT`.
- `DT_REG`.
- `DT_CANCEL`.
- `MOTIVO_CANCEL`.
- `DT_INI_SIT`.
- `SETOR_ATIV`.
- `TP_MERC`.
- `CATEG_REG`.
- `DT_INI_CATEG`.
- `SIT_EMISSOR`.
- `DT_INI_SIT_EMISSOR`.
- `CONTROLE_ACIONARIO`.
- address, responsible, auditor fields.

V2 behavior:

- Stage all rows.
- Normalize all rows.
- Build `hash_sem_mercado` ignoring `TP_MERC`, `linha_origem`, `hash_origem`.
- Group by `(fonte_cadastro, codigo_cvm, cnpj_companhia, hash_sem_mercado)`.
- If group differs only by `TP_MERC`, create one `companhia_registro_cvm` plus multiple `companhia_mercados`.
- If same CNPJ appears with different `CD_CVM`, bind all registrations to same canonical `companhia` unless evidence shows different legal identity.
- Never reject solely because CNPJ already appeared earlier in same file.

### Foreign Company Cadastro

Source:

- `CIA_ESTRANG/CAD/DADOS/cad_cia_estrang.csv`.

Important source differences:

- CNPJ column is `CNPJ`, not `CNPJ_CIA`.
- Includes `PAIS_ORIGEM`.
- Does not have the exact same shape as open company cadastro.

V2 normalized fields:

- `tipo_emissor = estrangeira`.
- `fonte_cadastro = cad_cia_estrang`.
- `cnpj_companhia = normalizar_cnpj(row["CNPJ"])` when present.
- `codigo_cvm = normalizar_codigo_cvm(row["CD_CVM"])`.
- `denominacao_social`.
- `denominacao_comercial`.
- `pais_origem`.
- `situacao_registro`.
- dates and sector where available.
- missing open-company-only fields become `None` or `{}`.

V2 behavior:

- Import foreign cadastro before DFP/ITR/FRE promotion.
- Add CNPJ and CVM code identifiers with high confidence.
- Use this source to resolve foreign issuer documents such as `AURA MINERALS INC.`, `GP INVESTMENTS, LTD.`, `NU HOLDINGS LTD.`, `G2D INVESTMENTS, LTD.`, `PPLA PARTICIPATIONS LTD.`, `WILSON SONS LTD.`, `INTER & CO, INC.`.

### Financial and FRE Documents

Document header rows are identity anchors.

For DFP/ITR:

- main file: `{prefixo}_cia_aberta_{ano}.csv`.
- key fields: `CNPJ_CIA`, `CD_CVM`, `DT_REFER`, `VERSAO`, `ID_DOC`.
- child files usually include `CNPJ_CIA`, `DT_REFER`, `VERSAO`; many include `CD_CVM`, some do not.

For FRE:

- main file: `fre_cia_aberta_{ano}.csv`.
- key fields: `CNPJ_CIA`, `CD_CVM`, `DT_REFER`, `VERSAO`, `ID_DOC`.
- child MVP files use mixed-case fields like `CNPJ_Companhia`, `Data_Referencia`, `Versao`, `ID_Documento`, and often lack `CD_CVM`.

V2 behavior:

- Parse and stage document header file first.
- Build document header map:
  - key: `(tipo_formulario, id_documento, versao, data_referencia)`.
  - value: resolved `companhia_id`, source CNPJ, source CVM code, denomination.
- For child rows:
  - first try direct CNPJ/code resolver.
  - if missing or ambiguous, try document header map by `ID_Documento`, `Versao`, `Data_Referencia`.
  - if direct CNPJ and document header disagree, quarantine as `companhia_ambigua` unless a repair rule explains it.

## Identity Resolution Algorithm

Inputs:

- `tipo_formulario`: nullable for cadastro.
- `arquivo_origem`.
- `ano_origem`.
- `cnpj_companhia`: nullable.
- `codigo_cvm`: nullable.
- `denominacao_companhia`: nullable.
- `id_documento`: nullable.
- `versao`: nullable.
- `data_referencia`: nullable.

Output:

- `companhia_id`.
- `resolution_method`.
- `resolution_confidence`.
- `resolution_details`.

Resolution order:

1. Exact CNPJ in `companhia_identificadores`.
   - `tipo='cnpj'`, `valor_normalizado=<cnpj>`.
   - If one active high-confidence match, return it.
   - If multiple matches point to same `companhia_id`, return that company.
   - If multiple companies, continue with CVM code if present, otherwise quarantine `companhia_ambigua`.

2. Exact CVM code in `companhia_identificadores`.
   - `tipo='codigo_cvm'`, `valor_normalizado=str(codigo_cvm)`.
   - If one active/high-confidence match, return it.
   - If CNPJ also matched a different company, quarantine `companhia_ambigua`.

3. Document header map.
   - Use `(tipo_formulario, id_documento, versao, data_referencia)`.
   - Confidence high when header was resolved by official cadastro.
   - Confidence medium when header used provisional issuer.

4. Repair rule.
   - Match `repair_rules.rule_type='identity_map'`.
   - Use explicit rule only.
   - Mark `resolution_method='manual_identity_rule'`.

5. Provisional issuer.
   - Only for document rows with enough stable identifiers:
     - CNPJ present and valid, or CVM code present.
     - denomination present.
   - Create/attach `companhia` with `tipo_emissor='provisorio'`, `qualidade_identidade='baixa'`.
   - Add identifiers with `fonte` matching document source and `confianca='baixa'`.
   - Mark row as warning, not hard reject.
   - Put linked quarantine item with `motivo_codigo='companhia_provisoria'` if follow-up is needed.

6. Quarantine.
   - `companhia_nao_encontrada` when no safe match and not enough data for provisional issuer.
   - `companhia_ambigua` when multiple plausible companies remain.

Resolution confidence:

- `alta`: official cadastro exact CNPJ/code, or child row via header map whose header was official-resolved.
- `media`: manual repair rule with exact identifiers, or child row via provisional header.
- `baixa`: provisional issuer from document-only evidence.

## Duplicate Handling

### Cadastro Duplicate Policy

Old behavior:

- Reject any repeated `CNPJ_CIA` in same file.

New behavior:

1. Same CNPJ, same `CD_CVM`, different `TP_MERC` only:
   - Promote one `companhia_registro_cvm`.
   - Promote all markets into `companhia_mercados`.
   - Count as `deduplicated_merged_market`, not rejected.

2. Same CNPJ, different `CD_CVM`:
   - Promote one canonical `companhia`.
   - Promote each `CD_CVM` as separate `companhia_registros_cvm`.
   - Add each code to `companhia_identificadores`.
   - Canonical `companhias.codigo_cvm` chooses best current/preferred code.
   - Count as `merged_historical_registration`, not rejected.

3. Same `CD_CVM`, same CNPJ, conflicting fields beyond market:
   - If conflict is only whitespace/canonical-equivalent, dedupe silently.
   - If conflict is status/date/category, choose deterministic winner for canonical company, preserve all registration rows, create warning event.
   - Do not hard reject unless required fields are invalid.

Canonical winner ranking:

1. `situacao_registro='ATIVO'`.
2. non-cancelled over cancelled.
3. latest `data_inicio_situacao`.
4. latest `data_registro`.
5. source priority: `cad_cia_aberta` over document provisional, `cad_cia_estrang` for foreign companies.
6. stable tie-breaker: lower `linha_origem`.

### Document Duplicate Policy

Old behavior:

- Reject any repeated natural key in a file.

New behavior:

1. Same natural key and same normalized hash:
   - Keep first for promotion.
   - Mark later rows as `ignored_duplicate`.
   - No quarantine error.

2. Same natural key and different normalized hash:
   - Preserve all rows in staging.
   - Promote deterministic winner only if rule exists for that table.
   - Otherwise quarantine later conflicting rows as `chave_natural_duplicada_conflitante`.
   - Add row event with field-level differences.

3. Same key but line metadata only differs:
   - Treat as identical duplicate.

4. Existing DB row and incoming row differ:
   - Existing v1 behavior of upsert plus history remains.
   - Difference is not a duplicate-file error; it is document update/re-presentation behavior.

## Validation Model

Validation should produce structured results, not just exceptions.

Validation output shape:

```json
{
  "status": "valid",
  "reason_code": null,
  "severity": "info",
  "details": {},
  "repairable": false
}
```

Validation groups:

1. Schema validation.
   - Header has required columns for row kind.
   - Unknown columns allowed by default but logged.
   - Missing required columns quarantines whole member as `schema_inesperado`.

2. Type validation.
   - CNPJ length and digits.
   - dates parse as ISO.
   - decimal CVM values parse.
   - integer fields parse.

3. Required business fields.
   - document rows need date, version, id_document when expected.
   - demonstration rows need account code, date, version, reference.
   - cadastro rows need at least CNPJ or CVM code plus name.

4. Natural key validation.
   - compute natural key.
   - detect exact duplicate vs conflict duplicate.

5. Referential validation.
   - resolve company.
   - if missing, repair/provisional/quarantine per resolver.

6. Promotion validation.
   - DB constraints.
   - foreign key availability.
   - idempotent upsert ability.

Quality counters:

- `rows_raw`.
- `rows_normalized`.
- `rows_valid`.
- `rows_promoted_inserted`.
- `rows_promoted_updated`.
- `rows_promoted_unchanged`.
- `rows_duplicate_ignored`.
- `rows_duplicate_merged`.
- `rows_quarantined`.
- `rows_repaired_auto`.
- `rows_repaired_manual`.
- `rows_provisional_company`.
- by `reason_code`.
- by `arquivo_origem`.

## Promotion Strategy

Promotion means writing normalized staged rows into existing domain tables.

Rules:

- Promotion reads from `ingestion_rows` where `validation_status in ('valid', 'warning')`.
- Promotion uses existing upsert logic where possible.
- Promotion writes `promoted_entity` and `promoted_entity_id` back to `ingestion_rows`.
- Promotion writes history rows when business fields change.
- Promotion never deletes source staging rows.
- Promotion can be replayed idempotently.

Transaction boundaries:

- Acquisition and staging commit independently.
- Promotion can commit per member or per batch.
- If promotion fails mid-file, staging remains complete; replay can resume.
- `ingestion_run.status='sucesso'` only when all required members are staged and promotion quality gates pass.

Quality gates:

- Fatal member schema error on required file: run fails.
- `companhia_nao_encontrada` above configured threshold: run status can be `falha_qualidade` or `sucesso_com_alerta` depending rollout phase.
- Any `erro_promocao_integridade`: run fails unless row was quarantined and remaining rows promoted.
- Deterministic duplicates merged/ignored do not fail quality gate.

## Retry Strategy

### Retryable Errors

Retry acquisition for:

- `httpx.TimeoutException`.
- network connection errors.
- HTTP `408`.
- HTTP `429`.
- HTTP `500`, `502`, `503`, `504`.
- incomplete read.
- corrupt ZIP when re-download may fix it.

Retry promotion for:

- transient DB connection loss.
- serialization/deadlock errors where transaction can be retried safely.

Defer and retry later:

- `dependencia_cadastro_ausente`: DFP/ITR/FRE requested before cadastro v2 completes.
- identity graph rebuild in progress.

### Non-retryable Errors

Do not retry:

- invalid CNPJ.
- invalid date.
- missing required field in source row.
- duplicate natural key conflict.
- company not found after all resolver paths.
- schema unsupported until code changes.
- DB integrity error caused by a deterministic model bug.

These must create quarantine or failed execution state with clear reason.

### Celery Task Configuration

Use Celery retry features for task-level transient failures:

- `autoretry_for=(httpx.TimeoutException, httpx.TransportError, RetryableIngestionError)`.
- `retry_backoff=True`.
- `retry_backoff_max=600`.
- `retry_jitter=True`.
- `max_retries=5`.

Task-specific behavior:

- Cadastro tasks retry acquisition only.
- DFP/ITR/FRE tasks check dependency state before download.
- If cadastro is absent or stale, mark `bloqueada_dependencia` and schedule/defer rather than importing with massive rejects.

### HTTP Client

Introduce shared acquisition helper:

- `app/services/ingestion/http.py`.

Responsibilities:

- use `httpx.Client`.
- set connect/read timeouts.
- classify HTTP status.
- compute SHA-256.
- store attempt metadata.
- return bytes plus response metadata.

Pseudo-code:

```python
def baixar_arquivo(url: str, *, timeout: float, run_id: UUID) -> DownloadResult:
    for attempt in range(max_attempts):
        try:
            response = client.get(url, timeout=timeout)
            if response.status_code in RETRYABLE_STATUS:
                raise RetryableHttpStatus(response.status_code)
            response.raise_for_status()
            return DownloadResult(...)
        except RETRYABLE_EXCEPTIONS as exc:
            registrar_attempt(...)
            if attempt == max_attempts - 1:
                raise
            sleep(backoff(attempt))
```

For Celery tasks, prefer Celery retry instead of manual `sleep` inside worker. Manual retry helper is acceptable for non-Celery contexts and tests, but worker should not sleep long inside task when `self.retry` can reschedule.

## Repair and Replay

### Repair Queue

Every quarantine item has:

- stable reason code.
- raw row link.
- normalized row if available.
- suggested repair strategy where possible.
- status.
- attempt count.

Auto-repair examples:

- `companhia_nao_encontrada` because foreign cadastro was not imported:
  - import `cad_cia_estrang.csv`.
  - rebuild identity graph.
  - replay quarantined rows.

- `chave_natural_duplicada_identica`:
  - mark duplicate rows ignored.
  - no domain replay needed.

- `schema_alias`:
  - if CVM renames column and alias rule exists, normalize and replay member.

Manual repair examples:

- ambiguous CNPJ maps to multiple canonical companies.
- document-only issuer with no official cadastro row.
- same natural key but conflicting values.

### Replay Modes

1. Row replay.
   - Reprocess selected `ingestion_rows`.
   - Use current normalizers, repair rules, identity graph.
   - Promote if valid.

2. File member replay.
   - Reprocess all rows in one CSV member.
   - Useful after schema alias or parser fix.

3. Run replay.
   - Reprocess full source run from already-stored payload/staging.
   - No network needed.

4. Full source re-download.
   - Used when CVM file changed or previous download corrupt.

Replay commands or service methods:

- `replay_quarantine(reason_code=None, arquivo_origem=None, ano=None)`.
- `replay_ingestion_run(run_id)`.
- `replay_file_member(member_id)`.
- `rebuild_identity_graph()`.

Admin API later:

- `POST /admin/ingestion-v2/replay/quarantine`.
- `POST /admin/ingestion-v2/runs/{run_id}/replay`.
- `POST /admin/ingestion-v2/identity/rebuild`.
- `GET /admin/ingestion-v2/quarantine`.
- `GET /admin/ingestion-v2/quality`.

## Source-specific Build Plan

### Phase 1: Observability and Audit Harness

Goal:

- Prove current rejection causes with repeatable local tooling.
- Add metrics before changing core ingestion.

Work:

- Add a script under `scripts/` or test helper:
  - downloads current official files.
  - samples `cad_cia_aberta.csv`, `cad_cia_estrang.csv`, DFP/ITR/FRE selected years.
  - computes duplicate categories.
  - computes `companhia_nao_encontrada` before/after foreign cadastro.
  - emits JSON and markdown summary.

Suggested script:

- `scripts/audit-ingestion-consistency.py`.

Outputs:

- `tmp/ingestion_audit_YYYYMMDD.json`.
- summary table in stdout.

Tests:

- Unit test categorization with small fixtures.
- No live network in default tests.
- Optional marker `pytest -m cvm_live`.

Definition of done:

- One command can reproduce current duplicate/missing-parent metrics.
- Audit logic proves v2 changes reduce deterministic rejects.

### Phase 2: Staging Tables

Goal:

- Preserve raw rows and validation results.

Work:

- Add Alembic migration for:
  - `ingestion_runs`.
  - `ingestion_files`.
  - `ingestion_file_members`.
  - `ingestion_rows`.
  - `ingestion_row_events`.
  - `ingestion_attempts`.
- Add SQLAlchemy models.
- Add repository helpers:
  - create run.
  - register file.
  - register member.
  - bulk insert rows.
  - update row validation state.
  - append events.

Testing:

- Migration upgrade/downgrade if downgrade supported locally.
- SQLite unit tests for models where possible.
- PostgreSQL compatibility should be checked in CI or local Docker because JSON/index behavior differs.

Definition of done:

- Cadastro v2 can stage all rows without promoting.
- DFP/ITR/FRE v2 can stage ZIP member metadata and row counts.

### Phase 3: Identity Graph

Goal:

- Model official CVM identity correctly.

Work:

- Add tables:
  - `companhia_registros_cvm`.
  - `companhia_mercados`.
  - `companhia_identificadores`.
  - optionally `repair_rules`.
- Implement `normalizar_linha_cadastro_aberta_v2`.
- Implement `normalizar_linha_cadastro_estrangeira_v2`.
- Implement merge logic:
  - group same code/CNPJ ignoring market.
  - create multiple markets.
  - bind same CNPJ different codes to canonical company.
- Implement canonical company selector.
- Implement identity identifier generation.

Important behavior:

- `cad_cia_aberta.csv` and `cad_cia_estrang.csv` both run before document promotion.
- Foreign cadastro uses `CNPJ`, not `CNPJ_CIA`.
- `companhias` remains canonical and API-compatible.

Testing:

- Fixture: same CNPJ + same CD + two markets -> one registro, two markets, no quarantine.
- Fixture: same CNPJ + two CD_CVM -> one companhia, two registros, two code identifiers.
- Fixture: foreign company with `CNPJ` column -> resolves by CNPJ and code.
- Fixture: duplicate foreign rows for same company -> merged deterministically.

Definition of done:

- Current `cad_cia_aberta.csv` duplicate pattern no longer creates hard rejects.
- Foreign company cadastro creates high-confidence identifiers.

### Phase 4: Shared Resolver

Goal:

- One resolver for DFP, ITR, FRE.

Work:

- Add `app/services/ingestion/resolver.py`.
- Implement `ResolverInput` and `ResolverResult`.
- Implement exact CNPJ lookup against `companhia_identificadores`.
- Implement exact CVM code lookup.
- Implement document header map lookup.
- Implement repair rule lookup.
- Implement provisional issuer creation behind explicit config flag.
- Write `resolution_method` and `resolution_confidence` to staging rows.

Resolver methods:

- `cnpj_identificador_alta`.
- `codigo_cvm_identificador_alta`.
- `documento_header_alta`.
- `manual_identity_rule_media`.
- `provisorio_documento_baixa`.

Testing:

- CNPJ resolves to one company.
- CVM code resolves when CNPJ absent.
- CNPJ and CVM code conflict -> `companhia_ambigua`.
- FRE child row resolves via `ID_Documento` map.
- Document-only issuer creates provisional company when enabled.
- Document-only issuer quarantines when provisional disabled.

Definition of done:

- DFP 2021 sample missing parents drop to zero with open + foreign cadastro.
- FRE 2021 sample missing parents drop to zero with header map and foreign cadastro.

### Phase 5: Document V2 Promotion

Goal:

- Promote DFP/ITR/FRE rows through staging and resolver.

Work:

- Extract current DFP/ITR parser logic from `sincronizacao_financeiro.py` into reusable v2 parser classes/functions.
- Extract current FRE parser logic from `sincronizacao_fre.py` into reusable v2 parser classes/functions.
- Preserve existing domain upsert functions but feed them from staged normalized rows.
- Add exact duplicate vs conflict duplicate detection.
- Record row promotion outcome.
- Keep legacy execution counters updated.

Ordering:

1. Stage all members.
2. Normalize all rows.
3. Validate all rows.
4. Promote document header rows first.
5. Build document header map.
6. Promote child rows.

DFP/ITR notes:

- `dfp_cia_aberta_{ano}.csv` and `itr_cia_aberta_{ano}.csv` must be first for document map.
- Demonstration natural key currently includes:
  - `tipo_formulario`.
  - `tipo_demonstracao`.
  - `escopo_demonstracao`.
  - `cnpj_companhia`.
  - `data_referencia`.
  - `versao`.
  - `grupo_demonstracao`.
  - `ordem_exercicio`.
  - `data_fim_exercicio`.
  - `codigo_conta`.
- Keep this key unless audit proves it causes false conflicts.

FRE notes:

- MVP files currently include:
  - documentos.
  - auditores.
  - capital social.
  - posicao acionaria.
  - remuneracao total orgao.
  - empregado posicao genero optional.
- Child rows often use mixed-case fields and lack `CD_CVM`.
- Header map is mandatory for consistent child resolution.

Testing:

- Existing v1 tests keep passing or get v2-equivalent tests.
- New fixture with foreign issuer in DFP resolves.
- New fixture with FRE child row lacking code resolves through header map.
- Duplicate identical row ignored, not quarantined.
- Duplicate conflicting row quarantined with diff details.

Definition of done:

- V2 can import small fixtures into existing domain tables.
- V2 can stage and report all rows for live 2021 files.
- Rejection reasons are structured and bounded.

### Phase 6: Repairable Quarantine and Replay

Goal:

- Make failures fixable without full manual DB surgery.

Work:

- Add `quarantine_items_v2`.
- Populate from `ingestion_rows`.
- Add `repair_rules`.
- Add replay services:
  - row replay.
  - member replay.
  - run replay.
  - quarantine replay by reason.
- Add admin API endpoints or internal service first.
- Add audit log events for repair/replay.

Auto-repair jobs:

- Rebuild identity graph after foreign cadastro import.
- Replay `companhia_nao_encontrada`.
- Mark identical duplicates ignored.
- Apply schema alias rule then replay affected member.

Testing:

- Quarantined missing company row resolves after identity graph adds company.
- Manual repair rule binds row to company and replay promotes it.
- Replay is idempotent.
- Replay increments attempt count and records last attempt.

Definition of done:

- No quarantine reason is a dead end.
- Operator can answer: why rejected, what fix is suggested, was it replayed, what happened.

### Phase 7: Retry and Dependency Deferral

Goal:

- Add safe retries without masking deterministic errors.

Work:

- Create retryable exception hierarchy:
  - `RetryableIngestionError`.
  - `RetryableHttpStatus`.
  - `DependencyNotReady`.
  - `TerminalIngestionError`.
- Add acquisition helper.
- Configure Celery `autoretry_for` and backoff for retryable exceptions.
- Add dependency check:
  - DFP/ITR/FRE require successful recent `cadastro_aberta` and `cadastro_estrangeira` v2 runs or valid identity graph.
- If dependency missing:
  - mark run `bloqueada_dependencia`.
  - schedule cadastro tasks.
  - retry/defer document task.

Testing:

- HTTP timeout retries.
- HTTP 404 does not retry.
- HTTP 503 retries.
- missing cadastro defers document sync, does not reject rows.
- parser validation error does not retry.

Definition of done:

- Retry count visible in execution/attempt logs.
- Transient failures recover.
- Deterministic row errors go to quarantine or failed quality gate.

### Phase 8: Admin and Observability

Goal:

- Make quality visible.

Work:

- Extend admin dashboard summary:
  - v2 run status.
  - quality counters.
  - top quarantine reasons.
  - top files by quarantine count.
  - retry attempts.
  - identity graph stats.
- Add Prometheus metrics:
  - `cvm_ingestion_rows_total{source,status,reason}`.
  - `cvm_ingestion_run_duration_seconds{source,phase}`.
  - `cvm_ingestion_retries_total{source,operation,error_type}`.
  - `cvm_ingestion_quarantine_total{source,reason}`.
  - `cvm_ingestion_identity_resolution_total{method,confidence}`.
  - `cvm_ingestion_provisional_companies_total`.

Alerts:

- `companhia_nao_encontrada` above threshold.
- required file missing.
- retry exhaustion.
- staging success but promotion failure.
- identity graph stale.

Definition of done:

- Operator can diagnose ingestion quality from API/dashboard/logs.
- Metrics distinguish deterministic data issues from transient platform issues.

### Phase 9: Rollout and Backfill

Goal:

- Move production safely from v1 to v2.

Rollout steps:

1. Deploy staging tables and v2 services dark.
2. Run v2 audit/staging side-by-side without domain promotion.
3. Compare v1 reject counters vs v2 predicted rejects.
4. Enable cadastro v2 promotion.
5. Rebuild identity graph.
6. Enable DFP/ITR/FRE v2 promotion for one year, e.g. 2021.
7. Validate row counts and API query behavior.
8. Enable all configured years.
9. Replay repairable quarantine.
10. Turn off v1 import paths after parity acceptance.

Backfill strategy:

- Prefer reprocessing from official files because v2 staging needs raw rows.
- If source hash unchanged and v1 domain rows already exist, v2 promotion should mark them unchanged.
- For historical years, run oldest to newest if canonical identity lifecycle needs history.
- For current daily/weekly jobs, run cadastro before docs.

Rollback:

- v2 tables are additive.
- Existing v1 tables remain.
- If v2 promotion fails, disable v2 task route and use v1 tasks.
- Do not drop v1 code until v2 has stable runs across configured years.

Definition of done:

- v2 imports configured years with quality gates.
- v1 tasks can be retired.
- admin/replay supports operations.

## Implementation Modules

Suggested new package:

```text
app/services/ingestion/
  __init__.py
  acquisition.py
  staging.py
  validation.py
  normalizers.py
  cadastro.py
  financeiro.py
  fre.py
  identity.py
  resolver.py
  promotion.py
  quarantine.py
  replay.py
  retry.py
  metrics.py
```

Suggested model files:

```text
app/models/ingestion.py
app/models/identidade.py
```

Suggested tests:

```text
tests/unit/test_ingestion_v2_acquisition.py
tests/unit/test_ingestion_v2_cadastro.py
tests/unit/test_ingestion_v2_identity.py
tests/unit/test_ingestion_v2_resolver.py
tests/unit/test_ingestion_v2_duplicates.py
tests/unit/test_ingestion_v2_quarantine.py
tests/unit/test_ingestion_v2_replay.py
tests/unit/test_ingestion_v2_retry.py
tests/integration/test_ingestion_v2_financeiro.py
tests/integration/test_ingestion_v2_fre.py
```

## Detailed Build Tasks

### Task Group A: Audit Harness

- Add audit script.
- Add fixtures for duplicate cadastro rows.
- Add fixtures for foreign issuer rows.
- Add output schema:
  - source.
  - row_count.
  - duplicate_count.
  - missing_parent_count.
  - missing_parent_after_foreign_count.
  - top reasons.
- Add documentation in script header.

Acceptance:

- Running script produces same category names every time.
- Script does not mutate DB.

### Task Group B: Migrations and Models

- Add Alembic migration for staging tables.
- Add Alembic migration for identity tables.
- Add SQLAlchemy models.
- Add model imports to `app/models/__init__.py` if project uses centralized metadata import.
- Add basic CRUD/service helpers.

Acceptance:

- `alembic upgrade head` succeeds.
- `pytest` fixture DB can create all tables.

### Task Group C: Cadastro V2

- Implement open cadastro parser.
- Implement foreign cadastro parser.
- Implement semantic duplicate merge.
- Implement canonical company selector.
- Implement identity generation.
- Add sync task or service:
  - `sincronizar_cadastro_companhias_v2`.
  - either downloads both sources or has separate sub-runs for open/foreign.

Acceptance:

- No hard reject for `TP_MERC` duplicate.
- Foreign companies exist in identity graph.
- Existing `companhias` API can still list canonical companies.

### Task Group D: Resolver V2

- Implement resolver input/output dataclasses.
- Implement exact lookup methods.
- Implement ambiguity handling.
- Implement document header map.
- Implement provisional issuer mode.
- Emit resolution details into staging rows.

Acceptance:

- Resolver can explain each decision.
- Ambiguous cases are quarantined, not randomly bound.

### Task Group E: Financeiro V2

- Stage ZIP members.
- Normalize DFP/ITR document rows.
- Normalize demonstration rows.
- Normalize composition rows.
- Normalize parecer rows.
- Validate natural keys.
- Promote through existing tables.
- Preserve existing history behavior.

Acceptance:

- Existing financeiro tests pass or v2 equivalents pass.
- 2021 DFP sample gets zero missing company after identity graph.
- 2021 ITR sample gets only known leftover before provisional/manual rule.

### Task Group F: FRE V2

- Stage FRE ZIP members.
- Normalize MVP files.
- Build header map from `fre_cia_aberta_{ano}.csv`.
- Resolve child rows through direct identity or header map.
- Promote through existing FRE tables.

Acceptance:

- Existing FRE tests pass or v2 equivalents pass.
- 2021 FRE sample gets zero missing company after identity graph/header map.

### Task Group G: Quarantine V2

- Implement quarantine item creation.
- Bridge to legacy `RegistroQuarentena`.
- Implement reason-code taxonomy.
- Add row event logging.
- Add replay services.

Acceptance:

- A missing company row can be replayed after identity fix.
- Exact duplicate can be auto-resolved.
- Admin can list v2 quarantine or service can expose it internally.

### Task Group H: Retry V2

- Add acquisition helper.
- Add retry exceptions.
- Configure Celery task retries.
- Add dependency deferral.
- Add attempt logging.

Acceptance:

- Retryable network failure retries.
- Terminal row validation failure does not retry.
- DFP/ITR/FRE does not run before identity prerequisites.

### Task Group I: Observability and SLO Gates

- Add counters to execution summaries.
- Add Prometheus metrics.
- Add log events with run ID, member, phase, and reason code.
- Add quality gate config.

Acceptance:

- Run quality can be seen without inspecting DB manually.
- Alert thresholds can be configured.

## Dependency and Configuration Plan

Dependencies:

- Prefer standard library plus current dependencies.
- Keep dependency source of truth in `pyproject.toml`.
- Do not add heavy data-quality frameworks unless needed. The design can use checkpoint-like concepts without adding Great Expectations.

Settings to add:

- `INGESTION_V2_ENABLED`: default `false`.
- `INGESTION_V2_PROMOTE_ENABLED`: default `false` during dark launch.
- `INGESTION_V2_PROVISIONAL_COMPANY_ENABLED`: default `true` only after review, or `false` first.
- `INGESTION_V2_MAX_RETRIES`: default `5`.
- `INGESTION_V2_RETRY_BACKOFF_MAX_SECONDS`: default `600`.
- `INGESTION_V2_COMPANY_MISSING_MAX_RATIO`: default `0.0001`.
- `INGESTION_V2_STAGE_BATCH_SIZE`: default `5000`.
- `INGESTION_V2_PROMOTE_BATCH_SIZE`: default `5000`.

## Testing Strategy

### Unit Tests

Must cover:

- open cadastro normalization.
- foreign cadastro normalization.
- CNPJ optional normalization.
- `CD_CVM` zero-padded normalization.
- duplicate market merge.
- same CNPJ different CVM code merge.
- canonical company selector.
- identity identifier generation.
- resolver exact CNPJ.
- resolver exact CVM code.
- resolver conflict.
- resolver header map.
- duplicate identical detection.
- duplicate conflict detection.
- quarantine reason code creation.
- retry classification.

### Integration Tests

Must cover:

- cadastro v2 full fixture into DB.
- DFP fixture with foreign issuer.
- ITR fixture with composition lacking `CD_CVM`.
- FRE fixture where child rows lack `CD_CVM` and resolve via header map.
- replay after identity graph update.
- idempotent second run with same file hash.
- update run with changed business value and history row.

### Live Optional Tests

Add optional marker:

- `pytest -m cvm_live`.

Use only manually or scheduled non-blocking job:

- download official current cadastro files.
- download one small selected year or cached sample.
- run audit without DB mutation or with disposable DB.

Do not make live CVM network required for default CI.

## Operational Runbooks

### Normal Daily Flow

1. Run open cadastro v2.
2. Run foreign cadastro v2.
3. Rebuild identity graph.
4. Run configured DFP/ITR/FRE jobs.
5. Replay auto-repairable quarantine for recent runs.
6. Emit quality report.

### When `companhia_nao_encontrada` Spikes

1. Check whether foreign cadastro ran successfully.
2. Check identity graph freshness.
3. Inspect top missing names/CNPJ/code.
4. Replay missing-company quarantine after identity rebuild.
5. If still missing, create provisional/manual identity rule only with source evidence.

### When Duplicate Natural Key Spikes

1. Split exact duplicate vs conflicting duplicate.
2. Exact duplicate: mark ignored.
3. Conflicting duplicate: inspect field diffs.
4. Add deterministic rule only if CVM pattern is understood.
5. Replay affected member.

### When Schema Error Appears

1. Compare header to expected schema.
2. If added columns only, allow and log.
3. If renamed columns, add schema alias rule and parser test.
4. Replay affected member.
5. If removed required columns, fail run and keep staged raw rows.

### When Retry Exhausts

1. Check `ingestion_attempts`.
2. If HTTP 5xx/timeout, rerun later.
3. If 404, confirm year/source URL exists.
4. If corrupt ZIP, re-download and compare hash.
5. If persistent, leave run failed with clear message.

## Risks and Mitigations

Risk: identity graph accidentally merges distinct companies.

Mitigation:

- Avoid fuzzy automatic matching.
- Use exact CNPJ/code first.
- Record resolution method.
- Quarantine ambiguity.
- Keep all official registration rows.

Risk: existing API assumes unique CNPJ/code.

Mitigation:

- Keep `companhias` canonical row.
- Move historical identities into child tables.
- Update lookup routes only when needed to search identifiers.

Risk: staging tables grow large.

Mitigation:

- Add retention policy after v2 stable.
- Keep raw rows for recent runs and failed/repaired rows longer.
- Store payload hash and source metadata.
- Consider compression or partitioning later if needed.

Risk: v2 complexity delays immediate rejection reduction.

Mitigation:

- Phase 3 foreign cadastro plus resolver can fix biggest `companhia_nao_encontrada` quickly.
- Duplicate market merge can fix cadastro 5.5% quickly.
- Staging/replay can be incremental.

Risk: retry creates duplicate execution noise.

Mitigation:

- Use idempotent file hash and run status.
- Log attempts separately.
- Keep `sem_alteracao` behavior when successful hash already imported.

Risk: partial promotion leaves inconsistent state.

Mitigation:

- Stage first.
- Promote idempotently.
- Track row promotion state.
- Replay incomplete runs.

## Suggested First Sprint

Sprint goal:

- Prove and fix largest deterministic rejection causes without broad API rewrite.

Scope:

1. Add audit script.
2. Add foreign cadastro normalizer and import path.
3. Add semantic duplicate handling for cadastro:
   - same `CD_CVM` + same CNPJ + different `TP_MERC`.
   - same CNPJ + different `CD_CVM` as identity child records if identity tables are ready, or at least stop classifying as unexplained duplicate in audit.
4. Add resolver prototype using open + foreign cadastro indexes.
5. Add tests proving DFP/FRE foreign issuer rows resolve.

Expected impact:

- `companhia_nao_encontrada` drops sharply.
- Cadastro duplicate rejection becomes explainable and mergeable.
- Foundation exists for staging/replay.

## Definition of Done for Ingestion V2

V2 is complete when:

- Both open and foreign cadastro are ingested.
- Cadastro duplicates are merged or modeled, not hard rejected.
- DFP/ITR/FRE rows resolve through shared resolver.
- FRE child rows can resolve through document header map.
- Staging preserves raw and normalized rows.
- Quarantine has repair state and replay.
- Retry policy is cause-based and visible.
- Metrics and admin/reporting show quality by source, file, reason, and resolver method.
- Default configured years import with rejection rates inside SLO.
- Existing public API behavior remains compatible.
- Tests cover normal, duplicate, missing parent, schema, retry, and replay paths.
