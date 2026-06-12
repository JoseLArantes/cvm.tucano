from __future__ import annotations

from collections import Counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ingestion import IngestionAttempt, IngestionRow, IngestionRun, QuarantineItem


def build_quality_summary(db: Session, *, ingestion_run_id: Any) -> dict[str, Any]:
    rows = list(db.execute(select(IngestionRow).where(IngestionRow.ingestion_run_id == ingestion_run_id)).scalars())
    quarantines = list(
        db.execute(select(QuarantineItem).where(QuarantineItem.ingestion_run_id == ingestion_run_id)).scalars()
    )
    attempts = list(
        db.execute(select(IngestionAttempt).where(IngestionAttempt.ingestion_run_id == ingestion_run_id)).scalars()
    )

    row_status_counts = Counter(row.validation_status for row in rows)
    reason_counts = Counter(row.validation_reason_code or "none" for row in rows)
    resolver_methods = Counter(row.resolution_method or "none" for row in rows)
    top_files = Counter(item.arquivo_origem for item in quarantines)
    provisional_count = sum(1 for row in rows if row.resolution_method == "provisional_company_baixa")

    return {
        "row_status_counts": dict(row_status_counts),
        "reason_counts": dict(reason_counts),
        "resolver_methods": dict(resolver_methods),
        "top_quarantine_files": [
            {"arquivo_origem": arquivo, "total": total} for arquivo, total in top_files.most_common(10)
        ],
        "provisional_company_count": provisional_count,
        "attempts": {
            "total": len(attempts),
            "by_status": dict(Counter(attempt.status for attempt in attempts)),
            "next_retry_at": max(
                (attempt.next_retry_at.isoformat() for attempt in attempts if attempt.next_retry_at is not None),
                default=None,
            ),
        },
        "quarantine_total": len(quarantines),
    }


def build_quality_summary_snapshot(
    *,
    row_status_counts: dict[str, int] | None = None,
    reason_counts: dict[str, int] | None = None,
    resolver_methods: dict[str, int] | None = None,
    quarantine_total: int = 0,
    provisional_company_count: int = 0,
    attempts_total: int = 0,
    attempts_by_status: dict[str, int] | None = None,
    top_quarantine_files: list[dict[str, Any]] | None = None,
    extras: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary = {
        "row_status_counts": row_status_counts or {},
        "reason_counts": reason_counts or {},
        "resolver_methods": resolver_methods or {},
        "top_quarantine_files": top_quarantine_files or [],
        "provisional_company_count": provisional_company_count,
        "attempts": {
            "total": attempts_total,
            "by_status": attempts_by_status or {},
            "next_retry_at": None,
        },
        "quarantine_total": quarantine_total,
    }
    if extras:
        summary.update(extras)
    return summary


def build_contadores_quality_summary(
    contadores: dict[str, int],
    *,
    extras: dict[str, Any] | None = None,
) -> dict[str, Any]:
    validos = contadores.get("inseridos", 0) + contadores.get("atualizados", 0) + contadores.get("inalterados", 0)
    rejeitados = contadores.get("rejeitados", 0)
    return build_quality_summary_snapshot(
        row_status_counts={"valid": validos, "invalid": rejeitados},
        quarantine_total=rejeitados,
        extras=extras,
    )


def persist_quality_summary(db: Session, *, run: IngestionRun) -> dict[str, Any]:
    summary = build_quality_summary(db, ingestion_run_id=run.id)
    run.quality_summary = summary
    return summary


def build_parity_report(*, legado: dict[str, Any], atual: dict[str, Any]) -> dict[str, Any]:
    keys = sorted(set(legado) | set(atual))

    def _delta(key: str) -> int | float | None:
        valor_legado = legado.get(key)
        valor_atual = atual.get(key)
        if not isinstance(valor_legado, (int, float)) or not isinstance(valor_atual, (int, float)):
            return None
        return valor_atual - valor_legado

    return {
        "comparison": [
            {
                "metric": key,
                "legado": legado.get(key),
                "atual": atual.get(key),
                "delta": _delta(key),
            }
            for key in keys
        ]
    }


def render_parity_report_markdown(*, legado: dict[str, Any], atual: dict[str, Any]) -> str:
    report = build_parity_report(legado=legado, atual=atual)
    linhas = [
        "# Ingestion Parity Report",
        "",
        "| metric | legado | atual | delta |",
        "| --- | ---: | ---: | ---: |",
    ]
    for item in report["comparison"]:
        linhas.append(f"| {item['metric']} | {item['legado']} | {item['atual']} | {item['delta']} |")
    return "\n".join(linhas) + "\n"
