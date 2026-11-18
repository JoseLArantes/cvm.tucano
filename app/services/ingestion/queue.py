from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.ingestion_queue import IngestionQueueBatch, IngestionQueueControl, IngestionQueueItem
from app.models.sincronizacao import ExecucaoSincronizacao
from app.services.ingestion.scheduling import novo_task_id

_CSV_TASK = "app.worker.tasks.sincronizar_member_task"
_ZIP_TASKS = {
    "dfp": "app.worker.tasks.sincronizar_dfp_task",
    "itr": "app.worker.tasks.sincronizar_itr_task",
    "fre": "app.worker.tasks.sincronizar_fre_task",
    "fca": "app.worker.tasks.sincronizar_fca_task",
    "ipe": "app.worker.tasks.sincronizar_ipe_task",
    "vlmo": "app.worker.tasks.sincronizar_vlmo_task",
    "cgvn": "app.worker.tasks.sincronizar_cgvn_task",
    "fii": "app.worker.tasks.sincronizar_fii_task",
}
_ACTIVE = ("reserved", "running")
_TRANSITIONS = ("transition_pending",)
_TERMINAL = ("completed", "failed", "cancelled")
_SUCCESS = ("sucesso", "sucesso_com_alerta", "sem_alteracao", "skipped")
_EXECUTION_TERMINAL = (*_SUCCESS, "falha", "cancelada", "quality_fail")
_FINALIZER_TASK = "app.worker.tasks.finalizar_sincronizacao_zip_task"


def criar_lote(
    db: Session,
    *,
    source: str = "admin",
    requested_by: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> IngestionQueueBatch:
    _control_lock(db)
    batch = IngestionQueueBatch(
        requested_by=requested_by,
        source=source,
        status="queued",
        metadata_json=metadata or {},
    )
    db.add(batch)
    db.flush()
    return batch


def adicionar_execucao_a_fila(
    db: Session,
    *,
    batch: IngestionQueueBatch,
    execucao: ExecucaoSincronizacao,
    task_name: str,
    args: list[Any] | None = None,
    kwargs: dict[str, Any] | None = None,
    kind: str | None = None,
    sequence: int = 0,
) -> IngestionQueueItem:
    # IDs Python-side defaults are assigned during flush, before the queue FK is built.
    db.flush()
    current = db.scalar(
        select(IngestionQueueItem).where(
            IngestionQueueItem.execucao_sincronizacao_id == execucao.id
        )
    )
    if current is not None:
        return current
    item_kind = kind or _kind_for_execution(execucao)
    item = IngestionQueueItem(
        batch_id=batch.id,
        execucao_sincronizacao_id=execucao.id,
        sequence=sequence,
        kind=item_kind,
        task_name=task_name,
        task_args=args or [],
        task_kwargs=kwargs or {},
        task_id=execucao.id_tarefa or novo_task_id(),
        status="queued",
        reason_code="aguardando_admissao",
    )
    execucao.id_tarefa = item.task_id
    db.add(item)
    db.flush()
    return item


def retomar_item_manual(
    db: Session,
    *,
    item: IngestionQueueItem,
    task_name: str,
    args: list[Any] | None = None,
    kwargs: dict[str, Any] | None = None,
) -> None:
    _control_lock(db)
    if item.status != "waiting_manual":
        raise ValueError("queue_item_not_waiting_for_operator")
    execution = db.get(ExecucaoSincronizacao, item.execucao_sincronizacao_id)
    if execution is None:
        raise ValueError("queue_execution_not_found")
    item.kind = "continuation"
    item.task_name = task_name
    item.task_args = args or []
    item.task_kwargs = kwargs or {}
    item.task_id = novo_task_id()
    item.status = "queued"
    item.reason_code = "confirmacao_recebida"
    item.reservation_token = None
    item.not_before = None
    item.finished_at = None
    item.queued_at = datetime.now(UTC)
    execution.id_tarefa = item.task_id


def enfileirar_replay(
    db: Session,
    *,
    execution: ExecucaoSincronizacao,
    task_name: str,
    args: list[Any] | None = None,
    kwargs: dict[str, Any] | None = None,
    kind: str | None = None,
) -> IngestionQueueBatch:
    batch = criar_lote(
        db,
        source="admin_replay",
        metadata={"execucao_id": str(execution.id)},
    )
    item = db_item_for_execution(db, execution.id)
    if item is None:
        adicionar_execucao_a_fila(
            db,
            batch=batch,
            execucao=execution,
            task_name=task_name,
            args=args,
            kwargs=kwargs,
            kind=kind,
        )
        return batch
    item.batch_id = batch.id
    item.sequence = 0
    item.kind = kind or _kind_for_execution(execution)
    item.task_name = task_name
    item.task_args = args or []
    item.task_kwargs = kwargs or {}
    item.task_id = execution.id_tarefa or novo_task_id()
    item.status = "queued"
    item.reason_code = "novo_pedido_de_reprocessamento"
    item.reservation_token = None
    item.not_before = None
    item.reserved_at = None
    item.published_at = None
    item.started_at = None
    item.finished_at = None
    item.queued_at = datetime.now(UTC)
    execution.id_tarefa = item.task_id
    return batch


def cancelar_execucoes_na_fila(db: Session, execution_ids: list[uuid.UUID]) -> int:
    if not execution_ids:
        return 0
    _control_lock(db)
    items = db.scalars(
        select(IngestionQueueItem).where(
            IngestionQueueItem.execucao_sincronizacao_id.in_(execution_ids),
            IngestionQueueItem.status.in_(("queued", "reserved", "waiting_manual")),
        )
    ).all()
    now = datetime.now(UTC)
    for item in items:
        item.status = "cancelled"
        item.reason_code = "cancelado_pelo_operador"
        item.reservation_token = None
        item.finished_at = now
    _update_batch_states(db)
    return len(items)


def _kind_for_execution(execucao: ExecucaoSincronizacao) -> str:
    if execucao.tipo_execucao == "arquivo_membro":
        return "csv"
    if execucao.tipo_fonte == "cadastro":
        return "cadastro"
    if execucao.tipo_execucao == "arquivo_zip":
        return "zip_prepare"
    return "simple"


def _control_lock(db: Session) -> IngestionQueueControl:
    control = db.scalar(
        select(IngestionQueueControl).where(IngestionQueueControl.id == 1).with_for_update()
    )
    if control is None:
        control = IngestionQueueControl(id=1, revision=0)
        db.add(control)
        db.flush()
    control.revision += 1
    return control


def _member_kwargs(db: Session, parent: ExecucaoSincronizacao, child: ExecucaoSincronizacao) -> dict[str, Any]:
    parent_item = db_item_for_execution(db, parent.id)
    force_reimport = bool((parent_item.task_kwargs if parent_item is not None else {}).get("force_reimport"))
    return {
        "tipo_fonte": parent.tipo_fonte,
        "ano": parent.ano or 0,
        "member_name": child.arquivo,
        "parent_execucao_id": str(parent.id),
        "child_execucao_id": str(child.id),
        "force_reimport": force_reimport,
    }


def _agendar_finalizador(
    parent: ExecucaoSincronizacao,
    parent_item: IngestionQueueItem,
) -> None:
    parent_item.kind = "continuation"
    parent_item.task_name = _FINALIZER_TASK
    parent_item.task_args = [str(parent.id)]
    parent_item.task_kwargs = {
        "pending_update_id": (parent_item.task_kwargs or {}).get("pending_update_id")
    }
    parent_item.task_id = novo_task_id()
    parent.id_tarefa = parent_item.task_id
    parent_item.status = "queued"
    parent_item.reason_code = "finalizacao_pendente"
    parent_item.reservation_token = None
    parent_item.reserved_at = None
    parent_item.published_at = None
    parent_item.started_at = None
    parent_item.finished_at = None
    parent_item.not_before = None


def db_item_for_execution(db: Session, execution_id: uuid.UUID) -> IngestionQueueItem | None:
    return db.scalar(
        select(IngestionQueueItem).where(
            IngestionQueueItem.execucao_sincronizacao_id == execution_id
        )
    )


def _ensure_child_items(db: Session, parent: ExecucaoSincronizacao, batch_id: uuid.UUID) -> int:
    if parent.status in ("falha", "cancelada"):
        return 0
    children = list(
        db.scalars(
            select(ExecucaoSincronizacao)
            .where(ExecucaoSincronizacao.parent_execucao_id == parent.id)
            .order_by(ExecucaoSincronizacao.arquivo.asc())
        ).all()
    )
    header_name = f"{parent.tipo_fonte}_cia_aberta_{parent.ano}.csv"
    header = next((child for child in children if child.arquivo == header_name), None)
    if header is not None and header.status not in _SUCCESS:
        eligible = [header] if header.status == "aguardando_ingestao" else []
    else:
        eligible = [
            child
            for child in children
            if child.status == "aguardando_ingestao"
            and (header is None or child.id != header.id)
        ]
    batch = db.get(IngestionQueueBatch, batch_id)
    if batch is None:
        return 0
    max_sequence = db.scalar(
        select(func.max(IngestionQueueItem.sequence)).where(IngestionQueueItem.batch_id == batch_id)
    )
    next_sequence = 0 if max_sequence is None else int(max_sequence) + 1
    count = 0
    for child in eligible:
        if db_item_for_execution(db, child.id) is not None:
            continue
        child.id_tarefa = child.id_tarefa or novo_task_id()
        adicionar_execucao_a_fila(
            db,
            batch=batch,
            execucao=child,
            task_name=_CSV_TASK,
            kwargs=_member_kwargs(db, parent, child),
            kind="csv",
            sequence=next_sequence,
        )
        next_sequence += 1
        child.status = "agendada"
        count += 1
    return count


def _apply_transitions(db: Session) -> int:
    db.flush()
    pending = list(
        db.scalars(
            select(IngestionQueueItem)
            .where(IngestionQueueItem.status == "transition_pending")
            .order_by(IngestionQueueItem.queued_at.asc())
        ).all()
    )
    created = 0
    for item in pending:
        execution = db.get(ExecucaoSincronizacao, item.execucao_sincronizacao_id)
        if execution is None:
            item.status = "failed"
            item.reason_code = "execucao_inexistente"
            item.finished_at = datetime.now(UTC)
            continue
        if item.kind in ("zip_prepare", "cadastro") and execution.parent_execucao_id is None:
            is_operator_stage = item.task_name.endswith("pre_processar_sincronizacao_task")
            if execution.status == "aguardando_ingestao" and item.kind == "zip_prepare" and not is_operator_stage:
                created += _ensure_child_items(db, execution, item.batch_id)
                children = list(
                    db.scalars(
                        select(ExecucaoSincronizacao).where(
                            ExecucaoSincronizacao.parent_execucao_id == execution.id
                        )
                    ).all()
                )
                header_name = f"{execution.tipo_fonte}_cia_aberta_{execution.ano}.csv"
                header = next((child for child in children if child.arquivo == header_name), None)
                header_failed = header is not None and header.status in ("falha", "quality_fail")
                all_finished = all(child.status in _EXECUTION_TERMINAL for child in children)
                if header_failed or all_finished:
                    _agendar_finalizador(execution, item)
                else:
                    item.status = "completed"
                    item.reason_code = "csvs_elegiveis_aplicados"
            elif execution.status == "aguardando_ingestao" and is_operator_stage:
                item.status = "waiting_manual"
                item.reason_code = "aguardando_confirmacao_operador"
            elif execution.status in _SUCCESS or execution.status in ("falha", "cancelada"):
                item.status = "completed" if execution.status in _SUCCESS else (
                    "cancelled" if execution.status == "cancelada" else "failed"
                )
                item.reason_code = f"execucao_{execution.status}"
            else:
                item.status = "waiting_manual"
                item.reason_code = "aguardando_confirmacao_operador"
        elif item.kind == "continuation" and execution.status == "aguardando_ingestao":
            created += _ensure_child_items(db, execution, item.batch_id)
            item.status = "completed"
            item.reason_code = "confirmacao_aplicada"
        else:
            item.status = "completed" if execution.status in _SUCCESS else (
                "cancelled" if execution.status == "cancelada" else "failed"
            )
            item.reason_code = f"execucao_{execution.status}"
            if execution.parent_execucao_id is not None:
                parent = db.get(ExecucaoSincronizacao, execution.parent_execucao_id)
                parent_item = db_item_for_execution(db, execution.parent_execucao_id)
                if parent is not None and parent_item is not None:
                    created += _ensure_child_items(db, parent, parent_item.batch_id)
                    siblings = list(
                        db.scalars(
                            select(ExecucaoSincronizacao).where(
                                ExecucaoSincronizacao.parent_execucao_id == parent.id
                            )
                        ).all()
                    )
                    header_name = f"{parent.tipo_fonte}_cia_aberta_{parent.ano}.csv"
                    header = next((child for child in siblings if child.arquivo == header_name), None)
                    header_failed = header is not None and header.status in ("falha", "quality_fail")
                    all_finished = all(child.status in _EXECUTION_TERMINAL for child in siblings)
                    if (
                        (header_failed or all_finished)
                        and parent_item.status == "completed"
                        and parent.status not in _EXECUTION_TERMINAL
                    ):
                        if header_failed:
                            from app.models.ingestion import IngestionRun
                            from app.services.ingestion.staging import update_run_state

                            for sibling in siblings:
                                if sibling.status == "aguardando_ingestao":
                                    sibling.status = "falha"
                                    sibling.mensagem_erro = "Dependencia de cabecalho CSV falhou."
                                    sibling.finalizada_em = datetime.now(UTC)
                                    runs = db.scalars(
                                        select(IngestionRun).where(
                                            IngestionRun.execucao_sincronizacao_id == sibling.id
                                        )
                                    ).all()
                                    for run in runs:
                                        update_run_state(
                                            run,
                                            status="falha",
                                            phase="complete",
                                            message=sibling.mensagem_erro,
                                            finished_at=sibling.finalizada_em,
                                        )
                        _agendar_finalizador(parent, parent_item)
                        item.status = "transition_pending"
                        item.reason_code = "aguardando_finalizacao_do_pai"
        item.finished_at = datetime.now(UTC)
        if item.status != "transition_pending":
            item.reservation_token = None
    return created


def _recover_persisted_results(db: Session) -> int:
    running = list(
        db.execute(
            select(IngestionQueueItem, ExecucaoSincronizacao)
            .join(ExecucaoSincronizacao, ExecucaoSincronizacao.id == IngestionQueueItem.execucao_sincronizacao_id)
            .where(IngestionQueueItem.status == "running")
        ).all()
    )
    recovered = 0
    for item, execution in running:
        awaiting_stage_result = execution.status == "aguardando_ingestao" and (
            item.kind == "zip_prepare"
            or item.task_name.endswith("pre_processar_sincronizacao_task")
            or item.task_name.endswith("ingerir_sincronizacao_task")
        )
        if execution.status in _EXECUTION_TERMINAL or awaiting_stage_result:
            item.status = "transition_pending"
            item.reason_code = "transicao_de_etapa"
            recovered += 1
    return recovered


def _eligible_items(db: Session, *, kind: str, now: datetime) -> list[IngestionQueueItem]:
    return list(
        db.scalars(
            select(IngestionQueueItem)
            .join(IngestionQueueBatch, IngestionQueueBatch.id == IngestionQueueItem.batch_id)
            .where(
                IngestionQueueItem.status == "queued",
                IngestionQueueItem.kind == kind,
                (IngestionQueueItem.not_before.is_(None)) | (IngestionQueueItem.not_before <= now),
            )
            .order_by(IngestionQueueBatch.requested_at.asc(), IngestionQueueItem.sequence.asc(), IngestionQueueItem.queued_at.asc())
        ).all()
    )


def _reserve(db: Session, item: IngestionQueueItem, now: datetime) -> None:
    item.status = "reserved"
    item.reason_code = "publicacao_pendente"
    item.reservation_token = str(uuid.uuid4())
    item.reserved_at = now
    item.published_at = None
    item.started_at = None
    item.not_before = None
    item.publish_error = None
    db.flush()


def reservar_vagas(db: Session) -> list[uuid.UUID]:
    """Reserva vagas sob uma linha global; o commit precede qualquer publicação Celery."""
    _control_lock(db)
    _recover_persisted_results(db)
    _apply_transitions(db)
    now = datetime.now(UTC)
    capacity = get_settings().ingestion_execution_slots
    active_count = int(
        db.scalar(
            select(func.count(IngestionQueueItem.id)).where(IngestionQueueItem.status.in_(_ACTIVE))
        )
        or 0
    )
    free = max(0, capacity - active_count)
    zip_active = int(
        db.scalar(
            select(func.count(IngestionQueueItem.id)).where(
                IngestionQueueItem.kind == "zip_prepare",
                IngestionQueueItem.status.in_((*_ACTIVE, *_TRANSITIONS)),
            )
        )
        or 0
    )
    selected: list[uuid.UUID] = []
    while free > 0:
        csvs = _eligible_items(db, kind="csv", now=now)
        candidate = csvs[0] if csvs else None
        if candidate is None:
            continuations = _eligible_items(db, kind="continuation", now=now)
            candidate = continuations[0] if continuations else None
        if candidate is None:
            transitions_pending = int(
                db.scalar(
                    select(func.count(IngestionQueueItem.id)).where(
                        IngestionQueueItem.status.in_(_TRANSITIONS)
                    )
                )
                or 0
            )
            roots = _eligible_items(db, kind="cadastro", now=now) + _eligible_items(
                db, kind="zip_prepare", now=now
            )
            roots.sort(key=lambda item: _queue_order(db, item))
            candidate = next(
                (
                    item
                    for item in roots
                    if item.kind != "zip_prepare" or (zip_active == 0 and transitions_pending == 0)
                ),
                None,
            )
            if candidate is not None and candidate.kind == "zip_prepare":
                zip_active += 1
        if candidate is None:
            break
        _reserve(db, candidate, now)
        selected.append(candidate.id)
        free -= 1
    _update_batch_states(db)
    return selected


def _queue_order(db: Session, item: IngestionQueueItem) -> tuple[datetime, int, datetime]:
    batch = db.get(IngestionQueueBatch, item.batch_id)
    requested_at = batch.requested_at if batch is not None else item.queued_at
    return (requested_at, item.sequence, item.queued_at)


def _update_batch_states(db: Session) -> None:
    db.flush()
    batches = db.scalars(select(IngestionQueueBatch)).all()
    now = datetime.now(UTC)
    for batch in batches:
        statuses = list(
            db.scalars(
                select(IngestionQueueItem.status).where(IngestionQueueItem.batch_id == batch.id)
            ).all()
        )
        if not statuses:
            batch.status = "queued"
        elif all(status in _TERMINAL for status in statuses):
            batch.status = "completed" if all(status == "completed" for status in statuses) else "finished_with_errors"
            batch.finished_at = batch.finished_at or now
        else:
            batch.status = "running" if any(status in ("reserved", "running", "transition_pending") for status in statuses) else "queued"


def obter_publicacoes_pendentes(db: Session) -> list[IngestionQueueItem]:
    return list(
        db.scalars(
            select(IngestionQueueItem)
            .where(IngestionQueueItem.status == "reserved", IngestionQueueItem.published_at.is_(None))
            .order_by(IngestionQueueItem.reserved_at.asc())
        ).all()
    )


def marcar_publicada(db: Session, *, item_id: uuid.UUID, token: str) -> None:
    item = db.get(IngestionQueueItem, item_id)
    if item is not None and item.status == "reserved" and item.reservation_token == token:
        item.published_at = datetime.now(UTC)
        item.publish_error = None
        item.publish_attempts += 1


def marcar_erro_publicacao(db: Session, *, item_id: uuid.UUID, token: str, error: str) -> None:
    item = db.get(IngestionQueueItem, item_id)
    if item is not None and item.status == "reserved" and item.reservation_token == token:
        item.publish_error = error[:4000]
        item.publish_attempts += 1


def iniciar_item(db: Session, *, item_id: uuid.UUID, token: str) -> bool:
    _control_lock(db)
    _recover_persisted_results(db)
    _apply_transitions(db)
    item = db.scalar(select(IngestionQueueItem).where(IngestionQueueItem.id == item_id).with_for_update())
    if item is None or item.status != "reserved" or item.reservation_token != token:
        return False
    execution = db.get(ExecucaoSincronizacao, item.execucao_sincronizacao_id)
    if execution is None or execution.status == "cancelada":
        item.status = "cancelled"
        item.reason_code = "execucao_cancelada_antes_do_inicio"
        item.finished_at = datetime.now(UTC)
        item.reservation_token = None
        reservar_vagas(db)
        return False
    if item.kind == "zip_prepare" and _eligible_items(db, kind="csv", now=datetime.now(UTC)):
        item.status = "queued"
        item.reason_code = "prioridade_csv"
        item.reservation_token = None
        item.reserved_at = None
        item.published_at = None
        reservar_vagas(db)
        return False
    item.status = "running"
    item.reason_code = "worker_iniciou"
    item.started_at = datetime.now(UTC)
    item.attempt += 1
    if (
        execution is not None
        and item.kind != "continuation"
        and execution.status in ("agendada", "aguardando_ingestao")
    ):
        execution.status = "em_execucao"
        execution.finalizada_em = None
    _update_batch_states(db)
    return True


def concluir_item(db: Session, *, item_id: uuid.UUID, token: str) -> bool:
    _control_lock(db)
    _recover_persisted_results(db)
    _apply_transitions(db)
    item = db.scalar(select(IngestionQueueItem).where(IngestionQueueItem.id == item_id).with_for_update())
    if item is None or item.status != "running" or item.reservation_token != token:
        return False
    item.status = "transition_pending"
    item.reason_code = "transicao_de_etapa"
    _apply_transitions(db)
    reservar_vagas(db)
    return True


def liberar_para_retentativa(
    db: Session,
    *,
    item_id: uuid.UUID,
    token: str,
    error: str,
    retryable: bool = True,
) -> None:
    _control_lock(db)
    item = db.scalar(select(IngestionQueueItem).where(IngestionQueueItem.id == item_id).with_for_update())
    if item is None or item.status != "running" or item.reservation_token != token:
        return
    execution = db.get(ExecucaoSincronizacao, item.execucao_sincronizacao_id)
    now = datetime.now(UTC)
    retry_limit_reached = item.attempt >= get_settings().ingestion_max_retries + 1
    if execution is not None and execution.status == "cancelada":
        item.status = "cancelled"
        item.reason_code = "cancelado_durante_execucao"
        item.finished_at = now
    elif retryable and not retry_limit_reached:
        item.status = "queued"
        item.reason_code = "retentativa"
        item.not_before = now + timedelta(seconds=get_settings().ingestion_queue_dispatch_poll_seconds)
        item.finished_at = None
        if execution is not None:
            execution.status = "agendada"
            execution.finalizada_em = None
        from app.models.ingestion import IngestionRun

        runs = db.scalars(
            select(IngestionRun).where(IngestionRun.execucao_sincronizacao_id == item.execucao_sincronizacao_id)
        ).all()
        for run in runs:
            if run.status != "cancelada":
                run.status = "agendada"
                run.finished_at = None
                run.message = error[:4000]
    else:
        item.status = "failed"
        item.reason_code = "limite_retentativas" if retryable else "falha_na_etapa"
        item.finished_at = now
        if execution is not None and execution.status not in _EXECUTION_TERMINAL:
            execution.status = "falha"
            execution.finalizada_em = now
            execution.mensagem_erro = error[:4000]
        from app.models.ingestion import IngestionRun

        runs = db.scalars(
            select(IngestionRun).where(IngestionRun.execucao_sincronizacao_id == item.execucao_sincronizacao_id)
        ).all()
        for run in runs:
            if run.status not in ("sucesso", "sucesso_com_alerta", "sem_alteracao", "skipped", "cancelada"):
                run.status = "falha"
                run.finished_at = now
                run.message = error[:4000]
    item.reservation_token = None
    item.reserved_at = None
    item.published_at = None
    if item.status != "queued":
        item.not_before = None
    item.publish_error = error[:4000]
    _update_batch_states(db)


def reconciliar_fila(db: Session) -> dict[str, int]:
    _control_lock(db)
    recovered = _recover_persisted_results(db)
    transitions = _apply_transitions(db)
    reserved = reservar_vagas(db)
    db.flush()
    return {"recovered_items": recovered, "applied_transitions": transitions, "new_reservations": len(reserved)}


def snapshot_fila(db: Session, *, page: int = 1, page_size: int = 25) -> dict[str, Any]:
    items = list(
        db.execute(
            select(IngestionQueueItem, IngestionQueueBatch, ExecucaoSincronizacao)
            .join(IngestionQueueBatch, IngestionQueueBatch.id == IngestionQueueItem.batch_id)
            .join(ExecucaoSincronizacao, ExecucaoSincronizacao.id == IngestionQueueItem.execucao_sincronizacao_id)
            .where(IngestionQueueItem.status.not_in(_TERMINAL))
            .order_by(IngestionQueueBatch.requested_at.asc(), IngestionQueueItem.sequence.asc())
        ).all()
    )
    active_batch_ids = list(dict.fromkeys(batch.id for _item, batch, _execution in items))
    if active_batch_ids:
        items = list(
            db.execute(
                select(IngestionQueueItem, IngestionQueueBatch, ExecucaoSincronizacao)
                .join(IngestionQueueBatch, IngestionQueueBatch.id == IngestionQueueItem.batch_id)
                .join(ExecucaoSincronizacao, ExecucaoSincronizacao.id == IngestionQueueItem.execucao_sincronizacao_id)
                .where(IngestionQueueItem.batch_id.in_(active_batch_ids))
                .order_by(IngestionQueueBatch.requested_at.asc(), IngestionQueueItem.sequence.asc())
            ).all()
        )
    grouped: dict[str, dict[str, Any]] = {}
    for _position, (item, batch, execution) in enumerate(items, start=1):
        key = str(batch.id)
        group = grouped.setdefault(
            key,
            {
                "lote_id": key,
                "posicao": len(grouped) + 1,
                "fontes": [],
                "itens": [],
                "status": batch.status,
                "solicitado_em": batch.requested_at,
                "motivo_espera": None,
                "progresso": {"total": 0, "concluidos": 0, "em_execucao": 0, "aguardando": 0},
            },
        )
        source_scope = {"tipo_fonte": execution.tipo_fonte, "ano": execution.ano}
        if source_scope not in group["fontes"]:
            group["fontes"].append(source_scope)
        group["itens"].append(
            {
                "item_id": str(item.id),
                "execucao_id": str(execution.id),
                "tipo_fonte": execution.tipo_fonte,
                "ano": execution.ano,
                "arquivo": execution.arquivo,
                "etapa": item.kind,
                "status": item.status,
                "motivo_espera": item.reason_code,
                "reservado_em": item.reserved_at,
                "iniciado_em": item.started_at,
                "tentativa": item.attempt,
            }
        )
        progress = group["progresso"]
        progress["total"] += 1
        if item.status == "completed":
            progress["concluidos"] += 1
        elif item.status in ("reserved", "running", "transition_pending"):
            progress["em_execucao"] += 1
        else:
            progress["aguardando"] += 1
        if group["motivo_espera"] is None and item.status in ("queued", "reserved", "waiting_manual", "transition_pending"):
            group["motivo_espera"] = item.reason_code
    result = list(grouped.values())
    start = (page - 1) * page_size
    return {"total": len(result), "dados": result[start : start + page_size]}


def estatisticas_fila(db: Session) -> dict[str, Any]:
    now = datetime.now(UTC)
    counts = dict(
        db.execute(
            select(IngestionQueueItem.status, func.count(IngestionQueueItem.id)).group_by(IngestionQueueItem.status)
        ).all()
    )
    oldest = db.scalar(
        select(func.min(IngestionQueueBatch.requested_at))
        .join(IngestionQueueItem, IngestionQueueItem.batch_id == IngestionQueueBatch.id)
        .where(IngestionQueueItem.status.not_in(_TERMINAL))
    )
    if oldest is not None and oldest.tzinfo is None:
        oldest = oldest.replace(tzinfo=UTC)
    reserved = int(counts.get("reserved", 0))
    running = int(counts.get("running", 0))
    return {
        "profundidade": int(counts.get("queued", 0)),
        "lotes_ativos": int(db.scalar(select(func.count(func.distinct(IngestionQueueItem.batch_id))).where(IngestionQueueItem.status.not_in(_TERMINAL))) or 0),
        "vagas_reservadas": reserved,
        "vagas_em_execucao": running,
        "capacidade_configurada": get_settings().ingestion_execution_slots,
        "preparacoes_zip_ativas": int(db.scalar(select(func.count(IngestionQueueItem.id)).where(IngestionQueueItem.kind == "zip_prepare", IngestionQueueItem.status.in_((*_ACTIVE, *_TRANSITIONS)))) or 0),
        "pedido_mais_antigo_em": oldest,
        "idade_pedido_mais_antigo_segundos": max(0, int((now - oldest).total_seconds())) if oldest else None,
        "itens_por_status": {str(key): int(value) for key, value in counts.items()},
    }
