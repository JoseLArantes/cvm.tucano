from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ingestion import IngestionRow, QuarantineItem
from app.models.sincronizacao import RegistroQuarentena
from app.services.ingestion.staging import register_row_event
from app.services.ingestion.validation import ValidationResult

DEFAULT_QUARANTINE_STATUS = "pendente"
DEFAULT_QUARANTINE_SEVERITY = "error"


def _agora() -> datetime:
    return datetime.now(UTC)


def _normalizar_reason_code(reason_code: str | None) -> str:
    if not reason_code:
        return "desconhecido"
    return reason_code.split(":", 1)[0].strip()


def create_quarantine_item(
    db: Session,
    *,
    ingestion_row: IngestionRow,
    result: ValidationResult,
    execucao_sincronizacao_id: Any | None = None,
    legacy_reason: str | None = None,
    created_by: str = "quarantine",
) -> QuarantineItem:
    motivo_codigo = _normalizar_reason_code(result.reason_code)
    item = db.scalar(select(QuarantineItem).where(QuarantineItem.ingestion_row_id == ingestion_row.id))
    if item is None:
        item = QuarantineItem(
            ingestion_run_id=ingestion_row.ingestion_run_id,
            ingestion_row_id=ingestion_row.id,
            execucao_sincronizacao_id=execucao_sincronizacao_id,
            arquivo_origem=ingestion_row.arquivo_origem,
            ano_origem=ingestion_row.ano_origem,
            linha_origem=ingestion_row.linha_origem,
            row_kind=ingestion_row.row_kind,
            status=DEFAULT_QUARANTINE_STATUS,
            motivo_codigo=motivo_codigo,
            severidade=result.severity or DEFAULT_QUARANTINE_SEVERITY,
            reparavel=result.repairable,
            diagnostico=result.to_json_payload(),
            tentativas_reprocessamento=0,
        )
        db.add(item)
    else:
        item.execucao_sincronizacao_id = execucao_sincronizacao_id or item.execucao_sincronizacao_id
        item.status = DEFAULT_QUARANTINE_STATUS
        item.motivo_codigo = motivo_codigo
        item.severidade = result.severity or DEFAULT_QUARANTINE_SEVERITY
        item.reparavel = result.repairable
        item.diagnostico = result.to_json_payload()
        item.ultimo_erro = None

    legado = db.scalar(
        select(RegistroQuarentena).where(
            RegistroQuarentena.execucao_sincronizacao_id == execucao_sincronizacao_id,
            RegistroQuarentena.arquivo_origem == ingestion_row.arquivo_origem,
            RegistroQuarentena.ano_origem == ingestion_row.ano_origem,
            RegistroQuarentena.linha_origem == ingestion_row.linha_origem,
        )
    )
    if legado is None and execucao_sincronizacao_id is not None:
        db.add(
            RegistroQuarentena(
                execucao_sincronizacao_id=execucao_sincronizacao_id,
                arquivo_origem=ingestion_row.arquivo_origem,
                ano_origem=ingestion_row.ano_origem,
                linha_origem=ingestion_row.linha_origem,
                motivo=legacy_reason or motivo_codigo,
                dados_originais=ingestion_row.raw_data,
            )
        )

    register_row_event(
        db,
        ingestion_row=ingestion_row,
        event_type="quarantined",
        event_payload={
            "motivo_codigo": motivo_codigo,
            "severidade": item.severidade,
            "reparavel": item.reparavel,
            "quarantine_item_id": str(item.id),
        },
        created_by=created_by,
    )
    return item


def mark_quarantine_resolved(
    db: Session,
    *,
    item: QuarantineItem,
    status: str,
    resolved_by: str,
    message: str | None = None,
) -> QuarantineItem:
    item.status = status
    item.resolvido_em = _agora()
    item.resolvido_por = resolved_by
    item.ultimo_erro = message
    return item


def register_quarantine_replay_attempt(
    item: QuarantineItem,
    *,
    success: bool,
    error_message: str | None = None,
) -> QuarantineItem:
    item.tentativas_reprocessamento += 1
    item.ultima_tentativa_em = _agora()
    if success:
        item.ultimo_erro = None
    else:
        item.ultimo_erro = error_message
    return item
