import httpx

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.ingestion.cadastro import sincronizar_cadastro_companhias_v2
from app.services.ingestion.financeiro import sincronizar_dfp_v2, sincronizar_itr_v2
from app.services.ingestion.fre import sincronizar_fre_v2
from app.services.ingestion.retry import DependencyNotReady, RetryableHttpStatus, RetryableIngestionError
from app.services.sincronizacao_cadastro import sincronizar_cadastro_companhias
from app.services.sincronizacao_financeiro import sincronizar_dfp, sincronizar_itr
from app.services.sincronizacao_fre import sincronizar_fre
from app.worker.celery_app import celery_app

_settings = get_settings()
_RETRY_KWARGS = {
    "autoretry_for": (
        httpx.TimeoutException,
        httpx.TransportError,
        RetryableIngestionError,
        RetryableHttpStatus,
        DependencyNotReady,
    ),
    "retry_backoff": True,
    "retry_backoff_max": _settings.ingestion_v2_retry_backoff_max_seconds,
    "retry_jitter": True,
    "max_retries": _settings.ingestion_v2_max_retries,
}

@celery_app.task(bind=True, name="app.worker.tasks.sincronizar_cadastro_companhias_task", **_RETRY_KWARGS)
def sincronizar_cadastro_companhias_task(self) -> dict[str, str]:
    db = SessionLocal()
    try:
        if _settings.ingestion_v2_enabled:
            resultado = sincronizar_cadastro_companhias_v2(db, task_id=str(self.request.id))
        else:
            resultado = sincronizar_cadastro_companhias(db, task_id=str(self.request.id))
        return {"status": str(resultado["status"]), "execucao_id": str(resultado["execucao_id"])}
    finally:
        db.close()


@celery_app.task(bind=True, name="app.worker.tasks.sincronizar_dfp_task", **_RETRY_KWARGS)
def sincronizar_dfp_task(self, ano: int) -> dict[str, str]:
    db = SessionLocal()
    try:
        if _settings.ingestion_v2_enabled:
            resultado = sincronizar_dfp_v2(db, ano, task_id=str(self.request.id))
        else:
            resultado = sincronizar_dfp(db, ano, task_id=str(self.request.id))
        return {"status": str(resultado["status"]), "execucao_id": str(resultado["execucao_id"])}
    finally:
        db.close()


@celery_app.task(bind=True, name="app.worker.tasks.sincronizar_itr_task", **_RETRY_KWARGS)
def sincronizar_itr_task(self, ano: int) -> dict[str, str]:
    db = SessionLocal()
    try:
        if _settings.ingestion_v2_enabled:
            resultado = sincronizar_itr_v2(db, ano, task_id=str(self.request.id))
        else:
            resultado = sincronizar_itr(db, ano, task_id=str(self.request.id))
        return {"status": str(resultado["status"]), "execucao_id": str(resultado["execucao_id"])}
    finally:
        db.close()


@celery_app.task(bind=True, name="app.worker.tasks.sincronizar_fre_task", **_RETRY_KWARGS)
def sincronizar_fre_task(self, ano: int) -> dict[str, str]:
    db = SessionLocal()
    try:
        if _settings.ingestion_v2_enabled:
            resultado = sincronizar_fre_v2(db, ano, task_id=str(self.request.id))
        else:
            resultado = sincronizar_fre(db, ano, task_id=str(self.request.id))
        return {"status": str(resultado["status"]), "execucao_id": str(resultado["execucao_id"])}
    finally:
        db.close()
