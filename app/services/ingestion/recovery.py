from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ingestion import IngestionFile, IngestionRow, IngestionRun
from app.models.sincronizacao import ExecucaoSincronizacao


@dataclass(frozen=True)
class IngestionRecoveryAssessment:
    """Fonte de recuperacao que o replay administrativo consegue executar hoje."""

    eligible: bool
    strategy: str | None
    reason_code: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class NoRecoverySourceError(ValueError):
    reason_code = "NO_RECOVERY_SOURCE"


def resolve_parent_ingestion_file(
    db: Session,
    *,
    parent_execucao: ExecucaoSincronizacao,
) -> IngestionFile | None:
    """Resolve o ZIP persistido que permite reprocessar um member isoladamente."""
    ingestion_file = db.scalar(
        select(IngestionFile)
        .join(IngestionRun, IngestionRun.id == IngestionFile.ingestion_run_id)
        .where(IngestionRun.execucao_sincronizacao_id == parent_execucao.id)
        .order_by(IngestionRun.started_at.desc())
        .limit(1)
    )
    if ingestion_file is not None:
        return ingestion_file

    parent_year_filter = (
        ExecucaoSincronizacao.ano.is_(None)
        if parent_execucao.ano is None
        else ExecucaoSincronizacao.ano == parent_execucao.ano
    )
    return db.scalar(
        select(IngestionFile)
        .join(IngestionRun, IngestionRun.id == IngestionFile.ingestion_run_id)
        .join(
            ExecucaoSincronizacao,
            IngestionRun.execucao_sincronizacao_id == ExecucaoSincronizacao.id,
        )
        .where(
            ExecucaoSincronizacao.arquivo == parent_execucao.arquivo,
            ExecucaoSincronizacao.tipo_fonte == parent_execucao.tipo_fonte,
            parent_year_filter,
        )
        .order_by(IngestionRun.started_at.desc())
        .limit(1)
    )


def assess_ingestion_run_recovery(
    db: Session,
    *,
    run: IngestionRun,
    execucao: ExecucaoSincronizacao | None = None,
    has_staged_rows: bool | None = None,
) -> IngestionRecoveryAssessment:
    """Avalia somente fontes que o comando de replay consegue reaplicar.

    Um snapshot de artifact, isoladamente, ainda nao tem uma estrategia de replay no
    comando administrativo. Ele nao deve tornar a run recuperavel de forma enganosa.
    """

    resolved_execucao = execucao
    if resolved_execucao is None and run.execucao_sincronizacao_id is not None:
        resolved_execucao = db.get(ExecucaoSincronizacao, run.execucao_sincronizacao_id)

    if resolved_execucao is not None and resolved_execucao.parent_execucao_id is not None:
        parent_execucao = db.get(ExecucaoSincronizacao, resolved_execucao.parent_execucao_id)
        if (
            parent_execucao is None
            or resolve_parent_ingestion_file(db, parent_execucao=parent_execucao) is None
        ):
            return IngestionRecoveryAssessment(
                eligible=False,
                strategy=None,
                reason_code="NO_RECOVERY_SOURCE",
            )
        return IngestionRecoveryAssessment(
            eligible=True,
            strategy="rerun_member_execution",
            reason_code="MEMBER_EXECUTION_AVAILABLE",
        )

    if has_staged_rows is None:
        staged_row_id = db.scalar(
            select(IngestionRow.id).where(IngestionRow.ingestion_run_id == run.id).limit(1)
        )
        has_staged = staged_row_id is not None
    else:
        has_staged = has_staged_rows

    if has_staged:
        return IngestionRecoveryAssessment(
            eligible=True,
            strategy="replay_staged_rows",
            reason_code="STAGED_ROWS_AVAILABLE",
        )

    if resolved_execucao is not None and resolved_execucao.parent_execucao_id is None:
        return IngestionRecoveryAssessment(
            eligible=True,
            strategy="rerun_parent_execution",
            reason_code="PARENT_EXECUTION_AVAILABLE",
        )

    return IngestionRecoveryAssessment(
        eligible=False,
        strategy=None,
        reason_code="NO_RECOVERY_SOURCE",
    )


def assess_ingestion_run_recovery_eligibility(
    db: Session,
    *,
    run: IngestionRun,
    state: str,
    error_retryable: bool,
    execucao: ExecucaoSincronizacao | None = None,
    parent_execucao: ExecucaoSincronizacao | None = None,
    has_staged_rows: bool | None = None,
) -> IngestionRecoveryAssessment:
    """Combina a fonte disponivel com o estado operacional atual da run."""

    if state in {"succeeded", "skipped"}:
        return IngestionRecoveryAssessment(
            eligible=False,
            strategy=None,
            reason_code="RUN_ALREADY_COMPLETED",
        )
    if state == "failed" and error_retryable is False:
        return IngestionRecoveryAssessment(
            eligible=False,
            strategy=None,
            reason_code="NON_RETRYABLE_FAILURE",
        )
    if state not in {"waiting", "stale", "failed"}:
        return IngestionRecoveryAssessment(
            eligible=False,
            strategy=None,
            reason_code="RUN_NOT_RECOVERABLE",
        )

    resolved_execucao = execucao
    if resolved_execucao is None and run.execucao_sincronizacao_id is not None:
        resolved_execucao = db.get(ExecucaoSincronizacao, run.execucao_sincronizacao_id)

    source = assess_ingestion_run_recovery(
        db,
        run=run,
        execucao=resolved_execucao,
        has_staged_rows=has_staged_rows,
    )
    if state == "waiting" and source.strategy in {"rerun_member_execution", "rerun_parent_execution"}:
        if source.strategy == "rerun_parent_execution":
            return source
        resolved_parent = parent_execucao
        if resolved_parent is None and resolved_execucao is not None and resolved_execucao.parent_execucao_id is not None:
            resolved_parent = db.get(ExecucaoSincronizacao, resolved_execucao.parent_execucao_id)
        if resolved_parent is not None and resolved_parent.status == "falha":
            return source
    if state == "stale":
        return source
    if state == "failed" and (error_retryable is True or source.eligible):
        return source
    if state == "failed":
        return IngestionRecoveryAssessment(
            eligible=False,
            strategy=None,
            reason_code="NON_RETRYABLE_FAILURE",
        )
    return IngestionRecoveryAssessment(
        eligible=False,
        strategy=None,
        reason_code="RUN_NOT_RECOVERABLE",
    )
