# Persistence Context

This context covers persisted state, SQLAlchemy models, Alembic migrations, and database portability.

## Scope

- SQLAlchemy models under `app/models/`
- Database sessions and base metadata under `app/db/`
- Alembic migrations under `alembic/versions/`
- Persistence-sensitive schemas and services
- Tests that use in-memory SQLite or assert migration-era behavior

## Domain vocabulary

- **Domain table** means a normalized business table such as `companhias`, financial statement tables, FRE/FCA/IPE/VLMO/CGVN tables, or canonical analysis tables.
- **Operational table** means a table that exists to run or observe the system, such as synchronization executions, ingestion runs, staging rows, quarantine rows, campaign state, leases, and users.
- **Natural key** means the business key used to identify a source row across repeated ingestion.
- **Surrogate key** means internal identifiers such as UUID primary keys.
- **Lineage fields** mean source artifact, source year, source member, source line, hashes, and timestamps used for auditability.
- **Persisted structural change** means adding, removing, renaming, or changing columns, indexes, constraints, tables, enum-like values stored in rows, or relationships.

## Persistence rules

- Any persisted structural change requires an Alembic migration.
- Keep migrations compatible with the current heads and naming style.
- Preserve idempotency and lineage fields unless the task explicitly changes the storage contract.
- Prefer logic that works in both PostgreSQL runtime and SQLite unit tests.
- If PostgreSQL-specific SQL is necessary, provide a portable fallback or isolate it behind dialect checks.
- Be careful with JSON fields, locking behavior, and server-side defaults because SQLite tests may not behave like PostgreSQL.
- Widening columns is usually safer than narrowing them for CVM source data, but still requires tests and migration notes.
- Do not silently drop operational history.

## Testing rules

- Model changes should have focused tests for insert, update, uniqueness, and query behavior where relevant.
- Ingestion persistence changes should include failure/quarantine/status tests.
- Analysis persistence changes should include canonical, fallback, monitoring, and recovery edge cases where relevant.
