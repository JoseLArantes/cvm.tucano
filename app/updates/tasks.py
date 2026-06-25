from typing import Any

from app.db.session import SessionLocal
from app.updates.service import cleanup_temp_files, run_deep_analysis, run_scanner
from app.worker.celery_app import celery_app


@celery_app.task(name="app.updates.tasks.run_daily_scanner_task")  # type: ignore[untyped-decorator]
def run_daily_scanner_task(scan_run_id: str | None = None) -> dict[str, Any]:
    import uuid
    db = SessionLocal()
    try:
        return run_scanner(db, scan_run_id=uuid.UUID(scan_run_id) if scan_run_id else None)
    finally:
        db.close()


@celery_app.task(name="app.updates.tasks.run_deep_analysis_task")  # type: ignore[untyped-decorator]
def run_deep_analysis_task(pending_update_id: str) -> dict[str, Any]:
    import uuid
    db = SessionLocal()
    try:
        pending = run_deep_analysis(db, uuid.UUID(pending_update_id))
        return {
            "status": pending.status,
            "pending_update_id": pending_update_id,
            "change_summary": pending.change_summary
        }
    finally:
        db.close()


@celery_app.task(name="app.updates.tasks.cleanup_temp_files_task")  # type: ignore[untyped-decorator]
def cleanup_temp_files_task() -> dict[str, Any]:
    cleaned = cleanup_temp_files()
    return {
        "status": "success",
        "cleaned_directories_count": cleaned
    }
