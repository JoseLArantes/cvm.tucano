# AGENTS.md

`tucano-cvm` is a FastAPI service for ingesting, normalizing, storing, and exposing public CVM data.

Stack: Python 3.12, FastAPI, SQLAlchemy 2.x, Alembic, Celery + Redis, PostgreSQL, Docusaurus.

## Working rules

- Use the repository as the source of truth. Read the existing flow and contracts before editing.
- Preserve local module patterns and fix problems at the root cause.
- Use `rg` for search and `apply_patch` for manual edits.
- Do not revert user changes or use destructive git commands.
- Default to ASCII in code and docs unless the file already requires Unicode.
- Documentation must describe current behavior only.
- User-facing product text and documentation for this project should be written in Brazilian Portuguese unless the task clearly requires English.

## Required validation

```bash
docker compose run --rm cvm_api mypy .
docker compose run --rm cvm_api ruff check . --ignore E501
docker compose run --rm cvm_api python -m pytest -q
```

When changing contracts, routers, schemas, or docs:

```bash
npm --prefix docusaurus run build
```

## Quick map

- API: `app/main.py`, `app/api/routers/`, `app/schemas/`
- DB: `app/models/`, `app/db/session.py`, `alembic/versions/`
- Worker: `app/worker/celery_app.py`, `app/worker/tasks.py`
- Analysis: `app/services/analise.py`, `app/api/routers/analise.py`, `app/schemas/analise.py`, `app/models/analise.py`
- Local runtime: `docker-compose.yml`, `docker-compose.workers.yml`

Any persisted structural change requires an Alembic migration.

## Analysis rules

- Analysis endpoints live under `/analise/companhias/...`.
- Contracts should be closed and typed.
- Units must be explicit.
- `resolution.mode` distinguishes `canonical` from `runtime_fallback`.
- Historical annual analysis is a first-class behavior.

## Materialization rules

- Materialization exists to persist the canonical analysis layer and avoid expensive per-request recomputation.
- Use the dedicated `analise_materializacao` queue; the default worker stays on `celery`.
- Campaigns aggregate work by company and scope; items run in chunks.
- Ingestion has total operational priority.
- The admission gate blocks new chunks during active ingestion or manual pause.
- Do not reintroduce massive post-ingestion per-company fan-out.
- Preserve observability by campaign, item, and execution under `/analise/materializacoes/...`.

## Ingestion rules

- Ingestion is a sensitive, priority pipeline.
- `ExecucaoSincronizacao` and `IngestionRun` are the primary operational state sources.
- Preserve idempotency, lineage, and real operational statuses.
- Do not hide failures behind silent fallbacks.
- Validate the impact on Celery behavior and monitoring.

## Testing rules

- A large part of the suite uses in-memory SQLite.
- Avoid relying on database-specific SQL without a portable fallback.
- Be careful with database-specific JSON and locking behavior.
- Prefer logic that works in both SQLite and PostgreSQL.
- When changing public behavior, test OpenAPI too.
- When changing materialization or worker behavior, test monitoring and status edge cases.

## Required documentation updates

If the change affects contracts, payloads, filters, fields, worker flow, or public surface area, update:

- OpenAPI through routers, schemas, and endpoint descriptions
- `docusaurus/docs/...`
- `docs/frontend_api_changelog.md`

For the frontend changelog, record the correct session date and highlight endpoints, fields, and consumer-visible behavior changes.

## Delivery checklist

1. Confirm architectural consistency.
2. Add a migration if persisted state changed.
3. Update relevant tests.
4. Run `mypy`, `ruff`, and `pytest`.
5. Update openapi documentation with very detailed information
6. Run the Docusaurus build when applicable.
7. Update `docs/frontend_api_changelog.md` if the frontend is affected.
