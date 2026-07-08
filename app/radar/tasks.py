from __future__ import annotations

from typing import Any

from app.radar.service import run_radar_collection
from app.worker.celery_app import celery_app


@celery_app.task(name="app.radar.tasks.run_radar_collection_task")  # type: ignore[untyped-decorator]
def run_radar_collection_task(channels: list[str] | None = None) -> dict[str, Any]:
    return run_radar_collection(channels=channels)
