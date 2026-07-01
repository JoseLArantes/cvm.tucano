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
- **Generic Row Staging** means loading raw CSV rows into `ingestion_rows` before validation and promotion. It is reserved for sources and error paths that still need row-level relational diagnostics.
- **Artifact Store** means the storage layer that keeps raw ZIPs, raw members, and normalized member artifacts outside the canonical relational model.
- **Artifact Manifest** means the durable metadata that identifies an artifact by URI, hash, size, source, member, and run lineage.
- **Normalized Artifact** means a rebuildable typed file produced from a member before PostgreSQL promotion.
- **Typed Staging** means rebuildable PostgreSQL staging tables loaded from normalized artifacts via streaming `COPY`.
- **Financial Direct Path** means the DFP/ITR member pipeline that reads the raw CSV artifact, normalizes valid rows into a typed normalized artifact, loads typed staging, promotes canonical rows, reconciles scope, and purges typed staging without persisting valid rows in `ingestion_rows`.
- **Promotion** means writing normalized rows into domain tables.
- **Phase Checkpoint** means the operational record that marks which ingestion phase has started, advanced, failed, or completed for a run or member.
- **Operational Signal** means the API-facing aggregate state that tells a decoupled consumer the current state, phase, progress, liveness, blocking reason, cancellation state, last error, and next recommended action for an ingestion scope.
- **Cancellation Request** means a durable operator request to stop a run, ZIP execution, member execution, quarantine replay, or task without relying only on transient Celery revoke state.
- **Reconcile** means removing or marking rows no longer present in the source scope after successful promotion.
- **Quarantine** means preserving invalid or unpromotable rows with enough context for inspection or repair.
- **Replay** means reprocessing previously persisted payloads without relying on a new remote download.
- **Lineage** means source file, year, row, member, hashes, and run identifiers that explain where data came from.

## Pipeline invariants

- Ingestion is more important than materialization and must keep operational priority.
- Do not hide failures behind silent fallbacks.
- Preserve idempotency, lineage, and real operational statuses.
- Treat `ExecucaoSincronizacao` and `IngestionRun` as primary operational state sources.
- API observability is part of the ingestion product contract; operators and frontends must not need worker logs to know current phase, liveness, cancellation state, blocking reason, or recovery action.
- Prefer chunked, restartable operations over large all-or-nothing jobs.
- Preserve raw payloads where the current pipeline depends on replay and self-healing.
- Prefer artifact-backed replay over relational storage of full successful staging history when redesigning the pipeline.
- DFP/ITR valid rows must follow the Financial Direct Path; `ingestion_rows` is acceptable there only for rejected rows that need quarantine compatibility.
- Isolated member replay must use bounded in-memory state; it must not depend on reloading the full staged history of sibling members.
- Be careful with database-specific JSON, locking, and COPY behavior; tests often run on SQLite.
- Any change to promoted tables, staging contracts, or operational state requires tests for failure and monitoring paths.

## Celery rules

- Validate queue names and routing when changing task behavior.
- Ingestion workers consume `ingestion` and `ingestion_control`; materialization workers consume only `analise_materializacao`.
- Do not create post-ingestion fan-out that can starve ingestion or flood workers.
- If a task changes status transitions, update monitoring expectations and tests.
- Use explicit failure states and summaries so operators can distinguish skipped, unchanged, warning, failed, and successful work.
- Cancellation must be durable in ingestion state, not only a best-effort Celery revoke.
