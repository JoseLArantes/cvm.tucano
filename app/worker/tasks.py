import uuid
from typing import Any

import httpx
import sqlalchemy.exc

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.ingestion.cadastro import sincronizar_cadastro_companhias
from app.services.ingestion.retry import DependencyNotReady, RetryableHttpStatus, RetryableIngestionError
from app.worker.celery_app import celery_app

_settings = get_settings()
_RETRY_KWARGS = {
    "autoretry_for": (
        httpx.TimeoutException,
        httpx.TransportError,
        RetryableIngestionError,
        RetryableHttpStatus,
        DependencyNotReady,
        sqlalchemy.exc.OperationalError,
        sqlalchemy.exc.InterfaceError,
    ),
    "retry_backoff": True,
    "retry_backoff_max": _settings.ingestion_retry_backoff_max_seconds,
    "retry_jitter": True,
    "max_retries": _settings.ingestion_max_retries,
}

_STATUS_FINAL_EXECUCAO = {"sucesso", "sem_alteracao", "skipped", "falha", "cancelada"}


def _resultado_cancelado(execucao_id: Any, message: str) -> dict[str, Any]:
    return {"execucao_id": str(execucao_id), "status": "cancelada", "message": message}


@celery_app.task(bind=True, name="app.worker.tasks.sincronizar_cadastro_companhias_task", **_RETRY_KWARGS)  # type: ignore[untyped-decorator]
def sincronizar_cadastro_companhias_task(self: Any, force_reimport: bool = False) -> dict[str, str]:
    db = SessionLocal()
    try:
        resultado = sincronizar_cadastro_companhias(db, task_id=str(self.request.id), force_reimport=force_reimport)
        return {"status": str(resultado["status"]), "execucao_id": str(resultado["execucao_id"])}
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
) -> dict[str, Any]:
    from datetime import UTC, datetime
    from pathlib import Path

    from app.models.ingestion import IngestionRun
    from app.models.sincronizacao import ExecucaoSincronizacao
    from app.services.ingestion.dedup import buscar_execucao_hash_existente
    from app.services.ingestion.file_manager import (
        compute_file_sha256,
        count_csv_rows,
        detect_encoding_and_delimiter,
        download_file_to_disk,
        extract_zip_member,
        get_csv_header,
    )
    from app.services.ingestion.staging import (
        create_run,
        member_has_successful_match,
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

    execucao = ExecucaoSincronizacao(
        tipo_fonte=tipo_fonte,
        ano=ano,
        id_tarefa=task_id,
        arquivo=arquivo_zip,
        url=url,
        status="em_execucao",
        tipo_execucao="arquivo_zip",
    )
    db.add(execucao)
    db.commit()
    db.refresh(execucao)

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

    zip_dir = Path(settings.storage_dir) / str(execucao.id)
    zip_path = zip_dir / arquivo_zip

    try:
        hash_arquivo = download_file_to_disk(url, str(zip_path), timeout=300)
        execucao.hash_arquivo = hash_arquivo

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
            raise ValueError(f"arquivo_nao_esperado_ausente: {','.join(faltando)}")

        extracted_dir = zip_dir / "extracted"

        supported_member_names = {
            item.render_member_name(ano=ano)
            for item in datasets
            if item.status_suporte == "suportado"
        }

        for member_name in ordered_members:
            # Extract to disk
            extracted_path = extract_zip_member(str(zip_path), member_name, str(extracted_dir))
            member_hash = compute_file_sha256(extracted_path)
            member_size = Path(extracted_path).stat().st_size
            member_payload = Path(extracted_path).read_bytes()

            # Check if supported
            if member_name not in supported_member_names:
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
                save_member_payload(db, child_exec.id, member_payload)
                db.flush()
                continue

            # Check match
            if member_has_successful_match(
                db,
                tipo_fonte=tipo_fonte,
                ano=ano,
                member_name=member_name,
                member_sha256=member_hash,
                current_run_id=run.id,
            ) and not force_reimport:
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
                save_member_payload(db, child_exec.id, member_payload)
                db.flush()
                continue

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
            save_member_payload(db, child_exec.id, member_payload)
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
) -> dict[str, Any]:
    from datetime import UTC, datetime

    from celery import chain
    from sqlalchemy import select

    from app.models.ingestion import IngestionRun
    from app.models.sincronizacao import ExecucaoSincronizacao
    from app.services.ingestion.dependencies import ensure_identity_graph_ready
    from app.services.ingestion.resolver import limpar_caches_resolver
    from app.services.ingestion.staging import update_run_state

    db = SessionLocal()
    settings = get_settings()
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

    execucao.status = "em_execucao"
    run = db.scalar(
        select(IngestionRun).where(IngestionRun.execucao_sincronizacao_id == execucao.id)
    )
    if run is not None:
        update_run_state(run, status="em_execucao", phase="stage")
    db.commit()

    try:
        children = db.scalars(
            select(ExecucaoSincronizacao)
            .where(ExecucaoSincronizacao.parent_execucao_id == execucao.id)
        ).all()

        doc_tasks_to_dispatch = []
        document_file = f"{execucao.tipo_fonte}_cia_aberta_{execucao.ano}.csv"

        for c in children:
            if c.status == "skipped":
                continue

            # Transition child to agendada
            c.status = "agendada"
            child_run = db.scalar(
                select(IngestionRun).where(IngestionRun.execucao_sincronizacao_id == c.id)
            )
            if child_run is not None:
                update_run_state(child_run, status="em_execucao", phase="stage")

            if c.arquivo == document_file:
                doc_tasks_to_dispatch.append({
                    "child_execucao_id": str(c.id),
                    "member_name": c.arquivo,
                })

        db.commit()

        if doc_tasks_to_dispatch:
            header_task = sincronizar_member_task.si(
                tipo_fonte=execucao.tipo_fonte,
                ano=execucao.ano,
                member_name=doc_tasks_to_dispatch[0]["member_name"],
                parent_execucao_id=str(execucao.id),
                child_execucao_id=doc_tasks_to_dispatch[0]["child_execucao_id"],
                force_reimport=force_reimport,
            )
            dispatch_dependents = disparar_dependentes_task.si(
                parent_execucao_id=str(execucao.id),
                force_reimport=force_reimport,
            )
            workflow = chain(header_task, dispatch_dependents)
            workflow.delay()
        else:
            disparar_dependentes_task.delay(
                parent_execucao_id=str(execucao.id),
                force_reimport=force_reimport,
            )

        return {
            "execucao_id": str(execucao.id),
            "status": "em_execucao",
            "message": "Celery workflow started asynchronously.",
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
        db.commit()
        raise
    finally:
        db.close()


def _coordenar_sincronizacao_zip(
    tipo_fonte: str,
    ano: int,
    task_id: str | None = None,
    force_reimport: bool = False,
) -> dict[str, Any]:
    import uuid

    # 1. Run Phase 1
    phase1_res = pre_processar_sincronizacao_zip(
        tipo_fonte=tipo_fonte,
        ano=ano,
        task_id=task_id,
        force_reimport=force_reimport,
    )
    if phase1_res["status"] == "skipped":
        return phase1_res

    # 2. Run Phase 2
    return ingerir_sincronizacao_zip(
        execucao_id=uuid.UUID(phase1_res["execucao_id"]),
        force_reimport=force_reimport,
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
) -> dict[str, str]:
    import gc
    import uuid
    from collections import Counter
    from datetime import UTC, datetime
    from pathlib import Path

    from sqlalchemy import select

    from app.models.ingestion import IngestionFile, IngestionRun
    from app.models.sincronizacao import ExecucaoSincronizacao
    from app.services.ingestion.file_manager import (
        compute_file_sha256,
        detect_encoding_and_delimiter,
        download_file_to_disk,
        extract_zip_member,
    )
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

    if execucao.status == "cancelada":
        return _resultado_cancelado(execucao.id, "Execution was cancelled before member processing started.")

    parent_execucao = db.get(ExecucaoSincronizacao, uuid.UUID(parent_execucao_id))
    if parent_execucao is None:
        raise ValueError(f"Parent execution not found: {parent_execucao_id}")
    if parent_execucao.status == "cancelada":
        if execucao.status not in _STATUS_FINAL_EXECUCAO:
            execucao.status = "cancelada"
            execucao.finalizada_em = datetime.now(UTC)
            execucao.mensagem_erro = "Execucao cancelada porque a sincronizacao pai foi cancelada."
            db.commit()
        return _resultado_cancelado(execucao.id, "Parent execution was cancelled before member processing started.")

    if task_id:
        execucao.id_tarefa = task_id
    execucao.status = "em_execucao"
    db.commit()

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

    ingestion_file = db.scalar(
        select(IngestionFile)
        .join(IngestionRun)
        .where(IngestionRun.execucao_sincronizacao_id == parent_execucao.id)
    )
    if ingestion_file is None:
        raise ValueError(f"IngestionFile not found for parent execution: {parent_execucao_id}")

    try:
        # Check if member file exists locally, otherwise self-heal
        zip_dir = Path(_settings.storage_dir) / str(parent_execucao.id)
        member_path = zip_dir / "extracted" / member_name

        if not member_path.exists():
            try:
                payload = get_member_payload(db, execucao.id)
                member_path.parent.mkdir(parents=True, exist_ok=True)
                member_path.write_bytes(payload)
            except ValueError:
                zip_path = zip_dir / parent_execucao.arquivo
                if not zip_path.exists():
                    download_file_to_disk(parent_execucao.url, str(zip_path), timeout=300)
                extract_zip_member(str(zip_path), member_name, str(zip_dir / "extracted"))

        encoding, delimiter = detect_encoding_and_delimiter(str(member_path))
        member_sha256 = compute_file_sha256(str(member_path))
        member_size = member_path.stat().st_size

        row_kind = get_row_kind(tipo_fonte, ano, member_name)

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
            header_map = rebuild_header_map(db, parent_execucao.id)

        contadores = {
            "lidas": 0,
            "inseridos": 0,
            "atualizados": 0,
            "inalterados": 0,
            "rejeitados": 0,
            "members_invalid_schema": 0,
        }
        seen_by_row_kind: dict[str, Any] = {}

        if tipo_fonte in ("dfp", "itr"):
            from app.services.ingestion.financeiro import _process_financeiro_member
            quality_counters: dict[str, Any] = {
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
            from app.models.ingestion import IngestionRow
            from app.services.ingestion.fca import _process_fca_rows
            rows = list(
                db.execute(
                    select(IngestionRow).where(IngestionRow.ingestion_file_member_id == member.id)
                ).scalars()
            )
            _process_fca_rows(
                db,
                execucao=execucao,
                run=run,
                ano=ano,
                staged_members=[(member, rows)],
                promote_enabled=_settings.ingestion_promote_enabled,
                contadores=contadores,
                seen_by_row_kind=seen_by_row_kind,
                header_map=header_map,
            )
        elif tipo_fonte == "ipe":
            from app.models.ingestion import IngestionRow
            from app.services.ingestion.ipe import _process_ipe_rows
            rows = list(
                db.execute(
                    select(IngestionRow).where(IngestionRow.ingestion_file_member_id == member.id)
                ).scalars()
            )
            _process_ipe_rows(
                db,
                execucao=execucao,
                run=run,
                ano=ano,
                staged_members=[(member, rows)],
                promote_enabled=_settings.ingestion_promote_enabled,
                contadores=contadores,
                seen_by_row_kind=seen_by_row_kind,
            )
        elif tipo_fonte == "vlmo":
            from app.models.ingestion import IngestionRow
            from app.services.ingestion.vlmo import _process_vlmo_rows
            rows = list(
                db.execute(
                    select(IngestionRow).where(IngestionRow.ingestion_file_member_id == member.id)
                ).scalars()
            )
            _process_vlmo_rows(
                db,
                execucao=execucao,
                run=run,
                ano=ano,
                staged_members=[(member, rows)],
                promote_enabled=_settings.ingestion_promote_enabled,
                contadores=contadores,
                seen_by_row_kind=seen_by_row_kind,
            )
        elif tipo_fonte == "cgvn":
            from app.models.ingestion import IngestionRow
            from app.services.ingestion.cgvn import _process_cgvn_rows
            rows = list(
                db.execute(
                    select(IngestionRow).where(IngestionRow.ingestion_file_member_id == member.id)
                ).scalars()
            )
            _process_cgvn_rows(
                db,
                execucao=execucao,
                run=run,
                ano=ano,
                staged_members=[(member, rows)],
                promote_enabled=_settings.ingestion_promote_enabled,
                contadores=contadores,
                seen_by_row_kind=seen_by_row_kind,
            )

        from app.services.ingestion.quality import enforce_quality_gate
        from app.services.ingestion.summary import build_contadores_quality_summary

        quality_summary = build_contadores_quality_summary(contadores)
        status_execucao, mensagem_status = enforce_quality_gate(quality_summary=quality_summary)

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
        db.commit()
        db.expunge_all()
        gc.collect()
        return {"status": status_execucao, "execucao_id": str(execucao.id)}

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
        db.commit()
        raise


@celery_app.task(bind=True, name="app.worker.tasks.sincronizar_member_task", **_RETRY_KWARGS)  # type: ignore[untyped-decorator]
def sincronizar_member_task(
    self: Any,
    tipo_fonte: str,
    ano: int,
    member_name: str,
    parent_execucao_id: str,
    child_execucao_id: str,
    force_reimport: bool = False,
) -> dict[str, str]:
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
        )
    finally:
        db.close()


@celery_app.task(bind=True, name="app.worker.tasks.disparar_dependentes_task", **_RETRY_KWARGS)  # type: ignore[untyped-decorator]
def disparar_dependentes_task(
    self: Any,
    parent_execucao_id: str,
    force_reimport: bool = False,
) -> dict[str, str]:
    import uuid

    from celery import chord, group
    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.models.sincronizacao import ExecucaoSincronizacao

    db = SessionLocal()
    try:
        parent_uuid = uuid.UUID(parent_execucao_id)
        execucao = db.get(ExecucaoSincronizacao, parent_uuid)
        if execucao is None:
            raise ValueError(f"Parent execution not found: {parent_execucao_id}")
        if execucao.status == "cancelada":
            return _resultado_cancelado(execucao.id, "Parent execution was cancelled before dependent dispatch.")

        document_file = f"{execucao.tipo_fonte}_cia_aberta_{execucao.ano}.csv"
        header_exec = db.scalar(
            select(ExecucaoSincronizacao)
            .where(
                ExecucaoSincronizacao.parent_execucao_id == parent_uuid,
                ExecucaoSincronizacao.arquivo == document_file,
            )
        )
        if header_exec is not None and header_exec.status in ("falha", "quality_fail"):
            raise RuntimeError(f"Cannot dispatch dependents. Document header task failed: {header_exec.id}")

        children = db.scalars(
            select(ExecucaoSincronizacao)
            .where(
                ExecucaoSincronizacao.parent_execucao_id == parent_uuid,
                ExecucaoSincronizacao.arquivo != document_file,
            )
        ).all()

        dep_signatures = []
        for c in children:
            if c.status == "skipped":
                continue

            c.status = "agendada"

            sig = sincronizar_member_task.si(
                tipo_fonte=execucao.tipo_fonte,
                ano=execucao.ano,
                member_name=c.arquivo,
                parent_execucao_id=parent_execucao_id,
                child_execucao_id=str(c.id),
                force_reimport=force_reimport,
            )
            dep_signatures.append(sig)

        db.commit()

        if dep_signatures:
            workflow = chord(
                group(dep_signatures),
                finalizar_sincronizacao_zip_task.si(parent_execucao_id=parent_execucao_id),
            )
            workflow.delay()
        else:
            finalizar_sincronizacao_zip_task.delay(parent_execucao_id=parent_execucao_id)

        return {"status": "dispatched", "parent_execucao_id": parent_execucao_id}
    finally:
        db.close()


@celery_app.task(bind=True, name="app.worker.tasks.finalizar_sincronizacao_zip_task", **_RETRY_KWARGS)  # type: ignore[untyped-decorator]
def finalizar_sincronizacao_zip_task(
    self: Any,
    parent_execucao_id: str,
) -> dict[str, Any]:
    import uuid
    from datetime import UTC, datetime
    from pathlib import Path

    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.models.ingestion import IngestionFile, IngestionRun
    from app.models.sincronizacao import ExecucaoSincronizacao
    from app.services.ingestion.staging import purge_member_success_rows, update_run_state

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
            message = "Um ou mais arquivos membros falharam."
        elif "em_execucao" in child_statuses or "agendada" in child_statuses:
            parent_status = "falha"
            message = "Tempo limite atingido para alguns arquivos membros."
        else:
            parent_status = "sucesso"
            message = "Todos os arquivos membros foram processados com sucesso."

        execucao.total_linhas_lidas = total_lidas
        execucao.total_inseridos = total_inseridos
        execucao.total_atualizados = total_atualizados
        execucao.total_inalterados = total_inalterados
        execucao.total_rejeitados = total_rejeitados
        execucao.status = parent_status
        execucao.finalizada_em = datetime.now(UTC)

        quality_summary = {
            "row_status_counts": {
                "valid": total_inseridos + total_atualizados + total_inalterados,
                "invalid": total_rejeitados,
            },
            "members_total": len(children),
            "members_processados": sum(1 for c in children if c.status != "skipped"),
            "members_skipped": sum(1 for c in children if c.status == "skipped"),
        }

        run = db.scalar(
            select(IngestionRun).where(IngestionRun.execucao_sincronizacao_id == execucao.id)
        )
        if run is not None:
            update_run_state(
                run,
                status=parent_status,
                phase="complete",
                message=message,
                quality_summary=quality_summary,
                finished_at=datetime.now(UTC),
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

        zip_dir = Path(_settings.storage_dir) / str(execucao.id)
        import shutil
        try:
            shutil.rmtree(zip_dir)
        except Exception:
            pass

        return {
            "execucao_id": str(execucao.id),
            "status": parent_status,
            "total_linhas_lidas": total_lidas,
            "total_inseridos": total_inseridos,
            "total_atualizados": total_atualizados,
            "total_inalterados": total_inalterados,
            "total_rejeitados": total_rejeitados,
        }
    finally:
        db.close()


@celery_app.task(bind=True, name="app.worker.tasks.sincronizar_dfp_task", **_RETRY_KWARGS)  # type: ignore[untyped-decorator]
def sincronizar_dfp_task(self: Any, ano: int, force_reimport: bool = False) -> dict[str, str]:
    resultado = _coordenar_sincronizacao_zip(
        tipo_fonte="dfp", ano=ano, task_id=str(self.request.id), force_reimport=force_reimport
    )
    return {"status": str(resultado["status"]), "execucao_id": str(resultado["execucao_id"])}


@celery_app.task(bind=True, name="app.worker.tasks.sincronizar_itr_task", **_RETRY_KWARGS)  # type: ignore[untyped-decorator]
def sincronizar_itr_task(self: Any, ano: int, force_reimport: bool = False) -> dict[str, str]:
    resultado = _coordenar_sincronizacao_zip(
        tipo_fonte="itr", ano=ano, task_id=str(self.request.id), force_reimport=force_reimport
    )
    return {"status": str(resultado["status"]), "execucao_id": str(resultado["execucao_id"])}


@celery_app.task(bind=True, name="app.worker.tasks.sincronizar_fre_task", **_RETRY_KWARGS)  # type: ignore[untyped-decorator]
def sincronizar_fre_task(self: Any, ano: int, force_reimport: bool = False) -> dict[str, str]:
    resultado = _coordenar_sincronizacao_zip(
        tipo_fonte="fre", ano=ano, task_id=str(self.request.id), force_reimport=force_reimport
    )
    return {"status": str(resultado["status"]), "execucao_id": str(resultado["execucao_id"])}


@celery_app.task(bind=True, name="app.worker.tasks.sincronizar_fca_task", **_RETRY_KWARGS)  # type: ignore[untyped-decorator]
def sincronizar_fca_task(self: Any, ano: int, force_reimport: bool = False) -> dict[str, str]:
    resultado = _coordenar_sincronizacao_zip(
        tipo_fonte="fca", ano=ano, task_id=str(self.request.id), force_reimport=force_reimport
    )
    return {"status": str(resultado["status"]), "execucao_id": str(resultado["execucao_id"])}


@celery_app.task(bind=True, name="app.worker.tasks.sincronizar_ipe_task", **_RETRY_KWARGS)  # type: ignore[untyped-decorator]
def sincronizar_ipe_task(self: Any, ano: int, force_reimport: bool = False) -> dict[str, str]:
    resultado = _coordenar_sincronizacao_zip(
        tipo_fonte="ipe", ano=ano, task_id=str(self.request.id), force_reimport=force_reimport
    )
    return {"status": str(resultado["status"]), "execucao_id": str(resultado["execucao_id"])}


@celery_app.task(bind=True, name="app.worker.tasks.sincronizar_vlmo_task", **_RETRY_KWARGS)  # type: ignore[untyped-decorator]
def sincronizar_vlmo_task(self: Any, ano: int, force_reimport: bool = False) -> dict[str, str]:
    resultado = _coordenar_sincronizacao_zip(
        tipo_fonte="vlmo", ano=ano, task_id=str(self.request.id), force_reimport=force_reimport
    )
    return {"status": str(resultado["status"]), "execucao_id": str(resultado["execucao_id"])}


@celery_app.task(bind=True, name="app.worker.tasks.sincronizar_cgvn_task", **_RETRY_KWARGS)  # type: ignore[untyped-decorator]
def sincronizar_cgvn_task(self: Any, ano: int, force_reimport: bool = False) -> dict[str, str]:
    resultado = _coordenar_sincronizacao_zip(
        tipo_fonte="cgvn", ano=ano, task_id=str(self.request.id), force_reimport=force_reimport
    )
    return {"status": str(resultado["status"]), "execucao_id": str(resultado["execucao_id"])}


@celery_app.task(bind=True, name="app.worker.tasks.pre_processar_sincronizacao_task", **_RETRY_KWARGS)  # type: ignore[untyped-decorator]
def pre_processar_sincronizacao_task(
    self: Any,
    tipo_fonte: str,
    ano: int | None = None,
    force_reimport: bool = False,
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
            execucao = ExecucaoSincronizacao(
                tipo_fonte="cadastro",
                ano=None,
                id_tarefa=str(self.request.id),
                arquivo=f"{ARQUIVO_CADASTRO_ABERTA}+{ARQUIVO_CADASTRO_ESTRANGEIRA}",
                url=f"{url_aberta}|{url_estrang}",
                status="em_execucao",
            )
            db.add(execucao)
            db.commit()
            db.refresh(execucao)
            resultado = pre_processar_cadastro(
                db,
                execucao_id=execucao.id,
                task_id=str(self.request.id),
                force_reimport=force_reimport,
            )
        else:
            if ano is None:
                raise ValueError(f"Ano obrigatorio para pre-processar {tipo_fonte.upper()}.")
            resultado = pre_processar_sincronizacao_zip(
                tipo_fonte=tipo_fonte,
                ano=ano,
                task_id=str(self.request.id),
                force_reimport=force_reimport,
            )
        return {"status": str(resultado["status"]), "execucao_id": str(resultado["execucao_id"])}
    finally:
        db.close()


@celery_app.task(bind=True, name="app.worker.tasks.ingerir_sincronizacao_task", **_RETRY_KWARGS)  # type: ignore[untyped-decorator]
def ingerir_sincronizacao_task(
    self: Any,
    execucao_id: str,
    force_reimport: bool = False,
) -> dict[str, Any]:
    from app.db.session import SessionLocal
    from app.models.sincronizacao import ExecucaoSincronizacao
    from app.services.ingestion.cadastro import ingerir_cadastro

    db = SessionLocal()
    try:
        exec_uuid = uuid.UUID(execucao_id)
        execucao = db.get(ExecucaoSincronizacao, exec_uuid)
        if execucao is None:
            raise ValueError(f"Execution not found: {execucao_id}")
        if execucao.status == "cancelada":
            return _resultado_cancelado(execucao.id, "Execution was cancelled before task start.")

        execucao.id_tarefa = str(self.request.id)
        db.commit()

        if execucao.tipo_fonte == "cadastro":
            resultado = ingerir_cadastro(db, execucao_id=exec_uuid)
        else:
            resultado = ingerir_sincronizacao_zip(
                execucao_id=exec_uuid,
                force_reimport=force_reimport,
            )
        return {"status": str(resultado["status"]), "execucao_id": str(resultado["execucao_id"])}
    finally:
        db.close()
