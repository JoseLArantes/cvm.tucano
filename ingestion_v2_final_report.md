# Ingestion V2 Final Report

Date: 2026-06-03

References:
- Plan: [ingestion_v2_plan.md](/Users/joseluiz/workspace/projects/tucano-cvm/ingestion_v2_plan.md)
- Tasks: [ingestion_v2_tasks.md](/Users/joseluiz/workspace/projects/tucano-cvm/ingestion_v2_tasks.md)

## Scope Completed

This delivery completes phases H through L from the implementation tracker:

- Phase H: quarantine v2 and replay
- Phase I: retry and dependency deferral
- Phase J: admin, metrics, and config
- Phase K: rollout and backfill
- Phase L: quality gates, audit evidence, and legacy-path isolation

## Phase H

Implemented repairable quarantine and replay:

- `quarantine_items_v2` model and migration
- quarantine service with bridge-write support
- persisted repair rules reuse
- row, member, run, and quarantine replay services
- replay attempt tracking and row events
- replay tests for success and failure paths

Primary files:

- [app/models/ingestion.py](/Users/joseluiz/workspace/projects/tucano-cvm/app/models/ingestion.py)
- [alembic/versions/0009_ingestion_v2_quarantine.py](/Users/joseluiz/workspace/projects/tucano-cvm/alembic/versions/0009_ingestion_v2_quarantine.py)
- [app/services/ingestion/quarantine.py](/Users/joseluiz/workspace/projects/tucano-cvm/app/services/ingestion/quarantine.py)
- [app/services/ingestion/replay.py](/Users/joseluiz/workspace/projects/tucano-cvm/app/services/ingestion/replay.py)
- [app/services/ingestion/repair_rules.py](/Users/joseluiz/workspace/projects/tucano-cvm/app/services/ingestion/repair_rules.py)

## Phase I

Implemented transient retry handling and dependency deferral:

- retry exception taxonomy
- acquisition helper with attempt persistence
- Celery autoretry/backoff/jitter wiring for v2 task paths
- identity-graph readiness check before document imports
- run summary attempt visibility

Primary files:

- [app/services/ingestion/retry.py](/Users/joseluiz/workspace/projects/tucano-cvm/app/services/ingestion/retry.py)
- [app/services/ingestion/acquisition.py](/Users/joseluiz/workspace/projects/tucano-cvm/app/services/ingestion/acquisition.py)
- [app/services/ingestion/dependencies.py](/Users/joseluiz/workspace/projects/tucano-cvm/app/services/ingestion/dependencies.py)
- [app/worker/tasks.py](/Users/joseluiz/workspace/projects/tucano-cvm/app/worker/tasks.py)

## Phase J

Implemented operational control and visibility:

- v2 settings and feature flags
- metrics helpers
- quality summary aggregation/persistence
- admin endpoints for runs and quarantine
- admin replay and identity rebuild endpoints

Primary files:

- [app/core/config.py](/Users/joseluiz/workspace/projects/tucano-cvm/app/core/config.py)
- [app/services/ingestion/metrics.py](/Users/joseluiz/workspace/projects/tucano-cvm/app/services/ingestion/metrics.py)
- [app/services/ingestion/summary.py](/Users/joseluiz/workspace/projects/tucano-cvm/app/services/ingestion/summary.py)
- [app/api/routers/admin.py](/Users/joseluiz/workspace/projects/tucano-cvm/app/api/routers/admin.py)
- [app/schemas/admin.py](/Users/joseluiz/workspace/projects/tucano-cvm/app/schemas/admin.py)

## Phase K

Implemented rollout controls:

- feature-flag routing between v1 and v2
- dark-launch mode with staging-only behavior
- parity report helpers
- backfill runner
- rollout runbook

Primary files:

- [app/services/ingestion/backfill.py](/Users/joseluiz/workspace/projects/tucano-cvm/app/services/ingestion/backfill.py)
- [app/services/ingestion/financeiro.py](/Users/joseluiz/workspace/projects/tucano-cvm/app/services/ingestion/financeiro.py)
- [app/services/ingestion/fre.py](/Users/joseluiz/workspace/projects/tucano-cvm/app/services/ingestion/fre.py)
- [docs/ingestion_v2_rollout.md](/Users/joseluiz/workspace/projects/tucano-cvm/docs/ingestion_v2_rollout.md)

## Phase L

Implemented final guardrails:

- quality gate enforcement
- live 2021 audit report generation
- v2 promotion path for one-year rollout via flags/backfill services
- replay workflow for repairable quarantine after identity fixes
- explicit isolation of v1 as rollback-only fallback during rollout

Primary files:

- [app/services/ingestion/quality.py](/Users/joseluiz/workspace/projects/tucano-cvm/app/services/ingestion/quality.py)
- [docs/ingestion_v2_rollout.md](/Users/joseluiz/workspace/projects/tucano-cvm/docs/ingestion_v2_rollout.md)

## Live 2021 Audit Evidence

Command executed:

```bash
python3 scripts/audit_ingestion_consistency.py --year 2021 --sources dfp itr fre --output-json .tmp_ingestion_v2_audit_2021.json
```

Observed results on 2026-06-03:

### Cadastro duplicates

- rows: `2675`
- duplicate buckets: `140`
- duplicate extra rows: `147`
- duplicate extra ratio: `5.50%`
- same `CD_CVM`, different `TP_MERC`: `110`
- same `CNPJ`, different `CD_CVM`: `37`

### Missing parent before and after foreign cadastro coverage

| Source | Rows | Missing with open cadastro only | Missing with open + foreign cadastro |
| --- | ---: | ---: | ---: |
| DFP 2021 | 1,237,654 | 9,711 | 0 |
| ITR 2021 | 3,643,850 | 18,875 | 1 |
| FRE 2021 | 185,667 | 1,432 | 0 |

Interpretation:

- foreign cadastro closes the documented `companhia_nao_encontrada` gap for DFP and FRE 2021
- ITR 2021 drops to a single residual record: `EMPRESA FINANCEIRA`, `CD_CVM=3`
- cadastro duplicate handling must treat multi-market rows as mergeable and historic `CD_CVM` changes as valid identity history

## Test Verification

Full repository test suite executed with Docker Compose:

```bash
docker compose run --rm cvm_api python -m pytest -q
```

Result:

- `100 passed`
- `1 warning`

The two v2 admin failures found during the first container run were fixed by:

- parsing admin `run_id` path parameters as `UUID`
- removing an unnecessary stale monkeypatch in `test_ingestion_v2_ops.py`

## Operational Notes

- `/health` remains unchanged and unauthenticated.
- Helm assumptions were preserved; nothing reintroduced in-cluster Postgres, Redis, or migration-job templates.
- v1 ingestion remains isolated behind `INGESTION_V2_ENABLED=false` for rollback only.
- Promotion of a full live year and replay against a mutable shared environment remain operator-controlled rollout steps; code, runbook, quality gates, and tests are ready.
