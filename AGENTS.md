# AGENTS

- Keep changes focused; do not widen scope without need.
- Use `pyproject.toml` as the dependency source of truth.
- Preserve `/health` as unauthenticated for Kubernetes probes.
- Kubernetes chart is in `deploy/helm/tucano-cvm`; Postgres and Redis are external there.
- Default Kubernetes service exposure is `NodePort 8110:30110`.
- Do not reintroduce migration-job, in-cluster Postgres, or in-cluster Redis templates unless explicitly requested.
