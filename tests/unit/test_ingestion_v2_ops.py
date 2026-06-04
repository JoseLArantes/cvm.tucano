import uuid
from datetime import UTC, datetime
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["TUCANO_CVM_TOKEN"] = "token-teste"

from app.core.config import Settings, get_settings
from app.db.base import Base
from app.models.ingestion import IngestionAttempt, IngestionRow, IngestionRun, QuarantineItemV2
from app.models.sincronizacao import ExecucaoSincronizacao
from app.services.ingestion.backfill import build_dark_launch_parity_report, run_backfill_years
from app.services.ingestion.metrics import RunTimer, get_ingestion_metrics
from app.services.ingestion.quality import enforce_quality_gate
from app.services.ingestion.summary import build_quality_summary, render_parity_report_markdown


@pytest.fixture()
def db_session():
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
def client(db_session: Session):
    pytest.importorskip("celery")
    from app.db.session import get_db
    from app.main import app

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    with TestClient(app, headers={"Authorization": "Bearer token-teste"}) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_config_v2_defaults_and_overrides() -> None:
    settings = Settings.model_validate(
        {
            "INGESTION_V2_ENABLED": True,
            "INGESTION_V2_PROMOTE_ENABLED": False,
            "INGESTION_V2_MAX_RETRIES": 7,
            "INGESTION_V2_COMPANY_MISSING_MAX_RATIO": 0.2,
        }
    )
    assert settings.ingestion_v2_enabled is True
    assert settings.ingestion_v2_promote_enabled is False
    assert settings.ingestion_v2_max_retries == 7
    assert settings.ingestion_v2_company_missing_max_ratio == 0.2


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
    db_session.add(
        QuarantineItemV2(
            ingestion_run_id=run.id,
            ingestion_row_id=db_session.query(IngestionRow).first().id if db_session.query(IngestionRow).first() else uuid.uuid4(),
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


def test_render_parity_report_markdown() -> None:
    texto = render_parity_report_markdown(v1={"a": 1, "b": 2}, v2={"a": 2, "b": 2})
    assert "| a | 1 | 2 | 1 |" in texto


def test_admin_v2_runs_and_quarantine_endpoints(client, db_session: Session) -> None:
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
        QuarantineItemV2(
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

    resposta_runs = client.get("/admin/ingestion-v2/runs")
    resposta_run = client.get(f"/admin/ingestion-v2/runs/{run.id}")
    resposta_quarentena = client.get("/admin/ingestion-v2/quarantine")

    assert resposta_runs.status_code == 200
    assert resposta_runs.json()["paginacao"]["total"] == 1
    assert resposta_run.status_code == 200
    assert resposta_quarentena.status_code == 200
    assert resposta_quarentena.json()["paginacao"]["total"] == 1


def test_admin_v2_replay_and_identity_rebuild_endpoints(client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.api.routers.admin.replay_quarantine",
        lambda *args, **kwargs: {"status": "sucesso", "total": 1},
    )
    monkeypatch.setattr(
        "app.api.routers.admin.replay_ingestion_run_service",
        lambda *args, **kwargs: {"status": "sucesso", "rows": []},
    )
    monkeypatch.setattr(
        "app.api.routers.admin.sincronizar_cadastro_companhias_v2",
        lambda *args, **kwargs: {"status": "sucesso", "execucao_id": "1"},
    )

    resposta_quarentena = client.post("/admin/ingestion-v2/replay/quarantine", json={"reason_code": "companhia_nao_encontrada"})
    resposta_identity = client.post("/admin/ingestion-v2/identity/rebuild")

    assert resposta_quarentena.status_code == 200
    assert resposta_identity.status_code == 200


def test_worker_tasks_use_feature_flag_and_retry_options(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("celery")
    from app.worker import tasks as worker_tasks

    settings = get_settings()
    monkeypatch.setattr(settings, "ingestion_v2_enabled", True)

    class DummyDb:
        def close(self) -> None:
            return None

    monkeypatch.setattr("app.worker.tasks.SessionLocal", lambda: DummyDb())
    monkeypatch.setattr(
        "app.worker.tasks.sincronizar_dfp_v2",
        lambda db, ano, task_id=None: {"status": "sucesso", "execucao_id": "v2"},
    )
    resultado = worker_tasks.sincronizar_dfp_task.run(2025)

    assert resultado["execucao_id"] == "v2"
    assert worker_tasks.sincronizar_dfp_task.max_retries == settings.ingestion_v2_max_retries
    assert getattr(worker_tasks.sincronizar_dfp_task, "retry_backoff", False) is True


def test_run_backfill_years_and_dark_launch_report(monkeypatch: pytest.MonkeyPatch, db_session: Session) -> None:
    chamadas: list[tuple[str, int]] = []
    monkeypatch.setattr(
        "app.services.ingestion.backfill.sincronizar_cadastro_companhias_v2",
        lambda db, task_id=None: {"status": "sucesso", "execucao_id": "cad"},
    )
    monkeypatch.setattr(
        "app.services.ingestion.backfill.sincronizar_dfp_v2",
        lambda db, ano, task_id=None: chamadas.append(("dfp_v2", ano)) or {"total_linhas_lidas": ano},
    )
    monkeypatch.setattr(
        "app.services.ingestion.backfill.sincronizar_itr_v2",
        lambda db, ano, task_id=None: chamadas.append(("itr_v2", ano)) or {"total_linhas_lidas": ano},
    )
    monkeypatch.setattr(
        "app.services.ingestion.backfill.sincronizar_fre_v2",
        lambda db, ano, task_id=None: chamadas.append(("fre_v2", ano)) or {"total_linhas_lidas": ano},
    )
    monkeypatch.setattr("app.services.ingestion.backfill.sincronizar_dfp", lambda db, ano: {"total_linhas_lidas": ano - 1})
    monkeypatch.setattr("app.services.ingestion.backfill.sincronizar_itr", lambda db, ano: {"total_linhas_lidas": ano - 1})
    monkeypatch.setattr("app.services.ingestion.backfill.sincronizar_fre", lambda db, ano: {"total_linhas_lidas": ano - 1})

    resultado = run_backfill_years(db_session, anos=[2025, 2024])
    report = build_dark_launch_parity_report(db_session, ano=2021)

    assert list(resultado["anos"].keys()) == [2024, 2025]
    assert chamadas[:3] == [("dfp_v2", 2024), ("itr_v2", 2024), ("fre_v2", 2024)]
    assert "# Ingestion V2 Parity Report" in report
