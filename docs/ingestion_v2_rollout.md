# Ingestion V2 Rollout

## Flags

- `INGESTION_V2_ENABLED`
- `INGESTION_V2_PROMOTE_ENABLED`
- `INGESTION_V2_PROVISIONAL_COMPANY_ENABLED`
- `INGESTION_V2_MAX_RETRIES`
- `INGESTION_V2_RETRY_BACKOFF_MAX_SECONDS`
- `INGESTION_V2_COMPANY_MISSING_MAX_RATIO`
- `INGESTION_V2_STAGE_BATCH_SIZE`
- `INGESTION_V2_PROMOTE_BATCH_SIZE`

## Dark Launch

1. Set `INGESTION_V2_ENABLED=true`
2. Set `INGESTION_V2_PROMOTE_ENABLED=false`
3. Run cadastro v2 first.
4. Run one target year for `dfp`, `itr`, `fre`.
5. Inspect:
   - `/admin/ingestion-v2/runs`
   - `/admin/ingestion-v2/quarantine`
   - quality summary on run detail

## Promotion Enablement

1. Keep `INGESTION_V2_ENABLED=true`
2. Set `INGESTION_V2_PROMOTE_ENABLED=true`
3. Run one year first.
4. Validate domain API behavior and quarantine drop.

## Rollback

1. Set `INGESTION_V2_ENABLED=false`
2. Keep `/health` unchanged.
3. Re-run failing year with legacy tasks if needed.

## Legacy V1 Isolation

- v1 ingestion remains only as feature-flagged fallback while rollout is active.
- Celery task names stay the same; routing chooses v1 or v2 by `INGESTION_V2_ENABLED`.
- Normal operation with v2 enabled does not require v1 paths.
- Admin compatibility stays unchanged during rollout so rollback is operationally cheap.

## Quality Gates

- `companhia_nao_encontrada` ratio must stay below `INGESTION_V2_COMPANY_MISSING_MAX_RATIO`
- schema errors produce `sucesso_com_alerta`
- quality gate breach produces `falha_qualidade`

## Backfill

Recommended order:

1. cadastro v2
2. dfp oldest -> newest
3. itr oldest -> newest
4. fre oldest -> newest

Use one-year batches first. Replays can be triggered after identity fixes.
