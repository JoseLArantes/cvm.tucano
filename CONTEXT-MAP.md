# Context Map

This repository uses multiple domain contexts. Read this file first, then read the `CONTEXT.md` files that match the area you are about to change.

If a topic spans contexts, read every relevant context before editing. When a context-specific rule conflicts with a general rule, follow the more specific context and surface the conflict in your response.

## Repository-wide operating context

- Always read the root `AGENTS.md` for project rules before editing.
- Local development and validation must use Docker Compose for the Python service.
- Required Python validation commands are:

```bash
docker compose run --rm cvm_api mypy .
docker compose run --rm cvm_api ruff check . --ignore E501
docker compose run --rm cvm_api python -m pytest -q
```

- When changing contracts, routers, schemas, public docs, worker flow, or public surface area, also run:

```bash
npm --prefix docusaurus run build
```

- OpenAPI documentation must be very detailed for every public endpoint, including request fields, response fields, filters, auth requirements, units, examples, status semantics, and operational edge cases.
- Docusaurus documentation must be updated whenever endpoints, schemas, payloads, filters, fields, worker flow, or public behavior changes.
- Frontend-visible changes must also be recorded in `docs/frontend_api_changelog.md` with the correct session date.

## Contexts

| Context | Read when working on | Context file |
| --- | --- | --- |
| API contracts | FastAPI routers, request/response schemas, OpenAPI descriptions, auth dependencies, public endpoint behavior | `app/api/CONTEXT.md` |
| Analysis | `/analise` endpoints, canonical annual analysis, materialization campaigns, materialization monitoring, analysis schemas/models/services | `app/services/CONTEXT.md` |
| Ingestion | CVM acquisition, staging, validation, identity resolution, promotion, quarantine, replay, Celery ingestion tasks, source registry | `app/services/ingestion/CONTEXT.md` |
| Persistence | SQLAlchemy models, Alembic migrations, table contracts, portability between SQLite tests and PostgreSQL runtime | `app/models/CONTEXT.md` |
| Documentation | Docusaurus docs, public API docs, frontend changelog, user-facing product text | `docusaurus/CONTEXT.md` |

## Cross-context work

- API changes usually require `app/api/CONTEXT.md`, the relevant service context, `app/models/CONTEXT.md` if persisted data changes, and `docusaurus/CONTEXT.md` because OpenAPI and Docusaurus must stay aligned with public behavior.
- Ingestion changes usually require `app/services/ingestion/CONTEXT.md`, `app/models/CONTEXT.md`, and `app/services/CONTEXT.md` if materialization or analysis invalidation is affected.
- Analysis materialization changes usually require `app/services/CONTEXT.md`, `app/models/CONTEXT.md`, and `app/api/CONTEXT.md` because observability is exposed under `/analise/materializacoes/...`.
- Documentation-only changes for user-facing product docs should follow `docusaurus/CONTEXT.md` and the root `AGENTS.md` language rule.

## ADRs

System-wide architectural decisions should live under `docs/adr/` when created. Context-scoped ADRs may live beside the relevant context if a future decision needs that granularity.
