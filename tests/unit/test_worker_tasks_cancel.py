import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.financeiro import DocumentoFinanceiro
from app.models.ingestion import IngestionCancellationRequest, IngestionFile, IngestionPhaseExecution, IngestionRun
from app.models.sincronizacao import ExecucaoSincronizacao
from app.services.ingestion.operational import reconcile_stale_ingestion_phase_executions
from app.services.ingestion.staging import create_run, register_file
from app.worker import tasks as worker_tasks
from app.worker.tasks import sincronizar_member_internal


def test_sincronizar_member_internal_ignora_execucao_cancelada(db_session: Session) -> None:
    execucao = ExecucaoSincronizacao(
        tipo_fonte="itr",
        ano=2025,
        arquivo="itr_cia_aberta_DRE_ind_2025.csv",
        url="http://exemplo/itr/dre",
        status="cancelada",
        finalizada_em=datetime.now(UTC),
    )
    db_session.add(execucao)
    db_session.commit()

    resultado = sincronizar_member_internal(
        db=db_session,
        tipo_fonte="itr",
        ano=2025,
        member_name=execucao.arquivo,
        parent_execucao_id=str(execucao.id),
        child_execucao_id=str(execucao.id),
        force_reimport=False,
        task_id="task-cancelada",
    )

    db_session.refresh(execucao)
    assert resultado["status"] == "cancelada"
    assert execucao.status == "cancelada"
    assert execucao.id_tarefa is None


def test_sincronizar_member_internal_cancela_filho_quando_pai_ja_cancelado(db_session: Session) -> None:
    agora = datetime.now(UTC)
    execucao_pai = ExecucaoSincronizacao(
        tipo_fonte="itr",
        ano=2025,
        arquivo="itr_cia_aberta_2025.zip",
        url="http://exemplo/itr",
        status="cancelada",
        finalizada_em=agora,
    )
    db_session.add(execucao_pai)
    db_session.flush()
    execucao_filha = ExecucaoSincronizacao(
        parent_execucao_id=execucao_pai.id,
        tipo_fonte="itr",
        ano=2025,
        arquivo="itr_cia_aberta_DRE_ind_2025.csv",
        url="http://exemplo/itr/dre",
        status="agendada",
        iniciada_em=agora,
    )
    db_session.add(execucao_filha)
    db_session.commit()

    resultado = sincronizar_member_internal(
        db=db_session,
        tipo_fonte="itr",
        ano=2025,
        member_name=execucao_filha.arquivo,
        parent_execucao_id=str(execucao_pai.id),
        child_execucao_id=str(execucao_filha.id),
        force_reimport=False,
        task_id="task-filha",
    )

    db_session.refresh(execucao_filha)
    assert resultado["status"] == "cancelada"
    assert execucao_filha.status == "cancelada"
    assert execucao_filha.finalizada_em is not None


def test_reconciliar_ingestion_stale_task_marca_falha_recuperavel(db_session: Session) -> None:
    agora = datetime.now(UTC)
    execucao = ExecucaoSincronizacao(
        tipo_fonte="itr",
        ano=2025,
        arquivo="itr_cia_aberta_2025.zip",
        url="http://exemplo/itr",
        status="em_execucao",
        iniciada_em=agora,
    )
    db_session.add(execucao)
    db_session.flush()
    run = create_run(
        db_session,
        tipo_fonte="itr",
        ano=2025,
        execucao_sincronizacao_id=execucao.id,
        status="em_execucao",
        phase="promote",
    )
    phase = db_session.scalar(select(IngestionPhaseExecution).where(IngestionPhaseExecution.ingestion_run_id == run.id))
    assert phase is not None
    phase.heartbeat_at = agora - timedelta(hours=1)
    db_session.commit()

    resultado = reconcile_stale_ingestion_phase_executions(db_session)
    db_session.commit()

    db_session.refresh(execucao)
    db_session.refresh(run)
    phase = db_session.scalar(select(IngestionPhaseExecution).where(IngestionPhaseExecution.ingestion_run_id == run.id))
    assert resultado["stale_candidates"] >= 1
    assert str(run.id) in resultado["failed_retryable_runs"]
    assert execucao.status == "falha"
    assert run.status == "falha"
    assert phase is not None
    assert phase.status == "failed_final"
    assert phase.error_type == "stale_phase"
    assert phase.error_retryable is True


def test_reconciliar_ingestion_stale_task_conclui_cancelamento_propagado(db_session: Session) -> None:
    agora = datetime.now(UTC)
    execucao = ExecucaoSincronizacao(
        tipo_fonte="dfp",
        ano=2025,
        arquivo="dfp_cia_aberta_2025.zip",
        url="http://exemplo/dfp",
        status="em_execucao",
        iniciada_em=agora,
    )
    db_session.add(execucao)
    db_session.flush()
    run = create_run(
        db_session,
        tipo_fonte="dfp",
        ano=2025,
        execucao_sincronizacao_id=execucao.id,
        status="em_execucao",
        phase="promote",
    )
    phase = db_session.scalar(select(IngestionPhaseExecution).where(IngestionPhaseExecution.ingestion_run_id == run.id))
    assert phase is not None
    phase.heartbeat_at = agora - timedelta(hours=1)
    db_session.add(
        IngestionCancellationRequest(
            scope_type="ingestion_run",
            scope_id=str(run.id),
            execucao_sincronizacao_id=execucao.id,
            ingestion_run_id=run.id,
            requested_by="api_admin",
            reason="cancelar",
            terminate_immediately=True,
            status="propagated",
        )
    )
    db_session.commit()

    resultado = reconcile_stale_ingestion_phase_executions(db_session)
    db_session.commit()

    db_session.refresh(execucao)
    db_session.refresh(run)
    phase = db_session.scalar(select(IngestionPhaseExecution).where(IngestionPhaseExecution.ingestion_run_id == run.id))
    request = db_session.scalar(select(IngestionCancellationRequest).where(IngestionCancellationRequest.ingestion_run_id == run.id))
    assert resultado["stale_candidates"] >= 1
    assert str(run.id) in resultado["cancelled_runs"]
    assert execucao.status == "cancelada"
    assert run.status == "cancelada"
    assert phase is not None
    assert phase.status == "cancelled"
    assert request is not None
    assert request.status == "completed"


def test_sincronizar_member_internal_passa_reconcile_required_no_worker_split(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    agora = datetime.now(UTC)
    execucao_pai = ExecucaoSincronizacao(
        tipo_fonte="dfp",
        ano=2025,
        arquivo="dfp_cia_aberta_2025.zip",
        url="http://exemplo/dfp",
        status="em_execucao",
        iniciada_em=agora,
    )
    db_session.add(execucao_pai)
    db_session.flush()
    execucao_filha = ExecucaoSincronizacao(
        parent_execucao_id=execucao_pai.id,
        tipo_fonte="dfp",
        ano=2025,
        arquivo="dfp_cia_aberta_DRE_ind_2025.csv",
        url="http://exemplo/dfp/dre",
        status="agendada",
        iniciada_em=agora,
    )
    db_session.add(execucao_filha)
    db_session.flush()

    run_pai = create_run(
        db_session,
        tipo_fonte="dfp",
        ano=2025,
        execucao_sincronizacao_id=execucao_pai.id,
        status="sucesso",
        phase="complete",
    )
    register_file(
        db_session,
        ingestion_run=run_pai,
        source_url=execucao_pai.url,
        source_filename=execucao_pai.arquivo,
        content_sha256="zip-sha",
        content_length_bytes=1,
        is_zip=True,
    )
    db_session.commit()

    extracted_dir = tmp_path / str(execucao_pai.id) / "extracted"
    extracted_dir.mkdir(parents=True, exist_ok=True)
    member_path = extracted_dir / execucao_filha.arquivo
    member_path.write_text(
        "CNPJ_CIA;DT_REFER;VERSAO;DENOM_CIA;CD_CVM;GRUPO_DFP;MOEDA;ESCALA_MOEDA;ORDEM_EXERC;DT_INI_EXERC;DT_FIM_EXERC;CD_CONTA;DS_CONTA;VL_CONTA;ST_CONTA_FIXA;COLUNA_DF\n",
        encoding="latin1",
    )

    monkeypatch.setattr("app.worker.tasks._settings.storage_dir", str(tmp_path))
    monkeypatch.setattr("app.worker.tasks._settings.ingestion_financeiro_direct_path_enabled", False)

    captured: dict[str, object] = {}

    def _fake_process_financeiro_member(*args: Any, **kwargs: Any) -> None:
        captured["reconcile_required"] = kwargs["reconcile_required"]
        contadores = kwargs["contadores"]
        contadores["lidas"] = 1

    monkeypatch.setattr(
        "app.services.ingestion.financeiro._process_financeiro_member",
        _fake_process_financeiro_member,
    )

    resultado = sincronizar_member_internal(
        db=db_session,
        tipo_fonte="dfp",
        ano=2025,
        member_name=execucao_filha.arquivo,
        parent_execucao_id=str(execucao_pai.id),
        child_execucao_id=str(execucao_filha.id),
        force_reimport=False,
        task_id="task-split-worker",
    )

    execucao_filha_atualizada = db_session.get(ExecucaoSincronizacao, execucao_filha.id)
    run_filha = db_session.scalar(select(IngestionRun).where(IngestionRun.execucao_sincronizacao_id == execucao_filha.id))
    ingestion_file = db_session.scalar(select(IngestionFile).where(IngestionFile.ingestion_run_id == run_pai.id))

    assert resultado["status"] == "sucesso"
    assert captured["reconcile_required"] is False
    assert execucao_filha_atualizada is not None
    assert execucao_filha_atualizada.status == "sucesso"
    assert run_filha is not None
    assert ingestion_file is not None


def test_sincronizar_member_internal_semeia_header_map_canonico_no_worker_split(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    agora = datetime.now(UTC)
    execucao_pai = ExecucaoSincronizacao(
        tipo_fonte="dfp",
        ano=2025,
        arquivo="dfp_cia_aberta_2025.zip",
        url="http://exemplo/dfp",
        status="em_execucao",
        iniciada_em=agora,
    )
    db_session.add(execucao_pai)
    db_session.flush()
    execucao_filha = ExecucaoSincronizacao(
        parent_execucao_id=execucao_pai.id,
        tipo_fonte="dfp",
        ano=2025,
        arquivo="dfp_cia_aberta_DRE_ind_2025.csv",
        url="http://exemplo/dfp/dre",
        status="agendada",
        iniciada_em=agora,
    )
    db_session.add(execucao_filha)
    db_session.flush()

    run_pai = create_run(
        db_session,
        tipo_fonte="dfp",
        ano=2025,
        execucao_sincronizacao_id=execucao_pai.id,
        status="sucesso",
        phase="complete",
    )
    register_file(
        db_session,
        ingestion_run=run_pai,
        source_url=execucao_pai.url,
        source_filename=execucao_pai.arquivo,
        content_sha256="zip-sha",
        content_length_bytes=1,
        is_zip=True,
    )
    companhia_id = uuid.uuid4()
    documento = DocumentoFinanceiro(
        companhia_id=companhia_id,
        tipo_formulario="DFP",
        cnpj_companhia="12345678000199",
        codigo_cvm=1234,
        data_referencia=date(2025, 12, 31),
        versao=1,
        denominacao_companhia="Companhia Teste",
        categoria_documento="DFP",
        id_documento=987,
        arquivo_origem="dfp_cia_aberta_2025.csv",
        ano_origem=2025,
        linha_origem=1,
        hash_origem="hash-doc",
    )
    db_session.add(documento)
    db_session.commit()

    extracted_dir = tmp_path / str(execucao_pai.id) / "extracted"
    extracted_dir.mkdir(parents=True, exist_ok=True)
    member_path = extracted_dir / execucao_filha.arquivo
    member_path.write_text(
        "CNPJ_CIA;DT_REFER;VERSAO;DENOM_CIA;CD_CVM;GRUPO_DFP;MOEDA;ESCALA_MOEDA;ORDEM_EXERC;DT_INI_EXERC;DT_FIM_EXERC;CD_CONTA;DS_CONTA;VL_CONTA;ST_CONTA_FIXA;COLUNA_DF\n",
        encoding="latin1",
    )

    monkeypatch.setattr("app.worker.tasks._settings.storage_dir", str(tmp_path))
    monkeypatch.setattr("app.worker.tasks._settings.ingestion_financeiro_direct_path_enabled", False)

    captured: dict[str, object] = {}

    def _fake_process_financeiro_member(*args: Any, **kwargs: Any) -> None:
        captured["header_map"] = kwargs["header_map"]
        contadores = kwargs["contadores"]
        contadores["lidas"] = 1

    monkeypatch.setattr(
        "app.services.ingestion.financeiro._process_financeiro_member",
        _fake_process_financeiro_member,
    )

    resultado = sincronizar_member_internal(
        db=db_session,
        tipo_fonte="dfp",
        ano=2025,
        member_name=execucao_filha.arquivo,
        parent_execucao_id=str(execucao_pai.id),
        child_execucao_id=str(execucao_filha.id),
        force_reimport=False,
        task_id="task-split-worker-header-map",
    )

    assert resultado["status"] == "sucesso"
    header_map = captured["header_map"]
    assert isinstance(header_map, dict)
    resolution = header_map[("DFP", 987, 1, date(2025, 12, 31))]
    assert resolution.companhia_id == companhia_id
    assert resolution.cnpj_companhia == "12345678000199"
    assert resolution.codigo_cvm == 1234


def test_disparar_dependentes_respeita_janela_sem_bloquear_pendentes(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import celery

    agora = datetime.now(UTC)
    execucao_pai = ExecucaoSincronizacao(
        tipo_fonte="itr",
        ano=2022,
        arquivo="itr_cia_aberta_2022.zip",
        url="http://exemplo/itr",
        status="em_execucao",
        iniciada_em=agora,
    )
    db_session.add(execucao_pai)
    db_session.flush()
    child_names = [
        "itr_cia_aberta_BPA_con_2022.csv",
        "itr_cia_aberta_BPA_ind_2022.csv",
        "itr_cia_aberta_BPP_con_2022.csv",
    ]
    children = []
    for child_name in child_names:
        child = ExecucaoSincronizacao(
            parent_execucao_id=execucao_pai.id,
            tipo_fonte="itr",
            ano=2022,
            arquivo=child_name,
            url=f"http://exemplo/itr/{child_name}",
            status="aguardando_ingestao",
            iniciada_em=agora,
        )
        db_session.add(child)
        db_session.flush()
        children.append(child)
        create_run(
            db_session,
            tipo_fonte="itr",
            ano=2022,
            execucao_sincronizacao_id=child.id,
            status="aguardando_ingestao",
            phase="stage",
        )
    db_session.commit()

    class _SessionProxy:
        def __getattr__(self, name: str) -> Any:
            return getattr(db_session, name)

        def close(self) -> None:
            pass

    dispatched: dict[str, Any] = {}

    class _Workflow:
        def delay(self) -> None:
            dispatched["delayed"] = True

    def _fake_group(signatures: Any) -> list[Any]:
        grouped = list(signatures)
        dispatched["group_size"] = len(grouped)
        return grouped

    def _fake_chord(grouped: Any, callback: Any) -> _Workflow:
        dispatched["callback"] = callback
        dispatched["grouped"] = grouped
        return _Workflow()

    monkeypatch.setattr("app.db.session.SessionLocal", lambda: _SessionProxy())
    monkeypatch.setattr("app.worker.tasks.SessionLocal", lambda: _SessionProxy())
    monkeypatch.setattr("app.worker.tasks._settings.ingestion_max_active_members_per_parent", 2)
    monkeypatch.setattr(celery, "group", _fake_group)
    monkeypatch.setattr(celery, "chord", _fake_chord)

    resultado = worker_tasks.disparar_dependentes_task.run(str(execucao_pai.id))

    db_session.expire_all()
    statuses = {}
    for child in children:
        child_atual = db_session.get(ExecucaoSincronizacao, child.id)
        assert child_atual is not None
        statuses[child.arquivo] = child_atual.status
    phase_statuses = {
        child.arquivo: db_session.scalar(
            select(IngestionPhaseExecution.status)
            .join(IngestionRun, IngestionRun.id == IngestionPhaseExecution.ingestion_run_id)
            .where(IngestionRun.execucao_sincronizacao_id == child.id)
            .order_by(IngestionPhaseExecution.created_at.desc())
            .limit(1)
        )
        for child in children
    }

    assert resultado["status"] == "dispatched"
    assert dispatched["group_size"] == 2
    assert list(statuses.values()).count("agendada") == 2
    assert list(statuses.values()).count("aguardando_ingestao") == 1
    assert set(phase_statuses.values()) == {"pending"}


def test_ingerir_sincronizacao_zip_agenda_apenas_member_principal(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import celery

    agora = datetime.now(UTC)
    execucao_pai = ExecucaoSincronizacao(
        tipo_fonte="itr",
        ano=2022,
        arquivo="itr_cia_aberta_2022.zip",
        url="http://exemplo/itr",
        status="aguardando_ingestao",
        iniciada_em=agora,
    )
    db_session.add(execucao_pai)
    db_session.flush()
    run_pai = create_run(
        db_session,
        tipo_fonte="itr",
        ano=2022,
        execucao_sincronizacao_id=execucao_pai.id,
        status="aguardando_ingestao",
        phase="stage",
    )
    child_names = [
        "itr_cia_aberta_2022.csv",
        "itr_cia_aberta_BPA_con_2022.csv",
        "itr_cia_aberta_BPA_ind_2022.csv",
    ]
    children = []
    for child_name in child_names:
        child = ExecucaoSincronizacao(
            parent_execucao_id=execucao_pai.id,
            tipo_fonte="itr",
            ano=2022,
            arquivo=child_name,
            url=f"http://exemplo/itr/{child_name}",
            status="aguardando_ingestao",
            iniciada_em=agora,
        )
        db_session.add(child)
        db_session.flush()
        children.append(child)
        create_run(
            db_session,
            tipo_fonte="itr",
            ano=2022,
            execucao_sincronizacao_id=child.id,
            status="aguardando_ingestao",
            phase="stage",
        )
    db_session.commit()

    class _SessionProxy:
        def __getattr__(self, name: str) -> Any:
            return getattr(db_session, name)

        def close(self) -> None:
            pass

    class _Workflow:
        def delay(self) -> None:
            pass

    monkeypatch.setattr("app.db.session.SessionLocal", lambda: _SessionProxy())
    monkeypatch.setattr("app.worker.tasks.SessionLocal", lambda: _SessionProxy())
    monkeypatch.setattr("app.services.ingestion.dependencies.ensure_identity_graph_ready", lambda db: None)
    monkeypatch.setattr(celery, "chain", lambda *args: _Workflow())

    resultado = worker_tasks.ingerir_sincronizacao_zip(execucao_pai.id)

    db_session.expire_all()
    statuses = {}
    for child in children:
        child_atual = db_session.get(ExecucaoSincronizacao, child.id)
        assert child_atual is not None
        statuses[child.arquivo] = child_atual.status
    parent_run = db_session.get(IngestionRun, run_pai.id)

    assert resultado["status"] == "em_execucao"
    assert parent_run is not None
    assert parent_run.status == "em_execucao"
    assert statuses["itr_cia_aberta_2022.csv"] == "agendada"
    assert statuses["itr_cia_aberta_BPA_con_2022.csv"] == "aguardando_ingestao"
    assert statuses["itr_cia_aberta_BPA_ind_2022.csv"] == "aguardando_ingestao"


def test_finalizar_sincronizacao_zip_resume_quality_summary_explicit_reuse(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agora = datetime.now(UTC)
    execucao_pai = ExecucaoSincronizacao(
        tipo_fonte="itr",
        ano=2025,
        arquivo="itr_cia_aberta_2025.zip",
        url="http://exemplo/itr",
        status="em_execucao",
        iniciada_em=agora,
    )
    db_session.add(execucao_pai)
    db_session.flush()

    run_pai = create_run(
        db_session,
        tipo_fonte="itr",
        ano=2025,
        execucao_sincronizacao_id=execucao_pai.id,
        status="em_execucao",
        phase="stage",
    )
    register_file(
        db_session,
        ingestion_run=run_pai,
        source_url=execucao_pai.url,
        source_filename=execucao_pai.arquivo,
        content_sha256="zip-sha",
        content_length_bytes=100,
        is_zip=True,
    )

    execucao_reused = ExecucaoSincronizacao(
        parent_execucao_id=execucao_pai.id,
        tipo_execucao="arquivo_membro",
        tipo_fonte="itr",
        ano=2025,
        arquivo="itr_cia_aberta_DRE_ind_2025.csv",
        url=execucao_pai.url,
        status="skipped",
        iniciada_em=agora,
        finalizada_em=agora,
    )
    execucao_processed = ExecucaoSincronizacao(
        parent_execucao_id=execucao_pai.id,
        tipo_execucao="arquivo_membro",
        tipo_fonte="itr",
        ano=2025,
        arquivo="itr_cia_aberta_DRA_ind_2025.csv",
        url=execucao_pai.url,
        status="sucesso",
        iniciada_em=agora,
        finalizada_em=agora,
        total_linhas_lidas=4,
        total_inseridos=3,
        total_inalterados=1,
    )
    db_session.add_all([execucao_reused, execucao_processed])
    db_session.flush()

    reused_run = create_run(
        db_session,
        tipo_fonte="itr",
        ano=2025,
        execucao_sincronizacao_id=execucao_reused.id,
        status="skipped",
        phase="complete",
        quality_summary={
            "skip_reason": "member_sha256_reused",
            "matched_via": "child_execution",
            "reused_from_failed_parent": True,
        },
    )
    reused_run.finished_at = agora
    processed_run = create_run(
        db_session,
        tipo_fonte="itr",
        ano=2025,
        execucao_sincronizacao_id=execucao_processed.id,
        status="sucesso",
        phase="complete",
    )
    processed_run.finished_at = agora
    db_session.commit()

    monkeypatch.setattr("app.db.session.SessionLocal", lambda: db_session)
    monkeypatch.setattr(worker_tasks.despachar_materializacao_pendente_task, "apply_async", lambda **kwargs: None)
    monkeypatch.setattr("app.worker.tasks._settings.storage_dir", str(Path.cwd() / "tmp-tests-storage"))

    resultado = worker_tasks.finalizar_sincronizacao_zip_task.run(str(execucao_pai.id))

    run_pai_atual = db_session.get(IngestionRun, run_pai.id)
    execucao_pai_atual = db_session.get(ExecucaoSincronizacao, execucao_pai.id)

    assert resultado["status"] == "sucesso"
    assert execucao_pai_atual is not None
    assert execucao_pai_atual.status == "sucesso"
    assert run_pai_atual is not None
    assert run_pai_atual.quality_summary is not None
    assert run_pai_atual.quality_summary["members_skipped"] == 1
    assert run_pai_atual.quality_summary["members_processados"] == 1
    assert run_pai_atual.quality_summary["members_reprocessed"] == 1
    assert run_pai_atual.quality_summary["members_reused_from_previous"] == 1
    assert run_pai_atual.quality_summary["members_reused_from_failed_parent"] == 1
