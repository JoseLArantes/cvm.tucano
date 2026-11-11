import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.sincronizacao import ExecucaoSincronizacao, StatusExecucao
from app.services.ingestion.queue import adicionar_execucao_a_fila, criar_lote
from app.services.ingestion.scheduling import criar_execucao_sincronizacao_agendada, novo_task_id
from app.worker.tasks import (
    sincronizar_cadastro_companhias_task,
    sincronizar_cgvn_task,
    sincronizar_dfp_task,
    sincronizar_fca_task,
    sincronizar_fre_task,
    sincronizar_ipe_task,
    sincronizar_itr_task,
    sincronizar_vlmo_task,
)

logger = logging.getLogger(__name__)

_STATUS_EXISTENTE_VALIDO = (
    StatusExecucao.agendada.value,
    StatusExecucao.aguardando_ingestao.value,
    StatusExecucao.em_execucao.value,
    StatusExecucao.sucesso.value,
    StatusExecucao.sem_alteracao.value,
    StatusExecucao.skipped.value,
)


def _possui_execucao_valida(db: Session, *, tipo_fonte: str, ano: int | None) -> bool:
    query = select(ExecucaoSincronizacao.id).where(
        ExecucaoSincronizacao.tipo_fonte == tipo_fonte,
        ExecucaoSincronizacao.status.in_(_STATUS_EXISTENTE_VALIDO),
    )
    if ano is None:
        query = query.where(ExecucaoSincronizacao.ano.is_(None))
    else:
        query = query.where(ExecucaoSincronizacao.ano == ano)
    return db.scalar(query) is not None


def agendar_sincronizacoes_iniciais() -> list[tuple[str, int | None]]:
    settings = get_settings()
    db = SessionLocal()
    agendadas: list[tuple[str, int | None]] = []
    try:
        tarefas_anuais = (
            ("dfp", settings.anos_iniciais_dfp, sincronizar_dfp_task),
            ("itr", settings.anos_iniciais_itr, sincronizar_itr_task),
            ("fre", settings.anos_iniciais_fre, sincronizar_fre_task),
            ("fca", settings.anos_iniciais_fca, sincronizar_fca_task),
            ("ipe", settings.anos_iniciais_ipe, sincronizar_ipe_task),
            ("vlmo", settings.anos_iniciais_vlmo, sincronizar_vlmo_task),
            ("cgvn", settings.anos_iniciais_cgvn, sincronizar_cgvn_task),
        )
        pendentes: list[tuple[str, int | None, Any, list[Any]]] = []
        if not _possui_execucao_valida(db, tipo_fonte="cadastro", ano=None):
            pendentes.append(("cadastro", None, sincronizar_cadastro_companhias_task, []))

        for tipo_fonte, anos_configurados, task in tarefas_anuais:
            for ano in settings.parse_anos(anos_configurados):
                if _possui_execucao_valida(db, tipo_fonte=tipo_fonte, ano=ano):
                    continue
                pendentes.append((tipo_fonte, ano, task, [ano]))
        if not pendentes:
            return agendadas

        batch = criar_lote(db, source="bootstrap", metadata={"requested_scopes": len(pendentes)})
        for sequence, (tipo_fonte, ano_agendado, task, args) in enumerate(pendentes):
            execution = criar_execucao_sincronizacao_agendada(
                db,
                tipo_fonte=tipo_fonte,
                ano=ano_agendado,
                task_id=novo_task_id(),
            )
            adicionar_execucao_a_fila(
                db,
                batch=batch,
                execucao=execution,
                task_name=task.name,
                args=args,
                sequence=sequence,
            )
            agendadas.append((tipo_fonte, ano_agendado))
        db.commit()
        try:
            from app.worker.tasks import despachar_fila_ingestao_task

            despachar_fila_ingestao_task.delay()
        except Exception:
            logger.exception("Falha ao sinalizar a fila persistida durante o bootstrap")
        return agendadas
    finally:
        db.close()


def main() -> None:
    agendadas = agendar_sincronizacoes_iniciais()
    if not agendadas:
        logger.info("Nenhuma sincronizacao inicial pendente para bootstrap.")
        return
    logger.info("Sincronizacoes iniciais agendadas: %s", agendadas)


if __name__ == "__main__":
    main()
