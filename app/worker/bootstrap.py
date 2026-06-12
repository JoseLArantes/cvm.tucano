import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.sincronizacao import ExecucaoSincronizacao, StatusExecucao
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
        if not _possui_execucao_valida(db, tipo_fonte="cadastro", ano=None):
            sincronizar_cadastro_companhias_task.delay()
            agendadas.append(("cadastro", None))

        tarefas_anuais = (
            ("dfp", settings.anos_iniciais_dfp, sincronizar_dfp_task.delay),
            ("itr", settings.anos_iniciais_itr, sincronizar_itr_task.delay),
            ("fre", settings.anos_iniciais_fre, sincronizar_fre_task.delay),
            ("fca", settings.anos_iniciais_fca, sincronizar_fca_task.delay),
            ("ipe", settings.anos_iniciais_ipe, sincronizar_ipe_task.delay),
            ("vlmo", settings.anos_iniciais_vlmo, sincronizar_vlmo_task.delay),
            ("cgvn", settings.anos_iniciais_cgvn, sincronizar_cgvn_task.delay),
        )
        for tipo_fonte, anos_configurados, delay in tarefas_anuais:
            for ano in settings.parse_anos(anos_configurados):
                if _possui_execucao_valida(db, tipo_fonte=tipo_fonte, ano=ano):
                    continue
                delay(ano)
                agendadas.append((tipo_fonte, ano))
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
