from __future__ import annotations

from typing import Any

from app.core.config import get_settings


def enforce_quality_gate(*, quality_summary: dict[str, Any]) -> tuple[str, str | None]:
    settings = get_settings()
    row_status_counts = quality_summary.get("row_status_counts", {})
    total_rows = sum(value for value in row_status_counts.values() if isinstance(value, int))
    if total_rows <= 0:
        return "sucesso", None

    reason_counts = quality_summary.get("reason_counts", {})
    missing_company = reason_counts.get("companhia_nao_encontrada", 0)
    ratio = missing_company / total_rows
    if ratio > settings.ingestion_company_missing_max_ratio:
        return "falha_qualidade", f"companhia_nao_encontrada_ratio={ratio:.4f}"

    schema_errors = reason_counts.get("schema_inesperado", 0)
    if schema_errors > 0:
        return "sucesso_com_alerta", "schema_inesperado"

    return "sucesso", None
