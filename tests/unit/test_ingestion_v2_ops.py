import io
import os
import uuid
import zipfile
from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["TUCANO_CVM_TOKEN"] = "token-teste"

from app.core.config import Settings, get_settings
from app.db.base import Base
from app.models.ingestion import IngestionAttempt, IngestionRow, IngestionRun, QuarantineItem
from app.models.sincronizacao import ExecucaoSincronizacao
from app.services.ingestion.backfill import build_dark_launch_parity_report, run_backfill_years
from app.services.ingestion.metrics import RunTimer, get_ingestion_metrics
from app.services.ingestion.quality import enforce_quality_gate
from app.services.ingestion.sql_batches import (
    iter_lookup_batches,
    iter_parameter_batches,
    max_rows_for_parameter_budget,
)
from app.services.ingestion.summary import build_quality_summary, render_parity_report_markdown
from app.worker.tasks import pre_processar_sincronizacao_zip


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    local_session = Session(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    try:
        yield local_session
    finally:
        local_session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    pytest.importorskip("celery")
    from app.db.session import get_db
    from app.main import app

    def override_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_db
    with TestClient(app, headers={"Authorization": "Bearer token-teste"}) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_config_v2_defaults_and_overrides() -> None:
    settings = Settings.model_validate(
        {
            "INGESTION_ENABLED": True,
            "INGESTION_PROMOTE_ENABLED": False,
            "INGESTION_MAX_RETRIES": 7,
            "INGESTION_COMPANY_MISSING_MAX_RATIO": 0.2,
        }
    )
    assert settings.ingestion_promote_enabled is False
    assert settings.ingestion_max_retries == 7
    assert settings.ingestion_company_missing_max_ratio == 0.2


def test_metrics_helpers_are_idempotent() -> None:
    metrics_a = get_ingestion_metrics()
    metrics_b = get_ingestion_metrics()
    timer = RunTimer("dfp", "promote")
    timer.observe()
    assert metrics_a is metrics_b


def test_build_quality_summary_and_quality_gate(db_session: Session) -> None:
    run = IngestionRun(tipo_fonte="dfp", ano=2025, status="em_execucao", phase="promote")
    db_session.add(run)
    db_session.flush()
    db_session.add_all(
        [
            IngestionRow(
                ingestion_run_id=run.id,
                ingestion_file_member_id=uuid.uuid4(),
                arquivo_origem="a.csv",
                ano_origem=2025,
                linha_origem=2,
                raw_data={"a": 1},
                raw_hash="1",
                row_kind="dfp_documento",
                validation_status="invalid",
                validation_reason_code="companhia_nao_encontrada",
                resolution_method="none",
            ),
            IngestionRow(
                ingestion_run_id=run.id,
                ingestion_file_member_id=uuid.uuid4(),
                arquivo_origem="b.csv",
                ano_origem=2025,
                linha_origem=3,
                raw_data={"a": 2},
                raw_hash="2",
                row_kind="dfp_documento",
                validation_status="valid",
                validation_reason_code=None,
                resolution_method="codigo_cvm_identificador_alta",
            ),
        ]
    )
    db_session.flush()
    primeira_linha = db_session.query(IngestionRow).first()
    assert primeira_linha is not None
    db_session.add(
        QuarantineItem(
            ingestion_run_id=run.id,
            ingestion_row_id=primeira_linha.id,
            arquivo_origem="a.csv",
            ano_origem=2025,
            linha_origem=2,
            row_kind="dfp_documento",
            status="pendente",
            motivo_codigo="companhia_nao_encontrada",
            severidade="error",
            reparavel=True,
            tentativas_reprocessamento=0,
        )
    )
    db_session.add(
        IngestionAttempt(
            ingestion_run_id=run.id,
            operation="download",
            attempt_number=1,
            status="retryable_failure",
            error_type="Timeout",
        )
    )
    db_session.commit()

    summary = build_quality_summary(db_session, ingestion_run_id=run.id)
    status, message = enforce_quality_gate(quality_summary=summary)

    assert summary["reason_counts"]["companhia_nao_encontrada"] == 1
    assert status == "falha_qualidade"
    assert message is not None


def test_build_quality_summary_prefers_persisted_run_summary(db_session: Session) -> None:
    run = IngestionRun(
        tipo_fonte="dfp",
        ano=2025,
        status="sucesso",
        phase="complete",
        quality_summary={
            "row_status_counts": {"valid": 10, "invalid": 1},
            "reason_counts": {"companhia_nao_encontrada": 1},
            "quarantine_total": 1,
        },
    )
    db_session.add(run)
    db_session.flush()
    db_session.add(
        IngestionAttempt(
            ingestion_run_id=run.id,
            operation="replay",
            attempt_number=1,
            status="success",
        )
    )
    db_session.commit()

    summary = build_quality_summary(db_session, ingestion_run_id=run.id)

    assert summary["row_status_counts"] == {"valid": 10, "invalid": 1}
    assert summary["attempts"]["total"] == 1


def test_sql_parameter_batches_respect_budget() -> None:
    rows = [{"a": idx, "b": idx, "c": idx, "d": idx, "e": idx, "f": idx, "g": idx} for idx in range(10000)]

    batch_size = max_rows_for_parameter_budget(parameter_width=7, budget=60000)
    batches = list(iter_parameter_batches(rows, parameter_width=7, budget=60000))

    assert batch_size == 8571
    assert len(batches) == 2
    assert len(batches[0]) == 8571
    assert len(batches[1]) == 1429


def test_render_parity_report_markdown() -> None:
    texto = render_parity_report_markdown(legado={"a": 1, "b": 2}, atual={"a": 2, "b": 2})
    assert "| a | 1 | 2 | 1 |" in texto


def test_admin_v2_runs_and_quarantine_endpoints(client: TestClient, db_session: Session) -> None:
    run = IngestionRun(tipo_fonte="dfp", ano=2025, status="sucesso", phase="complete", quality_summary={"ok": True})
    db_session.add(run)
    db_session.flush()
    row = IngestionRow(
        ingestion_run_id=run.id,
        ingestion_file_member_id=uuid.uuid4(),
        arquivo_origem="dfp.csv",
        ano_origem=2025,
        linha_origem=2,
        raw_data={"a": 1},
        raw_hash="1",
        row_kind="dfp_documento",
        validation_status="invalid",
    )
    db_session.add(row)
    db_session.flush()
    db_session.add(
        QuarantineItem(
            ingestion_run_id=run.id,
            ingestion_row_id=row.id,
            arquivo_origem="dfp.csv",
            ano_origem=2025,
            linha_origem=2,
            row_kind="dfp_documento",
            status="pendente",
            motivo_codigo="companhia_nao_encontrada",
            severidade="error",
            reparavel=True,
            tentativas_reprocessamento=0,
        )
    )
    db_session.commit()

    resposta_runs = client.get("/ingestion/runs")
    resposta_run = client.get(f"/ingestion/runs/{run.id}")
    resposta_quarentena = client.get("/ingestion/quarentena")
    resposta_resumo = client.get("/ingestion/quarentena/resumo")

    assert resposta_runs.status_code == 200
    assert resposta_runs.json()["paginacao"]["total"] == 1
    assert resposta_run.status_code == 200
    assert resposta_quarentena.status_code == 200
    assert resposta_quarentena.json()["paginacao"]["total"] == 1

    # Test new filters on /ingestion/quarentena
    res_filtros_ok = client.get("/ingestion/quarentena?arquivo_origem=dfp.csv&status=pendente&ano_origem=2025")
    assert res_filtros_ok.status_code == 200
    assert res_filtros_ok.json()["paginacao"]["total"] == 1

    res_filtros_vazio = client.get("/ingestion/quarentena?arquivo_origem=dfp_outro.csv")
    assert res_filtros_vazio.status_code == 200
    assert res_filtros_vazio.json()["paginacao"]["total"] == 0

    res_filtros_status_vazio = client.get("/ingestion/quarentena?status=resolvido_auto")
    assert res_filtros_status_vazio.status_code == 200
    assert res_filtros_status_vazio.json()["paginacao"]["total"] == 0

    res_filtros_ano_vazio = client.get("/ingestion/quarentena?ano_origem=2026")
    assert res_filtros_ano_vazio.status_code == 200
    assert res_filtros_ano_vazio.json()["paginacao"]["total"] == 0

    assert resposta_resumo.status_code == 200
    resumo = resposta_resumo.json()
    assert resumo["total"] == 1
    assert resumo["por_status"]["pendente"] == 1
    assert resumo["por_erro"][0]["motivo_codigo"] == "companhia_nao_encontrada"
    assert resumo["por_erro"][0]["quantidade"] == 1
    assert resumo["por_arquivo"][0]["arquivo_origem"] == "dfp.csv"
    assert resumo["por_arquivo"][0]["quantidade"] == 1
    assert resumo["por_arquivo_e_erro"][0]["arquivo_origem"] == "dfp.csv"
    assert resumo["por_arquivo_e_erro"][0]["motivo_codigo"] == "companhia_nao_encontrada"
    assert resumo["por_arquivo_e_erro"][0]["quantidade"] == 1
    assert resumo["total_pendentes"] == 1
    assert resumo["total_resolvidos"] == 0
    assert resumo["total_historico"] == 1


def test_admin_quarentena_defaults_to_pending_but_all_exposes_history(
    client: TestClient, db_session: Session
) -> None:
    run = IngestionRun(tipo_fonte="dfp", ano=2025, status="sucesso", phase="complete")
    db_session.add(run)
    db_session.flush()
    row_pendente = IngestionRow(
        ingestion_run_id=run.id,
        ingestion_file_member_id=uuid.uuid4(),
        arquivo_origem="dfp_pendente.csv",
        ano_origem=2025,
        linha_origem=2,
        raw_data={"a": 1},
        raw_hash="hash-pendente",
        row_kind="dfp_documento",
        validation_status="invalid",
    )
    row_resolvido = IngestionRow(
        ingestion_run_id=run.id,
        ingestion_file_member_id=uuid.uuid4(),
        arquivo_origem="dfp_resolvido.csv",
        ano_origem=2025,
        linha_origem=3,
        raw_data={"a": 2},
        raw_hash="hash-resolvido",
        row_kind="dfp_documento",
        validation_status="valid",
    )
    db_session.add_all([row_pendente, row_resolvido])
    db_session.flush()
    db_session.add_all(
        [
            QuarantineItem(
                ingestion_run_id=run.id,
                ingestion_row_id=row_pendente.id,
                arquivo_origem="dfp_pendente.csv",
                ano_origem=2025,
                linha_origem=2,
                row_kind="dfp_documento",
                status="pendente",
                motivo_codigo="companhia_nao_encontrada",
                severidade="error",
                reparavel=True,
                tentativas_reprocessamento=0,
            ),
            QuarantineItem(
                ingestion_run_id=run.id,
                ingestion_row_id=row_resolvido.id,
                arquivo_origem="dfp_resolvido.csv",
                ano_origem=2025,
                linha_origem=3,
                row_kind="dfp_documento",
                status="resolvido_auto",
                motivo_codigo="normalizacao_invalida",
                severidade="error",
                reparavel=True,
                tentativas_reprocessamento=1,
            ),
        ]
    )
    db_session.commit()

    resposta_padrao = client.get("/ingestion/quarentena")
    resposta_all = client.get("/ingestion/quarentena?status=all")
    resumo_padrao = client.get("/ingestion/quarentena/resumo")
    resumo_all = client.get("/ingestion/quarentena/resumo?status=all")

    assert resposta_padrao.status_code == 200
    assert resposta_padrao.json()["paginacao"]["total"] == 1
    assert resposta_padrao.json()["dados"][0]["status"] == "pendente"

    assert resposta_all.status_code == 200
    assert resposta_all.json()["paginacao"]["total"] == 2

    assert resumo_padrao.status_code == 200
    payload_padrao = resumo_padrao.json()
    assert payload_padrao["total"] == 1
    assert payload_padrao["total_pendentes"] == 1
    assert payload_padrao["total_resolvidos"] == 1
    assert payload_padrao["total_historico"] == 2
    assert payload_padrao["por_arquivo"][0]["arquivo_origem"] == "dfp_pendente.csv"

    assert resumo_all.status_code == 200
    payload_all = resumo_all.json()
    assert payload_all["total"] == 2
    assert payload_all["total_pendentes"] == 1
    assert payload_all["total_resolvidos"] == 1
    assert payload_all["total_historico"] == 2


def test_admin_v2_replay_and_identity_rebuild_endpoints(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.api.routers.admin.replay_quarantine",
        lambda *args, **kwargs: {"status": "sucesso", "total": 1},
    )
    monkeypatch.setattr(
        "app.api.routers.admin.replay_ingestion_run_service",
        lambda *args, **kwargs: {"status": "sucesso", "rows": []},
    )
    monkeypatch.setattr(
        "app.api.routers.admin.sincronizar_cadastro_companhias",
        lambda *args, **kwargs: {"status": "sucesso", "execucao_id": "1"},
    )

    resposta_quarentena = client.post(
        "/ingestion/replay/quarentena", json={"reason_code": "companhia_nao_encontrada"}
    )
    resposta_identity = client.post("/ingestion/identity/rebuild")

    assert resposta_quarentena.status_code == 200
    assert resposta_identity.status_code == 200


def test_worker_tasks_use_single_ingestion_path_and_retry_options(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("celery")
    from app.worker import tasks as worker_tasks

    settings = get_settings()
    class DummyDb:
        def close(self) -> None:
            return None

    monkeypatch.setattr("app.worker.tasks.SessionLocal", lambda: DummyDb())
    monkeypatch.setattr(
        "app.worker.tasks._coordenar_sincronizacao_zip",
        lambda tipo_fonte, ano, task_id=None, force_reimport=False, *args, **kwargs: {
            "status": "sucesso",
            "execucao_id": "v2" if tipo_fonte == "dfp" else f"{tipo_fonte}-v2",
        },
    )
    resultado = worker_tasks.sincronizar_dfp_task.run(2025)
    resultado_fca = worker_tasks.sincronizar_fca_task.run(2025)
    resultado_ipe = worker_tasks.sincronizar_ipe_task.run(2025)
    resultado_vlmo = worker_tasks.sincronizar_vlmo_task.run(2025)

    assert resultado["execucao_id"] == "v2"
    assert resultado_fca["execucao_id"] == "fca-v2"
    assert resultado_ipe["execucao_id"] == "ipe-v2"
    assert resultado_vlmo["execucao_id"] == "vlmo-v2"
    assert worker_tasks.sincronizar_dfp_task.max_retries == settings.ingestion_max_retries
    assert worker_tasks.sincronizar_ipe_task.max_retries == settings.ingestion_max_retries
    assert worker_tasks.sincronizar_vlmo_task.max_retries == settings.ingestion_max_retries
    assert getattr(worker_tasks.sincronizar_dfp_task, "retry_backoff", False) is True
    assert getattr(worker_tasks.sincronizar_ipe_task, "retry_backoff", False) is True
    assert getattr(worker_tasks.sincronizar_vlmo_task, "retry_backoff", False) is True


def test_pre_processar_sincronizacao_zip_ignora_membro_ausente_e_segue_com_disponiveis(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    settings = get_settings()
    monkeypatch.setattr("app.worker.tasks.SessionLocal", lambda: db_session)
    monkeypatch.setattr(settings, "storage_dir", str(tmp_path))

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr(
            "itr_cia_aberta_2019.csv",
            (
                "CNPJ_CIA;CD_CVM;DT_REFER;VERSAO;DENOM_CIA;CATEG_DOC;ID_DOC;DT_RECEB;LINK_DOC\n"
                "00000000000191;1023;2019-12-31;1;BANCO DO BRASIL;ITR;111;2020-03-31;http://exemplo\n"
            ).encode("latin1"),
        )
        zip_file.writestr(
            "itr_cia_aberta_DRE_ind_2019.csv",
            (
                "CNPJ_CIA;CD_CVM;DT_REFER;VERSAO;DENOM_CIA;GRUPO_DFP;MOEDA;ESCALA_MOEDA;ORDEM_EXERC;"
                "DT_INI_EXERC;DT_FIM_EXERC;CD_CONTA;DS_CONTA;VL_CONTA;ST_CONTA_FIXA;COLUNA_DF\n"
                "00000000000191;1023;2019-12-31;1;BANCO DO BRASIL;DF Consolidado;REAL;UNIDADE;ULTIMO;"
                "2019-01-01;2019-12-31;3.01;Receita;100;S;Atual\n"
            ).encode("latin1"),
        )
    payload = buffer.getvalue()

    def _fake_download(url: str, dest_path: str, timeout: float = 300) -> str:
        path = os.fspath(dest_path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as file_obj:
            file_obj.write(payload)
        import hashlib

        return hashlib.sha256(payload).hexdigest()

    monkeypatch.setattr("app.services.ingestion.file_manager.download_file_to_disk", _fake_download)

    resultado = pre_processar_sincronizacao_zip(tipo_fonte="itr", ano=2019, task_id="task-itr-missing-member")

    assert resultado["status"] == "aguardando_ingestao"

    execucao = db_session.get(ExecucaoSincronizacao, uuid.UUID(resultado["execucao_id"]))
    assert execucao is not None
    assert execucao.status == "aguardando_ingestao"
    assert execucao.mensagem_erro is not None
    assert "membros_ausentes_ignorados" in execucao.mensagem_erro
    assert "itr_cia_aberta_composicao_capital_2019.csv" in execucao.mensagem_erro

    run = db_session.scalar(select(IngestionRun).where(IngestionRun.execucao_sincronizacao_id == execucao.id))
    assert run is not None
    assert run.message is not None
    assert "itr_cia_aberta_composicao_capital_2019.csv" in run.message

    filhos = db_session.scalars(
        select(ExecucaoSincronizacao).where(ExecucaoSincronizacao.parent_execucao_id == execucao.id)
    ).all()
    arquivos_filhos = {item.arquivo for item in filhos}
    assert "itr_cia_aberta_2019.csv" in arquivos_filhos
    assert "itr_cia_aberta_DRE_ind_2019.csv" in arquivos_filhos
    assert "itr_cia_aberta_composicao_capital_2019.csv" not in arquivos_filhos


def test_run_backfill_years_and_dark_launch_report(monkeypatch: pytest.MonkeyPatch, db_session: Session) -> None:
    chamadas: list[tuple[str, int]] = []

    def registrar(tipo_fonte: str, ano: int) -> dict[str, Any]:
        chamadas.append((tipo_fonte, ano))
        return {"total_linhas_lidas": ano}

    monkeypatch.setattr(
        "app.services.ingestion.backfill.sincronizar_cadastro_companhias",
        lambda db, task_id=None: {"status": "sucesso", "execucao_id": "cad"},
    )
    monkeypatch.setattr(
        "app.services.ingestion.backfill.sincronizar_dfp",
        lambda db, ano, task_id=None: registrar("dfp_v2", ano),
    )
    monkeypatch.setattr(
        "app.services.ingestion.backfill.sincronizar_itr",
        lambda db, ano, task_id=None: registrar("itr_v2", ano),
    )
    monkeypatch.setattr(
        "app.services.ingestion.backfill.sincronizar_fre",
        lambda db, ano, task_id=None: registrar("fre_v2", ano),
    )
    monkeypatch.setattr(
        "app.services.ingestion.backfill.sincronizar_dfp",
        lambda db, ano, task_id=None: {"total_linhas_lidas": ano - 1},
    )
    monkeypatch.setattr(
        "app.services.ingestion.backfill.sincronizar_itr",
        lambda db, ano, task_id=None: {"total_linhas_lidas": ano - 1},
    )
    monkeypatch.setattr(
        "app.services.ingestion.backfill.sincronizar_fre",
        lambda db, ano, task_id=None: {"total_linhas_lidas": ano - 1},
    )

    resultado = run_backfill_years(db_session, anos=[2025, 2024])

    assert list(resultado["anos"].keys()) == [2024, 2025]
    assert chamadas == []
    with pytest.raises(RuntimeError, match="relatorio_paridade_legado_removido"):
        build_dark_launch_parity_report(db_session, ano=2021)


def test_iter_lookup_batches_uses_smaller_budget_for_large_key_lookups() -> None:
    rows = list(range(1200))

    batches = list(iter_lookup_batches(rows, parameter_width=12))

    assert [len(batch) for batch in batches] == [500, 500, 200]
