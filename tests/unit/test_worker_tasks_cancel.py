from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ingestion import IngestionFile, IngestionRun
from app.models.sincronizacao import ExecucaoSincronizacao
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
