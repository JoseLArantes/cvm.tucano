from app.db.session import SessionLocal
from app.services.sincronizacao_cadastro import sincronizar_cadastro_companhias
from app.services.sincronizacao_financeiro import sincronizar_dfp, sincronizar_itr
from app.services.sincronizacao_fre import sincronizar_fre
from app.worker.celery_app import celery_app


@celery_app.task(bind=True, name="app.worker.tasks.sincronizar_cadastro_companhias_task")
def sincronizar_cadastro_companhias_task(self) -> dict[str, str]:
    db = SessionLocal()
    try:
        resultado = sincronizar_cadastro_companhias(db, task_id=str(self.request.id))
        return {"status": str(resultado["status"]), "execucao_id": str(resultado["execucao_id"])}
    finally:
        db.close()


@celery_app.task(bind=True, name="app.worker.tasks.sincronizar_dfp_task")
def sincronizar_dfp_task(self, ano: int) -> dict[str, str]:
    db = SessionLocal()
    try:
        resultado = sincronizar_dfp(db, ano, task_id=str(self.request.id))
        return {"status": str(resultado["status"]), "execucao_id": str(resultado["execucao_id"])}
    finally:
        db.close()


@celery_app.task(bind=True, name="app.worker.tasks.sincronizar_itr_task")
def sincronizar_itr_task(self, ano: int) -> dict[str, str]:
    db = SessionLocal()
    try:
        resultado = sincronizar_itr(db, ano, task_id=str(self.request.id))
        return {"status": str(resultado["status"]), "execucao_id": str(resultado["execucao_id"])}
    finally:
        db.close()


@celery_app.task(bind=True, name="app.worker.tasks.sincronizar_fre_task")
def sincronizar_fre_task(self, ano: int) -> dict[str, str]:
    db = SessionLocal()
    try:
        resultado = sincronizar_fre(db, ano, task_id=str(self.request.id))
        return {"status": str(resultado["status"]), "execucao_id": str(resultado["execucao_id"])}
    finally:
        db.close()
