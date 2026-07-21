from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ingestion import IngestionRow, IngestionRun
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


def assess_ingestion_run_recovery(db: Session, *, run: IngestionRun) -> IngestionRecoveryAssessment:
    """Avalia somente fontes que o comando de replay consegue reaplicar.

    Um snapshot de artifact, isoladamente, ainda nao tem uma estrategia de replay no
    comando administrativo. Ele nao deve tornar a run recuperavel de forma enganosa.
    """

    if run.execucao_sincronizacao_id is not None:
        execucao = db.get(ExecucaoSincronizacao, run.execucao_sincronizacao_id)
        if execucao is not None and execucao.parent_execucao_id is not None:
            return IngestionRecoveryAssessment(
                eligible=True,
                strategy="rerun_member_execution",
                reason_code="MEMBER_EXECUTION_AVAILABLE",
            )

    staged_row_id = db.scalar(
        select(IngestionRow.id).where(IngestionRow.ingestion_run_id == run.id).limit(1)
    )
    if staged_row_id is not None:
        return IngestionRecoveryAssessment(
            eligible=True,
            strategy="replay_staged_rows",
            reason_code="STAGED_ROWS_AVAILABLE",
        )

    return IngestionRecoveryAssessment(
        eligible=False,
        strategy=None,
        reason_code="NO_RECOVERY_SOURCE",
    )
