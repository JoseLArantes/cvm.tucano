from app.db.session import SessionLocal
from app.services.sincronizacao_cadastro import sincronizar_cadastro_companhias
from app.services.sincronizacao_financeiro import sincronizar_dfp, sincronizar_itr
from app.services.sincronizacao_fre import sincronizar_fre
from app.worker.celery_app import celery_app


@celery_app.task(name="app.worker.tasks.sincronizar_cadastro_companhias_task")
def sincronizar_cadastro_companhias_task() -> dict[str, str]:
    db = SessionLocal()
    try:
        resultado = sincronizar_cadastro_companhias(db)
        return {"status": str(resultado["status"]), "execucao_id": str(resultado["execucao_id"])}
    finally:
        db.close()


@celery_app.task(name="app.worker.tasks.sincronizar_dfp_task")
def sincronizar_dfp_task(ano: int) -> dict[str, str]:
    db = SessionLocal()
    try:
        resultado = sincronizar_dfp(db, ano)
        return {"status": str(resultado["status"]), "execucao_id": str(resultado["execucao_id"])}
    finally:
        db.close()


@celery_app.task(name="app.worker.tasks.sincronizar_itr_task")
def sincronizar_itr_task(ano: int) -> dict[str, str]:
    db = SessionLocal()
    try:
        resultado = sincronizar_itr(db, ano)
        return {"status": str(resultado["status"]), "execucao_id": str(resultado["execucao_id"])}
    finally:
        db.close()


@celery_app.task(name="app.worker.tasks.sincronizar_fre_task")
def sincronizar_fre_task(ano: int) -> dict[str, str]:
    db = SessionLocal()
    try:
        resultado = sincronizar_fre(db, ano)
        return {"status": str(resultado["status"]), "execucao_id": str(resultado["execucao_id"])}
    finally:
        db.close()
