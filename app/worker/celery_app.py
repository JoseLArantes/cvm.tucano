from typing import Any

from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "cvm_worker",
    broker=settings.redis_url,
    backend=settings.redis_url,
)
celery_app.conf.timezone = "America/Sao_Paulo"


def construir_beat_schedule() -> dict[str, dict[str, Any]]:
    beat_schedule: dict[str, dict[str, Any]] = {
        "sincronizar-cadastro-diario": {
            "task": "app.worker.tasks.sincronizar_cadastro_companhias_task",
            "schedule": crontab(hour=1, minute=0),
        }
    }
    tarefas_anuais = (
        ("dfp", settings.anos_iniciais_dfp, "app.worker.tasks.sincronizar_dfp_task"),
        ("itr", settings.anos_iniciais_itr, "app.worker.tasks.sincronizar_itr_task"),
    )
    deslocamento_minutos = 0
    for tipo_fonte, anos_configurados, tarefa in tarefas_anuais:
        for ano in settings.parse_anos(anos_configurados):
            beat_schedule[f"sincronizar-{tipo_fonte}-{ano}-diario"] = {
                "task": tarefa,
                "schedule": crontab(hour=2 + (deslocamento_minutos // 60), minute=deslocamento_minutos % 60),
                "args": (ano,),
            }
            deslocamento_minutos += 5
    return beat_schedule


celery_app.conf.beat_schedule = construir_beat_schedule()
celery_app.autodiscover_tasks(["app.worker"])
