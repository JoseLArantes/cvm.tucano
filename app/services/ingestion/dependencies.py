from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.identidade import CompanhiaIdentificador
from app.models.sincronizacao import ExecucaoSincronizacao
from app.services.ingestion.dedup import STATUSS_REAPROVEITAVEIS_EXECUCAO
from app.services.ingestion.retry import DependencyNotReady


def ensure_identity_graph_ready(db: Session) -> None:
    identifiers = db.scalar(select(func.count()).select_from(CompanhiaIdentificador))
    if identifiers:
        return

    cadastro_ok = db.scalar(
        select(func.count())
        .select_from(ExecucaoSincronizacao)
        .where(
            ExecucaoSincronizacao.tipo_fonte == "cadastro",
            ExecucaoSincronizacao.status.in_(STATUSS_REAPROVEITAVEIS_EXECUCAO),
        )
    )
    if not cadastro_ok:
        raise DependencyNotReady("cadastro_nao_concluido")
    raise DependencyNotReady("identity_graph_nao_pronto")
