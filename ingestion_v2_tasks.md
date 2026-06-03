# Ingestion V2 Implementation Tasks

## How To Use

This checklist turns [ingestion_v2_plan.md](ingestion_v2_plan.md) into implementation tasks. Each task links back to plan section. Keep each task scoped; do not merge phases unless dependency is complete.

Task status legend:

- `[ ]`: not started.
- `[~]`: in progress.
- `[x]`: done.

## Phase A: Audit Harness

Goal: reproduce current rejection causes with deterministic tooling before changing ingestion behavior.

### A1. Add live-audit script skeleton

- Status: `[x]`
- Depends on: none
- Plan refs: [Phase 1](ingestion_v2_plan.md#phase-1-observability-and-audit-harness), [Evidence](ingestion_v2_plan.md#evidence-from-current-research), [Task Group A](ingestion_v2_plan.md#task-group-a-audit-harness)
- Files:
  - `scripts/audit_ingestion_consistency.py`
  - optional `tests/unit/test_ingestion_v2_audit.py`
- Build:
  - CLI script using stdlib only, unless existing deps already cover need.
  - Arguments: `--year`, `--sources`, `--output-json`, `--no-network-cache` if cache later exists.
  - Default year: `2021`.
  - Sources: `cadastro`, `dfp`, `itr`, `fre`, `all`.
  - Print compact summary table.
  - Optionally write JSON report to `tmp/ingestion_audit_YYYYMMDD.json`.
- Acceptance:
  - Script runs without DB mutation.
  - Script has no effect on app state.
  - Default invocation documents what it downloads.

### A2. Implement official CVM download helpers in audit script

- Status: `[x]`
- Depends on: A1
- Plan refs: [Evidence](ingestion_v2_plan.md#evidence-from-current-research), [HTTP Client](ingestion_v2_plan.md#http-client)
- Build:
  - Fetch:
    - `cad_cia_aberta.csv`.
    - `cad_cia_estrang.csv`.
    - `dfp_cia_aberta_{ano}.zip`.
    - `itr_cia_aberta_{ano}.zip`.
    - `fre_cia_aberta_{ano}.zip`.
  - Compute SHA-256 and byte length.
  - Decode CSV with `utf-8-sig`, fallback `latin1`.
  - Expand ZIP members in memory.
- Acceptance:
  - Report includes source URL, size, hash prefix/full hash.
  - Network failure exits non-zero with clear message.

### A3. Categorize cadastro duplicates

- Status: `[x]`
- Depends on: A1, A2
- Plan refs: [Duplicate Handling](ingestion_v2_plan.md#duplicate-handling), [Cadastro Duplicate Policy](ingestion_v2_plan.md#cadastro-duplicate-policy), [Open Company Cadastro](ingestion_v2_plan.md#open-company-cadastro)
- Build:
  - Group `cad_cia_aberta.csv` by normalized `CNPJ_CIA`.
  - Count duplicate buckets and extra rows.
  - Categorize:
    - `same_cd_only_tipo_mercado`.
    - `same_cd_other_diff`.
    - `different_cd`.
  - Include sample rows with `linha`, `CNPJ_CIA`, `CD_CVM`, `SIT`, `TP_MERC`, `CATEG_REG`, `DT_REG`, `DT_CANCEL`, `DENOM_SOCIAL`.
- Acceptance:
  - Current official file shows categories similar to plan evidence.
  - Unit fixture proves each category.

### A4. Measure parent-company missing counts

- Status: `[x]`
- Depends on: A2
- Plan refs: [Evidence](ingestion_v2_plan.md#evidence-from-current-research), [Foreign Company Cadastro](ingestion_v2_plan.md#foreign-company-cadastro), [Identity Resolution Algorithm](ingestion_v2_plan.md#identity-resolution-algorithm)
- Build:
  - Build identity sets from open cadastro only.
  - Build identity sets from open + foreign cadastro.
  - Scan DFP/ITR/FRE ZIP rows.
  - Count `companhia_nao_encontrada` under both identity sets.
  - Count by CSV member and issuer name.
- Acceptance:
  - Report shows before/after missing parent counts.
  - Output lists top missing names and files.

### A5. Add audit JSON schema and snapshot fixture tests

- Status: `[x]`
- Depends on: A3, A4
- Plan refs: [Testing Strategy](ingestion_v2_plan.md#testing-strategy), [Live Optional Tests](ingestion_v2_plan.md#live-optional-tests)
- Build:
  - Define stable JSON keys:
    - `generated_at`.
    - `year`.
    - `sources`.
    - `cadastro_duplicates`.
    - `missing_parent`.
    - `files`.
  - Add unit tests with tiny CSV/ZIP fixtures created in memory.
- Acceptance:
  - Tests do not hit network.
  - Live audit remains manual or optional.

### A6. Add optional live pytest marker

- Status: `[x]`
- Depends on: A5
- Plan refs: [Live Optional Tests](ingestion_v2_plan.md#live-optional-tests)
- Build:
  - Add `cvm_live` marker to pytest config if used.
  - Keep default tests offline.
  - Optional live test invokes audit helpers with network.
- Acceptance:
  - `pytest` default does not call CVM.
  - `pytest -m cvm_live` can run manually.

## Phase B: Staging Schema and Services

Goal: preserve raw rows, member metadata, normalized payloads, validation state, and row events.

### B1. Add `app/models/ingestion.py`

- Status: `[x]`
- Depends on: none
- Plan refs: [New Data Model](ingestion_v2_plan.md#new-data-model), [ingestion_runs](ingestion_v2_plan.md#ingestion_runs), [ingestion_files](ingestion_v2_plan.md#ingestion_files), [ingestion_file_members](ingestion_v2_plan.md#ingestion_file_members), [ingestion_rows](ingestion_v2_plan.md#ingestion_rows), [ingestion_row_events](ingestion_v2_plan.md#ingestion_row_events), [ingestion_attempts](ingestion_v2_plan.md#ingestion_attempts)
- Build:
  - SQLAlchemy models:
    - `IngestionRun`.
    - `IngestionFile`.
    - `IngestionFileMember`.
    - `IngestionRow`.
    - `IngestionRowEvent`.
    - `IngestionAttempt`.
  - Use existing project naming/import style.
  - Use JSON columns where plan requires JSON.
- Acceptance:
  - Models import cleanly.
  - Type hints pass local style.

### B2. Add staging Alembic migration

- Status: `[x]`
- Depends on: B1
- Plan refs: [Phase 2](ingestion_v2_plan.md#phase-2-staging-tables), [Task Group B](ingestion_v2_plan.md#task-group-b-migrations-and-models)
- Build:
  - Migration creates:
    - `ingestion_runs`.
    - `ingestion_files`.
    - `ingestion_file_members`.
    - `ingestion_rows`.
    - `ingestion_row_events`.
    - `ingestion_attempts`.
  - Add indexes from plan.
  - Add FK constraints.
- Acceptance:
  - `alembic upgrade head` succeeds on clean DB.
  - Existing tests still create metadata.

### B3. Register models in metadata import path

- Status: `[x]`
- Depends on: B1
- Plan refs: [Implementation Modules](ingestion_v2_plan.md#implementation-modules)
- Build:
  - Update `app/models/__init__.py` if needed.
  - Ensure Alembic autoload sees models.
- Acceptance:
  - No missing table in tests/migrations.

### B4. Create staging service package

- Status: `[x]`
- Depends on: B1
- Plan refs: [Implementation Modules](ingestion_v2_plan.md#implementation-modules), [Target Pipeline](ingestion_v2_plan.md#target-pipeline)
- Files:
  - `app/services/ingestion/__init__.py`
  - `app/services/ingestion/staging.py`
- Build:
  - Functions:
    - `criar_run`.
    - `registrar_arquivo`.
    - `registrar_membro`.
    - `inserir_linhas`.
    - `atualizar_linha_validacao`.
    - `registrar_evento_linha`.
    - `registrar_attempt`.
  - Prefer explicit DB session parameter.
- Acceptance:
  - Unit tests can create run, file, member, rows, event.

### B5. Add staged CSV reader

- Status: `[x]`
- Depends on: B4
- Plan refs: [Target Pipeline](ingestion_v2_plan.md#target-pipeline), [Normalization Strategy](ingestion_v2_plan.md#normalization-strategy)
- Build:
  - Input: bytes and member name.
  - Detect encoding using current app fallback order.
  - Use `csv.DictReader(..., delimiter=";")`.
  - Return header and `(linha_origem, raw_data)`.
  - Preserve raw field names exactly.
- Acceptance:
  - Handles plain CSV and ZIP member CSV.
  - Preserves line numbers starting at 2.

### B6. Add ZIP staging helper

- Status: `[x]`
- Depends on: B4, B5
- Plan refs: [ingestion_file_members](ingestion_v2_plan.md#ingestion_file_members), [Target Pipeline](ingestion_v2_plan.md#target-pipeline)
- Build:
  - Read ZIP payload.
  - Register one member per CSV.
  - Compute member SHA-256 and row count.
  - Insert `ingestion_rows` in batches.
- Acceptance:
  - Tiny ZIP fixture stages all members.
  - Member metadata includes header and row count.

### B7. Add run phase/status updates

- Status: `[x]`
- Depends on: B4
- Plan refs: [ingestion_runs](ingestion_v2_plan.md#ingestion_runs), [Promotion Strategy](ingestion_v2_plan.md#promotion-strategy)
- Build:
  - Helper to set run `phase`, `status`, `message`, timestamps.
  - Ensure failure path records final state.
- Acceptance:
  - Unit test simulates phase progression.

## Phase C: Identity Schema and Cadastro V2

Goal: model official CVM identity reality and stop rejecting cadastro duplicates.

### C1. Add `app/models/identidade.py`

- Status: `[ ]`
- Depends on: none
- Plan refs: [companhia_registros_cvm](ingestion_v2_plan.md#companhia_registros_cvm), [companhia_mercados](ingestion_v2_plan.md#companhia_mercados), [companhia_identificadores](ingestion_v2_plan.md#companhia_identificadores)
- Build:
  - SQLAlchemy models:
    - `CompanhiaRegistroCvm`.
    - `CompanhiaMercado`.
    - `CompanhiaIdentificador`.
  - Add relationships only if local pattern supports them; otherwise keep FK columns.
- Acceptance:
  - Models import cleanly.

### C2. Add identity Alembic migration

- Status: `[ ]`
- Depends on: C1
- Plan refs: [Phase 3](ingestion_v2_plan.md#phase-3-identity-graph), [Task Group C](ingestion_v2_plan.md#task-group-c-cadastro-v2)
- Build:
  - Create identity tables.
  - Add indexes:
    - `cnpj_companhia`.
    - `codigo_cvm`.
    - `companhia_id`.
    - `(tipo, valor_normalizado)`.
  - Do not add global uniqueness on identifiers.
- Acceptance:
  - Migration runs.
  - Existing schema remains compatible.

### C3. Extend `companhias` for v2 metadata

- Status: `[ ]`
- Depends on: C2
- Plan refs: [companhias](ingestion_v2_plan.md#companhias), [Existing Table Changes](ingestion_v2_plan.md#existing-table-changes)
- Build:
  - Add nullable fields:
    - `tipo_emissor`.
    - `fonte_identidade_principal`.
    - `qualidade_identidade`.
  - Update model.
- Acceptance:
  - Existing tests still pass.
  - No existing API break.

### C4. Add shared v2 normalizers

- Status: `[ ]`
- Depends on: none
- Plan refs: [Shared Normalization Rules](ingestion_v2_plan.md#shared-normalization-rules), [Normalization Strategy](ingestion_v2_plan.md#normalization-strategy)
- Files:
  - `app/services/ingestion/normalizers.py`
- Build:
  - Wrap/reuse current normalizers.
  - Add:
    - `normalizar_cnpj_opcional`.
    - `normalizar_codigo_cvm`.
    - `normalizar_nome_emissor_chave`.
    - `normalizar_tipo_mercado`.
    - `normalizar_header`.
    - `normalizar_chave_natural`.
- Acceptance:
  - Unit tests cover blank CNPJ, invalid CNPJ, zero-padded CVM code.

### C5. Implement open cadastro v2 parser

- Status: `[ ]`
- Depends on: C4, B4
- Plan refs: [Open Company Cadastro](ingestion_v2_plan.md#open-company-cadastro), [Cadastro Duplicate Policy](ingestion_v2_plan.md#cadastro-duplicate-policy)
- Files:
  - `app/services/ingestion/cadastro.py`
- Build:
  - Function `normalizar_linha_cadastro_aberta_v2`.
  - Produce normalized dict with source fields from plan.
  - Compute `hash_sem_mercado`.
  - Compute `hash_origem`.
  - Return validation result instead of raising for expected row issues where possible.
- Acceptance:
  - Unit test parses current v1 fixture.
  - Unit test handles duplicate markets.

### C6. Implement foreign cadastro v2 parser

- Status: `[ ]`
- Depends on: C4, B4
- Plan refs: [Foreign Company Cadastro](ingestion_v2_plan.md#foreign-company-cadastro)
- Files:
  - `app/services/ingestion/cadastro.py`
- Build:
  - Function `normalizar_linha_cadastro_estrangeira_v2`.
  - Use `CNPJ`, not `CNPJ_CIA`.
  - Map `PAIS_ORIGEM`.
  - Missing open-company-only fields become `None`/`{}`.
- Acceptance:
  - Unit test parses foreign fixture.
  - Foreign CNPJ/code identifiers can be derived.

### C7. Implement canonical company selector

- Status: `[ ]`
- Depends on: C5, C6
- Plan refs: [Cadastro Duplicate Policy](ingestion_v2_plan.md#cadastro-duplicate-policy)
- Build:
  - Ranking:
    - active over cancelled.
    - non-cancelled over cancelled.
    - latest `data_inicio_situacao`.
    - latest `data_registro`.
    - source priority.
    - lower `linha_origem` tie-breaker.
  - Return canonical normalized record.
- Acceptance:
  - Unit tests cover active vs cancelled and tie-breaker.

### C8. Implement cadastro merge service

- Status: `[ ]`
- Depends on: C1, C5, C6, C7
- Plan refs: [Cadastro Duplicate Policy](ingestion_v2_plan.md#cadastro-duplicate-policy), [companhia_registros_cvm](ingestion_v2_plan.md#companhia_registros_cvm), [companhia_mercados](ingestion_v2_plan.md#companhia_mercados)
- Build:
  - Group open cadastro rows by CNPJ/code/hash-sem-market.
  - Create/update canonical `Companhia`.
  - Create/update `CompanhiaRegistroCvm`.
  - Create/update `CompanhiaMercado`.
  - Same CNPJ different code -> same canonical company plus multiple registrations.
- Acceptance:
  - Same CNPJ + same code + two markets => one company, one registro, two markets.
  - Same CNPJ + two codes => one company, two registros.

### C9. Implement identifier generation

- Status: `[ ]`
- Depends on: C8
- Plan refs: [companhia_identificadores](ingestion_v2_plan.md#companhia_identificadores), [Identity Resolution Algorithm](ingestion_v2_plan.md#identity-resolution-algorithm)
- Build:
  - Generate high-confidence identifiers:
    - CNPJ.
    - CVM code.
    - optional normalized name with lower confidence if used later.
  - Source-specific `fonte`.
  - Avoid global unique conflicts.
- Acceptance:
  - Foreign issuer creates CNPJ and CVM code identifiers.
  - Same company can have multiple CVM code identifiers.

### C10. Add `sincronizar_cadastro_companhias_v2`

- Status: `[ ]`
- Depends on: B4, B5, C8, C9
- Plan refs: [Phase 3](ingestion_v2_plan.md#phase-3-identity-graph), [Normal Daily Flow](ingestion_v2_plan.md#normal-daily-flow)
- Build:
  - Download/stage open cadastro and foreign cadastro.
  - Normalize rows.
  - Promote identity graph.
  - Update legacy `ExecucaoSincronizacao` counters if using existing admin flow.
  - Feature-flag promotion if needed.
- Acceptance:
  - Sync imports both official cadastro sources.
  - No hard reject solely due to duplicated CNPJ.

## Phase D: Shared Resolver

Goal: one auditable company resolver for DFP, ITR, FRE.

### D1. Define resolver dataclasses/results

- Status: `[ ]`
- Depends on: C1
- Plan refs: [Identity Resolution Algorithm](ingestion_v2_plan.md#identity-resolution-algorithm), [Task Group D](ingestion_v2_plan.md#task-group-d-resolver-v2)
- Files:
  - `app/services/ingestion/resolver.py`
- Build:
  - `ResolverInput`.
  - `ResolverResult`.
  - result statuses:
    - `resolved`.
    - `ambiguous`.
    - `not_found`.
    - `provisional_created`.
- Acceptance:
  - Type-safe inputs and outputs.

### D2. Resolve by exact CNPJ identifier

- Status: `[ ]`
- Depends on: D1, C9
- Plan refs: [Identity Resolution Algorithm](ingestion_v2_plan.md#identity-resolution-algorithm)
- Build:
  - Query `companhia_identificadores` by `tipo='cnpj'`.
  - If multiple rows same `companhia_id`, OK.
  - If multiple companies, return ambiguous unless CVM code disambiguates.
- Acceptance:
  - Unit tests cover single, duplicate same company, ambiguous.

### D3. Resolve by exact CVM code identifier

- Status: `[ ]`
- Depends on: D1, C9
- Plan refs: [Identity Resolution Algorithm](ingestion_v2_plan.md#identity-resolution-algorithm)
- Build:
  - Query by `tipo='codigo_cvm'`.
  - Detect conflict with CNPJ result.
  - Return `codigo_cvm_identificador_alta`.
- Acceptance:
  - Zero-padded source code resolves same as int string.
  - Conflict returns `companhia_ambigua`.

### D4. Add document header map resolver

- Status: `[ ]`
- Depends on: D1
- Plan refs: [Financial and FRE Documents](ingestion_v2_plan.md#financial-and-fre-documents), [Identity Resolution Algorithm](ingestion_v2_plan.md#identity-resolution-algorithm)
- Build:
  - Map key: `(tipo_formulario, id_documento, versao, data_referencia)`.
  - Map value: `companhia_id`, CNPJ, code, confidence.
  - Child rows use map when direct resolver fails or lacks code.
- Acceptance:
  - FRE child row without `CD_CVM` resolves via header map.

### D5. Add repair-rule resolver hook

- Status: `[ ]`
- Depends on: D1
- Plan refs: [repair_rules](ingestion_v2_plan.md#repair_rules), [Identity Resolution Algorithm](ingestion_v2_plan.md#identity-resolution-algorithm)
- Build:
  - Query enabled identity map rules.
  - Match exact payload only.
  - Return `manual_identity_rule_media`.
- Acceptance:
  - Manual rule can resolve known leftover issuer.

### D6. Add provisional issuer creation

- Status: `[ ]`
- Depends on: D1, C9
- Plan refs: [Identity Resolution Algorithm](ingestion_v2_plan.md#identity-resolution-algorithm), [Dependency and Configuration Plan](ingestion_v2_plan.md#dependency-and-configuration-plan)
- Build:
  - Config flag: `INGESTION_V2_PROVISIONAL_COMPANY_ENABLED`.
  - Create canonical `Companhia` with:
    - `tipo_emissor='provisorio'`.
    - `qualidade_identidade='baixa'`.
  - Add low-confidence identifiers.
  - Return warning resolution.
- Acceptance:
  - Disabled flag quarantines.
  - Enabled flag creates provisional and marks confidence low.

### D7. Persist resolution details into staging rows

- Status: `[ ]`
- Depends on: D2, D3, D4, D5, D6, B4
- Plan refs: [ingestion_rows](ingestion_v2_plan.md#ingestion_rows), [Identity Resolution Algorithm](ingestion_v2_plan.md#identity-resolution-algorithm)
- Build:
  - Update `resolved_companhia_id`.
  - Update `resolution_method`.
  - Update `resolution_confidence`.
  - Add row event `resolved`.
- Acceptance:
  - Every promoted row has resolution metadata.

## Phase E: Validation and Duplicate Engine

Goal: convert parser exceptions into structured validation and split exact duplicates from conflicts.

### E1. Define validation result structure

- Status: `[ ]`
- Depends on: B4
- Plan refs: [Validation Model](ingestion_v2_plan.md#validation-model)
- Files:
  - `app/services/ingestion/validation.py`
- Build:
  - `ValidationResult`.
  - `status`, `reason_code`, `severity`, `details`, `repairable`.
- Acceptance:
  - Unit test serializes details to JSON.

### E2. Implement schema validation helpers

- Status: `[ ]`
- Depends on: E1
- Plan refs: [Validation Model](ingestion_v2_plan.md#validation-model), [When Schema Error Appears](ingestion_v2_plan.md#when-schema-error-appears)
- Build:
  - Required-column check by row kind.
  - Unknown columns allowed and logged.
  - Missing required columns => `schema_inesperado`.
- Acceptance:
  - Fixture with missing required column quarantines member/rows.

### E3. Implement natural-key builder registry

- Status: `[ ]`
- Depends on: E1
- Plan refs: [Document Duplicate Policy](ingestion_v2_plan.md#document-duplicate-policy), [Promotion Strategy](ingestion_v2_plan.md#promotion-strategy)
- Build:
  - Registry by row kind/table.
  - Generate stable JSON natural key.
  - Reuse existing key definitions unless audit says otherwise.
- Acceptance:
  - DFP demonstration, FRE auditor, cadastro registration keys produced.

### E4. Implement duplicate classifier

- Status: `[ ]`
- Depends on: E3
- Plan refs: [Document Duplicate Policy](ingestion_v2_plan.md#document-duplicate-policy), [When Duplicate Natural Key Spikes](ingestion_v2_plan.md#when-duplicate-natural-key-spikes)
- Build:
  - Same key + same normalized hash => `ignored_duplicate`.
  - Same key + different normalized hash => `chave_natural_duplicada_conflitante`.
  - Store field-level diff in details.
- Acceptance:
  - Exact duplicate ignored, not quarantined.
  - Conflict duplicate quarantined with diff.

### E5. Add validation status writer

- Status: `[ ]`
- Depends on: E1, B4
- Plan refs: [ingestion_rows](ingestion_v2_plan.md#ingestion_rows), [ingestion_row_events](ingestion_v2_plan.md#ingestion_row_events)
- Build:
  - Update `validation_status`, `validation_reason_code`, `validation_details`.
  - Add event `validated` or `quarantined`.
- Acceptance:
  - Validation events visible for rows.

## Phase F: Financeiro V2 Promotion

Goal: DFP/ITR stage-normalize-validate-resolve-promote through v2 path.

### F1. Extract DFP/ITR member map service

- Status: `[ ]`
- Depends on: B6
- Plan refs: [Financial and FRE Documents](ingestion_v2_plan.md#financial-and-fre-documents), [Phase 5](ingestion_v2_plan.md#phase-5-document-v2-promotion), [Task Group E](ingestion_v2_plan.md#task-group-e-financeiro-v2)
- Files:
  - `app/services/ingestion/financeiro.py`
- Build:
  - Identify main document file.
  - Identify composition/parecer files.
  - Identify demonstration files via existing `arquivos_demonstracao`.
  - Enforce expected required members.
- Acceptance:
  - DFP/ITR fixture maps all expected files.

### F2. Implement financeiro v2 normalizers

- Status: `[ ]`
- Depends on: F1, C4
- Plan refs: [Financial and FRE Documents](ingestion_v2_plan.md#financial-and-fre-documents), [Shared Normalization Rules](ingestion_v2_plan.md#shared-normalization-rules)
- Build:
  - Normalize:
    - document header.
    - demonstration.
    - composition capital.
    - parecer.
  - Reuse v1 field mapping where correct.
  - Return normalized data and row kind.
- Acceptance:
  - Existing v1 financeiro fixture normalizes to expected values.

### F3. Promote financeiro document headers first

- Status: `[ ]`
- Depends on: F2, D7, E5
- Plan refs: [Financial and FRE Documents](ingestion_v2_plan.md#financial-and-fre-documents), [Promotion Strategy](ingestion_v2_plan.md#promotion-strategy)
- Build:
  - Validate document rows.
  - Resolve company.
  - Upsert `DocumentoFinanceiro`.
  - Build document header map.
  - Write promotion metadata.
- Acceptance:
  - Header map available to child promotion.

### F4. Promote financeiro child rows

- Status: `[ ]`
- Depends on: F3, D4, E4
- Plan refs: [Promotion Strategy](ingestion_v2_plan.md#promotion-strategy), [Phase 5](ingestion_v2_plan.md#phase-5-document-v2-promotion)
- Build:
  - Promote:
    - `DemonstracaoFinanceira`.
    - `ComposicaoCapital`.
    - `ParecerFinanceiro`.
  - Use shared resolver.
  - Use existing history logic for changed fields.
  - Commit by batch.
- Acceptance:
  - Existing DFP/ITR fixture inserts same domain row counts as v1.

### F5. Add financeiro v2 service entrypoints

- Status: `[ ]`
- Depends on: F4
- Plan refs: [Phase 5](ingestion_v2_plan.md#phase-5-document-v2-promotion), [Rollout and Backfill](ingestion_v2_plan.md#phase-9-rollout-and-backfill)
- Build:
  - `sincronizar_dfp_v2(db, ano, task_id=None)`.
  - `sincronizar_itr_v2(db, ano, task_id=None)`.
  - Feature flag controls v2 vs v1 task usage later.
- Acceptance:
  - Unit/integration tests call v2 directly.

### F6. Add foreign issuer financeiro tests

- Status: `[ ]`
- Depends on: F5, C10
- Plan refs: [Target Outcomes](ingestion_v2_plan.md#target-outcomes), [Testing Strategy](ingestion_v2_plan.md#testing-strategy)
- Build:
  - Fixture with foreign company in `cad_cia_estrang`.
  - DFP/ITR document and child rows reference same issuer.
  - Assert no `companhia_nao_encontrada`.
- Acceptance:
  - Test proves DFP/FRE style missing-parent reduction path.

## Phase G: FRE V2 Promotion

Goal: FRE stage-normalize-validate-resolve-promote with header map for child files.

### G1. Extract FRE MVP member map service

- Status: `[ ]`
- Depends on: B6
- Plan refs: [Financial and FRE Documents](ingestion_v2_plan.md#financial-and-fre-documents), [Phase 5](ingestion_v2_plan.md#phase-5-document-v2-promotion), [Task Group F](ingestion_v2_plan.md#task-group-f-fre-v2)
- Files:
  - `app/services/ingestion/fre.py`
- Build:
  - Identify:
    - `documentos`.
    - `auditores`.
    - `capital_social`.
    - `posicao_acionaria`.
    - `remuneracao_total_orgao`.
    - `empregado_posicao_genero` optional.
  - Preserve optional-file behavior.
- Acceptance:
  - Existing optional gender file test has v2 equivalent.

### G2. Implement FRE v2 normalizers

- Status: `[ ]`
- Depends on: G1, C4
- Plan refs: [Financial and FRE Documents](ingestion_v2_plan.md#financial-and-fre-documents), [FRE V2](ingestion_v2_plan.md#task-group-f-fre-v2)
- Build:
  - Normalize document header uppercase fields.
  - Normalize child mixed-case fields:
    - `CNPJ_Companhia`.
    - `Data_Referencia`.
    - `Versao`.
    - `ID_Documento`.
  - Reuse v1 field mapping where correct.
- Acceptance:
  - Existing FRE fixture normalizes.

### G3. Promote FRE document headers first

- Status: `[ ]`
- Depends on: G2, D7, E5
- Plan refs: [Financial and FRE Documents](ingestion_v2_plan.md#financial-and-fre-documents), [Promotion Strategy](ingestion_v2_plan.md#promotion-strategy)
- Build:
  - Validate document rows.
  - Resolve by CNPJ/code.
  - Upsert `FreDocumento`.
  - Build header map.
- Acceptance:
  - Header map contains `(id_documento, versao, data_referencia)`.

### G4. Promote FRE child rows through header map

- Status: `[ ]`
- Depends on: G3, D4, E4
- Plan refs: [Financial and FRE Documents](ingestion_v2_plan.md#financial-and-fre-documents), [Identity Resolution Algorithm](ingestion_v2_plan.md#identity-resolution-algorithm)
- Build:
  - Direct resolve by CNPJ first.
  - If no code/direct miss, use header map.
  - Promote:
    - `FreAuditor`.
    - `FreCapitalSocial`.
    - `FrePosicaoAcionaria`.
    - `FreRemuneracaoTotalOrgao`.
    - `FreEmpregadoPosicaoGenero`.
- Acceptance:
  - FRE child row lacking `CD_CVM` resolves through document header.

### G5. Add FRE v2 service entrypoint

- Status: `[ ]`
- Depends on: G4
- Plan refs: [Phase 5](ingestion_v2_plan.md#phase-5-document-v2-promotion), [Rollout and Backfill](ingestion_v2_plan.md#phase-9-rollout-and-backfill)
- Build:
  - `sincronizar_fre_v2(db, ano, task_id=None)`.
  - Keep v1 available.
- Acceptance:
  - Existing FRE MVP scenario passes v2 test.

### G6. Add FRE foreign/header-map tests

- Status: `[ ]`
- Depends on: G5, C10
- Plan refs: [Target Outcomes](ingestion_v2_plan.md#target-outcomes), [Testing Strategy](ingestion_v2_plan.md#testing-strategy)
- Build:
  - Fixture with foreign issuer in main FRE file.
  - Child files omit `CD_CVM`.
  - Assert all child rows resolve and promote.
- Acceptance:
  - No `companhia_nao_encontrada` for foreign FRE child rows.

## Phase H: Quarantine V2 and Replay

Goal: transform rejected rows into repairable, replayable queue.

### H1. Add `quarantine_items_v2` model and migration

- Status: `[ ]`
- Depends on: B1
- Plan refs: [quarantine_items_v2](ingestion_v2_plan.md#quarantine_items_v2), [Phase 6](ingestion_v2_plan.md#phase-6-repairable-quarantine-and-replay), [Task Group G](ingestion_v2_plan.md#task-group-g-quarantine-v2)
- Build:
  - SQLAlchemy model.
  - Alembic migration.
  - Index `status`, `motivo_codigo`, source fields.
- Acceptance:
  - Migration succeeds.

### H2. Implement quarantine service

- Status: `[ ]`
- Depends on: H1, B4
- Plan refs: [Repair Queue](ingestion_v2_plan.md#repair-queue), [quarantine_items_v2](ingestion_v2_plan.md#quarantine_items_v2)
- Files:
  - `app/services/ingestion/quarantine.py`
- Build:
  - Create item from `ingestion_row`.
  - Stable reason codes.
  - Severity/status defaults.
  - Bridge-write legacy `RegistroQuarentena` while admin v1 remains.
- Acceptance:
  - Validation failure creates v2 and legacy quarantine.

### H3. Add repair rules model/service

- Status: `[ ]`
- Depends on: H1
- Plan refs: [repair_rules](ingestion_v2_plan.md#repair_rules), [Repair and Replay](ingestion_v2_plan.md#repair-and-replay)
- Build:
  - Add model/migration if not done in identity phase.
  - CRUD-like internal service for enabled rules.
  - Exact match evaluation.
- Acceptance:
  - Rule can be inserted and read by resolver.

### H4. Implement row replay service

- Status: `[ ]`
- Depends on: H2, D7, E5
- Plan refs: [Replay Modes](ingestion_v2_plan.md#replay-modes), [Repair and Replay](ingestion_v2_plan.md#repair-and-replay)
- Files:
  - `app/services/ingestion/replay.py`
- Build:
  - Reprocess one `ingestion_row`.
  - Re-run normalization if parser version changed.
  - Re-run validation/resolution.
  - Promote if now valid.
  - Update quarantine item status.
- Acceptance:
  - Missing-company row resolves after identity added.

### H5. Implement member/run/quarantine replay

- Status: `[ ]`
- Depends on: H4
- Plan refs: [Replay Modes](ingestion_v2_plan.md#replay-modes)
- Build:
  - `replay_file_member(member_id)`.
  - `replay_ingestion_run(run_id)`.
  - `replay_quarantine(reason_code=None, arquivo_origem=None, ano=None)`.
- Acceptance:
  - Replay is idempotent.
  - Attempt count and events update.

### H6. Add quarantine/replay tests

- Status: `[ ]`
- Depends on: H5
- Plan refs: [Testing Strategy](ingestion_v2_plan.md#testing-strategy)
- Build:
  - Test missing company repaired by foreign cadastro import.
  - Test manual repair rule.
  - Test exact duplicate auto-resolved/ignored.
  - Test replay failure increments attempt count.
- Acceptance:
  - Tests cover success and failure replay paths.

## Phase I: Retry and Dependency Deferral

Goal: add retries only for transient failures and defer document imports until identity prerequisites are ready.

### I1. Add retry exception taxonomy

- Status: `[ ]`
- Depends on: none
- Plan refs: [Retry Strategy](ingestion_v2_plan.md#retry-strategy), [Retryable Errors](ingestion_v2_plan.md#retryable-errors), [Non-retryable Errors](ingestion_v2_plan.md#non-retryable-errors), [Task Group H](ingestion_v2_plan.md#task-group-h-retry-v2)
- Files:
  - `app/services/ingestion/retry.py`
- Build:
  - `RetryableIngestionError`.
  - `RetryableHttpStatus`.
  - `DependencyNotReady`.
  - `TerminalIngestionError`.
- Acceptance:
  - Unit tests classify retryable vs terminal.

### I2. Implement acquisition helper

- Status: `[ ]`
- Depends on: I1, B4
- Plan refs: [HTTP Client](ingestion_v2_plan.md#http-client), [ingestion_attempts](ingestion_v2_plan.md#ingestion_attempts)
- Files:
  - `app/services/ingestion/acquisition.py`
- Build:
  - Download URL with `httpx`.
  - Classify status:
    - retry: `408`, `429`, `5xx`.
    - terminal: `404`, invalid URL, etc.
  - Compute hash and metadata.
  - Register attempts.
- Acceptance:
  - Tests monkeypatch httpx for timeout, 503, 404, success.

### I3. Configure Celery retries for v2 tasks

- Status: `[ ]`
- Depends on: I1, I2
- Plan refs: [Celery Task Configuration](ingestion_v2_plan.md#celery-task-configuration)
- Files:
  - `app/worker/tasks.py`
  - maybe new v2 task module if cleaner
- Build:
  - `autoretry_for` retryable exceptions.
  - `retry_backoff=True`.
  - `retry_backoff_max=600`.
  - `retry_jitter=True`.
  - `max_retries=5`.
- Acceptance:
  - Unit test verifies task decorator/options where feasible.

### I4. Add document dependency check

- Status: `[ ]`
- Depends on: C10, I1
- Plan refs: [Retry Strategy](ingestion_v2_plan.md#retry-strategy), [Normal Daily Flow](ingestion_v2_plan.md#normal-daily-flow)
- Build:
  - DFP/ITR/FRE v2 require:
    - successful open cadastro v2.
    - successful foreign cadastro v2.
    - identity graph not stale.
  - If missing, raise `DependencyNotReady` or mark `bloqueada_dependencia`.
- Acceptance:
  - Document sync with empty identity graph defers; it does not process rows into mass rejects.

### I5. Add attempt visibility to run summary

- Status: `[ ]`
- Depends on: B4, I2
- Plan refs: [ingestion_attempts](ingestion_v2_plan.md#ingestion_attempts), [When Retry Exhausts](ingestion_v2_plan.md#when-retry-exhausts)
- Build:
  - Include retry/attempt counts in `quality_summary`.
  - Store `next_retry_at` where known.
- Acceptance:
  - Failed retry exhaustion visible from DB.

## Phase J: Admin, Metrics, and Config

Goal: expose v2 quality and make rollout controllable.

### J1. Add v2 settings

- Status: `[ ]`
- Depends on: none
- Plan refs: [Dependency and Configuration Plan](ingestion_v2_plan.md#dependency-and-configuration-plan)
- Files:
  - `app/core/config.py`
- Build:
  - Add:
    - `INGESTION_V2_ENABLED`.
    - `INGESTION_V2_PROMOTE_ENABLED`.
    - `INGESTION_V2_PROVISIONAL_COMPANY_ENABLED`.
    - `INGESTION_V2_MAX_RETRIES`.
    - `INGESTION_V2_RETRY_BACKOFF_MAX_SECONDS`.
    - `INGESTION_V2_COMPANY_MISSING_MAX_RATIO`.
    - `INGESTION_V2_STAGE_BATCH_SIZE`.
    - `INGESTION_V2_PROMOTE_BATCH_SIZE`.
- Acceptance:
  - Config tests cover defaults and env override.

### J2. Add ingestion v2 metrics helpers

- Status: `[ ]`
- Depends on: B4
- Plan refs: [Phase 8](ingestion_v2_plan.md#phase-8-admin-and-observability), [Observability and SLO Gates](ingestion_v2_plan.md#task-group-i-observability-and-slo-gates)
- Files:
  - `app/services/ingestion/metrics.py`
- Build:
  - Counters/gauges using current Prometheus setup:
    - rows by source/status/reason.
    - run duration by source/phase.
    - retries by operation/error.
    - quarantine by reason.
    - identity resolution by method/confidence.
- Acceptance:
  - Metrics functions can be called without duplicate registration errors.

### J3. Add quality summary builder

- Status: `[ ]`
- Depends on: B4, E5, H2
- Plan refs: [Validation Model](ingestion_v2_plan.md#validation-model), [Phase 8](ingestion_v2_plan.md#phase-8-admin-and-observability)
- Build:
  - Aggregate:
    - row statuses.
    - reason counts.
    - top files by quarantine.
    - resolver methods.
    - provisional company count.
  - Store in `ingestion_runs.quality_summary`.
- Acceptance:
  - Unit test builds summary from staged rows.

### J4. Add internal/admin list endpoints for v2 runs/quarantine

- Status: `[ ]`
- Depends on: H2, J3
- Plan refs: [Repair and Replay](ingestion_v2_plan.md#repair-and-replay), [Phase 8](ingestion_v2_plan.md#phase-8-admin-and-observability)
- Files:
  - likely `app/api/routers/admin.py` or v2 router
- Build:
  - List runs.
  - Get run quality.
  - List quarantine v2.
  - Keep auth requirements consistent with existing admin.
- Acceptance:
  - Admin tests cover auth and pagination.

### J5. Add admin replay endpoints

- Status: `[ ]`
- Depends on: H5, J4
- Plan refs: [Replay Modes](ingestion_v2_plan.md#replay-modes)
- Build:
  - `POST /admin/ingestion-v2/replay/quarantine`.
  - `POST /admin/ingestion-v2/runs/{run_id}/replay`.
  - `POST /admin/ingestion-v2/identity/rebuild`.
- Acceptance:
  - Endpoint calls service and returns task/result metadata.

## Phase K: Rollout and Backfill

Goal: safely move from v1 to v2.

### K1. Add v2 task routes behind feature flags

- Status: `[ ]`
- Depends on: C10, F5, G5, I3, J1
- Plan refs: [Phase 9](ingestion_v2_plan.md#phase-9-rollout-and-backfill), [Rollout and Backfill](ingestion_v2_plan.md#phase-9-rollout-and-backfill)
- Build:
  - Existing task names can call v1 or v2 based on `INGESTION_V2_ENABLED`.
  - Keep v1 fallback.
  - Do not change `/health`.
- Acceptance:
  - Feature disabled => v1 behavior.
  - Feature enabled => v2 service called.

### K2. Add dark-launch staging mode

- Status: `[ ]`
- Depends on: B6, J1
- Plan refs: [Phase 9](ingestion_v2_plan.md#phase-9-rollout-and-backfill), [Promotion Strategy](ingestion_v2_plan.md#promotion-strategy)
- Build:
  - If `INGESTION_V2_PROMOTE_ENABLED=false`, stage/validate only.
  - Do not write domain tables except run/staging/quarantine.
- Acceptance:
  - Dark launch produces quality summary and no domain row changes.

### K3. Add parity report between v1 and v2

- Status: `[ ]`
- Depends on: K2, A4
- Plan refs: [Rollout and Backfill](ingestion_v2_plan.md#phase-9-rollout-and-backfill), [Target Outcomes](ingestion_v2_plan.md#target-outcomes)
- Build:
  - Compare:
    - rows read.
    - inserted/updated/unchanged predicted.
    - quarantine/reject counts.
    - missing-parent count.
  - Output markdown or JSON.
- Acceptance:
  - One report can justify enabling promotion.

### K4. Add backfill runner

- Status: `[ ]`
- Depends on: K1, K2
- Plan refs: [Rollout and Backfill](ingestion_v2_plan.md#phase-9-rollout-and-backfill)
- Build:
  - Run years oldest to newest.
  - Cadastro first, then identity, then DFP/ITR/FRE.
  - Resume-safe.
  - Can run for one year first.
- Acceptance:
  - Backfill for one test year completes idempotently.

### K5. Add rollout documentation

- Status: `[ ]`
- Depends on: K1, K2, K3
- Plan refs: [Operational Runbooks](ingestion_v2_plan.md#operational-runbooks), [Risks and Mitigations](ingestion_v2_plan.md#risks-and-mitigations)
- Build:
  - Document:
    - env flags.
    - dark launch.
    - promotion enablement.
    - rollback to v1.
    - quality gates.
  - Could be appended to this tasks doc or separate runbook.
- Acceptance:
  - Operator can run/rollback v2 from docs.

## Phase L: Final SLO and Cleanup

Goal: verify v2 meets target outcomes and retire dead paths only after stable production use.

### L1. Add quality gate enforcement

- Status: `[ ]`
- Depends on: J3
- Plan refs: [Promotion Strategy](ingestion_v2_plan.md#promotion-strategy), [Target Outcomes](ingestion_v2_plan.md#target-outcomes)
- Build:
  - Enforce max `companhia_nao_encontrada` ratio.
  - Enforce required member schema success.
  - Mark run `sucesso_com_alerta` or failure equivalent depending chosen status model.
- Acceptance:
  - Test high missing-parent ratio fails quality gate.

### L2. Run live audit and v2 dark launch for 2021

- Status: `[ ]`
- Depends on: K2, A6
- Plan refs: [Target Outcomes](ingestion_v2_plan.md#target-outcomes), [Suggested First Sprint](ingestion_v2_plan.md#suggested-first-sprint)
- Build:
  - Use official 2021 DFP/ITR/FRE.
  - Compare with plan target numbers.
  - Store/report result.
- Acceptance:
  - DFP 2021 missing parent target: `0`.
  - FRE 2021 missing parent target: `0`.
  - ITR 2021 missing parent target: `<= 1` before provisional/manual rule, `0` after.

### L3. Enable v2 promotion for one year

- Status: `[ ]`
- Depends on: L2, K1
- Plan refs: [Rollout and Backfill](ingestion_v2_plan.md#phase-9-rollout-and-backfill)
- Build:
  - Enable promotion in non-prod or local first.
  - Run one configured year.
  - Validate API queries still work.
- Acceptance:
  - Domain row counts sane.
  - Existing API tests pass.

### L4. Replay repairable quarantine after identity fixes

- Status: `[ ]`
- Depends on: H5, L3
- Plan refs: [Repair and Replay](ingestion_v2_plan.md#repair-and-replay), [When `companhia_nao_encontrada` Spikes](ingestion_v2_plan.md#when-companhia_nao_encontrada-spikes)
- Build:
  - Replay by `companhia_nao_encontrada`.
  - Replay exact duplicate auto-resolutions.
  - Generate post-replay quality report.
- Acceptance:
  - Repairable quarantine count drops.

### L5. Retire or isolate v1 paths

- Status: `[ ]`
- Depends on: L3, L4
- Plan refs: [Definition of Done](ingestion_v2_plan.md#definition-of-done-for-ingestion-v2), [Rollout and Backfill](ingestion_v2_plan.md#phase-9-rollout-and-backfill)
- Build:
  - Keep rollback path until stable runs across configured years.
  - After stability, remove duplicate v1 import code or mark legacy.
  - Keep admin compatibility if needed.
- Acceptance:
  - No v1 code path needed for normal operations.
  - Rollback plan documented.

## Cross-cutting Rules For Agents

- Keep changes focused per task.
- Use `pyproject.toml` for dependencies.
- Prefer stdlib/current dependencies; do not add data-quality frameworks unless task explicitly requires it.
- Preserve `/health` unauthenticated.
- Keep Helm chart constraints: external Postgres/Redis, NodePort default, no migration-job.
- Never make live CVM network part of default tests.
- Add tests proportional to task risk.
- For DB model changes, include Alembic migration and model tests.
- For resolver changes, include ambiguity tests.
- For retry changes, prove deterministic row errors do not retry.

## Suggested Implementation Order

1. A1-A6: audit proof.
2. B1-B7: staging foundation.
3. C1-C10: identity graph and cadastro v2.
4. D1-D7: resolver.
5. E1-E5: validation/duplicates.
6. F1-F6: DFP/ITR v2.
7. G1-G6: FRE v2.
8. H1-H6: quarantine/replay.
9. I1-I5: retry/dependency deferral.
10. J1-J5: admin/metrics/config.
11. K1-K5: rollout/backfill.
12. L1-L5: SLO verification and cleanup.
