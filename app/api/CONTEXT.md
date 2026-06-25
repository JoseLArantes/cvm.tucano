# API Contracts Context

This context covers the public HTTP surface implemented by FastAPI routers and Pydantic schemas.

## Scope

- Routers under `app/api/routers/`
- Auth and dependency helpers in `app/api/auth.py` and `app/api/deps.py`
- Request and response contracts under `app/schemas/`
- OpenAPI metadata, endpoint descriptions, filters, pagination, error semantics, and response examples
- Tests under `tests/unit/test_api_*.py`

## Domain vocabulary

- **Public surface** means anything a frontend, operator, or API consumer can call or parse.
- **Contract** means request fields, response fields, status codes, query parameters, path structure, enum values, defaults, ordering, nullability, and documented behavior.
- **Closed and typed contract** means schemas should reject unexpected shape where appropriate and expose explicit types instead of unstructured dictionaries.
- **System token** means `TUCANO_CVM_TOKEN`, used for bootstrap and privileged operational access.
- **User token** means a bearer token returned by `/auth/login`.
- **Operational endpoint** means an endpoint used to inspect or control backend state, especially ingestion and analysis materialization.

## Current API shape

- `/health` is intentionally public.
- `/auth/*` handles login and current-user inspection.
- `/usuarios/*` is administrative and accepts the system token or an admin user where implemented.
- CVM data surfaces are split by domain routers such as `companhias`, `financeiro`, `fre`, `fca`, `ipe`, `vlmo`, and `cgvn`.
- Analysis endpoints live under `/analise/companhias/...`.
- Analysis materialization observability and controls live under `/analise/materializacoes/...`.
- The updates service has its own router under `app/updates/router.py`.

## Rules for API changes

- Preserve existing route prefixes unless the task explicitly changes the public contract.
- Keep units explicit in schemas and descriptions. Financial values must clarify whether they are reported values, scaled values, ratios, counts, or percentages.
- For analysis responses, preserve `resolution.mode` and distinguish `canonical` from `runtime_fallback`.
- When changing a public contract, update router/schema OpenAPI descriptions, focused API tests, Docusaurus docs, and `docs/frontend_api_changelog.md`.
- OpenAPI documentation must be very detailed: describe authentication, permissions, request bodies, path and query parameters, filters, defaults, response fields, units, enum/status values, pagination, examples, no-op cases, partial-success cases, and operational edge cases.
- Router descriptions and schema field descriptions are part of the contract. Keep them synchronized with the implemented behavior and with Docusaurus.
- When changing authentication or authorization, test both allowed and denied paths.
- Do not hide operational failures behind successful responses unless the current contract explicitly models partial success or no-op behavior.
