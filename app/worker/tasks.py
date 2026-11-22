import logging
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, Literal, cast

import httpx
import sqlalchemy.exc
from botocore.exceptions import ConnectionClosedError, ConnectTimeoutError, EndpointConnectionError, ReadTimeoutError
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.ingestion.cadastro import sincronizar_cadastro_companhias
from app.services.ingestion.retry import DependencyNotReady, RetryableHttpStatus, RetryableIngestionError
from app.worker.celery_app import celery_app

_settings = get_settings()
_logger = logging.getLogger(__name__)
_AUTORETRY_FOR: tuple[type[Exception], ...] = (
    httpx.TimeoutException,
    httpx.TransportError,
    RetryableIngestionError,
    RetryableHttpStatus,
    DependencyNotReady,
    sqlalchemy.exc.OperationalError,
    sqlalchemy.exc.InterfaceError,
    ConnectTimeoutError,
    ConnectionClosedError,
    EndpointConnectionError,
    ReadTimeoutError,
)

_RETRY_KWARGS = {
    "autoretry_for": _AUTORETRY_FOR,
    "retry_backoff": True,
    "retry_backoff_max": _settings.ingestion_retry_backoff_max_seconds,
    "retry_jitter": True,
    "max_retries": _settings.ingestion_max_retries,
}

_STATUS_FINAL_EXECUCAO = {"sucesso", "sem_alteracao", "skipped", "falha", "cancelada"}


def _resultado_cancelado(execucao_id: Any, message: str) -> dict[str, Any]:
    return {"execucao_id": str(execucao_id), "status": "cancelada", "message": message}


def _capturar_na_fila(
    task_self: Any,
    *,
    task_name: str,
    task_args: list[Any],
    task_kwargs: dict[str, Any],
    execution_id: str | None = None,
    kind: str | None = None,
    task_id_override: str | None = None,
) -> dict[str, Any]:
    """Converte chamadas legadas/automáticas em pedidos persistidos sem acessar a CVM."""
    from app.models.ingestion_queue import IngestionQueueItem
    from app.models.sincronizacao import ExecucaoSincronizacao
    from app.services.ingestion.queue import _control_lock, adicionar_execucao_a_fila, criar_lote

    db = SessionLocal()
    try:
        _control_lock(db)
        task_id = task_id_override or str(task_self.request.id or uuid.uuid4())
        execution = db.get(ExecucaoSincronizacao, uuid.UUID(execution_id)) if execution_id else None
        if execution is None:
            execution = db.scalar(
                select(ExecucaoSincronizacao).where(ExecucaoSincronizacao.id_tarefa == task_id).limit(1)
            )
        if execution is None:
            task_year = task_args[0] if task_args and isinstance(task_args[0], int) else task_kwargs.get("ano")
            task_source = str(task_kwargs.get("tipo_fonte") or task_name.rsplit("_", 2)[-2]).lower()
            task_source = task_source.removesuffix("_task")
            if task_name.endswith("sincronizar_cadastro_companhias_task"):
                task_source, task_year = "cadastro", None
            from app.services.ingestion.scheduling import sync_execution_metadata

            archive, url, execution_type = sync_execution_metadata(tipo_fonte=task_source, ano=task_year)
            execution = ExecucaoSincronizacao(
                tipo_execucao=execution_type,
                tipo_fonte=task_source,
                ano=task_year,
                id_tarefa=task_id,
                arquivo=archive,
                url=url,
                status="agendada",
            )
            db.add(execution)
            db.flush()
        existing = db.scalar(
            select(IngestionQueueItem).where(
                IngestionQueueItem.execucao_sincronizacao_id == execution.id
            )
        )
        if existing is not None and existing.status == "waiting_manual":
            existing.kind = "continuation"
            existing.task_name = task_name
            existing.task_args = task_args
            existing.task_kwargs = task_kwargs
            existing.task_id = task_id
            existing.status = "queued"
            existing.reason_code = "confirmacao_recebida"
            existing.reservation_token = None
            existing.not_before = None
            existing.finished_at = None
            execution.id_tarefa = task_id
        elif existing is not None and existing.status in ("completed", "failed", "cancelled"):
            batch = criar_lote(db, source="celery_replay")
            existing.batch_id = batch.id
            existing.sequence = 0
            existing.kind = kind or (
                "csv" if execution.tipo_execucao == "arquivo_membro"
                else "cadastro" if execution.tipo_fonte == "cadastro"
                else "zip_prepare" if execution.tipo_execucao == "arquivo_zip"
                else "simple"
            )
            existing.task_name = task_name
            existing.task_args = task_args
            existing.task_kwargs = task_kwargs
            existing.task_id = task_id
            existing.status = "queued"
            existing.reason_code = "novo_pedido_de_reprocessamento"
            existing.reservation_token = None
            existing.not_before = None
            existing.reserved_at = None
            existing.published_at = None
            existing.started_at = None
            existing.finished_at = None
            execution.id_tarefa = task_id
            execution.status = "agendada"
            execution.finalizada_em = None
        elif existing is None:
            batch = criar_lote(db, source="celery_automatic")
            adicionar_execucao_a_fila(
                db,
                batch=batch,
                execucao=execution,
                task_name=task_name,
                args=task_args,
                kwargs=task_kwargs,
                kind=kind,
            )
        else:
            return {"status": "already_queued", "execucao_id": str(execution.id)}
        db.commit()
        despachar_fila_ingestao_task.delay()
        return {"status": "queued", "execucao_id": str(execution.id)}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@celery_app.task(
    bind=True,
    name="app.worker.tasks.agendar_ingestao_automatica_task",
    **_RETRY_KWARGS,
)  # type: ignore[untyped-decorator]
def agendar_ingestao_automatica_task(
    self: Any,
    task_name: str,
    task_args: list[Any] | tuple[Any, ...] | None = None,
    task_kwargs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    allowed_tasks = {
        "app.worker.tasks.sincronizar_cadastro_companhias_task",
        "app.worker.tasks.sincronizar_dfp_task",
        "app.worker.tasks.sincronizar_itr_task",
        "app.worker.tasks.sincronizar_fre_task",
        "app.worker.tasks.sincronizar_fca_task",
        "app.worker.tasks.sincronizar_ipe_task",
        "app.worker.tasks.sincronizar_vlmo_task",
        "app.worker.tasks.sincronizar_cgvn_task",
        "app.worker.tasks.sincronizar_fii_task",
    }
    if task_name not in allowed_tasks:
        raise ValueError(f"Task de ingestao automatica nao permitida: {task_name}")
    from app.services.ingestion.scheduling import novo_task_id

    return _capturar_na_fila(
        self,
        task_name=task_name,
        task_args=list(task_args or []),
        task_kwargs=task_kwargs or {},
        task_id_override=novo_task_id(),
    )


def _executar_com_reserva(
    task_self: Any,
    *,
    queue_item_id: str | None,
    reservation_token: str | None,
    task_name: str,
    task_args: list[Any],
    task_kwargs: dict[str, Any],
    operation: Any,
    execution_id: str | None = None,
    kind: str | None = None,
) -> dict[str, Any]:
    if queue_item_id is None or reservation_token is None:
        return _capturar_na_fila(
            task_self,
            task_name=task_name,
            task_args=task_args,
            task_kwargs=task_kwargs,
            execution_id=execution_id,
            kind=kind,
        )
    from app.services.ingestion.queue import concluir_item, iniciar_item, liberar_para_retentativa

    item_id = uuid.UUID(queue_item_id)
    db = SessionLocal()
    try:
        started = iniciar_item(db, item_id=item_id, token=reservation_token)
        db.commit()
    finally:
        db.close()
    if not started:
        despachar_fila_ingestao_task.delay()
        return {"status": "stale_reservation", "queue_item_id": queue_item_id}
    try:
        result = operation()
    except Exception as exc:
        db = SessionLocal()
        try:
            liberar_para_retentativa(
                db,
                item_id=item_id,
                token=reservation_token,
                error=str(exc),
                retryable=isinstance(exc, _AUTORETRY_FOR),
            )
            db.commit()
        finally:
            db.close()
        despachar_fila_ingestao_task.delay()
        raise
    db = SessionLocal()
    try:
        concluir_item(db, item_id=item_id, token=reservation_token)
        db.commit()
    finally:
        db.close()
    despachar_fila_ingestao_task.delay()
    return cast(dict[str, Any], result)


def _iniciar_reserva(queue_item_id: str, token: str) -> bool:
    from app.services.ingestion.queue import iniciar_item

    db = SessionLocal()
    try:
        result = iniciar_item(db, item_id=uuid.UUID(queue_item_id), token=token)
        db.commit()
        return result
    finally:
        db.close()


def _concluir_reserva(queue_item_id: str, token: str) -> None:
    from app.services.ingestion.queue import concluir_item

    db = SessionLocal()
    try:
        concluir_item(db, item_id=uuid.UUID(queue_item_id), token=token)
        db.commit()
    finally:
        db.close()
    despachar_fila_ingestao_task.delay()


def _liberar_reserva(queue_item_id: str, token: str, error: str, *, retryable: bool = True) -> None:
    from app.services.ingestion.queue import liberar_para_retentativa

    db = SessionLocal()
    try:
        liberar_para_retentativa(
            db,
            item_id=uuid.UUID(queue_item_id),
            token=token,
            error=error,
            retryable=retryable,
        )
        db.commit()
    finally:
        db.close()
    despachar_fila_ingestao_task.delay()


@celery_app.task(bind=True, name="app.worker.tasks.despachar_fila_ingestao_task", **_RETRY_KWARGS)  # type: ignore[untyped-decorator]
def despachar_fila_ingestao_task(self: Any) -> dict[str, Any]:
    from app.services.ingestion.queue import (
        marcar_erro_publicacao,
        marcar_publicada,
        obter_publicacoes_pendentes,
        reconciliar_fila,
    )

    db = SessionLocal()
    try:
        result = reconciliar_fila(db)
        db.commit()
    finally:
        db.close()

    db = SessionLocal()
    try:
        pending = [
            (item.id, item.reservation_token, item.task_name, list(item.task_args), dict(item.task_kwargs), item.task_id)
            for item in obter_publicacoes_pendentes(db)
            if item.reservation_token is not None
        ]
    finally:
        db.close()
    published = 0
    for item_id, token, task_name, args, kwargs, task_id in pending:
        payload = {**kwargs, "_queue_item_id": str(item_id), "_queue_reservation_token": token}
        try:
            celery_app.send_task(
                task_name,
                args=args,
                kwargs=payload,
                task_id=task_id,
                queue=_settings.ingestion_queue_name,
            )
        except Exception as exc:
            db = SessionLocal()
            try:
                marcar_erro_publicacao(db, item_id=item_id, token=str(token), error=str(exc))
                db.commit()
            finally:
                db.close()
        else:
            db = SessionLocal()
            try:
                marcar_publicada(db, item_id=item_id, token=str(token))
                db.commit()
            finally:
                db.close()
            published += 1
    return {"status": "completed", **result, "published": published}


def _enfileirar_fontes_anuais_agendadas(
    db: Any,
    *,
    ano: int,
    force_reimport: bool,
) -> list[str]:
    from app.models.ingestion_queue import IngestionQueueItem
    from app.models.sincronizacao import ExecucaoSincronizacao
    from app.services.ingestion.queue import adicionar_execucao_a_fila, criar_lote

    task_map = {
        "dfp": sincronizar_dfp_task,
        "itr": sincronizar_itr_task,
        "fre": sincronizar_fre_task,
        "fca": sincronizar_fca_task,
        "ipe": sincronizar_ipe_task,
        "vlmo": sincronizar_vlmo_task,
        "cgvn": sincronizar_cgvn_task,
        "fii": sincronizar_fii_task,
    }
    rows = db.scalars(
        select(ExecucaoSincronizacao)
        .where(
            ExecucaoSincronizacao.ano == ano,
            ExecucaoSincronizacao.tipo_execucao == "arquivo_zip",
            ExecucaoSincronizacao.tipo_fonte.in_(task_map.keys()),
            ExecucaoSincronizacao.status == "agendada",
            ExecucaoSincronizacao.parent_execucao_id.is_(None),
            ExecucaoSincronizacao.id_tarefa.is_not(None),
        )
        .order_by(ExecucaoSincronizacao.tipo_fonte.asc())
    ).all()
    pendentes = [
        execucao
        for execucao in rows
        if execucao.id_tarefa is not None
        and db.scalar(
            select(IngestionQueueItem.id).where(
                IngestionQueueItem.execucao_sincronizacao_id == execucao.id
            )
        ) is None
    ]
    if not pendentes:
        return []
    batch = criar_lote(
        db,
        source="annual_after_cadastro",
        metadata={"ano": ano, "force_reimport": force_reimport},
    )
    queued: list[str] = []
    for sequence, execucao in enumerate(pendentes):
        task = task_map.get(execucao.tipo_fonte)
        if execucao.id_tarefa is None or task is None:
            continue
        adicionar_execucao_a_fila(
            db,
            batch=batch,
            execucao=execucao,
            task_name=task.name,
            args=[ano],
            kwargs={"force_reimport": force_reimport},
            sequence=sequence,
        )
        queued.append(execucao.id_tarefa)
    db.commit()
    return queued


@celery_app.task(bind=True, name="app.worker.tasks.reconciliar_ingestion_stale_task", **_RETRY_KWARGS)  # type: ignore[untyped-decorator]
def reconciliar_ingestion_stale_task(self: Any) -> dict[str, Any]:
    from app.services.ingestion.operational import reconcile_stale_ingestion_phase_executions
    from app.services.ingestion.replay import auto_repair_and_replay_quarantine

    db = SessionLocal()
    try:
        resultado = reconcile_stale_ingestion_phase_executions(db)
        quarantine_repair = auto_repair_and_replay_quarantine(db, max_items=100)
        db.commit()
        return {
            "status": "completed",
            **resultado,
            "quarantine_repair": quarantine_repair,
        }
    finally:
        db.close()


def _obter_gate_materializacao_snapshot() -> tuple[str, str, int]:
    from app.services.analise import obter_estado_gate_materializacao

    db = SessionLocal()
    try:
        gate = obter_estado_gate_materializacao(db)
        return gate.status, gate.reason_code, gate.blocking_ingestions
    finally:
        db.close()


def _enfileiramento_materializacao_bloqueado() -> tuple[bool, str, int]:
    status, reason_code, blocking_ingestions = _obter_gate_materializacao_snapshot()
    return status == "red", reason_code, blocking_ingestions


def _reagendar_campanha_materializacao(campanha_id: str, *, countdown: int | None = None) -> bool:
    blocked, _reason_code, _blocking_ingestions = _enfileiramento_materializacao_bloqueado()
    if blocked:
        return False
    materializar_analise_campanha_task.apply_async(
        args=(campanha_id,),
        countdown=_settings.analise_materializacao_gate_poll_seconds if countdown is None else countdown,
        queue=_settings.analise_materializacao_queue_name,
    )
    return True


def _disparar_dispatcher_materializacao(*, countdown: int | None = None) -> bool:
    blocked, _reason_code, _blocking_ingestions = _enfileiramento_materializacao_bloqueado()
    if blocked:
        return False
    despachar_materializacao_pendente_task.apply_async(
        countdown=0 if countdown is None else countdown,
        queue=_settings.analise_materializacao_queue_name,
    )
    return True


def _enfileirar_campanha_materializacao(campanha_id: str, *, countdown: int | None = None) -> bool:
    blocked, _reason_code, _blocking_ingestions = _enfileiramento_materializacao_bloqueado()
    if blocked:
        return False
    materializar_analise_campanha_task.apply_async(
        args=(campanha_id,),
        countdown=0 if countdown is None else countdown,
        queue=_settings.analise_materializacao_queue_name,
    )
    return True


@celery_app.task(bind=True, name="app.worker.tasks.materializar_analise_companhia_task", **_RETRY_KWARGS)  # type: ignore[untyped-decorator]
def materializar_analise_companhia_task(
    self: Any,
    codigo_cvm: int,
    escopo: str = "consolidated",
    source: str = "post_ingestion",
    invalidated_from: str | None = None,
    incluir_canceladas: bool = False,
    campanha_id: str | None = None,
    campanha_item_id: str | None = None,
    chunk_execucao_id: str | None = None,
    position_in_chunk: int | None = None,
) -> dict[str, Any]:
    from sqlalchemy import select

    from app.models.companhia import Companhia
    from app.services.analise import materializar_analise_companhia

    db = SessionLocal()
    try:
        gate = _obter_gate_materializacao_snapshot()
        if gate[0] == "red":
            return {
                "status": "waiting_for_gate",
                "codigo_cvm": codigo_cvm,
                "escopo": escopo,
                "reason_code": gate[1],
                "blocking_ingestions": gate[2],
            }
        companhia = db.scalar(select(Companhia).where(Companhia.codigo_cvm == codigo_cvm))
        if companhia is None:
            return {"status": "missing_company", "codigo_cvm": codigo_cvm, "escopo": escopo}
        execucao = materializar_analise_companhia(
            db,
            companhia,
            scope=cast(Literal["consolidated", "individual"], escopo),
            source=source,
            invalidated_from=datetime.fromisoformat(invalidated_from).date() if invalidated_from else None,
            campanha_id=uuid.UUID(campanha_id) if campanha_id else None,
            campanha_item_id=uuid.UUID(campanha_item_id) if campanha_item_id else None,
            chunk_execucao_id=uuid.UUID(chunk_execucao_id) if chunk_execucao_id else None,
            queue_name=_settings.analise_materializacao_queue_name,
            task_id=str(self.request.id),
            position_in_chunk=position_in_chunk,
        )
        return {
            "status": execucao.status,
            "codigo_cvm": codigo_cvm,
            "escopo": escopo,
            "materializacao_execucao_id": str(execucao.id),
            "coverage_complete": execucao.coverage_complete,
            "skipped_reason": (execucao.summary or {}).get("skipped_reason"),
            "legacy_incluir_canceladas_ignored": incluir_canceladas,
        }
    finally:
        db.close()


@celery_app.task(bind=True, name="app.worker.tasks.materializar_analise_campanha_task", **_RETRY_KWARGS)  # type: ignore[untyped-decorator]
def materializar_analise_campanha_task(self: Any, campanha_id: str) -> dict[str, Any]:
    from sqlalchemy import func, select

    from app.models.analise import AnaliseMaterializacaoCampanha
    from app.services.analise import (
        _recalcular_materializacao_campanha,
        claim_materializacao_campanha_chunks,
        contar_chunks_ativos_campanha,
        listar_chunks_ativos_campanha,
        obter_chunks_stale_ativos,
        obter_estado_gate_materializacao,
        recuperar_chunks_materializacao_stale,
    )

    db = SessionLocal()
    try:
        campanha_uuid = uuid.UUID(campanha_id)
        campanha = db.get(AnaliseMaterializacaoCampanha, campanha_uuid)
        if campanha is None:
            return {"status": "missing_campaign", "campanha_id": campanha_id}
        _recalcular_materializacao_campanha(db, campanha)
        db.commit()
        db.refresh(campanha)
        if campanha.status in {"success", "failed", "partial"}:
            return {"status": "finished_campaign", "campanha_id": campanha_id, "campanha_status": campanha.status}

        stale_chunks = len(obter_chunks_stale_ativos(db, campanha_id=campanha_uuid))
        if stale_chunks > 0:
            recuperacao = recuperar_chunks_materializacao_stale(db, campanha_id=campanha_uuid)
            if recuperacao.recovered_chunks > 0:
                campanha = db.get(AnaliseMaterializacaoCampanha, campanha_uuid)
                if campanha is not None:
                    now = datetime.now(UTC)
                    campanha.summary = {
                        **(campanha.summary or {}),
                        "recovery_state": "requeued",
                        "last_recovery_check_at": now.isoformat(),
                        "last_recovery_action": "worker_recovered_and_requeued",
                        "last_recovery_reason_code": "STALE_CHUNK",
                    }
                    campanha.updated_at = now
                    db.commit()
                _reagendar_campanha_materializacao(campanha_id, countdown=0)
                return {
                    "status": "recovered_stale_and_requeued",
                    "campanha_id": campanha_id,
                    "recovered_chunks": recuperacao.recovered_chunks,
                    "recovered_items": recuperacao.recovered_items,
                }
            campanha.status = "pending"
            campanha.summary = {
                **(campanha.summary or {}),
                "wait_reason": "STALE_CHUNK_DETECTED",
                "wait_retry_scheduled_in_seconds": _settings.analise_materializacao_recovery_sweep_seconds,
                "stale_chunks": stale_chunks,
            }
            campanha.updated_at = datetime.now(UTC)
            db.commit()
            _reagendar_campanha_materializacao(
                campanha_id,
                countdown=_settings.analise_materializacao_recovery_sweep_seconds,
            )
            return {
                "status": "waiting_for_stale_recovery",
                "campanha_id": campanha_id,
                "stale_chunks": stale_chunks,
            }

        gate = obter_estado_gate_materializacao(db)
        if gate.status == "red":
            campanha.status = "pending"
            campanha.summary = {
                **(campanha.summary or {}),
                "wait_reason": gate.reason_code,
                "wait_retry_scheduled_in_seconds": _settings.analise_materializacao_gate_poll_seconds,
                "gate_blocking_ingestions": gate.blocking_ingestions,
            }
            campanha.updated_at = datetime.now(UTC)
            db.commit()
            return {
                "status": "waiting_for_gate",
                "campanha_id": campanha_id,
                "reason_code": gate.reason_code,
                "blocking_ingestions": gate.blocking_ingestions,
            }

        running_campaigns = int(
            db.scalar(
                select(func.count(AnaliseMaterializacaoCampanha.id)).where(
                    AnaliseMaterializacaoCampanha.status == "running",
                    AnaliseMaterializacaoCampanha.id != campanha_uuid,
                )
            )
            or 0
        )
        if running_campaigns >= _settings.analise_materializacao_max_active_campaigns:
            campanha.status = "pending"
            campanha.summary = {
                **(campanha.summary or {}),
                "wait_reason": "MAX_ACTIVE_CAMPAIGNS_REACHED",
                "wait_retry_scheduled_in_seconds": 30,
            }
            campanha.updated_at = datetime.now(UTC)
            db.commit()
            _reagendar_campanha_materializacao(campanha_id, countdown=30)
            return {
                "status": "waiting_for_slot",
                "campanha_id": campanha_id,
                "running_campaigns": running_campaigns,
                "max_active_campaigns": _settings.analise_materializacao_max_active_campaigns,
            }

        active_chunks = listar_chunks_ativos_campanha(db, campanha_uuid, limit=5)
        available_chunk_slots = max(
            0,
            _settings.analise_materializacao_max_active_chunks_per_campaign - len(active_chunks),
        )
        if available_chunk_slots <= 0:
            campanha.summary = {
                **(campanha.summary or {}),
                "wait_reason": "MAX_ACTIVE_CHUNKS_PER_CAMPAIGN_REACHED",
                "active_chunks": contar_chunks_ativos_campanha(db, campanha_uuid),
                "max_active_chunks_per_campaign": _settings.analise_materializacao_max_active_chunks_per_campaign,
            }
            campanha.updated_at = datetime.now(UTC)
            db.commit()
            return {
                "status": "waiting_for_chunk_slot",
                "campanha_id": campanha_id,
                "active_chunks": len(active_chunks),
                "max_active_chunks_per_campaign": _settings.analise_materializacao_max_active_chunks_per_campaign,
                "active_chunk_ids_preview": [str(chunk.id) for chunk in active_chunks],
            }

        claimed = claim_materializacao_campanha_chunks(
            db,
            campanha_uuid,
            chunk_size=campanha.chunk_size,
            max_chunks=_settings.analise_materializacao_max_active_chunks_per_campaign,
        )
        if not claimed:
            campanha = db.get(AnaliseMaterializacaoCampanha, campanha_uuid)
            if campanha is not None:
                _recalcular_materializacao_campanha(db, campanha)
                db.commit()
            return {
                "status": "no_pending_items",
                "campanha_id": campanha_id,
            }
        claimed_item_count = 0
        chunk_ids: list[str] = []
        for chunk, items in claimed:
            materializar_analise_chunk_task.delay(campanha_id, str(chunk.id))
            claimed_item_count += len(items)
            chunk_ids.append(str(chunk.id))

        return {
            "status": "enqueued",
            "campanha_id": campanha_id,
            "chunk_count": len(claimed),
            "claimed_items": claimed_item_count,
            "chunk_execucao_id": chunk_ids[0],
            "chunk_execucao_ids": chunk_ids,
        }
    finally:
        db.close()


@celery_app.task(bind=True, name="app.worker.tasks.despachar_materializacao_pendente_task", **_RETRY_KWARGS)  # type: ignore[untyped-decorator]
def despachar_materializacao_pendente_task(self: Any) -> dict[str, Any]:
    from sqlalchemy import func, select

    from app.models.analise import AnaliseMaterializacaoCampanha
    from app.services.analise import obter_estado_gate_materializacao

    db = SessionLocal()
    try:
        gate = obter_estado_gate_materializacao(db)
        if gate.status == "red":
            return {
                "status": "waiting_for_gate",
                "reason_code": gate.reason_code,
                "blocking_ingestions": gate.blocking_ingestions,
            }

        running_campaigns = int(
            db.scalar(select(func.count(AnaliseMaterializacaoCampanha.id)).where(AnaliseMaterializacaoCampanha.status == "running"))
            or 0
        )
        available_slots = max(0, _settings.analise_materializacao_max_active_campaigns - running_campaigns)
        if available_slots <= 0:
            return {
                "status": "waiting_for_slot",
                "running_campaigns": running_campaigns,
                "max_active_campaigns": _settings.analise_materializacao_max_active_campaigns,
            }

        campanhas = list(
            db.scalars(
                select(AnaliseMaterializacaoCampanha)
                .where(AnaliseMaterializacaoCampanha.status == "pending")
                .order_by(AnaliseMaterializacaoCampanha.created_at.asc())
                .limit(available_slots)
            ).all()
        )
        for campanha in campanhas:
            materializar_analise_campanha_task.delay(str(campanha.id))

        return {
            "status": "dispatched",
            "dispatched_campaigns": [str(campanha.id) for campanha in campanhas],
            "available_slots": available_slots,
        }
    finally:
        db.close()


@celery_app.task(bind=True, name="app.worker.tasks.materializar_analise_chunk_task", **_RETRY_KWARGS)  # type: ignore[untyped-decorator]
def materializar_analise_chunk_task(self: Any, campanha_id: str, chunk_execucao_id: str) -> dict[str, Any]:
    from app.models.analise import AnaliseMaterializacaoCampanhaItem, AnaliseMaterializacaoChunkExecucao
    from app.models.companhia import Companhia
    from app.services.analise import (
        finalizar_chunk_execucao,
        iniciar_chunk_execucao,
        materializar_analise_companhia,
        obter_estado_gate_materializacao,
        registrar_progresso_chunk_execucao,
        registrar_resultado_materializacao_campanha_item,
        renovar_chunk_execucao_lease,
        reverter_itens_materializacao_para_pending,
    )

    db = SessionLocal()
    try:
        chunk_uuid = uuid.UUID(chunk_execucao_id)
        chunk = db.get(AnaliseMaterializacaoChunkExecucao, chunk_uuid)
        if chunk is None:
            return {"status": "missing_chunk", "campanha_id": campanha_id, "chunk_execucao_id": chunk_execucao_id}
        if chunk.status in {"stale", "cancelled", "success", "failed"}:
            if chunk.status in {"stale", "cancelled"}:
                _reagendar_campanha_materializacao(campanha_id, countdown=0)
            return {
                "status": "ignored_chunk",
                "campanha_id": campanha_id,
                "chunk_execucao_id": chunk_execucao_id,
                "chunk_status": chunk.status,
            }

        lease_owner = str(self.request.id)
        gate = obter_estado_gate_materializacao(db)
        if gate.status == "red":
            item_ids = [
                str(item_id)
                for item_id in db.scalars(
                    select(AnaliseMaterializacaoCampanhaItem.id)
                    .where(AnaliseMaterializacaoCampanhaItem.chunk_execucao_id == chunk_uuid)
                    .order_by(AnaliseMaterializacaoCampanhaItem.ordem.asc(), AnaliseMaterializacaoCampanhaItem.created_at.asc())
                ).all()
            ]
            remaining_ids = [uuid.UUID(item_id) for item_id in item_ids]
            reverter_itens_materializacao_para_pending(db, remaining_ids, reason=gate.reason_code)
            chunk = db.get(AnaliseMaterializacaoChunkExecucao, chunk_uuid)
            if chunk is not None:
                finalizar_chunk_execucao(
                    db,
                    chunk,
                    status="cancelled",
                    processed_items=0,
                    success_items=0,
                    failed_items=0,
                    summary={"reason": gate.reason_code, "requeued_items": len(remaining_ids)},
                )
            _reagendar_campanha_materializacao(campanha_id)
            return {
                "status": "waiting_for_gate",
                "campanha_id": campanha_id,
                "chunk_execucao_id": chunk_execucao_id,
                "reason_code": gate.reason_code,
                "requeued_items": len(remaining_ids),
            }
        iniciar_chunk_execucao(db, chunk, lease_owner=lease_owner)
        item_ids = [
            str(item_id)
            for item_id in db.scalars(
                select(AnaliseMaterializacaoCampanhaItem.id)
                .where(AnaliseMaterializacaoCampanhaItem.chunk_execucao_id == chunk_uuid)
                .order_by(AnaliseMaterializacaoCampanhaItem.ordem.asc(), AnaliseMaterializacaoCampanhaItem.created_at.asc())
            ).all()
        ]
        processed = 0
        success_items = 0
        failed_items = 0
        skipped_items = 0
        for position, item_id in enumerate(item_ids, start=1):
            chunk = db.get(AnaliseMaterializacaoChunkExecucao, chunk_uuid)
            if chunk is None or chunk.status in {"stale", "cancelled"}:
                _reagendar_campanha_materializacao(campanha_id, countdown=0)
                return {
                    "status": "aborted_chunk",
                    "campanha_id": campanha_id,
                    "chunk_execucao_id": chunk_execucao_id,
                }
            renovar_chunk_execucao_lease(db, chunk, lease_owner=lease_owner)
            db.commit()
            gate = obter_estado_gate_materializacao(db)
            if gate.status == "red":
                remaining_ids = [uuid.UUID(remaining_id) for remaining_id in item_ids[position - 1:]]
                reverter_itens_materializacao_para_pending(db, remaining_ids, reason=gate.reason_code)
                chunk = db.get(AnaliseMaterializacaoChunkExecucao, chunk_uuid)
                if chunk is not None:
                    finalizar_chunk_execucao(
                        db,
                        chunk,
                        status="cancelled",
                        processed_items=processed,
                        success_items=success_items,
                        failed_items=failed_items,
                        skipped_items=skipped_items,
                        summary={"reason": gate.reason_code, "requeued_items": len(remaining_ids)},
                    )
                _reagendar_campanha_materializacao(campanha_id)
                return {
                    "status": "paused_by_gate",
                    "campanha_id": campanha_id,
                    "chunk_execucao_id": chunk_execucao_id,
                    "reason_code": gate.reason_code,
                    "requeued_items": len(remaining_ids),
                    "processed_items": processed,
                }
            item = db.get(AnaliseMaterializacaoCampanhaItem, uuid.UUID(item_id))
            if item is None:
                continue
            item.started_at = item.started_at or datetime.now(UTC)
            item.updated_at = datetime.now(UTC)
            item.attempts += 1
            db.commit()

            companhia = None
            if item.companhia_id is not None:
                companhia = db.get(Companhia, item.companhia_id)
            if companhia is None:
                companhia = db.scalar(select(Companhia).where(Companhia.codigo_cvm == item.codigo_cvm))
            if companhia is None:
                registrar_resultado_materializacao_campanha_item(
                    db,
                    item,
                    status="failed",
                    last_error=f"Companhia nao encontrada para codigo_cvm={item.codigo_cvm}.",
                )
                failed_items += 1
                processed += 1
                continue

            try:
                execucao = materializar_analise_companhia(
                    db,
                    companhia,
                    scope=cast(Literal["consolidated", "individual"], item.escopo),
                    source="post_ingestion",
                    invalidated_from=item.invalidated_from,
                    incluir_canceladas=False,
                    campanha_id=uuid.UUID(campanha_id),
                    campanha_item_id=item.id,
                    chunk_execucao_id=chunk_uuid,
                    queue_name=_settings.analise_materializacao_queue_name,
                    task_id=str(self.request.id),
                    position_in_chunk=position,
                )
                skipped_reason = (execucao.summary or {}).get("skipped_reason")
                registrar_resultado_materializacao_campanha_item(
                    db,
                    item,
                    status=(
                        "skipped"
                        if skipped_reason is not None
                        else "success" if execucao.status == "success" else "failed"
                    ),
                    materializacao_execucao_id=execucao.id,
                    last_error=None if execucao.status == "success" else "materialization_failed",
                    reason=skipped_reason,
                )
                if skipped_reason is not None:
                    skipped_items += 1
                elif execucao.status == "success":
                    success_items += 1
                else:
                    failed_items += 1
            except Exception as exc:
                registrar_resultado_materializacao_campanha_item(
                    db,
                    item,
                    status="failed",
                    last_error=str(exc),
                )
                failed_items += 1
            processed += 1
            chunk = db.get(AnaliseMaterializacaoChunkExecucao, chunk_uuid)
            if chunk is not None:
                registrar_progresso_chunk_execucao(
                    db,
                    chunk,
                    lease_owner=lease_owner,
                    processed_items=processed,
                    success_items=success_items,
                    failed_items=failed_items,
                    skipped_items=skipped_items,
                )

        chunk = db.get(AnaliseMaterializacaoChunkExecucao, chunk_uuid)
        if chunk is not None:
            finalizar_chunk_execucao(
                db,
                chunk,
                status="failed" if failed_items > 0 else "success",
                processed_items=processed,
                success_items=success_items,
                failed_items=failed_items,
                skipped_items=skipped_items,
            )
        _reagendar_campanha_materializacao(campanha_id, countdown=0)
        return {
            "status": "processed",
            "campanha_id": campanha_id,
            "chunk_execucao_id": chunk_execucao_id,
            "processed_items": processed,
            "success_items": success_items,
            "failed_items": failed_items,
            "skipped_items": skipped_items,
        }
    finally:
        db.close()


@celery_app.task(bind=True, name="app.worker.tasks.reconciliar_materializacao_stale_task", **_RETRY_KWARGS)  # type: ignore[untyped-decorator]
def reconciliar_materializacao_stale_task(self: Any, campanha_id: str | None = None) -> dict[str, Any]:
    from app.services.analise import recuperar_chunks_materializacao_stale

    db = SessionLocal()
    try:
        campanha_uuid = uuid.UUID(campanha_id) if campanha_id else None
        resultado = recuperar_chunks_materializacao_stale(db, campanha_id=campanha_uuid)
        for campanha_afetada in resultado.affected_campaigns:
            _reagendar_campanha_materializacao(
                campanha_afetada,
                countdown=0,
            )
        return {
            "status": "recovered" if resultado.recovered_chunks > 0 else "noop",
            "recovered_chunks": resultado.recovered_chunks,
            "recovered_items": resultado.recovered_items,
            "affected_campaigns": list(resultado.affected_campaigns),
            "chunk_ids": list(resultado.chunk_ids),
        }
    finally:
        db.close()


@celery_app.task(bind=True, name="app.worker.tasks.recuperar_materializacao_pendente_task", **_RETRY_KWARGS)  # type: ignore[untyped-decorator]
def recuperar_materializacao_pendente_task(self: Any) -> dict[str, Any]:
    from app.services.analise import recuperar_materializacao_pendente

    db = SessionLocal()
    try:
        resultado = recuperar_materializacao_pendente(db)
        for campanha_id in resultado.requeued_campaigns:
            _enfileirar_campanha_materializacao(campanha_id)
        return {
            "status": resultado.status,
            "reason_code": resultado.reason_code,
            "affected_campaigns": list(resultado.affected_campaigns),
            "requeued_campaigns": list(resultado.requeued_campaigns),
            "recovered_chunks": resultado.recovered_chunks,
            "recovered_items": resultado.recovered_items,
            "dispatcher_enqueued": resultado.dispatcher_enqueued,
            "scanned_campaigns": resultado.scanned_campaigns,
            "recoverable_campaigns": resultado.recoverable_campaigns,
            "triggered_at": resultado.triggered_at.isoformat(),
        }
    finally:
        db.close()


@celery_app.task(bind=True, name="app.worker.tasks.reconciliar_materializacoes_terminais_task", **_RETRY_KWARGS)  # type: ignore[untyped-decorator]
def reconciliar_materializacoes_terminais_task(self: Any) -> dict[str, Any]:
    from app.services.analise import obter_estado_gate_materializacao
    from app.services.analise_materializacao_operacional import (
        reconcile_completion_pending_executions,
    )

    inspect = celery_app.control.inspect(timeout=0.5)
    try:
        active = inspect.active()
        reserved = inspect.reserved()
        scheduled = inspect.scheduled()
    except Exception:
        active = reserved = scheduled = None
    inspection_available = not (
        active is None and reserved is None and scheduled is None
    )
    task_ids: set[str] = set()
    for payload, is_scheduled in (
        (active or {}, False),
        (reserved or {}, False),
        (scheduled or {}, True),
    ):
        for tasks in payload.values():
            if not isinstance(tasks, list):
                continue
            for task in tasks:
                if not isinstance(task, dict):
                    continue
                request = task.get("request") if is_scheduled else task
                if isinstance(request, dict) and isinstance(request.get("id"), str):
                    task_ids.add(request["id"])

    db = SessionLocal()
    try:
        gate = obter_estado_gate_materializacao(db)
        return reconcile_completion_pending_executions(
            db,
            active_task_ids=task_ids,
            task_inspection_available=inspection_available,
            gate_status=gate.status,
            gate_reason_code=gate.reason_code,
            stalled_threshold_seconds=300,
        )
    finally:
        db.close()


@celery_app.task(bind=True, name="app.worker.tasks.sincronizar_isin_task", **_RETRY_KWARGS)  # type: ignore[untyped-decorator]
def sincronizar_isin_task(self: Any, execucao_id: str, _queue_item_id: str | None = None, _queue_reservation_token: str | None = None) -> dict[str, Any]:
    def operacao() -> dict[str, Any]:
        from app.models.sincronizacao import ExecucaoSincronizacao
        from app.services.ingestion.isin import importar_isin

        db = SessionLocal()
        try:
            execucao = db.get(ExecucaoSincronizacao, uuid.UUID(execucao_id))
            if execucao is None:
                raise ValueError("Execucao ISIN nao encontrada")
            return importar_isin(db, execucao)
        finally:
            db.close()

    return _executar_com_reserva(self, queue_item_id=_queue_item_id, reservation_token=_queue_reservation_token,
                                 task_name=self.name, task_args=[], task_kwargs={"execucao_id": execucao_id},
                                 execution_id=execucao_id, operation=operacao, kind="simple")


@celery_app.task(bind=True, name="app.worker.tasks.sincronizar_cadastro_companhias_task", **_RETRY_KWARGS)  # type: ignore[untyped-decorator]
def sincronizar_cadastro_companhias_task(
    self: Any,
    force_reimport: bool = False,
    skip_probe: bool = False,
    pending_update_id: str | None = None,
    dispatch_year_after_success: int | None = None,
    _queue_item_id: str | None = None,
    _queue_reservation_token: str | None = None,
) -> dict[str, str]:
    import uuid

    from sqlalchemy import select

    from app.models.ingestion import IngestionRun
    from app.updates.lifecycle import finalize_pending_update_by_run_id

    if _queue_item_id is None or _queue_reservation_token is None:
        return cast(
            dict[str, str],
            _capturar_na_fila(
                self,
                task_name=self.name,
                task_args=[],
                task_kwargs={
                    "force_reimport": force_reimport,
                    "skip_probe": skip_probe,
                    "pending_update_id": pending_update_id,
                    "dispatch_year_after_success": dispatch_year_after_success,
                },
            ),
        )
    if not _iniciar_reserva(_queue_item_id, _queue_reservation_token):
        despachar_fila_ingestao_task.delay()
        return {"status": "stale_reservation", "execucao_id": ""}

    db = SessionLocal()
    try:
        resultado = sincronizar_cadastro_companhias(
            db,
            task_id=str(self.request.id),
            force_reimport=force_reimport,
            pending_update_id=pending_update_id,
        )
        status_res = resultado.get("status")
        execucao_id = resultado.get("execucao_id")

        if execucao_id and pending_update_id:
            stmt_run = select(IngestionRun).where(
                IngestionRun.execucao_sincronizacao_id == uuid.UUID(execucao_id)
            )
            run = db.scalar(stmt_run)
            if finalize_pending_update_by_run_id(
                db,
                pending_update_id=pending_update_id,
                run=run,
            ):
                db.commit()
        if status_res in ("sucesso", "sem_alteracao", "skipped"):
            if dispatch_year_after_success is not None:
                queued = _enfileirar_fontes_anuais_agendadas(
                    db,
                    ano=dispatch_year_after_success,
                    force_reimport=force_reimport,
                )
                _logger.info(
                    "ingestion.batch_annual_sources_published",
                    extra={
                        "dispatch_year": dispatch_year_after_success,
                        "queued_tasks": queued,
                    },
                )
                if queued:
                    despachar_fila_ingestao_task.delay()

        _concluir_reserva(_queue_item_id, _queue_reservation_token)
        return {"status": str(resultado["status"]), "execucao_id": str(resultado["execucao_id"])}
    except Exception as exc:
        db.rollback()
        _liberar_reserva(
            _queue_item_id,
            _queue_reservation_token,
            str(exc),
            retryable=isinstance(exc, _AUTORETRY_FOR),
        )
        run = db.scalar(
            select(IngestionRun)
            .where(IngestionRun.requested_by_task_id == str(self.request.id))
            .order_by(IngestionRun.created_at.desc())
            .limit(1)
        )
        if finalize_pending_update_by_run_id(
            db,
            pending_update_id=pending_update_id,
            run=run,
        ):
            db.commit()
        raise
    finally:
        db.close()


def _download(url: str, *, timeout: float) -> bytes:
    import httpx
    response = httpx.get(url, timeout=timeout)
    response.raise_for_status()
    return response.content


def get_row_kind(tipo_fonte: str, ano: int, member_name: str) -> str:
    if tipo_fonte in ("dfp", "itr"):
        from app.services.ingestion.financeiro import map_financeiro_members
        row_kind_map, _ = map_financeiro_members(tipo_fonte, ano)
    elif tipo_fonte == "fre":
        from app.services.ingestion.fre import map_fre_members
        row_kind_map, _, _ = map_fre_members(ano)
    elif tipo_fonte == "fca":
        from app.services.ingestion.fca import map_fca_members
        row_kind_map, _, _, _ = map_fca_members(ano)
    elif tipo_fonte == "ipe":
        from app.services.ingestion.ipe import map_ipe_members
        row_kind_map, _, _, _ = map_ipe_members(ano)
    elif tipo_fonte == "vlmo":
        from app.services.ingestion.vlmo import map_vlmo_members
        row_kind_map, _, _, _ = map_vlmo_members(ano)
    elif tipo_fonte == "cgvn":
        from app.services.ingestion.cgvn import map_cgvn_members
        row_kind_map, _, _, _ = map_cgvn_members(ano)
    else:
        row_kind_map = {}
    return row_kind_map.get(member_name, "desconhecido")


def get_ordered_members(tipo_fonte: str, ano: int, payload: bytes) -> list[tuple[str, bytes]]:
    from app.services.ingestion.source_registry import listar_datasets
    from app.services.ingestion.staging import iter_zip_csv_members
    datasets = listar_datasets(tipo_fonte)
    order_map = {item.render_member_name(ano=ano): idx for idx, item in enumerate(datasets)}
    return sorted(iter_zip_csv_members(payload), key=lambda item: (order_map.get(item[0], 999), item[0]))


def _seed_member_reprocess_header_map(db: Any, *, tipo_fonte: str, ano: int) -> dict[Any, Any]:
    from sqlalchemy import select

    from app.models.financeiro import DocumentoFinanceiro
    from app.models.fre import FreDocumento
    from app.services.ingestion.resolver import register_document_header

    if tipo_fonte == "fca":
        from app.services.ingestion.fca import _seed_fca_header_map

        return _seed_fca_header_map(db, ano=ano)

    header_map: dict[Any, Any] = {}
    if tipo_fonte in {"dfp", "itr"}:
        rows = db.execute(
            select(
                DocumentoFinanceiro.tipo_formulario,
                DocumentoFinanceiro.id_documento,
                DocumentoFinanceiro.versao,
                DocumentoFinanceiro.data_referencia,
                DocumentoFinanceiro.companhia_id,
                DocumentoFinanceiro.cnpj_companhia,
                DocumentoFinanceiro.codigo_cvm,
            ).where(
                DocumentoFinanceiro.ano_origem == ano,
                DocumentoFinanceiro.tipo_formulario == tipo_fonte.upper(),
                DocumentoFinanceiro.companhia_id.is_not(None),
            )
        )
        for row in rows:
            register_document_header(
                header_map,
                tipo_formulario=row[0],
                id_documento=row[1],
                versao=row[2],
                data_referencia=row[3],
                companhia_id=row[4],
                cnpj_companhia=row[5],
                codigo_cvm=row[6],
            )
        return header_map

    if tipo_fonte == "fre":
        rows = db.execute(
            select(
                FreDocumento.id_documento,
                FreDocumento.versao,
                FreDocumento.data_referencia,
                FreDocumento.companhia_id,
                FreDocumento.cnpj_companhia,
                FreDocumento.codigo_cvm,
            ).where(
                FreDocumento.ano_origem == ano,
                FreDocumento.companhia_id.is_not(None),
            )
        )
        for row in rows:
            register_document_header(
                header_map,
                tipo_formulario="FRE",
                id_documento=row[0],
                versao=row[1],
                data_referencia=row[2],
                companhia_id=row[3],
                cnpj_companhia=row[4],
                codigo_cvm=row[5],
            )
        return header_map

    return header_map


def rebuild_header_map(db: Any, parent_execucao_id: Any) -> dict[Any, Any]:
    from sqlalchemy import select

    from app.models.ingestion import IngestionRow, IngestionRun
    from app.models.sincronizacao import ExecucaoSincronizacao
    from app.services.ingestion.resolver import register_document_header

    header_map: dict[Any, Any] = {}
    child_execs = db.execute(
        select(ExecucaoSincronizacao.id)
        .where(
            ExecucaoSincronizacao.parent_execucao_id == parent_execucao_id,
            ExecucaoSincronizacao.status == "sucesso"
        )
    ).scalars().all()
    if not child_execs:
        return {}
        
    rows = list(
        db.execute(
            select(IngestionRow)
            .join(IngestionRun, IngestionRun.id == IngestionRow.ingestion_run_id)
            .where(
                IngestionRun.execucao_sincronizacao_id.in_(child_execs),
                IngestionRow.row_kind.in_(("dfp_documento", "itr_documento", "fre_documento", "fca_documento")),
                IngestionRow.resolved_companhia_id.is_not(None),
            )
        ).scalars()
    )
    for row in rows:
        dados = row.normalized_data or {}
        if row.resolved_companhia_id is not None:
            register_document_header(
                header_map,
                tipo_formulario=dados.get(
                    "tipo_formulario",
                    "FRE" if row.row_kind == "fre_documento" else "FCA" if row.row_kind == "fca_documento" else None,
                ),
                id_documento=dados.get("id_documento"),
                versao=dados.get("versao"),
                data_referencia=dados.get("data_referencia"),
                companhia_id=row.resolved_companhia_id,
                cnpj_companhia=dados.get("cnpj_companhia"),
                codigo_cvm=dados.get("codigo_cvm"),
            )
    return header_map


def pre_processar_sincronizacao_zip(
    tipo_fonte: str,
    ano: int,
    task_id: str | None = None,
    force_reimport: bool = False,
    skip_probe: bool = False,
    pending_update_id: str | None = None,
) -> dict[str, Any]:
    from datetime import UTC, datetime
    from pathlib import Path

    from sqlalchemy import select

    from app.models.ingestion import IngestionFile, IngestionRun
    from app.models.sincronizacao import ExecucaoSincronizacao
    from app.services.ingestion.artifact_store import build_artifact_metadata, describe_member_artifact
    from app.services.ingestion.dedup import buscar_execucao_hash_existente
    from app.services.ingestion.file_manager import (
        compute_file_sha256,
        count_csv_rows,
        detect_encoding_and_delimiter,
        download_file_to_disk,
        extract_zip_member,
        get_csv_header,
    )
    from app.services.ingestion.operational import record_phase_artifact
    from app.services.ingestion.scheduling import adotar_ou_criar_execucao_sincronizacao
    from app.services.ingestion.staging import (
        create_run,
        find_reusable_member_match,
        register_file,
        register_member,
        save_member_payload,
        update_run_state,
    )

    db = SessionLocal()
    settings = get_settings()

    tipo_formulario = tipo_fonte.upper()
    arquivo_zip = f"{tipo_fonte}_cia_aberta_{ano}.zip"
    url = f"{settings.cvm_base_url}/CIA_ABERTA/DOC/{tipo_formulario}/DADOS/{arquivo_zip}"

    execucao = adotar_ou_criar_execucao_sincronizacao(
        db,
        tipo_fonte=tipo_fonte,
        ano=ano,
        task_id=task_id,
        arquivo=arquivo_zip,
        url=url,
        tipo_execucao="arquivo_zip",
    )
    db.commit()
    db.refresh(execucao)

    zip_dir = Path(settings.storage_dir) / str(execucao.id)
    if execucao.status == "aguardando_ingestao" and zip_dir.exists():
        db.close()
        return {"execucao_id": str(execucao.id), "status": "aguardando_ingestao"}

    existing_run = db.scalar(
        select(IngestionRun)
        .where(IngestionRun.execucao_sincronizacao_id == execucao.id)
        .order_by(IngestionRun.created_at.desc())
        .limit(1)
    )
    if existing_run is not None:
        run = existing_run
        run.requested_by_task_id = task_id or run.requested_by_task_id
        run.finished_at = None
        update_run_state(run, status="em_execucao", phase="acquire", message=None)
    else:
        run = create_run(
            db,
            tipo_fonte=tipo_fonte,
            ano=ano,
            execucao_sincronizacao_id=execucao.id,
            requested_by_task_id=task_id,
            phase="acquire",
        )
    db.commit()
    db.refresh(run)
    if pending_update_id is not None:
        from app.updates.lifecycle import link_pending_update_to_run

        link_pending_update_to_run(
            db,
            pending_update_id=pending_update_id,
            run=run,
        )
        db.commit()

    zip_dir = Path(settings.storage_dir) / str(execucao.id)
    zip_path = zip_dir / arquivo_zip

    try:
        hash_arquivo = download_file_to_disk(url, str(zip_path), timeout=300)
        execucao.hash_arquivo = hash_arquivo
        record_phase_artifact(
            db,
            run_id=run.id,
            direction="output",
            artifact=build_artifact_metadata(
                artifact_path=zip_path,
                role="raw_zip",
                content_type="application/zip",
                logical_name=arquivo_zip,
                content_sha256=hash_arquivo,
            ),
        )

        anterior = buscar_execucao_hash_existente(
            db,
            tipo_fonte=tipo_fonte,
            ano=ano,
            hash_arquivo=hash_arquivo,
            execucao_atual_id=execucao.id,
        )
        if anterior is not None and not force_reimport:
            execucao.status = "skipped"
            execucao.finalizada_em = datetime.now(UTC)
            update_run_state(run, status="skipped", phase="complete", finished_at=datetime.now(UTC))
            db.commit()

            # Clean up disk
            import shutil
            try:
                shutil.rmtree(zip_dir)
            except Exception:
                pass

            return {"execucao_id": str(execucao.id), "status": "skipped"}

        existing_file = db.scalar(
            select(IngestionFile)
            .where(IngestionFile.ingestion_run_id == run.id)
            .limit(1)
        )
        if existing_file is not None:
            existing_file.content_sha256 = hash_arquivo
            existing_file.content_length_bytes = zip_path.stat().st_size
            ingestion_file = existing_file
            db.flush()
        else:
            ingestion_file = register_file(
                db,
                ingestion_run=run,
                source_url=url,
                source_filename=arquivo_zip,
                content_sha256=hash_arquivo,
                content_length_bytes=zip_path.stat().st_size,
                is_zip=True,
            )
        update_run_state(run, phase="stage")
        db.commit()

        # Get members inside zip
        from app.services.ingestion.source_registry import listar_datasets
        datasets = listar_datasets(tipo_fonte)

        import zipfile
        with zipfile.ZipFile(zip_path) as archive:
            member_names = [n for n in archive.namelist() if n.endswith(".csv")]

        order_map = {item.render_member_name(ano=ano): idx for idx, item in enumerate(datasets)}
        ordered_members = sorted(member_names, key=lambda name: (order_map.get(name, 999), name))

        required_members = {item.render_member_name(ano=ano) for item in datasets if item.obrigatorio}
        staged_names = set(ordered_members)

        faltando = sorted(required_members - staged_names)
        if faltando:
            aviso_membros_ausentes = (
                "membros_ausentes_ignorados: "
                f"{','.join(faltando)}. O ZIP sera ingerido com os membros disponiveis."
            )
            execucao.mensagem_erro = aviso_membros_ausentes
            run.message = aviso_membros_ausentes
            _logger.warning(
                "ZIP %s/%s sem membros esperados; seguindo com os disponiveis: %s",
                tipo_fonte,
                ano,
                ",".join(faltando),
            )

        extracted_dir = zip_dir / "extracted"

        supported_member_names = {
            item.render_member_name(ano=ano)
            for item in datasets
            if item.status_suporte == "suportado"
        }

        existing_children_by_name = {
            c.arquivo: c
            for c in db.scalars(
                select(ExecucaoSincronizacao).where(
                    ExecucaoSincronizacao.parent_execucao_id == execucao.id
                )
            ).all()
        }

        for member_name in ordered_members:
            # Extract to disk
            extracted_path = extract_zip_member(str(zip_path), member_name, str(extracted_dir))
            member_hash = compute_file_sha256(extracted_path)
            member_size = Path(extracted_path).stat().st_size
            member_payload = Path(extracted_path).read_bytes()

            existing_child = existing_children_by_name.get(member_name)
            if existing_child is not None and existing_child.status in {
                "sucesso",
                "sucesso_com_alerta",
                "sem_alteracao",
                "skipped",
            }:
                save_member_payload(db, existing_child.id, member_payload, member_name=member_name)
                db.flush()
                continue

            # Check if supported
            if member_name not in supported_member_names:
                if existing_child is not None:
                    child_exec = existing_child
                    child_exec.status = "skipped"
                    child_exec.hash_arquivo = member_hash
                    child_exec.finalizada_em = datetime.now(UTC)
                    child_exec.mensagem_erro = None
                else:
                    child_exec = ExecucaoSincronizacao(
                        parent_execucao_id=execucao.id,
                        tipo_execucao="arquivo_membro",
                        tipo_fonte=tipo_fonte,
                        ano=ano,
                        arquivo=member_name,
                        url=url,
                        status="skipped",
                        hash_arquivo=member_hash,
                        finalizada_em=datetime.now(UTC),
                    )
                    db.add(child_exec)
                db.flush()

                existing_child_run = db.scalar(
                    select(IngestionRun)
                    .where(IngestionRun.execucao_sincronizacao_id == child_exec.id)
                    .order_by(IngestionRun.created_at.desc())
                    .limit(1)
                )
                if existing_child_run is not None:
                    run_created = update_run_state(
                        existing_child_run,
                        status="skipped",
                        phase="complete",
                        finished_at=datetime.now(UTC),
                    )
                else:
                    run_created = create_run(
                        db,
                        tipo_fonte=tipo_fonte,
                        ano=ano,
                        execucao_sincronizacao_id=child_exec.id,
                        status="skipped",
                        phase="complete",
                    )
                    run_created.finished_at = datetime.now(UTC)
                register_member(
                    db,
                    ingestion_file=ingestion_file,
                    member_name=member_name,
                    member_sha256=member_hash,
                    member_size_bytes=member_size,
                    header=None,
                    row_count=0,
                    encoding=None,
                    schema_status="ok",
                )
                save_member_payload(db, child_exec.id, member_payload, member_name=member_name)
                record_phase_artifact(
                    db,
                    run_id=run_created.id,
                    direction="output",
                    artifact=describe_member_artifact(
                        execution_id=str(child_exec.id),
                        member_name=member_name,
                        content_sha256=member_hash,
                    ),
                )
                db.flush()
                continue

            # Check match
            reusable_match = find_reusable_member_match(
                db,
                tipo_fonte=tipo_fonte,
                ano=ano,
                member_name=member_name,
                member_sha256=member_hash,
                current_run_id=run.id,
            )
            if reusable_match is not None and not force_reimport:
                if existing_child is not None:
                    child_exec = existing_child
                    child_exec.status = "skipped"
                    child_exec.hash_arquivo = member_hash
                    child_exec.finalizada_em = datetime.now(UTC)
                    child_exec.mensagem_erro = None
                else:
                    child_exec = ExecucaoSincronizacao(
                        parent_execucao_id=execucao.id,
                        tipo_execucao="arquivo_membro",
                        tipo_fonte=tipo_fonte,
                        ano=ano,
                        arquivo=member_name,
                        url=url,
                        status="skipped",
                        hash_arquivo=member_hash,
                        finalizada_em=datetime.now(UTC),
                    )
                    db.add(child_exec)
                db.flush()

                skip_quality = {
                    "skip_reason": "member_sha256_reused",
                    "matched_via": reusable_match["matched_via"],
                    "reused_from_failed_parent": reusable_match["reused_from_failed_parent"],
                }
                existing_child_run = db.scalar(
                    select(IngestionRun)
                    .where(IngestionRun.execucao_sincronizacao_id == child_exec.id)
                    .order_by(IngestionRun.created_at.desc())
                    .limit(1)
                )
                if existing_child_run is not None:
                    run_created = update_run_state(
                        existing_child_run,
                        status="skipped",
                        phase="complete",
                        message="member_sha256_reused",
                        quality_summary=skip_quality,
                        finished_at=datetime.now(UTC),
                    )
                else:
                    run_created = create_run(
                        db,
                        tipo_fonte=tipo_fonte,
                        ano=ano,
                        execucao_sincronizacao_id=child_exec.id,
                        status="skipped",
                        phase="complete",
                        message="member_sha256_reused",
                        quality_summary=skip_quality,
                    )
                    run_created.finished_at = datetime.now(UTC)
                register_member(
                    db,
                    ingestion_file=ingestion_file,
                    member_name=member_name,
                    member_sha256=member_hash,
                    member_size_bytes=member_size,
                    header=None,
                    row_count=0,
                    encoding=None,
                    schema_status="ok",
                )
                save_member_payload(db, child_exec.id, member_payload, member_name=member_name)
                record_phase_artifact(
                    db,
                    run_id=run_created.id,
                    direction="output",
                    artifact=describe_member_artifact(
                        execution_id=str(child_exec.id),
                        member_name=member_name,
                        content_sha256=member_hash,
                    ),
                )
                db.flush()
                continue

            if existing_child is not None:
                child_exec = existing_child
                child_exec.status = "aguardando_ingestao"
                child_exec.hash_arquivo = member_hash
                child_exec.finalizada_em = None
                child_exec.mensagem_erro = None
            else:
                child_exec = ExecucaoSincronizacao(
                    parent_execucao_id=execucao.id,
                    tipo_execucao="arquivo_membro",
                    tipo_fonte=tipo_fonte,
                    ano=ano,
                    arquivo=member_name,
                    url=url,
                    status="aguardando_ingestao",
                    hash_arquivo=member_hash,
                )
                db.add(child_exec)
            db.flush()

            existing_child_run = db.scalar(
                select(IngestionRun)
                .where(IngestionRun.execucao_sincronizacao_id == child_exec.id)
                .order_by(IngestionRun.created_at.desc())
                .limit(1)
            )
            if existing_child_run is not None:
                child_run = update_run_state(
                    existing_child_run,
                    status="aguardando_ingestao",
                    phase="stage",
                    message=None,
                )
                child_run.finished_at = None
            else:
                child_run = create_run(
                    db,
                    tipo_fonte=tipo_fonte,
                    ano=ano,
                    execucao_sincronizacao_id=child_exec.id,
                    status="aguardando_ingestao",
                    phase="stage",
                )
            db.flush()

            # Extract header, encoding, delimiter, row count
            encoding, delimiter = detect_encoding_and_delimiter(extracted_path)
            header = get_csv_header(extracted_path, encoding, delimiter)
            row_count = count_csv_rows(extracted_path, encoding, delimiter)

            register_member(
                db,
                ingestion_file=ingestion_file,
                member_name=member_name,
                member_sha256=member_hash,
                member_size_bytes=member_size,
                header=header,
                row_count=row_count,
                encoding=encoding,
                delimiter=delimiter,
            )
            save_member_payload(db, child_exec.id, member_payload, member_name=member_name)
            record_phase_artifact(
                db,
                run_id=child_run.id,
                direction="output",
                artifact=describe_member_artifact(
                    execution_id=str(child_exec.id),
                    member_name=member_name,
                    content_sha256=member_hash,
                ),
            )
            db.flush()

        # Update parent execution to aguardando_ingestao
        execucao.status = "aguardando_ingestao"
        update_run_state(run, status="aguardando_ingestao", phase="stage")
        db.commit()
        return {"execucao_id": str(execucao.id), "status": "aguardando_ingestao"}

    except Exception as exc:
        db.rollback()
        execucao_erro = db.get(ExecucaoSincronizacao, execucao.id)
        if execucao_erro is not None:
            execucao_erro.status = "falha"
            execucao_erro.mensagem_erro = str(exc)
            execucao_erro.finalizada_em = datetime.now(UTC)
        run_erro = db.get(IngestionRun, run.id)
        if run_erro is not None:
            update_run_state(
                run_erro,
                status="falha",
                phase="complete",
                message=str(exc),
                finished_at=datetime.now(UTC)
            )
            if pending_update_id is not None:
                from app.updates.lifecycle import finalize_pending_update_by_run_id

                finalize_pending_update_by_run_id(
                    db,
                    pending_update_id=pending_update_id,
                    run=run_erro,
                )
        db.commit()

        # Clean up files
        import shutil
        try:
            shutil.rmtree(zip_dir)
        except Exception:
            pass
        raise
    finally:
        db.close()


def ingerir_sincronizacao_zip(
    execucao_id: uuid.UUID,
    force_reimport: bool = False,
    pending_update_id: str | None = None,
) -> dict[str, Any]:
    from datetime import UTC, datetime

    from sqlalchemy import select

    from app.models.ingestion import IngestionRun
    from app.models.sincronizacao import ExecucaoSincronizacao
    from app.services.ingestion.dependencies import ensure_identity_graph_ready
    from app.services.ingestion.resolver import limpar_caches_resolver
    from app.services.ingestion.staging import update_run_state

    db = SessionLocal()
    limpar_caches_resolver()
    ensure_identity_graph_ready(db)

    execucao = db.get(ExecucaoSincronizacao, execucao_id)
    if execucao is None:
        db.close()
        raise ValueError(f"Execution not found: {execucao_id}")

    if execucao.status == "cancelada":
        db.close()
        return _resultado_cancelado(execucao.id, "Execution was cancelled before ingestion started.")

    if execucao.status != "aguardando_ingestao":
        db.close()
        return {
            "execucao_id": str(execucao.id),
            "status": execucao.status,
            "message": f"Execution is in state '{execucao.status}', not 'aguardando_ingestao'."
        }

    parent_runs = list(
        db.scalars(
            select(IngestionRun)
            .where(IngestionRun.execucao_sincronizacao_id == execucao.id)
            .order_by(IngestionRun.created_at.desc())
        ).all()
    )
    run = parent_runs[0] if parent_runs else None
    for parent_run in parent_runs:
        update_run_state(parent_run, status="aguardando_ingestao", phase="stage")
    db.commit()

    try:
        disparar_dependentes_task.delay(
            parent_execucao_id=str(execucao.id),
            force_reimport=force_reimport,
            pending_update_id=pending_update_id,
        )

        return {
            "execucao_id": str(execucao.id),
            "status": "aguardando_ingestao",
            "message": "Ingestion work is waiting for a global member slot.",
        }

    except Exception as exc:
        db.rollback()
        execucao_erro = db.get(ExecucaoSincronizacao, execucao.id)
        if execucao_erro is not None:
            execucao_erro.status = "falha"
            execucao_erro.mensagem_erro = str(exc)
            execucao_erro.finalizada_em = datetime.now(UTC)
        run_erro = db.get(IngestionRun, run.id) if run else None
        if run_erro is not None:
            update_run_state(
                run_erro,
                status="falha",
                phase="complete",
                message=str(exc),
                finished_at=datetime.now(UTC)
            )
            if pending_update_id is not None:
                from app.updates.lifecycle import finalize_pending_update_by_run_id

                finalize_pending_update_by_run_id(
                    db,
                    pending_update_id=pending_update_id,
                    run=run_erro,
                )
        db.commit()
        raise
    finally:
        db.close()


def _coordenar_sincronizacao_zip(
    tipo_fonte: str,
    ano: int,
    task_id: str | None = None,
    force_reimport: bool = False,
    skip_probe: bool = False,
    pending_update_id: str | None = None,
) -> dict[str, Any]:
    import uuid

    from sqlalchemy import select

    from app.db.session import SessionLocal

    # Check dependency gate BEFORE pre-processing (downloading/extracting ZIPs)
    db_check = SessionLocal()
    try:
        from app.services.ingestion.dependencies import ensure_identity_graph_ready

        ensure_identity_graph_ready(db_check)
    finally:
        db_check.close()

    # 1. Run Phase 1
    phase1_res = pre_processar_sincronizacao_zip(
        tipo_fonte=tipo_fonte,
        ano=ano,
        task_id=task_id,
        force_reimport=force_reimport,
        skip_probe=skip_probe,
        pending_update_id=pending_update_id,
    )
    if phase1_res["status"] == "skipped":
        db = SessionLocal()
        try:
            from app.models.ingestion import IngestionRun
            from app.updates.lifecycle import finalize_pending_update_by_run_id

            stmt_run = select(IngestionRun).where(
                IngestionRun.execucao_sincronizacao_id
                == uuid.UUID(phase1_res["execucao_id"])
            )
            run = db.scalar(stmt_run)
            if finalize_pending_update_by_run_id(
                db,
                pending_update_id=pending_update_id,
                run=run,
            ):
                db.commit()
        finally:
            db.close()
        return phase1_res

    # 2. Run Phase 2
    return ingerir_sincronizacao_zip(
        execucao_id=uuid.UUID(phase1_res["execucao_id"]),
        force_reimport=force_reimport,
        pending_update_id=pending_update_id,
    )


def sincronizar_member_internal(
    db: Any,
    tipo_fonte: str,
    ano: int,
    member_name: str,
    parent_execucao_id: str,
    child_execucao_id: str,
    force_reimport: bool = False,
    task_id: str | None = None,
    task_retry_count: int = 0,
    max_retries: int = 0,
) -> dict[str, str]:
    import gc
    import uuid
    from collections import Counter
    from datetime import UTC, datetime
    from pathlib import Path

    from sqlalchemy import select

    from app.models.ingestion import IngestionRun
    from app.models.sincronizacao import ExecucaoSincronizacao
    from app.services.ingestion.artifact_store import build_artifact_metadata, describe_member_artifact
    from app.services.ingestion.file_manager import (
        compute_file_sha256,
        detect_encoding_and_delimiter,
        download_file_to_disk,
        extract_zip_member,
    )
    from app.services.ingestion.operational import (
        get_latest_phase_execution,
        record_phase_artifact,
        touch_parent_execution_heartbeat,
    )
    from app.services.ingestion.recovery import resolve_parent_ingestion_file
    from app.services.ingestion.staging import (
        create_run,
        get_member_payload,
        purge_member_success_rows,
        stage_csv_payload_streaming_from_disk,
        update_run_state,
    )

    execucao = db.get(ExecucaoSincronizacao, uuid.UUID(child_execucao_id))
    if execucao is None:
        raise ValueError(f"Execution not found: {child_execucao_id}")

    is_automatic_retry = task_retry_count > 0 and task_id is not None and execucao.id_tarefa == task_id
    if execucao.status in _STATUS_FINAL_EXECUCAO and not force_reimport and not (
        execucao.status == "falha" and is_automatic_retry
    ):
        if execucao.status == "cancelada":
            return _resultado_cancelado(execucao.id, "Execution was cancelled before member processing started.")
        _logger.warning(
            "Member task %s for execution %s already in terminal state '%s', skipping duplicate processing.",
            member_name,
            execucao.id,
            execucao.status,
        )
        return {"status": execucao.status, "execucao_id": str(execucao.id)}

    parent_execucao = db.get(ExecucaoSincronizacao, uuid.UUID(parent_execucao_id))
    if parent_execucao is None:
        raise ValueError(f"Parent execution not found: {parent_execucao_id}")
    if parent_execucao.status in ("cancelada", "falha") and not force_reimport:
        if execucao.status not in _STATUS_FINAL_EXECUCAO:
            execucao.status = parent_execucao.status
            execucao.finalizada_em = datetime.now(UTC)
            execucao.mensagem_erro = f"Execucao cancelada/abortada porque a sincronizacao pai terminou com status '{parent_execucao.status}'."
            db.commit()
        if parent_execucao.status == "cancelada":
            return _resultado_cancelado(execucao.id, "Parent execution was cancelled before member processing started.")
        return {"status": "falha", "execucao_id": str(execucao.id), "error": f"Parent execution {parent_execucao_id} failed."}

    if task_id:
        execucao.id_tarefa = task_id
    if is_automatic_retry:
        execucao.finalizada_em = None
        execucao.mensagem_erro = None
        execucao.total_linhas_lidas = 0
        execucao.total_inseridos = 0
        execucao.total_atualizados = 0
        execucao.total_inalterados = 0
        execucao.total_rejeitados = 0
    execucao.status = "em_execucao"
    execucao.finalizada_em = None

    run = db.scalar(
        select(IngestionRun).where(IngestionRun.execucao_sincronizacao_id == execucao.id)
    )
    if run is None:
        run = create_run(
            db,
            tipo_fonte=tipo_fonte,
            ano=ano,
            execucao_sincronizacao_id=execucao.id,
            requested_by_task_id=task_id,
            phase="acquire",
        )
        db.commit()
        db.refresh(run)
    else:
        run.requested_by_task_id = task_id or run.requested_by_task_id
        if is_automatic_retry:
            run.message = None
            run.quality_summary = None
            run.finished_at = None
        update_run_state(run, status="em_execucao", phase="stage")

    parent_run = db.scalar(
        select(IngestionRun)
        .where(IngestionRun.execucao_sincronizacao_id == parent_execucao.id)
        .order_by(IngestionRun.created_at.desc())
        .limit(1)
    )
    parent_execucao.status = "em_execucao"
    parent_execucao.finalizada_em = None
    if parent_run is not None:
        update_run_state(parent_run, status="em_execucao", phase="stage")
    touch_parent_execution_heartbeat(db, parent_execucao_id=parent_execucao.id)
    db.commit()

    try:
        ingestion_file = resolve_parent_ingestion_file(db, parent_execucao=parent_execucao)
        if ingestion_file is None:
            raise ValueError(
                f"IngestionFile not found for parent execution: {parent_execucao_id}. "
                "O arquivo principal precisa ser reprocessado primeiro."
            )

        # Check if member file exists locally, otherwise self-heal
        zip_dir = Path(_settings.storage_dir) / str(parent_execucao.id)
        member_path = zip_dir / "extracted" / member_name
        input_artifact: dict[str, Any] | None = None

        if not member_path.exists():
            try:
                payload = get_member_payload(db, execucao.id, member_name=member_name)
                member_path.parent.mkdir(parents=True, exist_ok=True)
                member_path.write_bytes(payload)
                input_artifact = describe_member_artifact(
                    execution_id=str(execucao.id),
                    member_name=member_name,
                )
            except ValueError:
                zip_path = zip_dir / parent_execucao.arquivo
                if not zip_path.exists():
                    download_file_to_disk(parent_execucao.url, str(zip_path), timeout=300)
                extract_zip_member(str(zip_path), member_name, str(zip_dir / "extracted"))
        if input_artifact is None:
            input_artifact = build_artifact_metadata(
                artifact_path=member_path,
                role="raw_member_extracted",
                content_type="text/csv",
                logical_name=member_name,
            )
        record_phase_artifact(db, run_id=run.id, direction="input", artifact=input_artifact)

        encoding, delimiter = detect_encoding_and_delimiter(str(member_path))
        member_sha256 = compute_file_sha256(str(member_path))
        member_size = member_path.stat().st_size

        row_kind = get_row_kind(tipo_fonte, ano, member_name)
        reconcile_required = False
        if tipo_fonte in ("dfp", "itr", "fre"):
            from app.services.ingestion.lifecycle import previous_member_snapshot

            reconcile_required = (
                previous_member_snapshot(
                    db,
                    tipo_fonte=tipo_fonte,
                    ano=ano,
                    current_run_id=run.id,
                    member_name=member_name,
                )
                is not None
            )

        header_map = {}
        if tipo_fonte in ("dfp", "itr", "fre", "fca"):
            header_map = _seed_member_reprocess_header_map(db, tipo_fonte=tipo_fonte, ano=ano)

        contadores = {
            "lidas": 0,
            "inseridos": 0,
            "atualizados": 0,
            "inalterados": 0,
            "rejeitados": 0,
            "members_invalid_schema": 0,
        }
        seen_by_row_kind: dict[str, Any] = {}

        financeiro_direct_path = (
            tipo_fonte in {"dfp", "itr"} and _settings.ingestion_financeiro_direct_path_enabled
        )

        if financeiro_direct_path:
            from app.services.ingestion.financeiro import process_financeiro_member_direct_from_disk

            quality_counters: dict[str, Any] = {
                "reason_counts": Counter(),
                "resolver_methods": Counter(),
                "top_quarantine_files": Counter(),
                "provisional_company_count": 0,
            }
            _, _, member = process_financeiro_member_direct_from_disk(
                db,
                execucao=execucao,
                run=run,
                ingestion_file=ingestion_file,
                file_path=str(member_path),
                member_name=member_name,
                row_kind=row_kind,
                member_sha256=member_sha256,
                member_size_bytes=member_size,
                encoding=encoding,
                delimiter=delimiter,
                reconcile_required=reconcile_required,
                prefixo=tipo_fonte,
                tipo_formulario=tipo_fonte.upper(),
                ano=ano,
                promote_enabled=_settings.ingestion_promote_enabled,
                contadores=contadores,
                quality_counters=quality_counters,
                seen_by_row_kind=seen_by_row_kind,
                header_map=header_map,
                chunk_size=_settings.ingestion_promote_batch_size,
            )
        else:
            member = stage_csv_payload_streaming_from_disk(
                db,
                ingestion_run=run,
                ingestion_file=ingestion_file,
                file_path=str(member_path),
                member_name=member_name,
                arquivo_origem=member_name,
                ano_origem=ano,
                row_kind=row_kind,
                member_sha256=member_sha256,
                member_size_bytes=member_size,
                encoding=encoding,
                delimiter=delimiter,
                chunk_size=_settings.ingestion_stage_batch_size,
            )
            db.commit()
            db.refresh(member)

        if tipo_fonte in ("dfp", "itr") and not financeiro_direct_path:
            from app.services.ingestion.financeiro import _process_financeiro_member

            quality_counters = {
                "reason_counts": Counter(),
                "resolver_methods": Counter(),
                "top_quarantine_files": Counter(),
                "provisional_company_count": 0,
            }
            _process_financeiro_member(
                db,
                execucao=execucao,
                run=run,
                member=member,
                reconcile_required=reconcile_required,
                prefixo=tipo_fonte,
                tipo_formulario=tipo_fonte.upper(),
                ano=ano,
                promote_enabled=_settings.ingestion_promote_enabled,
                contadores=contadores,
                quality_counters=quality_counters,
                seen_by_row_kind=seen_by_row_kind,
                header_map=header_map,
                chunk_size=_settings.ingestion_promote_batch_size,
            )
        elif tipo_fonte == "fre":
            from app.services.ingestion.fre import _process_fre_member
            _process_fre_member(
                db,
                execucao=execucao,
                run=run,
                ano=ano,
                member=member,
                reconcile_required=reconcile_required,
                promote_enabled=_settings.ingestion_promote_enabled,
                contadores=contadores,
                seen_by_row_kind=seen_by_row_kind,
                header_map=header_map,
                chunk_size=_settings.ingestion_promote_batch_size,
            )
        elif tipo_fonte == "fca":
            from app.services.ingestion.fca import _process_fca_member

            _process_fca_member(
                db,
                execucao=execucao,
                run=run,
                ano=ano,
                member=member,
                promote_enabled=_settings.ingestion_promote_enabled,
                contadores=contadores,
                seen_by_row_kind=seen_by_row_kind,
                header_map=header_map,
                chunk_size=_settings.ingestion_promote_batch_size,
            )
        elif tipo_fonte == "ipe":
            from app.services.ingestion.ipe import _process_ipe_member

            _process_ipe_member(
                db,
                execucao=execucao,
                run=run,
                ano=ano,
                member=member,
                promote_enabled=_settings.ingestion_promote_enabled,
                contadores=contadores,
                seen_by_row_kind=seen_by_row_kind,
                chunk_size=_settings.ingestion_promote_batch_size,
            )
        elif tipo_fonte == "vlmo":
            from app.services.ingestion.vlmo import _process_vlmo_member

            _process_vlmo_member(
                db,
                execucao=execucao,
                run=run,
                ano=ano,
                member=member,
                promote_enabled=_settings.ingestion_promote_enabled,
                contadores=contadores,
                seen_by_row_kind=seen_by_row_kind,
                chunk_size=_settings.ingestion_promote_batch_size,
            )
        elif tipo_fonte == "cgvn":
            from app.services.ingestion.cgvn import _process_cgvn_member

            _process_cgvn_member(
                db,
                execucao=execucao,
                run=run,
                ano=ano,
                member=member,
                promote_enabled=_settings.ingestion_promote_enabled,
                contadores=contadores,
                seen_by_row_kind=seen_by_row_kind,
                chunk_size=_settings.ingestion_promote_batch_size,
            )

        from app.services.ingestion.quality import enforce_quality_gate
        from app.services.ingestion.summary import build_contadores_quality_summary

        quality_summary = build_contadores_quality_summary(contadores)
        status_execucao, mensagem_status = enforce_quality_gate(
            quality_summary=quality_summary,
            require_rows=False,
        )

        execucao = db.get(ExecucaoSincronizacao, execucao.id)
        run = db.get(IngestionRun, run.id)

        execucao.status = status_execucao
        execucao.finalizada_em = datetime.now(UTC)
        execucao.total_linhas_lidas = contadores.get("lidas", 0)
        execucao.total_inseridos = contadores.get("inseridos", 0)
        execucao.total_atualizados = contadores.get("atualizados", 0)
        execucao.total_inalterados = contadores.get("inalterados", 0)
        execucao.total_rejeitados = contadores.get("rejeitados", 0)

        update_run_state(
            run,
            status=status_execucao,
            phase="complete",
            quality_summary=quality_summary,
            message=mensagem_status,
            finished_at=datetime.now(UTC),
        )
        document_file = f"{tipo_fonte}_cia_aberta_{ano}.csv"
        if status_execucao in {"sucesso", "sucesso_com_alerta"} and member_name != document_file:
            purge_member_success_rows(db, ingestion_file_member_id=member.id)
        touch_parent_execution_heartbeat(db, parent_execucao_id=parent_execucao.id)
        db.commit()
        db.expunge_all()
        gc.collect()
        return {"status": status_execucao, "execucao_id": str(execucao.id)}

    except Exception as exc:
        db.rollback()
        erro_retentavel = isinstance(exc, _AUTORETRY_FOR)
        retentativa_pendente = erro_retentavel and task_retry_count < max_retries
        execucao_erro = db.get(ExecucaoSincronizacao, execucao.id)
        if execucao_erro is not None:
            execucao_erro.status = "agendada" if retentativa_pendente else "falha"
            execucao_erro.mensagem_erro = str(exc)
            execucao_erro.finalizada_em = None if retentativa_pendente else datetime.now(UTC)
        run_erro = db.get(IngestionRun, run.id)
        if run_erro is not None:
            if retentativa_pendente:
                run_erro.finished_at = None
                update_run_state(run_erro, status="agendada", message=str(exc))
                phase_execution = get_latest_phase_execution(db, run_id=run_erro.id)
                if phase_execution is not None:
                    retry_at = datetime.now(UTC)
                    phase_execution.status = "failed_retryable"
                    phase_execution.finished_at = retry_at
                    phase_execution.heartbeat_at = retry_at
                    phase_execution.error_type = type(exc).__name__
                    phase_execution.error_message = str(exc)
                    phase_execution.error_retryable = True
                parent_erro = db.get(ExecucaoSincronizacao, parent_execucao.id)
                parent_run_erro = db.scalar(
                    select(IngestionRun)
                    .where(IngestionRun.execucao_sincronizacao_id == parent_execucao.id)
                    .order_by(IngestionRun.created_at.desc())
                    .limit(1)
                )
                if parent_erro is not None:
                    parent_erro.status = "aguardando_ingestao"
                    parent_erro.finalizada_em = None
                if parent_run_erro is not None:
                    update_run_state(
                        parent_run_erro,
                        status="aguardando_ingestao",
                        phase="stage",
                    )
            else:
                update_run_state(
                    run_erro,
                    status="falha",
                    phase="complete",
                    message=str(exc),
                    finished_at=datetime.now(UTC),
                )
                phase_execution = get_latest_phase_execution(db, run_id=run_erro.id)
                if phase_execution is not None:
                    phase_execution.error_type = type(exc).__name__
                    phase_execution.error_message = str(exc)
                    phase_execution.error_retryable = erro_retentavel
                touch_parent_execution_heartbeat(db, parent_execucao_id=parent_execucao.id)
        db.commit()
        if erro_retentavel:
            raise
        _logger.error("Member task %s failed permanently: %s", member_name, exc)
        return {"status": "falha", "execucao_id": str(execucao.id), "error": str(exc)}


@celery_app.task(bind=True, name="app.worker.tasks.sincronizar_member_task", **_RETRY_KWARGS)  # type: ignore[untyped-decorator]
def sincronizar_member_task(
    self: Any,
    tipo_fonte: str,
    ano: int,
    member_name: str,
    parent_execucao_id: str,
    child_execucao_id: str,
    force_reimport: bool = False,
    _queue_item_id: str | None = None,
    _queue_reservation_token: str | None = None,
) -> dict[str, str]:
    def operation() -> dict[str, str]:
        db = SessionLocal()
        try:
            return sincronizar_member_internal(
                db=db,
                tipo_fonte=tipo_fonte,
                ano=ano,
                member_name=member_name,
                parent_execucao_id=parent_execucao_id,
                child_execucao_id=child_execucao_id,
                force_reimport=force_reimport,
                task_id=str(self.request.id),
                task_retry_count=int(self.request.retries),
                max_retries=_settings.ingestion_max_retries,
            )
        finally:
            db.close()

    return cast(dict[str, str], _executar_com_reserva(
        self,
        queue_item_id=_queue_item_id,
        reservation_token=_queue_reservation_token,
        task_name=self.name,
        task_args=[],
        task_kwargs={
            "tipo_fonte": tipo_fonte,
            "ano": ano,
            "member_name": member_name,
            "parent_execucao_id": parent_execucao_id,
            "child_execucao_id": child_execucao_id,
            "force_reimport": force_reimport,
        },
        operation=operation,
        execution_id=child_execucao_id,
        kind="csv",
    ))


@celery_app.task(bind=True, name="app.worker.tasks.disparar_dependentes_task", **_RETRY_KWARGS)  # type: ignore[untyped-decorator]
def disparar_dependentes_task(
    self: Any,
    parent_execucao_id: str,
    force_reimport: bool = False,
    pending_update_id: str | None = None,
) -> dict[str, str]:
    # A transicao do ZIP para os members e persistida antes que o escalonador libere a vaga.
    import uuid

    from app.models.sincronizacao import ExecucaoSincronizacao
    from app.services.ingestion.queue import (
        _control_lock,
        _ensure_child_items,
        adicionar_execucao_a_fila,
        criar_lote,
        db_item_for_execution,
    )

    db = SessionLocal()
    try:
        parent = db.get(ExecucaoSincronizacao, uuid.UUID(parent_execucao_id))
        if parent is None:
            raise ValueError(f"Parent execution not found: {parent_execucao_id}")
        _control_lock(db)
        if parent.status in ("falha", "cancelada"):
            return {"status": parent.status, "parent_execucao_id": parent_execucao_id}
        parent_item = db_item_for_execution(db, parent.id)
        if parent_item is None:
            # Drain callbacks from work admitted before the durable queue was enabled.
            batch = criar_lote(
                db,
                source="legacy_transition",
                metadata={"parent_execucao_id": parent_execucao_id},
            )
            parent_item = adicionar_execucao_a_fila(
                db,
                batch=batch,
                execucao=parent,
                task_name=self.name,
                args=[parent_execucao_id],
                kwargs={"force_reimport": force_reimport, "pending_update_id": pending_update_id},
                kind="continuation",
            )
            parent_item.status = "completed"
            parent_item.reason_code = "transicao_legada_aplicada"
        admitted = _ensure_child_items(db, parent, parent_item.batch_id)
        db.commit()
        despachar_fila_ingestao_task.delay()
        return {
            "status": "queued",
            "parent_execucao_id": parent_execucao_id,
            "members_admitted": str(admitted),
        }
    finally:
        db.close()


def _resumir_falhas_membros(
    children: Sequence[Any],
    *,
    statuses: tuple[str, ...],
    label: str,
) -> str:
    selected = [child for child in children if child.status in statuses]
    details: list[str] = []
    for child in selected[:5]:
        first_line = (child.mensagem_erro or "erro sem detalhes").splitlines()[0].strip()
        if len(first_line) > 180:
            first_line = f"{first_line[:177]}..."
        details.append(f"{child.arquivo}: {first_line}")
    remaining = len(selected) - len(details)
    suffix = f"; mais {remaining} membro(s)" if remaining > 0 else ""
    return (
        f"{label} ({len(selected)} membro(s)): {'; '.join(details)}{suffix}. "
        "Consulte as execucoes filhas para obter os detalhes completos."
    )


@celery_app.task(bind=True, name="app.worker.tasks.finalizar_sincronizacao_zip_task", **_RETRY_KWARGS)  # type: ignore[untyped-decorator]
def finalizar_sincronizacao_zip_task(
    self: Any,
    parent_execucao_id: str,
    pending_update_id: str | None = None,
    _queue_item_id: str | None = None,
    _queue_reservation_token: str | None = None,
) -> dict[str, Any]:
    import uuid
    from datetime import UTC, datetime
    from pathlib import Path

    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.models.financeiro import DemonstracaoFinanceira
    from app.models.ingestion import IngestionFile, IngestionRun
    from app.models.sincronizacao import ExecucaoSincronizacao
    from app.services.ingestion.staging import purge_member_success_rows, update_run_state

    if _queue_item_id is None or _queue_reservation_token is None:
        return _capturar_na_fila(
            self,
            task_name=self.name,
            task_args=[parent_execucao_id],
            task_kwargs={"pending_update_id": pending_update_id},
            execution_id=parent_execucao_id,
            kind="continuation",
        )
    if not _iniciar_reserva(_queue_item_id, _queue_reservation_token):
        despachar_fila_ingestao_task.delay()
        return {"status": "stale_reservation", "parent_execucao_id": parent_execucao_id}

    db = SessionLocal()
    try:
        parent_uuid = uuid.UUID(parent_execucao_id)
        execucao = db.get(ExecucaoSincronizacao, parent_uuid)
        if execucao is None:
            raise ValueError(f"Execution not found: {parent_execucao_id}")

        children = db.scalars(
            select(ExecucaoSincronizacao)
            .where(ExecucaoSincronizacao.parent_execucao_id == parent_uuid)
        ).all()

        total_lidas = sum(c.total_linhas_lidas or 0 for c in children)
        total_inseridos = sum(c.total_inseridos or 0 for c in children)
        total_atualizados = sum(c.total_atualizados or 0 for c in children)
        total_inalterados = sum(c.total_inalterados or 0 for c in children)
        total_rejeitados = sum(c.total_rejeitados or 0 for c in children)

        child_statuses = {c.status for c in children}
        if execucao.status == "cancelada":
            parent_status = "cancelada"
            message = execucao.mensagem_erro or "Sincronizacao cancelada manualmente."
        elif "falha" in child_statuses or "quality_fail" in child_statuses:
            parent_status = "falha"
            message = _resumir_falhas_membros(
                children,
                statuses=("falha", "quality_fail"),
                label="Membros com falha",
            )
        elif "em_execucao" in child_statuses or "agendada" in child_statuses:
            parent_status = "falha"
            message = _resumir_falhas_membros(
                children,
                statuses=("em_execucao", "agendada"),
                label="Tempo limite; membros sem conclusao",
            )
        else:
            parent_status = "sucesso"
            message = "Todos os arquivos membros foram processados com sucesso."

        execucao.total_linhas_lidas = total_lidas
        execucao.total_inseridos = total_inseridos
        execucao.total_atualizados = total_atualizados
        execucao.total_inalterados = total_inalterados
        execucao.total_rejeitados = total_rejeitados
        execucao.status = parent_status
        if parent_status == "falha":
            execucao.mensagem_erro = message
        execucao.finalizada_em = datetime.now(UTC)

        child_run_map = {
            child_run.execucao_sincronizacao_id: child_run
            for child_run in db.scalars(
                select(IngestionRun).where(
                    IngestionRun.execucao_sincronizacao_id.in_([child.id for child in children])
                )
            ).all()
        }
        members_reused_from_previous = 0
        members_reused_from_failed_parent = 0
        for child in children:
            child_run = child_run_map.get(child.id)
            if child_run is None:
                continue
            child_quality = child_run.quality_summary or {}
            if child_quality.get("skip_reason") != "member_sha256_reused":
                continue
            members_reused_from_previous += 1
            if child_quality.get("reused_from_failed_parent") is True:
                members_reused_from_failed_parent += 1

        quality_summary = {
            "row_status_counts": {
                "valid": total_inseridos + total_atualizados + total_inalterados,
                "invalid": total_rejeitados,
            },
            "members_total": len(children),
            "members_processados": sum(1 for c in children if c.status != "skipped"),
            "members_skipped": sum(1 for c in children if c.status == "skipped"),
            "members_reprocessed": sum(1 for c in children if c.status != "skipped"),
            "members_reused_from_previous": members_reused_from_previous,
            "members_reused_from_failed_parent": members_reused_from_failed_parent,
        }

        parent_runs = list(
            db.scalars(
                select(IngestionRun)
                .where(IngestionRun.execucao_sincronizacao_id == execucao.id)
                .order_by(IngestionRun.created_at.desc())
            ).all()
        )
        run = parent_runs[0] if parent_runs else None
        now_done = datetime.now(UTC)
        for prun in parent_runs:
            update_run_state(
                prun,
                status=parent_status,
                phase="complete",
                message=message,
                quality_summary=quality_summary,
                finished_at=now_done,
            )

        from app.updates.lifecycle import finalize_pending_update_by_run_id

        finalize_pending_update_by_run_id(
            db,
            pending_update_id=pending_update_id,
            run=run,
        )

        from app.models.ingestion import IngestionFileMember

        parent_run = db.scalar(
            select(IngestionRun).where(IngestionRun.execucao_sincronizacao_id == execucao.id)
        )
        if parent_run is not None:
            ingestion_file = db.scalar(
                select(IngestionFile)
                .where(IngestionFile.ingestion_run_id == parent_run.id)
            )
            if ingestion_file is not None:
                members = db.scalars(
                    select(IngestionFileMember).where(IngestionFileMember.ingestion_file_id == ingestion_file.id)
                ).all()
                for member in members:
                    purge_member_success_rows(db, ingestion_file_member_id=member.id)

        db.commit()

        if parent_status == "sucesso" and execucao.tipo_fonte in {"dfp", "itr"}:
            codigos_cvm = db.scalars(
                select(DemonstracaoFinanceira.codigo_cvm)
                .where(
                    DemonstracaoFinanceira.tipo_formulario == execucao.tipo_fonte.upper(),
                    DemonstracaoFinanceira.ano_origem == execucao.ano,
                    DemonstracaoFinanceira.codigo_cvm.is_not(None),
                )
                .distinct()
            ).all()
            codigos_validos = sorted({codigo_cvm for codigo_cvm in codigos_cvm if codigo_cvm is not None})
            if codigos_validos:
                from app.services.analise import criar_materializacao_campanha

                criar_materializacao_campanha(
                    db,
                    codigos_cvm=codigos_validos,
                    source="post_ingestion",
                    source_execucao_id=str(execucao.id),
                )
                _disparar_dispatcher_materializacao()

        zip_dir = Path(_settings.storage_dir) / str(execucao.id)
        import shutil
        try:
            shutil.rmtree(zip_dir)
        except Exception:
            pass

        result = {
            "execucao_id": str(execucao.id),
            "status": parent_status,
            "total_linhas_lidas": total_lidas,
            "total_inseridos": total_inseridos,
            "total_atualizados": total_atualizados,
            "total_inalterados": total_inalterados,
            "total_rejeitados": total_rejeitados,
        }
        _concluir_reserva(_queue_item_id, _queue_reservation_token)
        return result
    except Exception as exc:
        _liberar_reserva(
            _queue_item_id,
            _queue_reservation_token,
            str(exc),
            retryable=isinstance(exc, _AUTORETRY_FOR),
        )
        raise
    finally:
        db.close()


@celery_app.task(bind=True, name="app.worker.tasks.sincronizar_dfp_task", **_RETRY_KWARGS)  # type: ignore[untyped-decorator]
def sincronizar_dfp_task(
    self: Any,
    ano: int,
    force_reimport: bool = False,
    skip_probe: bool = False,
    pending_update_id: str | None = None,
    _queue_item_id: str | None = None,
    _queue_reservation_token: str | None = None,
) -> dict[str, str]:
    return cast(dict[str, str], _executar_com_reserva(
        self,
        queue_item_id=_queue_item_id,
        reservation_token=_queue_reservation_token,
        task_name=self.name,
        task_args=[ano],
        task_kwargs={"force_reimport": force_reimport, "skip_probe": skip_probe, "pending_update_id": pending_update_id},
        operation=lambda: _resultado_zip_enfileirado(
            tipo_fonte="dfp", ano=ano, task_id=str(self.request.id), force_reimport=force_reimport,
            skip_probe=skip_probe, pending_update_id=pending_update_id,
        ),
        kind="zip_prepare",
    ))


def _resultado_zip_enfileirado(
    *, tipo_fonte: str, ano: int, task_id: str, force_reimport: bool, skip_probe: bool,
    pending_update_id: str | None,
) -> dict[str, str]:
    resultado = _coordenar_sincronizacao_zip(
        tipo_fonte=tipo_fonte, ano=ano, task_id=task_id, force_reimport=force_reimport,
        skip_probe=skip_probe, pending_update_id=pending_update_id,
    )
    return {"status": str(resultado["status"]), "execucao_id": str(resultado["execucao_id"])}


@celery_app.task(bind=True, name="app.worker.tasks.sincronizar_itr_task", **_RETRY_KWARGS)  # type: ignore[untyped-decorator]
def sincronizar_itr_task(
    self: Any,
    ano: int,
    force_reimport: bool = False,
    skip_probe: bool = False,
    pending_update_id: str | None = None,
    _queue_item_id: str | None = None,
    _queue_reservation_token: str | None = None,
) -> dict[str, str]:
    return cast(dict[str, str], _executar_com_reserva(
        self, queue_item_id=_queue_item_id, reservation_token=_queue_reservation_token,
        task_name=self.name, task_args=[ano],
        task_kwargs={"force_reimport": force_reimport, "skip_probe": skip_probe, "pending_update_id": pending_update_id},
        operation=lambda: _resultado_zip_enfileirado(
            tipo_fonte="itr", ano=ano, task_id=str(self.request.id), force_reimport=force_reimport,
            skip_probe=skip_probe, pending_update_id=pending_update_id,
        ), kind="zip_prepare",
    ))


@celery_app.task(bind=True, name="app.worker.tasks.sincronizar_fre_task", **_RETRY_KWARGS)  # type: ignore[untyped-decorator]
def sincronizar_fre_task(
    self: Any,
    ano: int,
    force_reimport: bool = False,
    skip_probe: bool = False,
    pending_update_id: str | None = None,
    _queue_item_id: str | None = None,
    _queue_reservation_token: str | None = None,
) -> dict[str, str]:
    return cast(dict[str, str], _executar_com_reserva(
        self, queue_item_id=_queue_item_id, reservation_token=_queue_reservation_token,
        task_name=self.name, task_args=[ano],
        task_kwargs={"force_reimport": force_reimport, "skip_probe": skip_probe, "pending_update_id": pending_update_id},
        operation=lambda: _resultado_zip_enfileirado(
            tipo_fonte="fre", ano=ano, task_id=str(self.request.id), force_reimport=force_reimport,
            skip_probe=skip_probe, pending_update_id=pending_update_id,
        ), kind="zip_prepare",
    ))


@celery_app.task(bind=True, name="app.worker.tasks.sincronizar_fca_task", **_RETRY_KWARGS)  # type: ignore[untyped-decorator]
def sincronizar_fca_task(
    self: Any,
    ano: int,
    force_reimport: bool = False,
    skip_probe: bool = False,
    pending_update_id: str | None = None,
    _queue_item_id: str | None = None,
    _queue_reservation_token: str | None = None,
) -> dict[str, str]:
    return cast(dict[str, str], _executar_com_reserva(
        self, queue_item_id=_queue_item_id, reservation_token=_queue_reservation_token,
        task_name=self.name, task_args=[ano],
        task_kwargs={"force_reimport": force_reimport, "skip_probe": skip_probe, "pending_update_id": pending_update_id},
        operation=lambda: _resultado_zip_enfileirado(
            tipo_fonte="fca", ano=ano, task_id=str(self.request.id), force_reimport=force_reimport,
            skip_probe=skip_probe, pending_update_id=pending_update_id,
        ), kind="zip_prepare",
    ))


@celery_app.task(bind=True, name="app.worker.tasks.sincronizar_ipe_task", **_RETRY_KWARGS)  # type: ignore[untyped-decorator]
def sincronizar_ipe_task(
    self: Any,
    ano: int,
    force_reimport: bool = False,
    skip_probe: bool = False,
    pending_update_id: str | None = None,
    _queue_item_id: str | None = None,
    _queue_reservation_token: str | None = None,
) -> dict[str, str]:
    return cast(dict[str, str], _executar_com_reserva(
        self, queue_item_id=_queue_item_id, reservation_token=_queue_reservation_token,
        task_name=self.name, task_args=[ano],
        task_kwargs={"force_reimport": force_reimport, "skip_probe": skip_probe, "pending_update_id": pending_update_id},
        operation=lambda: _resultado_zip_enfileirado(
            tipo_fonte="ipe", ano=ano, task_id=str(self.request.id), force_reimport=force_reimport,
            skip_probe=skip_probe, pending_update_id=pending_update_id,
        ), kind="zip_prepare",
    ))


@celery_app.task(bind=True, name="app.worker.tasks.sincronizar_vlmo_task", **_RETRY_KWARGS)  # type: ignore[untyped-decorator]
def sincronizar_vlmo_task(
    self: Any,
    ano: int,
    force_reimport: bool = False,
    skip_probe: bool = False,
    pending_update_id: str | None = None,
    _queue_item_id: str | None = None,
    _queue_reservation_token: str | None = None,
) -> dict[str, str]:
    return cast(dict[str, str], _executar_com_reserva(
        self, queue_item_id=_queue_item_id, reservation_token=_queue_reservation_token,
        task_name=self.name, task_args=[ano],
        task_kwargs={"force_reimport": force_reimport, "skip_probe": skip_probe, "pending_update_id": pending_update_id},
        operation=lambda: _resultado_zip_enfileirado(
            tipo_fonte="vlmo", ano=ano, task_id=str(self.request.id), force_reimport=force_reimport,
            skip_probe=skip_probe, pending_update_id=pending_update_id,
        ), kind="zip_prepare",
    ))


@celery_app.task(bind=True, name="app.worker.tasks.sincronizar_cgvn_task", **_RETRY_KWARGS)  # type: ignore[untyped-decorator]
def sincronizar_cgvn_task(
    self: Any,
    ano: int,
    force_reimport: bool = False,
    skip_probe: bool = False,
    pending_update_id: str | None = None,
    _queue_item_id: str | None = None,
    _queue_reservation_token: str | None = None,
) -> dict[str, str]:
    return cast(dict[str, str], _executar_com_reserva(
        self, queue_item_id=_queue_item_id, reservation_token=_queue_reservation_token,
        task_name=self.name, task_args=[ano],
        task_kwargs={"force_reimport": force_reimport, "skip_probe": skip_probe, "pending_update_id": pending_update_id},
        operation=lambda: _resultado_zip_enfileirado(
            tipo_fonte="cgvn", ano=ano, task_id=str(self.request.id), force_reimport=force_reimport,
            skip_probe=skip_probe, pending_update_id=pending_update_id,
        ), kind="zip_prepare",
    ))


@celery_app.task(bind=True, name="app.worker.tasks.sincronizar_fii_task", **_RETRY_KWARGS)  # type: ignore[untyped-decorator]
def sincronizar_fii_task(
    self: Any,
    ano: int,
    force_reimport: bool = False,
    _queue_item_id: str | None = None,
    _queue_reservation_token: str | None = None,
) -> dict[str, Any]:
    return _executar_com_reserva(
        self,
        queue_item_id=_queue_item_id,
        reservation_token=_queue_reservation_token,
        task_name=self.name,
        task_args=[ano],
        task_kwargs={"force_reimport": force_reimport},
        operation=lambda: _processar_fii_enfileirado(
            ano=ano,
            task_id=str(self.request.id),
            force_reimport=force_reimport,
        ),
        kind="zip_prepare",
    )


def _processar_fii_enfileirado(*, ano: int, task_id: str, force_reimport: bool) -> dict[str, Any]:
    from app.services.ingestion.fii import processar_informe_fii

    return processar_informe_fii(ano=ano, task_id=task_id, force_reimport=force_reimport)


@celery_app.task(name="app.worker.tasks.agendar_ingestao_fii_semanal_task")  # type: ignore[untyped-decorator]
def agendar_ingestao_fii_semanal_task() -> dict[str, Any]:
    from app.services.ingestion.fii import agendar_ingestao_semanal_fii

    resultado = agendar_ingestao_semanal_fii()
    if resultado.get("anos_enfileirados"):
        despachar_fila_ingestao_task.delay()
    return resultado


@celery_app.task(bind=True, name="app.worker.tasks.pre_processar_sincronizacao_task", **_RETRY_KWARGS)  # type: ignore[untyped-decorator]
def pre_processar_sincronizacao_task(
    self: Any,
    tipo_fonte: str,
    ano: int | None = None,
    force_reimport: bool = False,
    _queue_item_id: str | None = None,
    _queue_reservation_token: str | None = None,
) -> dict[str, Any]:
    return _executar_com_reserva(
        self, queue_item_id=_queue_item_id, reservation_token=_queue_reservation_token,
        task_name=self.name, task_args=[],
        task_kwargs={"tipo_fonte": tipo_fonte, "ano": ano, "force_reimport": force_reimport},
        operation=lambda: _pre_processar_sincronizacao_operacao(
            self, tipo_fonte=tipo_fonte, ano=ano, force_reimport=force_reimport,
        ), kind="zip_prepare" if tipo_fonte != "cadastro" else "cadastro",
    )


def _pre_processar_sincronizacao_operacao(
    task_self: Any, *, tipo_fonte: str, ano: int | None, force_reimport: bool
) -> dict[str, Any]:
    from app.db.session import SessionLocal
    db = SessionLocal()
    try:
        if tipo_fonte == "cadastro":
            from app.models.sincronizacao import ExecucaoSincronizacao
            from app.services.ingestion.cadastro import (
                ARQUIVO_CADASTRO_ABERTA,
                ARQUIVO_CADASTRO_ESTRANGEIRA,
                pre_processar_cadastro,
            )
            from app.services.ingestion.resolver import limpar_caches_resolver
            limpar_caches_resolver()
            settings = get_settings()
            url_aberta = f"{settings.cvm_base_url}/CIA_ABERTA/CAD/DADOS/{ARQUIVO_CADASTRO_ABERTA}"
            url_estrang = f"{settings.cvm_base_url}/CIA_ESTRANG/CAD/DADOS/{ARQUIVO_CADASTRO_ESTRANGEIRA}"
            execucao = db.scalar(
                select(ExecucaoSincronizacao).where(
                    ExecucaoSincronizacao.id_tarefa == str(task_self.request.id)
                ).limit(1)
            )
            if execucao is None:
                execucao = ExecucaoSincronizacao(
                    tipo_fonte="cadastro", ano=None, id_tarefa=str(task_self.request.id),
                    arquivo=f"{ARQUIVO_CADASTRO_ABERTA}+{ARQUIVO_CADASTRO_ESTRANGEIRA}",
                    url=f"{url_aberta}|{url_estrang}", status="em_execucao",
                )
                db.add(execucao)
                db.commit()
                db.refresh(execucao)
            resultado = pre_processar_cadastro(
                db, execucao_id=execucao.id, task_id=str(task_self.request.id), force_reimport=force_reimport,
            )
        else:
            if ano is None:
                raise ValueError(f"Ano obrigatorio para pre-processar {tipo_fonte.upper()}.")
            resultado = pre_processar_sincronizacao_zip(
                tipo_fonte=tipo_fonte, ano=ano, task_id=str(task_self.request.id), force_reimport=force_reimport,
            )
        return {"status": str(resultado["status"]), "execucao_id": str(resultado["execucao_id"])}
    finally:
        db.close()


@celery_app.task(bind=True, name="app.worker.tasks.ingerir_sincronizacao_task", **_RETRY_KWARGS)  # type: ignore[untyped-decorator]
def ingerir_sincronizacao_task(
    self: Any,
    execucao_id: str,
    force_reimport: bool = False,
    _queue_item_id: str | None = None,
    _queue_reservation_token: str | None = None,
) -> dict[str, Any]:
    return _executar_com_reserva(
        self, queue_item_id=_queue_item_id, reservation_token=_queue_reservation_token,
        task_name=self.name, task_args=[],
        task_kwargs={"execucao_id": execucao_id, "force_reimport": force_reimport},
        execution_id=execucao_id,
        operation=lambda: _ingerir_sincronizacao_operacao(self, execucao_id=execucao_id, force_reimport=force_reimport),
        kind="continuation",
    )


def _ingerir_sincronizacao_operacao(task_self: Any, *, execucao_id: str, force_reimport: bool) -> dict[str, Any]:
    from app.db.session import SessionLocal
    from app.models.sincronizacao import ExecucaoSincronizacao
    from app.services.ingestion.cadastro import ingerir_cadastro
    db = SessionLocal()
    try:
        execucao = db.get(ExecucaoSincronizacao, uuid.UUID(execucao_id))
        if execucao is None:
            raise ValueError(f"Execucao nao encontrada: {execucao_id}")
        if execucao.status != "aguardando_ingestao":
            raise ValueError(f"Execucao deve estar aguardando_ingestao; status atual: {execucao.status}")
        if execucao.tipo_fonte == "cadastro":
            return ingerir_cadastro(db, execucao_id=execucao.id)
        return ingerir_sincronizacao_zip(execucao_id=execucao.id, force_reimport=force_reimport)
    finally:
        db.close()
