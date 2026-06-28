# Ingestion Context

This context covers the priority pipeline that acquires, normalizes, stores, and reconciles public CVM data.

## Scope

- `app/services/ingestion/`
- ingestion-related models in `app/models/ingestion.py` and `app/models/sincronizacao.py`
- ingestion orchestration in `app/worker/tasks.py`
- ingestion source documentation in `docs/ingestion.md` and `docusaurus/docs/ingestion/`
- tests named `tests/unit/test_ingestion_*.py`

## Domain vocabulary

- **Source** means a supported CVM dataset such as `cadastro`, `dfp`, `itr`, `fre`, `fca`, `ipe`, `vlmo`, or `cgvn`.
- **Acquisition** means remote probe, download, checksum, member extraction, and payload persistence before domain promotion.
- **IngestionRun** means the v2 operational run for one source artifact.
- **ExecucaoSincronizacao** means the synchronization execution record used as a primary operational state source.
- **Member** means a CSV file inside a CVM ZIP artifact.
- **Reusable member result** means a previously successful member execution that can be reused by `member_sha256` in a later rerun, even if the yearly ZIP parent execution that originally contained it ended in failure.
- **Header seed** means the compact set of previously promoted document identities used to resolve company identity during isolated member replay.
- **Staging** means loading raw CSV rows into `ingestion_rows` before validation and promotion.
- **Promotion** means writing normalized rows into domain tables.
- **Reconcile** means removing or marking rows no longer present in the source scope after successful promotion.
- **Quarantine** means preserving invalid or unpromotable rows with enough context for inspection or repair.
- **Replay** means reprocessing previously persisted payloads without relying on a new remote download.
- **Lineage** means source file, year, row, member, hashes, and run identifiers that explain where data came from.

## Pipeline invariants

- Ingestion is more important than materialization and must keep operational priority.
- Do not hide failures behind silent fallbacks.
- Preserve idempotency, lineage, and real operational statuses.
- Treat `ExecucaoSincronizacao` and `IngestionRun` as primary operational state sources.
- Prefer chunked, restartable operations over large all-or-nothing jobs.
- Preserve raw payloads where the current pipeline depends on replay and self-healing.
- Isolated member replay must use bounded in-memory state; it must not depend on reloading the full staged history of sibling members.
- Be careful with database-specific JSON, locking, and COPY behavior; tests often run on SQLite.
- Any change to promoted tables, staging contracts, or operational state requires tests for failure and monitoring paths.

## Celery rules

- Validate queue names and routing when changing task behavior.
- Do not create post-ingestion fan-out that can starve ingestion or flood workers.
- If a task changes status transitions, update monitoring expectations and tests.
- Use explicit failure states and summaries so operators can distinguish skipped, unchanged, warning, failed, and successful work.
