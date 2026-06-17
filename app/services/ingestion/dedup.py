from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.sincronizacao import ExecucaoSincronizacao, StatusExecucao

STATUSS_REAPROVEITAVEIS_EXECUCAO = (
    StatusExecucao.sucesso.value,
    StatusExecucao.sem_alteracao.value,
    StatusExecucao.skipped.value,
)


def buscar_execucao_hash_existente(
    db: Session,
    *,
    tipo_fonte: str,
    ano: int | None,
    hash_arquivo: str,
    execucao_atual_id: UUID,
) -> ExecucaoSincronizacao | None:
    return db.scalar(
        select(ExecucaoSincronizacao).where(
            ExecucaoSincronizacao.tipo_fonte == tipo_fonte,
            ExecucaoSincronizacao.ano == ano,
            ExecucaoSincronizacao.hash_arquivo == hash_arquivo,
            ExecucaoSincronizacao.status.in_(STATUSS_REAPROVEITAVEIS_EXECUCAO),
            ExecucaoSincronizacao.id != execucao_atual_id,
        )
    )
