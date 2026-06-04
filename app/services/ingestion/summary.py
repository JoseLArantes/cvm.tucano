from __future__ import annotations

from collections import Counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ingestion import IngestionAttempt, IngestionRow, IngestionRun, QuarantineItemV2


def build_quality_summary(db: Session, *, ingestion_run_id: Any) -> dict[str, Any]:
    rows = list(db.execute(select(IngestionRow).where(IngestionRow.ingestion_run_id == ingestion_run_id)).scalars())
    quarantines = list(
        db.execute(select(QuarantineItemV2).where(QuarantineItemV2.ingestion_run_id == ingestion_run_id)).scalars()
    )
    attempts = list(db.execute(select(IngestionAttempt).where(IngestionAttempt.ingestion_run_id == ingestion_run_id)).scalars())

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
            {"arquivo_origem": arquivo, "total": total}
            for arquivo, total in top_files.most_common(10)
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


def persist_quality_summary(db: Session, *, run: IngestionRun) -> dict[str, Any]:
    summary = build_quality_summary(db, ingestion_run_id=run.id)
    run.quality_summary = summary
    return summary


def build_parity_report(*, v1: dict[str, Any], v2: dict[str, Any]) -> dict[str, Any]:
    keys = sorted(set(v1) | set(v2))
    return {
        "comparison": [
            {
                "metric": key,
                "v1": v1.get(key),
                "v2": v2.get(key),
                "delta": None
                if not isinstance(v1.get(key), (int, float)) or not isinstance(v2.get(key), (int, float))
                else v2.get(key) - v1.get(key),
            }
            for key in keys
        ]
    }


def render_parity_report_markdown(*, v1: dict[str, Any], v2: dict[str, Any]) -> str:
    report = build_parity_report(v1=v1, v2=v2)
    linhas = ["# Ingestion V2 Parity Report", "", "| metric | v1 | v2 | delta |", "| --- | ---: | ---: | ---: |"]
    for item in report["comparison"]:
        linhas.append(f"| {item['metric']} | {item['v1']} | {item['v2']} | {item['delta']} |")
    return "\n".join(linhas) + "\n"
