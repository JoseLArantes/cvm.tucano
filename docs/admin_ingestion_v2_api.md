# Admin Ingestion V2 API

This document complements `/openapi.json` and `/docs` for the ingestion v2 operational surface used by the frontend.

Base auth rule:

- all endpoints below require the existing bearer token used by `/admin/*`

## Endpoints

### `GET /admin/ingestion-v2/runs`

Purpose:

- list ingestion v2 runs for operational dashboards

Query params:

- `pagina`
- `tamanho_pagina`

Response shape:

```json
{
  "dados": [
    {
      "id": "6a31c7f8-1c89-4f3d-87db-7e6a8e196999",
      "execucao_sincronizacao_id": "02be26d3-8db8-48a1-bcd0-4737b8157116",
      "tipo_fonte": "dfp",
      "ano": 2025,
      "status": "sucesso_com_alerta",
      "phase": "promote",
      "quality_summary": {
        "row_counts": {
          "valid": 1200,
          "invalid": 3
        },
        "reason_counts": {
          "companhia_nao_encontrada": 2,
          "schema_inesperado": 1
        },
        "resolver_methods": {
          "codigo_cvm_identificador_alta": 1180,
          "repair_rule": 20
        },
        "quarantine_total": 3
      }
    }
  ],
  "paginacao": {
    "pagina": 1,
    "tamanho_pagina": 100,
    "total": 1
  }
}
```

Frontend notes:

- `status` is the main run badge
- `phase` is useful for progress/state chips
- `quality_summary` is semi-structured; frontend should read keys defensively

### `GET /admin/ingestion-v2/runs/{run_id}`

Purpose:

- fetch one run for detail views or action drawers

Path params:

- `run_id`: UUID

Response:

- same object shape as one row from the list endpoint

### `GET /admin/ingestion-v2/quarantine`

Purpose:

- list repairable and non-repairable rejected rows from ingestion v2

Query params:

- `pagina`
- `tamanho_pagina`
- `motivo_codigo` optional

Response shape:

```json
{
  "dados": [
    {
      "id": "0ebc5c67-25a4-4e0c-ab25-66eaf4af4ced",
      "ingestion_run_id": "6a31c7f8-1c89-4f3d-87db-7e6a8e196999",
      "ingestion_row_id": "9b3a4f45-b7ab-4de6-a93d-95f85913df71",
      "arquivo_origem": "itr_cia_aberta_2021.csv",
      "ano_origem": 2021,
      "linha_origem": 1692,
      "row_kind": "itr_documento",
      "status": "pendente",
      "motivo_codigo": "companhia_nao_encontrada",
      "severidade": "error",
      "reparavel": true,
      "tentativas_reprocessamento": 1,
      "diagnostico": {
        "codigo_cvm": 3,
        "denominacao_companhia": "EMPRESA FINANCEIRA",
        "resolution_method": "none"
      }
    }
  ],
  "paginacao": {
    "pagina": 1,
    "tamanho_pagina": 100,
    "total": 1
  }
}
```

Frontend notes:

- `motivo_codigo` should drive filters and grouping
- `reparavel` controls whether replay actions are enabled
- `tentativas_reprocessamento` is important for retry exhaustion UI
- `diagnostico` is semi-structured; render as expandable JSON or selected known keys

## Replay Actions

### `POST /admin/ingestion-v2/replay/quarantine`

Purpose:

- replay pending quarantine rows, optionally filtered

Request body:

```json
{
  "reason_code": "companhia_nao_encontrada",
  "arquivo_origem": "itr_cia_aberta_2021.csv",
  "ano": 2021
}
```

All fields are optional.

Recommended UI behavior:

- send only fields actually chosen by the operator
- treat an empty body as "replay all pending"
- confirm before broad replay

### `POST /admin/ingestion-v2/runs/{run_id}/replay`

Purpose:

- replay all rows from one run

Path params:

- `run_id`: UUID

### `POST /admin/ingestion-v2/identity/rebuild`

Purpose:

- rebuild identity graph from cadastro v2
- this is normally followed by quarantine replay for `companhia_nao_encontrada`

## Shared Replay Response

Replay and identity rebuild return:

```json
{
  "status": "sucesso",
  "detalhe": {
    "status": "sucesso"
  }
}
```

`detalhe` is operation-specific. The frontend should:

- rely on top-level `status` for request acceptance
- show `detalhe.status`, `detalhe.total`, `detalhe.rows`, or `detalhe.items` when present
- avoid strict assumptions that every replay mode returns identical keys

## Important Status Semantics

Run statuses currently relevant to v2:

- `em_execucao`
- `sucesso`
- `sucesso_com_alerta`
- `falha`
- `falha_qualidade`

Quarantine statuses currently relevant to v2:

- `pendente`
- `resolvido_auto`
- `resolvido_manual`
- `ignorado`

## Stable Reason Codes

Frontend filters should be built around stable reason codes, especially:

- `companhia_nao_encontrada`
- `chave_natural_duplicada_no_arquivo`
- `schema_inesperado`

More codes may be added without endpoint shape changes.

## Source of Truth

Generated OpenAPI remains the source of truth for exact schema metadata:

- `/openapi.json`
- `/docs`
