from datetime import timedelta
from typing import Any

from celery import Celery
from celery.schedules import crontab
from kombu import Queue

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "cvm_worker",
    broker=settings.redis_url,
    backend=settings.redis_url,
)
celery_app.conf.timezone = "America/Sao_Paulo"
celery_app.conf.worker_prefetch_multiplier = 1
celery_app.conf.task_acks_late = True
celery_app.conf.task_reject_on_worker_lost = True
celery_app.conf.worker_cancel_long_running_tasks_on_connection_loss = True
celery_app.conf.worker_max_tasks_per_child = settings.celery_worker_max_tasks_per_child
celery_app.conf.worker_max_memory_per_child = settings.celery_worker_max_memory_per_child_kb
celery_app.conf.task_default_queue = "celery"
celery_app.conf.task_queues = (
    Queue("celery"),
    Queue(settings.analise_materializacao_queue_name),
)
celery_app.conf.task_routes = {
    "app.worker.tasks.sincronizar_cadastro_companhias_task": {"queue": "celery"},
    "app.worker.tasks.sincronizar_member_task": {"queue": "celery"},
    "app.worker.tasks.disparar_dependentes_task": {"queue": "celery"},
    "app.worker.tasks.finalizar_sincronizacao_zip_task": {"queue": "celery"},
    "app.worker.tasks.sincronizar_dfp_task": {"queue": "celery"},
    "app.worker.tasks.sincronizar_itr_task": {"queue": "celery"},
    "app.worker.tasks.sincronizar_fre_task": {"queue": "celery"},
    "app.worker.tasks.sincronizar_fca_task": {"queue": "celery"},
    "app.worker.tasks.sincronizar_ipe_task": {"queue": "celery"},
    "app.worker.tasks.sincronizar_vlmo_task": {"queue": "celery"},
    "app.worker.tasks.sincronizar_cgvn_task": {"queue": "celery"},
    "app.worker.tasks.pre_processar_sincronizacao_task": {"queue": "celery"},
    "app.worker.tasks.ingerir_sincronizacao_task": {"queue": "celery"},
    "app.worker.tasks.reconciliar_ingestion_stale_task": {"queue": "celery"},
    "app.worker.tasks.materializar_analise_companhia_task": {"queue": settings.analise_materializacao_queue_name},
    "app.worker.tasks.materializar_analise_campanha_task": {"queue": settings.analise_materializacao_queue_name},
    "app.worker.tasks.materializar_analise_chunk_task": {"queue": settings.analise_materializacao_queue_name},
    "app.worker.tasks.despachar_materializacao_pendente_task": {"queue": settings.analise_materializacao_queue_name},
    "app.worker.tasks.reconciliar_materializacao_stale_task": {"queue": settings.analise_materializacao_queue_name},
    "app.worker.tasks.recuperar_materializacao_pendente_task": {"queue": settings.analise_materializacao_queue_name},
}


def construir_beat_schedule() -> dict[str, dict[str, Any]]:
    beat_schedule: dict[str, dict[str, Any]] = {
        "ingestion-stale-recovery": {
            "task": "app.worker.tasks.reconciliar_ingestion_stale_task",
            "schedule": timedelta(seconds=settings.ingestion_recovery_sweep_seconds),
        },
        "analise-materializacao-stale-recovery": {
            "task": "app.worker.tasks.reconciliar_materializacao_stale_task",
            "schedule": timedelta(seconds=settings.analise_materializacao_recovery_sweep_seconds),
        }
    }
    if settings.analise_materializacao_pending_recovery_enabled:
        beat_schedule["analise-materializacao-pending-recovery"] = {
            "task": "app.worker.tasks.recuperar_materializacao_pendente_task",
            "schedule": timedelta(seconds=settings.analise_materializacao_pending_recovery_sweep_seconds),
        }
    
    if settings.auto_trigger_updates:
        beat_schedule["sincronizar-cadastro-diario"] = {
            "task": "app.worker.tasks.sincronizar_cadastro_companhias_task",
            "schedule": crontab(hour=1, minute=0),
        }
        tarefas_anuais = (
            ("dfp", settings.anos_iniciais_dfp, "app.worker.tasks.sincronizar_dfp_task"),
            ("itr", settings.anos_iniciais_itr, "app.worker.tasks.sincronizar_itr_task"),
            ("fre", settings.anos_iniciais_fre, "app.worker.tasks.sincronizar_fre_task"),
            ("fca", settings.anos_iniciais_fca, "app.worker.tasks.sincronizar_fca_task"),
            ("ipe", settings.anos_iniciais_ipe, "app.worker.tasks.sincronizar_ipe_task"),
            ("vlmo", settings.anos_iniciais_vlmo, "app.worker.tasks.sincronizar_vlmo_task"),
            ("cgvn", settings.anos_iniciais_cgvn, "app.worker.tasks.sincronizar_cgvn_task"),
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
    else:
        beat_schedule["cvm-updates-scanner"] = {
            "task": "app.updates.tasks.run_daily_scanner_task",
            "schedule": crontab(hour=0, minute=30),
        }
        beat_schedule["cvm-updates-temp-cleanup"] = {
            "task": "app.updates.tasks.cleanup_temp_files_task",
            "schedule": crontab(hour=4, minute=0),
        }
    return beat_schedule


celery_app.conf.beat_schedule = construir_beat_schedule()
celery_app.autodiscover_tasks(["app.worker", "app.updates"])
