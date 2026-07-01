# Documentation Context

This context covers user-facing documentation, API reference pages, schema docs, and frontend-facing changelogs.

## Scope

- `docusaurus/docs/`
- `docusaurus/sidebars.js`
- `docusaurus/src/` when changing documentation presentation
- `docs/frontend_api_changelog.md`
- Cross-referenced public docs under root `docs/` when they describe public behavior

## Domain vocabulary

- **Public documentation** means docs intended for API consumers, frontend developers, operators, or users.
- **Frontend changelog** means `docs/frontend_api_changelog.md`, the consumer-facing record of endpoint, field, filter, and behavior changes.
- **Contract documentation** means endpoint docs, schema docs, examples, field descriptions, filters, status values, and operational semantics.
- **Current behavior only** means docs must describe how the code behaves now, not intended future behavior.

## Language rules

- User-facing product text and public documentation for this project should be written in Brazilian Portuguese unless the task clearly requires English.
- Agent setup files and conversation/instruction files may be English when the user asks for that.
- Preserve code identifiers exactly as implemented, even inside Portuguese prose.

## Documentation rules

- When contracts, payloads, filters, fields, worker flow, or public surface area change, update the relevant Docusaurus docs and `docs/frontend_api_changelog.md`.
- Docusaurus updates are required for every public behavior change, including endpoint additions/removals, schema changes, filter/default changes, auth changes, worker-flow changes visible to operators, status semantics, and frontend-visible edge cases.
- Docusaurus and OpenAPI must tell the same story. If a router or schema description changes, update the matching docs page; if a docs page changes because behavior changed, make sure OpenAPI metadata is equally detailed.
- Frontend changelog entries must use the correct session date and highlight consumer-visible endpoint, field, and behavior changes.
- Keep examples aligned with actual route prefixes, auth requirements, query parameters, response fields, and status semantics.
- Run `npm --prefix docusaurus run build` after Docusaurus changes or public documentation changes.
- Do not add roadmap claims to reference docs unless the current behavior already supports them.
