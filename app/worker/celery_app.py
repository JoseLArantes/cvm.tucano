from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "cvm_worker",
    broker=settings.redis_url,
    backend=settings.redis_url,
)
celery_app.conf.timezone = "America/Sao_Paulo"
celery_app.conf.beat_schedule = {
    "sincronizar-cadastro-diario": {
        "task": "app.worker.tasks.sincronizar_cadastro_companhias_task",
        "schedule": 24 * 60 * 60,
    }
}
celery_app.autodiscover_tasks(["app.worker"])
