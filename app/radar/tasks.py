from __future__ import annotations

from typing import Any

from app.core.cache import cache
from app.core.config import get_settings
from app.radar.service import CollectionMode, run_radar_collection
from app.worker.celery_app import celery_app


@celery_app.task(name="app.radar.tasks.run_radar_collection_task")  # type: ignore[untyped-decorator]
def run_radar_collection_task(
    channels: list[str] | None = None,
    mode: str = "full",
) -> dict[str, Any]:
    settings = get_settings()
    token = cache.acquire_lock("radar-cvm:collection", ttl_seconds=settings.radar_cvm_lock_ttl_seconds)
    if token is None:
        return {"status": "failed", "published": False, "reason": "collection_lock_unavailable"}
    if token == "":
        return {"status": "skipped", "published": False, "reason": "collection_already_running"}
    try:
        normalized_mode: CollectionMode = "incremental" if mode == "incremental" else "full"
        return run_radar_collection(channels=channels, mode=normalized_mode)
    finally:
        if token:
            cache.release_lock("radar-cvm:collection", token)
