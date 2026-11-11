from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.ingestion_queue import IngestionQueueItem
from app.models.sincronizacao import ExecucaoSincronizacao
from app.services.ingestion.queue import (
    adicionar_execucao_a_fila,
    cancelar_execucoes_na_fila,
    concluir_item,
    criar_lote,
    iniciar_item,
    liberar_para_retentativa,
    obter_publicacoes_pendentes,
    reservar_vagas,
)


def _execution(
    db: Session,
    *,
    source: str,
    year: int | None,
    status: str = "agendada",
    parent_id: uuid.UUID | None = None,
    kind: str = "arquivo_zip",
    filename: str | None = None,
) -> ExecucaoSincronizacao:
    execution = ExecucaoSincronizacao(
        parent_execucao_id=parent_id,
        tipo_execucao=kind,
        tipo_fonte=source,
        ano=year,
        id_tarefa=str(uuid.uuid4()),
        arquivo=filename or (f"{source}_cia_aberta_{year}.zip" if year else "cadastro.csv"),
        url="https://example.test/data",
        status=status,
    )
    db.add(execution)
    db.flush()
    return execution


def _queued_item(
    db: Session,
    *,
    source: str,
    year: int,
    kind: str = "zip_prepare",
    status: str = "agendada",
    task_name: str = "app.worker.tasks.sincronizar_dfp_task",
    task_args: list[object] | None = None,
    task_kwargs: dict[str, object] | None = None,
    sequence: int = 0,
    parent_id: uuid.UUID | None = None,
    execution_kind: str = "arquivo_zip",
    filename: str | None = None,
) -> tuple[ExecucaoSincronizacao, IngestionQueueItem]:
    execution = _execution(
        db,
        source=source,
        year=year,
        status=status,
        parent_id=parent_id,
        kind=execution_kind,
        filename=filename,
    )
    batch = criar_lote(db, source="test", metadata={"year": year})
    item = adicionar_execucao_a_fila(
        db,
        batch=batch,
        execucao=execution,
        task_name=task_name,
        args=task_args,
        kwargs=task_kwargs,
        kind=kind,
        sequence=sequence,
    )
    return execution, item


def test_scheduler_reserves_ready_csv_before_zip_and_only_one_zip(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "ingestion_execution_slots", 4)
    _, first_zip = _queued_item(db_session, source="dfp", year=2024)
    _, second_zip = _queued_item(db_session, source="dfp", year=2025)
    _, ready_csv = _queued_item(
        db_session,
        source="dfp",
        year=2024,
        kind="csv",
        task_name="app.worker.tasks.sincronizar_member_task",
        task_kwargs={"child_execucao_id": "member"},
        execution_kind="arquivo_membro",
        filename="dfp_cia_aberta_BPA_con_2024.csv",
    )

    reserved_ids = reservar_vagas(db_session)
    db_session.flush()
    reserved = list(
        db_session.scalars(
            select(IngestionQueueItem).where(IngestionQueueItem.id.in_(reserved_ids))
        ).all()
    )

    assert len(reserved) == 2
    assert ready_csv.status == "reserved"
    assert first_zip.status == "reserved"
    assert second_zip.status == "queued"
    assert sum(item.kind == "zip_prepare" for item in reserved) == 1


def test_zip_reservation_is_returned_when_csv_becomes_ready_before_start(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "ingestion_execution_slots", 1)
    _, zip_item = _queued_item(db_session, source="dfp", year=2025)
    reserved = reservar_vagas(db_session)
    token = zip_item.reservation_token
    assert zip_item.status == "reserved"
    assert token is not None

    _, csv_item = _queued_item(
        db_session,
        source="dfp",
        year=2024,
        kind="csv",
        task_name="app.worker.tasks.sincronizar_member_task",
        task_kwargs={"child_execucao_id": "member"},
        execution_kind="arquivo_membro",
        filename="dfp_cia_aberta_BPA_con_2024.csv",
    )
    db_session.flush()

    assert iniciar_item(db_session, item_id=zip_item.id, token=token) is False
    assert csv_item.status == "reserved"
    assert zip_item.status == "queued"
    assert all(item.id != zip_item.id for item in obter_publicacoes_pendentes(db_session))
    assert reserved == [zip_item.id]


def test_header_transition_queues_header_before_later_zip(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "ingestion_execution_slots", 1)
    parent, parent_item = _queued_item(
        db_session,
        source="dfp",
        year=2024,
        status="aguardando_ingestao",
    )
    parent_item.status = "transition_pending"
    header = _execution(
        db_session,
        source="dfp",
        year=2024,
        status="aguardando_ingestao",
        parent_id=parent.id,
        kind="arquivo_membro",
        filename="dfp_cia_aberta_2024.csv",
    )
    _execution(
        db_session,
        source="dfp",
        year=2024,
        status="aguardando_ingestao",
        parent_id=parent.id,
        kind="arquivo_membro",
        filename="dfp_cia_aberta_BPA_con_2024.csv",
    )
    _, later_zip = _queued_item(db_session, source="dfp", year=2025)

    reserved_ids = reservar_vagas(db_session)
    header_item = db_session.scalar(
        select(IngestionQueueItem).where(
            IngestionQueueItem.execucao_sincronizacao_id == header.id
        )
    )

    assert header_item is not None
    assert reserved_ids == [header_item.id]
    assert header_item.status == "reserved"
    assert later_zip.status == "queued"


def test_duplicate_reservation_token_can_start_only_once(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "ingestion_execution_slots", 1)
    _, item = _queued_item(db_session, source="itr", year=2025)
    reservar_vagas(db_session)
    token = item.reservation_token
    assert token is not None

    assert iniciar_item(db_session, item_id=item.id, token=token) is True
    assert iniciar_item(db_session, item_id=item.id, token=token) is False

    item.status = "transition_pending"
    execution = db_session.get(ExecucaoSincronizacao, item.execucao_sincronizacao_id)
    assert execution is not None
    execution.status = "sucesso"
    assert concluir_item(db_session, item_id=item.id, token=token) is False
    assert item.status == "completed"


def test_cancelled_reservation_cannot_start(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "ingestion_execution_slots", 1)
    execution, item = _queued_item(db_session, source="dfp", year=2025)
    reservar_vagas(db_session)
    token = item.reservation_token
    assert token is not None

    assert cancelar_execucoes_na_fila(db_session, [execution.id]) == 1
    assert iniciar_item(db_session, item_id=item.id, token=token) is False
    assert item.status == "cancelled"


def test_retry_releases_slot_and_fails_after_configured_attempts(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "ingestion_execution_slots", 1)
    monkeypatch.setattr(settings, "ingestion_max_retries", 1)
    execution, item = _queued_item(db_session, source="dfp", year=2025)

    assert reservar_vagas(db_session) == [item.id]
    token = item.reservation_token
    assert token is not None
    assert iniciar_item(db_session, item_id=item.id, token=token) is True
    assert item.attempt == 1

    liberar_para_retentativa(
        db_session,
        item_id=item.id,
        token=token,
        error="timeout na origem",
        retryable=True,
    )
    assert item.status == "queued"
    assert item.reason_code == "retentativa"
    assert execution.status == "agendada"
    assert reservar_vagas(db_session) == []

    item.not_before = datetime.now(UTC) - timedelta(seconds=1)
    assert reservar_vagas(db_session) == [item.id]
    retry_token = item.reservation_token
    assert retry_token is not None
    assert iniciar_item(db_session, item_id=item.id, token=retry_token) is True
    assert item.attempt == 2

    liberar_para_retentativa(
        db_session,
        item_id=item.id,
        token=retry_token,
        error="timeout persistente",
        retryable=True,
    )
    assert item.status == "failed"
    assert item.reason_code == "limite_retentativas"
    assert execution.status == "falha"
