import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.ingestion import (
    IngestionCancellationRequest,
    IngestionFile,
    IngestionFileMember,
    IngestionPhaseExecution,
    IngestionRow,
    IngestionRun,
    QuarantineItem,
    SourceArtifactSnapshot,
    SourceDeliverySnapshot,
    SourceMemberSnapshot,
)
from app.models.sincronizacao import ExecucaoSincronizacao, HistoricoAlteracaoCampo


def test_admin_sincronizacao_tudo_agenda_tarefas(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    wf_applied = False

    class FakeWorkflow:
        def apply_async(self) -> None:
            nonlocal wf_applied
            wf_applied = True

    monkeypatch.setattr("app.api.routers.admin.chain", lambda *args, **kwargs: FakeWorkflow())
    monkeypatch.setattr("app.api.routers.admin.group", lambda *args, **kwargs: FakeWorkflow())

    resposta = client.post("/ingestion/sincronizacoes/tudo/2025?force_reimport=true")
    assert resposta.status_code == 200
    payload = resposta.json()
    assert payload["status"] == "agendada"
    assert len(payload["tarefas"]) == 8
    assert payload["tarefas"][0]["tipo_fonte"] == "cadastro"
    assert payload["tarefas"][0]["ano"] is None
    assert [item["ano"] for item in payload["tarefas"][1:]] == [2025] * 7
    assert wf_applied is True


def test_admin_fontes_endpoints_expoem_registry(client: TestClient) -> None:
    resposta_lista = client.get("/ingestion/fontes")
    resposta_detalhe = client.get("/ingestion/fontes/fre")
    resposta_inexistente = client.get("/ingestion/fontes/inexistente")

    assert resposta_lista.status_code == 200
    dados = resposta_lista.json()["dados"]
    assert [item["fonte"] for item in dados[:8]] == ["cadastro", "dfp", "itr", "fre", "fca", "ipe", "vlmo", "cgvn"]
    assert resposta_detalhe.status_code == 200
    detalhe = resposta_detalhe.json()
    assert detalhe["fonte"] == "fre"
    assert detalhe["datasets_opcionais"] == 56
    assert len(detalhe["datasets"]) == 61
    assert detalhe["datasets"][0]["dataset"] == "documentos"
    assert resposta_inexistente.status_code == 404


def test_admin_sincronizacao_vlmo_agenda_tarefa(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.api.routers.admin.sincronizar_vlmo_task.delay",
        lambda ano, **kwargs: SimpleNamespace(id=f"task-vlmo-{ano}-{kwargs.get('force_reimport', False)}"),
    )

    resposta = client.post("/ingestion/sincronizacoes/vlmo/2025?force_reimport=true")

    assert resposta.status_code == 200
    assert resposta.json() == {"id_tarefa": "task-vlmo-2025-True", "status": "agendada"}


def test_admin_fontes_auditar_expoe_resposta_estruturada(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.api.routers.admin.build_dataset_discovery_audit",
        lambda **kwargs: {
            "ano": kwargs.get("year"),
            "fontes": [
                {
                    "fonte": "fre",
                    "familia": "formulario_referencia",
                    "descricao": "FRE MVP",
                    "status_suporte": "suportado",
                    "artifact_type": "annual_zip_replacement",
                    "update_cadence": "weekday_or_weekly",
                    "remote_probe_strategy": "ckan_head_sha",
                    "version_semantics": "all_versions_retained",
                    "reconcile_policy": "artifact_member_replace",
                    "ano": 2025,
                    "url": "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/FRE/DADOS/fre_cia_aberta_2025.zip",
                    "arquivo_principal": "fre_cia_aberta_2025.zip",
                    "acessivel": True,
                    "sha256": "abc",
                    "tamanho_bytes": 10,
                    "datasets_esperados": 6,
                    "datasets_encontrados": 6,
                    "datasets_faltantes": 0,
                    "drift_summary": {"required_member_missing": [], "optional_member_missing": []},
                    "datasets": [],
                    "observacoes": None,
                }
            ],
            "total_fontes": 1,
            "total_fontes_acessiveis": 1,
            "total_datasets_faltantes": 0,
            "novidades": {"source_url": "https://dados.cvm.gov.br/pages/novidades", "highlights": [], "total_highlights": 0},
        },
    )

    resposta = client.post("/ingestion/fontes/auditar", json={"ano": 2025, "fontes": ["fre"]})

    assert resposta.status_code == 200
    payload = resposta.json()
    assert payload["ano"] == 2025
    assert payload["total_fontes"] == 1
    assert payload["fontes"][0]["fonte"] == "fre"
    assert payload["fontes"][0]["datasets_faltantes"] == 0
    assert payload["fontes"][0]["artifact_type"] == "annual_zip_replacement"
    assert payload["novidades"]["source_url"] == "https://dados.cvm.gov.br/pages/novidades"


def test_admin_reprocessar_arquivo_valida_registry_para_csv_e_zip(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, db_session: Session
) -> None:
    from app.models.ingestion import IngestionFile, IngestionRun

    # Seed parent executions for CSV member reprocessing
    for fonte, ano in (("fre", 2025), ("itr", 2026), ("ipe", 2025), ("vlmo", 2025)):
        exec_pai = ExecucaoSincronizacao(
            id=uuid.uuid4(),
            tipo_fonte=fonte,
            ano=ano,
            arquivo=f"{fonte}_cia_aberta_{ano}.zip",
            url=f"http://example.com/{fonte}",
            status="sucesso",
            tipo_execucao="arquivo_zip",
        )
        db_session.add(exec_pai)
        db_session.flush()
        
        run = IngestionRun(
            id=uuid.uuid4(),
            execucao_sincronizacao_id=exec_pai.id,
            tipo_fonte=fonte,
            ano=ano,
            status="sucesso",
            phase="complete",
        )
        db_session.add(run)
        db_session.flush()
        
        file = IngestionFile(
            id=uuid.uuid4(),
            ingestion_run_id=run.id,
            source_url=exec_pai.url,
            source_filename=exec_pai.arquivo,
            content_sha256="abc",
            content_length_bytes=1000,
        )
        db_session.add(file)
        db_session.flush()
        
    db_session.commit()

    monkeypatch.setattr(
        "app.api.routers.admin.sincronizar_dfp_task.delay",
        lambda ano, **kwargs: SimpleNamespace(id=f"task-dfp-{ano}-{kwargs.get('force_reimport', False)}"),
    )
    monkeypatch.setattr(
        "app.api.routers.admin.sincronizar_fre_task.delay",
        lambda ano, **kwargs: SimpleNamespace(id=f"task-fre-{ano}-{kwargs.get('force_reimport', False)}"),
    )
    monkeypatch.setattr(
        "app.api.routers.admin.sincronizar_fca_task.delay",
        lambda ano, **kwargs: SimpleNamespace(id=f"task-fca-{ano}-{kwargs.get('force_reimport', False)}"),
    )
    monkeypatch.setattr(
        "app.api.routers.admin.sincronizar_ipe_task.delay",
        lambda ano, **kwargs: SimpleNamespace(id=f"task-ipe-{ano}-{kwargs.get('force_reimport', False)}"),
    )
    monkeypatch.setattr(
        "app.api.routers.admin.sincronizar_vlmo_task.delay",
        lambda ano, **kwargs: SimpleNamespace(id=f"task-vlmo-{ano}-{kwargs.get('force_reimport', False)}"),
    )
    monkeypatch.setattr(
        "app.worker.tasks.sincronizar_member_task.delay",
        lambda **kwargs: SimpleNamespace(
            id=(
                f"task-{kwargs.get('tipo_fonte')}-member-"
                f"{kwargs.get('ano')}-{kwargs.get('member_name')}-{kwargs.get('force_reimport', False)}"
            )
        ),
    )

    resposta_zip = client.post("/ingestion/sincronizacoes/reprocessar-arquivo", json={"arquivo": "dfp_cia_aberta_2025.zip"})
    resposta_csv = client.post(
        "/ingestion/sincronizacoes/reprocessar-arquivo",
        json={"arquivo": "fre_cia_aberta_2025.csv", "ano": 2025},
    )
    resposta_itr_csv_maiusculo = client.post(
        "/ingestion/sincronizacoes/reprocessar-arquivo",
        json={"arquivo": "itr_cia_aberta_BPA_con_2026.csv", "ano": 2026},
    )
    resposta_fca = client.post("/ingestion/sincronizacoes/reprocessar-arquivo", json={"arquivo": "fca_cia_aberta_2025.zip"})
    resposta_ipe_zip = client.post(
        "/ingestion/sincronizacoes/reprocessar-arquivo", json={"arquivo": "ipe_cia_aberta_2025.zip"}
    )
    resposta_ipe_csv = client.post(
        "/ingestion/sincronizacoes/reprocessar-arquivo",
        json={"arquivo": "ipe_cia_aberta_2025.csv", "ano": 2025},
    )
    resposta_vlmo_zip = client.post(
        "/ingestion/sincronizacoes/reprocessar-arquivo", json={"arquivo": "vlmo_cia_aberta_2025.zip"}
    )
    resposta_vlmo_csv = client.post(
        "/ingestion/sincronizacoes/reprocessar-arquivo",
        json={"arquivo": "vlmo_cia_aberta_con_2025.csv", "ano": 2025},
    )
    resposta_invalida = client.post(
        "/ingestion/sincronizacoes/reprocessar-arquivo",
        json={"arquivo": "arquivo_inexistente_2025.csv", "ano": 2025},
    )

    assert resposta_zip.status_code == 200
    assert resposta_zip.json()["tarefas"][0]["tipo_fonte"] == "dfp"
    assert resposta_zip.json()["tarefas"][0]["id_tarefa"] == "task-dfp-2025-False"
    assert resposta_csv.status_code == 200
    assert resposta_csv.json()["tarefas"][0]["tipo_fonte"] == "fre_membro"
    assert resposta_itr_csv_maiusculo.status_code == 200
    assert resposta_itr_csv_maiusculo.json()["tarefas"][0]["tipo_fonte"] == "itr_membro"
    assert (
        resposta_itr_csv_maiusculo.json()["tarefas"][0]["id_tarefa"]
        == "task-itr-member-2026-itr_cia_aberta_BPA_con_2026.csv-False"
    )
    assert resposta_fca.status_code == 200
    assert resposta_fca.json()["tarefas"][0]["tipo_fonte"] == "fca"
    assert resposta_ipe_zip.status_code == 200
    assert resposta_ipe_zip.json()["tarefas"][0]["tipo_fonte"] == "ipe"
    assert resposta_ipe_csv.status_code == 200
    assert resposta_ipe_csv.json()["tarefas"][0]["tipo_fonte"] == "ipe_membro"
    assert resposta_vlmo_zip.status_code == 200
    assert resposta_vlmo_zip.json()["tarefas"][0]["tipo_fonte"] == "vlmo"
    assert resposta_vlmo_csv.status_code == 200
    assert resposta_vlmo_csv.json()["tarefas"][0]["tipo_fonte"] == "vlmo_membro"
    assert resposta_invalida.status_code == 422

    resposta_forcada = client.post(
        "/ingestion/sincronizacoes/reprocessar-arquivo",
        json={"arquivo": "dfp_cia_aberta_2025.zip", "force_reimport": True},
    )
    assert resposta_forcada.status_code == 200
    assert resposta_forcada.json()["tarefas"][0]["id_tarefa"] == "task-dfp-2025-True"


def test_admin_dashboard_quarentena_alteracoes(client: TestClient, db_session: Session) -> None:
    agora = datetime.now(UTC)
    execucao_id = uuid.uuid4()
    entidade_id = uuid.uuid4()
    db_session.add(
        ExecucaoSincronizacao(
            id=execucao_id,
            tipo_fonte="dfp",
            ano=2025,
            arquivo="dfp_cia_aberta_2025.zip",
            url="http://exemplo",
            hash_arquivo="abc",
            iniciada_em=agora,
            finalizada_em=agora,
            status="sucesso",
            total_linhas_lidas=10,
            total_inseridos=8,
            total_atualizados=1,
            total_inalterados=1,
            total_rejeitados=2,
            mensagem_erro=None,
        )
    )
    db_session.flush()
    run = IngestionRun(
        id=uuid.uuid4(),
        execucao_sincronizacao_id=execucao_id,
        tipo_fonte="dfp",
        ano=2025,
        status="sucesso",
        phase="complete",
    )
    db_session.add(run)
    db_session.flush()
    row = IngestionRow(
        ingestion_run_id=run.id,
        ingestion_file_member_id=uuid.uuid4(),
        arquivo_origem="dfp_cia_aberta_2025.csv",
        ano_origem=2025,
        linha_origem=5,
        raw_data={"CNPJ_CIA": "000"},
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
            execucao_sincronizacao_id=execucao_id,
            arquivo_origem="dfp_cia_aberta_2025.csv",
            ano_origem=2025,
            linha_origem=5,
            row_kind="dfp_documento",
            status="pendente",
            motivo_codigo="companhia_nao_encontrada",
            severidade="error",
            reparavel=True,
            tentativas_reprocessamento=0,
            created_at=agora,
        )
    )
    db_session.add(
        HistoricoAlteracaoCampo(
            entidade="documentos_financeiros",
            entidade_id=entidade_id,
            companhia_id=None,
            campo="denominacao_companhia",
            valor_anterior="A",
            valor_novo="B",
            alterado_em=agora,
            execucao_sincronizacao_id=execucao_id,
            arquivo_origem="dfp_cia_aberta_2025.csv",
            ano_origem=2025,
        )
    )
    db_session.commit()

    resposta_dashboard = client.get("/ingestion/dashboard")
    assert resposta_dashboard.status_code == 200
    assert resposta_dashboard.json()["total_execucoes"] == 1

    resposta_quarentena = client.get("/ingestion/quarentena")
    assert resposta_quarentena.status_code == 200
    assert resposta_quarentena.json()["paginacao"]["total"] == 1

    resposta_alteracoes = client.get("/ingestion/alteracoes")
    assert resposta_alteracoes.status_code == 200
    assert resposta_alteracoes.json()["paginacao"]["total"] == 1


def test_admin_cancelar_sincronizacao_por_execucao(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    agora = datetime.now(UTC)
    execucao = ExecucaoSincronizacao(
        tipo_fonte="dfp",
        ano=2025,
        id_tarefa="task-dfp-2025",
        arquivo="dfp_cia_aberta_2025.zip",
        url="http://exemplo/dfp",
        status="em_execucao",
        iniciada_em=agora,
        total_linhas_lidas=123,
    )
    db_session.add(execucao)
    db_session.commit()

    chamadas: list[tuple[str, bool, str]] = []

    def fake_revoke(task_id: str, terminate: bool, signal: str) -> None:
        chamadas.append((task_id, terminate, signal))

    monkeypatch.setattr("app.api.routers.admin.celery_app.control.revoke", fake_revoke)

    resposta = client.post(
        "/ingestion/sincronizacoes/cancelar",
        json={"id_execucao": str(execucao.id), "terminar_imediatamente": True, "motivo": "Teste"},
    )

    assert resposta.status_code == 200
    payload = resposta.json()
    assert payload["id_execucao"] == str(execucao.id)
    assert payload["id_tarefa"] == "task-dfp-2025"
    assert payload["execucao_encontrada"] is True
    assert payload["status_execucao"] == "cancelada"
    assert chamadas == [("task-dfp-2025", True, "SIGTERM")]

    db_session.refresh(execucao)
    assert execucao.status == "cancelada"
    assert execucao.finalizada_em is not None
    assert "Teste" in (execucao.mensagem_erro or "")
    requests = db_session.query(IngestionCancellationRequest).all()
    assert len(requests) == 1
    assert requests[0].scope_type == "execucao_sincronizacao"
    assert requests[0].status == "completed"
    assert requests[0].affected_task_ids == ["task-dfp-2025"]


def test_admin_cancelar_sincronizacao_por_tarefa_sem_execucao(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    chamadas: list[tuple[str, bool, str]] = []

    def fake_revoke(task_id: str, terminate: bool, signal: str) -> None:
        chamadas.append((task_id, terminate, signal))

    monkeypatch.setattr("app.api.routers.admin.celery_app.control.revoke", fake_revoke)

    resposta = client.post(
        "/ingestion/sincronizacoes/cancelar",
        json={"id_tarefa": "task-sem-execucao", "terminar_imediatamente": True},
    )

    assert resposta.status_code == 200
    payload = resposta.json()
    assert payload["id_execucao"] is None
    assert payload["id_tarefa"] == "task-sem-execucao"
    assert payload["execucao_encontrada"] is False
    assert payload["status_execucao"] is None
    assert chamadas == [("task-sem-execucao", True, "SIGTERM")]


def test_admin_cancelar_sincronizacao_rejeita_execucao_finalizada(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    execucao = ExecucaoSincronizacao(
        tipo_fonte="dfp",
        ano=2025,
        id_tarefa="task-finalizada",
        arquivo="dfp_cia_aberta_2025.zip",
        url="http://exemplo/dfp",
        status="sucesso",
    )
    db_session.add(execucao)
    db_session.commit()

    monkeypatch.setattr("app.api.routers.admin.celery_app.control.revoke", lambda *args, **kwargs: None)

    resposta = client.post(
        "/ingestion/sincronizacoes/cancelar",
        json={"id_execucao": str(execucao.id), "terminar_imediatamente": True},
    )

    assert resposta.status_code == 409


def test_admin_cancelar_sincronizacao_sem_id_tarefa_marca_cancelada_no_banco(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    execucao = ExecucaoSincronizacao(
        tipo_fonte="dfp",
        ano=2024,
        id_tarefa=None,
        arquivo="dfp_cia_aberta_2024.zip",
        url="http://exemplo/dfp-2024",
        status="em_execucao",
        total_linhas_lidas=321,
    )
    db_session.add(execucao)
    db_session.commit()

    chamadas: list[tuple[str, bool, str]] = []

    def fake_revoke(task_id: str, terminate: bool, signal: str) -> None:
        chamadas.append((task_id, terminate, signal))

    monkeypatch.setattr("app.api.routers.admin.celery_app.control.revoke", fake_revoke)

    resposta = client.post(
        "/ingestion/sincronizacoes/cancelar",
        json={"id_execucao": str(execucao.id), "terminar_imediatamente": True, "motivo": "Encerrar legado"},
    )

    assert resposta.status_code == 200
    payload = resposta.json()
    assert payload["id_execucao"] == str(execucao.id)
    assert payload["id_tarefa"] is None
    assert payload["execucao_encontrada"] is True
    assert payload["status_execucao"] == "cancelada"
    assert payload["revogacao_solicitada"] is False
    assert chamadas == []

    db_session.refresh(execucao)
    assert execucao.status == "cancelada"
    assert execucao.finalizada_em is not None
    assert "sem revogacao remota" in (execucao.mensagem_erro or "")


def test_admin_cancelar_sincronizacao_pai_propaga_para_filhos_e_runs(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.models.ingestion import IngestionRun

    agora = datetime.now(UTC)
    execucao_pai = ExecucaoSincronizacao(
        tipo_fonte="itr",
        ano=2025,
        id_tarefa="task-pai",
        arquivo="itr_cia_aberta_2025.zip",
        url="http://exemplo/itr",
        status="em_execucao",
        iniciada_em=agora,
    )
    db_session.add(execucao_pai)
    db_session.flush()
    execucao_filha_ativa = ExecucaoSincronizacao(
        parent_execucao_id=execucao_pai.id,
        tipo_fonte="itr",
        ano=2025,
        id_tarefa="task-filha-ativa",
        arquivo="itr_cia_aberta_DRE_ind_2025.csv",
        url="http://exemplo/itr/dre",
        status="agendada",
        iniciada_em=agora,
    )
    execucao_filha_final = ExecucaoSincronizacao(
        parent_execucao_id=execucao_pai.id,
        tipo_fonte="itr",
        ano=2025,
        id_tarefa="task-filha-final",
        arquivo="itr_cia_aberta_2025.csv",
        url="http://exemplo/itr/header",
        status="sucesso",
        iniciada_em=agora,
    )
    db_session.add_all([execucao_filha_ativa, execucao_filha_final])
    db_session.flush()
    db_session.add_all(
        [
            IngestionRun(
                execucao_sincronizacao_id=execucao_pai.id,
                tipo_fonte="itr",
                ano=2025,
                status="em_execucao",
                phase="promote",
            ),
            IngestionRun(
                execucao_sincronizacao_id=execucao_filha_ativa.id,
                tipo_fonte="itr",
                ano=2025,
                status="em_execucao",
                phase="stage",
            ),
            IngestionRun(
                execucao_sincronizacao_id=execucao_filha_final.id,
                tipo_fonte="itr",
                ano=2025,
                status="sucesso",
                phase="complete",
            ),
        ]
    )
    db_session.commit()

    chamadas: list[tuple[str, bool, str]] = []

    def fake_revoke(task_id: str, terminate: bool, signal: str) -> None:
        chamadas.append((task_id, terminate, signal))

    monkeypatch.setattr("app.api.routers.admin.celery_app.control.revoke", fake_revoke)

    resposta = client.post(
        "/ingestion/sincronizacoes/cancelar",
        json={"id_execucao": str(execucao_pai.id), "terminar_imediatamente": True, "motivo": "Parar lote"},
    )

    assert resposta.status_code == 200
    assert chamadas == [("task-pai", True, "SIGTERM"), ("task-filha-ativa", True, "SIGTERM"), ("task-filha-final", True, "SIGTERM")]

    db_session.refresh(execucao_pai)
    db_session.refresh(execucao_filha_ativa)
    db_session.refresh(execucao_filha_final)
    assert execucao_pai.status == "cancelada"
    assert execucao_filha_ativa.status == "cancelada"
    assert execucao_filha_final.status == "sucesso"

    runs = {
        run.execucao_sincronizacao_id: run
        for run in db_session.query(IngestionRun).all()
    }
    assert runs[execucao_pai.id].status == "cancelada"
    assert runs[execucao_filha_ativa.id].status == "cancelada"
    assert runs[execucao_filha_final.id].status == "sucesso"


def test_openapi_documenta_cancelamento_sincronizacao(client: TestClient) -> None:
    resposta = client.get("/openapi.json")

    assert resposta.status_code == 200
    payload = resposta.json()
    operacao = payload["paths"]["/ingestion/sincronizacoes/cancelar"]["post"]
    esquema = payload["components"]["schemas"]["SolicitacaoCancelamentoSincronizacao"]

    assert operacao["summary"] == "Cancelar Sincronizacao em Andamento ou na Fila"
    assert "id_execucao" in operacao["description"]
    assert "id_tarefa" in operacao["description"]
    assert "sem `id_tarefa`" in operacao["description"]
    assert "SIGTERM" in operacao["description"]
    assert operacao["operationId"] == "cancelarSincronizacaoAdmin"
    assert esquema["properties"]["id_execucao"]["anyOf"][0]["format"] == "uuid"
    assert esquema["properties"]["id_tarefa"]["anyOf"][1]["type"] == "null"
    assert len(esquema["examples"]) == 2


def test_openapi_documenta_admin_ingestion(client: TestClient) -> None:
    resposta = client.get("/openapi.json")

    assert resposta.status_code == 200
    payload = resposta.json()

    assert "/ingestion/ingestion-v2/runs" not in payload["paths"]
    assert "/ingestion/ingestion-v2/quarantine" not in payload["paths"]
    assert "/ingestion/quarantine" not in payload["paths"]

    rota_runs = payload["paths"]["/ingestion/runs"]["get"]
    rota_run_phases = payload["paths"]["/ingestion/runs/{run_id}/phases"]["get"]
    rota_quarantine = payload["paths"]["/ingestion/quarentena"]["get"]
    rota_replay_quarantine = payload["paths"]["/ingestion/replay/quarentena"]["post"]
    rota_quarentena_resumo = payload["paths"]["/ingestion/quarentena/resumo"]["get"]
    rota_replay_run = payload["paths"]["/ingestion/runs/{run_id}/replay"]["post"]
    rota_identity = payload["paths"]["/ingestion/identity/rebuild"]["post"]
    rota_tudo = payload["paths"]["/ingestion/sincronizacoes/tudo/{ano}"]["post"]

    assert rota_runs["summary"] == "Listar Runs de Ingestion"
    assert rota_run_phases["summary"] == "Listar fases de uma run de ingestion"
    assert "quality_summary" in rota_runs["description"]
    assert "members reaproveitados" in rota_runs["description"]
    assert rota_tudo["summary"] == "Disparar Sincronizacao Completa por Ano"
    assert "cadastro" in rota_tudo["description"]
    assert "ANOS_INICIAIS" in rota_tudo["description"]
    assert "execucao anual anterior tiver terminado em `falha`" in rota_tudo["description"]
    assert rota_tudo["parameters"][0]["name"] == "ano"
    assert rota_quarantine["summary"] == "Listar Quarentena de Ingestion"
    assert "motivo_codigo" in rota_quarantine["description"]
    params_quarentena = {p["name"] for p in rota_quarantine.get("parameters", [])}
    assert "motivo_codigo" in params_quarentena
    assert "arquivo_origem" in params_quarentena
    assert "status" in params_quarentena
    assert "ano_origem" in params_quarentena
    assert rota_replay_quarantine["summary"] == "Reprocessar Quarentena de Ingestion"
    assert "reason_code" in rota_replay_quarantine["description"]
    assert rota_quarentena_resumo["summary"] == "Resumo Analítico da Quarentena"
    assert "status" in rota_quarentena_resumo["description"]
    assert rota_replay_run["summary"] == "Reprocessar Run de Ingestion"
    assert rota_identity["summary"] == "Reconstruir Identidade de Ingestion"
    assert rota_runs["operationId"] == "listarIngestionRunsAdmin"
    assert rota_identity["operationId"] == "rebuildIngestionIdentityAdmin"
    assert rota_quarantine["operationId"] == "listarIngestionQuarentenaAdmin"
    assert rota_replay_quarantine["operationId"] == "replayIngestionQuarentenaAdmin"
    assert rota_quarentena_resumo["operationId"] == "resumoIngestionQuarentenaAdmin"

    esquema_run = payload["components"]["schemas"]["IngestionRunResumo"]
    esquema_quarentena = payload["components"]["schemas"]["QuarantineItemResposta"]
    esquema_replay_req = payload["components"]["schemas"]["ReplayQuarantineRequisicao"]
    esquema_resumo_quarentena = payload["components"]["schemas"]["QuarentenaResumoResposta"]

    assert "quality_summary" in esquema_run["properties"]
    assert "artifact_snapshot" in esquema_run["properties"]
    assert "member_snapshot_summary" in esquema_run["properties"]
    assert "delivery_snapshot_summary" in esquema_run["properties"]
    assert "reconcile_summary" in esquema_run["properties"]
    assert "lifecycle_decision" in esquema_run["properties"]
    assert "state" in esquema_run["properties"]
    assert "liveness" in esquema_run["properties"]
    assert "blocking" in esquema_run["properties"]
    assert "cancellation" in esquema_run["properties"]
    assert "next_action" in esquema_run["properties"]
    assert "members_reused_from_failed_parent" in esquema_run["properties"]["quality_summary"]["description"]
    assert "reaproveitados a partir de resultados anteriores" in esquema_run["properties"]["lifecycle_decision"]["description"]
    esquema_phase = payload["components"]["schemas"]["IngestionRunPhaseExecutionResumo"]
    assert "input_artifact_uri" in esquema_phase["properties"]
    assert "output_artifact_uri" in esquema_phase["properties"]
    assert "tentativas_reprocessamento" in esquema_quarentena["properties"]
    assert "total_pendentes" in esquema_resumo_quarentena["properties"]
    assert "total_resolvidos" in esquema_resumo_quarentena["properties"]
    assert "total_historico" in esquema_resumo_quarentena["properties"]
    assert esquema_replay_req["properties"]["reason_code"]["anyOf"][1]["type"] == "null"
    assert len(esquema_replay_req["examples"]) == 3


def test_admin_sincronizacao_detalhe_analise_arquivos(client: TestClient, db_session: Session) -> None:
    import uuid
    from datetime import UTC, datetime

    from app.models.ingestion import IngestionFile, IngestionFileMember, IngestionRun

    agora = datetime.now(UTC)
    execucao_id = uuid.uuid4()
    run_id = uuid.uuid4()
    file_id = uuid.uuid4()

    db_session.add(
        ExecucaoSincronizacao(
            id=execucao_id,
            tipo_fonte="dfp",
            ano=2020,
            arquivo="dfp_cia_aberta_2020.zip",
            url="http://exemplo",
            iniciada_em=agora,
            status="sucesso",
            total_linhas_lidas=10,
            total_inseridos=8,
            total_atualizados=1,
            total_inalterados=1,
            total_rejeitados=0,
        )
    )
    db_session.add(
        IngestionRun(
            id=run_id,
            execucao_sincronizacao_id=execucao_id,
            tipo_fonte="dfp",
            ano=2020,
            status="sucesso",
            phase="complete",
        )
    )
    db_session.add(
        IngestionFile(
            id=file_id,
            ingestion_run_id=run_id,
            source_url="http://exemplo",
            source_filename="dfp_cia_aberta_2020.zip",
            content_sha256="abc",
            content_length_bytes=1000,
        )
    )
    db_session.add(
        IngestionFileMember(
            ingestion_file_id=file_id,
            member_name="dfp_cia_aberta_2020.csv",
            member_sha256="def",
            member_size_bytes=5000,
            encoding="utf-8",
            delimiter=";",
            header=["CNPJ_CIA", "DT_REFER", "VERSAO", "ID_DOC"],
            row_count=10,
            schema_status="valid",
        )
    )
    db_session.commit()

    resposta = client.get(f"/ingestion/sincronizacoes/{execucao_id}")
    assert resposta.status_code == 200
    payload = resposta.json()
    assert payload["analise_arquivos"] is not None
    assert len(payload["analise_arquivos"]) == 1
    analise = payload["analise_arquivos"][0]
    assert analise["file_name"] == "dfp_cia_aberta_2020.csv"
    assert analise["file_size"] == "4.88 KB"
    assert analise["rows_count"] == 10
    assert analise["columns_count"] == 4
    assert analise["header_columns"] == ["CNPJ_CIA", "DT_REFER", "VERSAO", "ID_DOC"]
    assert analise["encoding"] == "utf-8"
    assert analise["delimiter"] == ";"


def test_admin_runs_expoem_estado_operacional_e_fases(client: TestClient, db_session: Session) -> None:
    agora = datetime.now(UTC)
    execucao_id = uuid.uuid4()
    run_id = uuid.uuid4()
    db_session.add(
        ExecucaoSincronizacao(
            id=execucao_id,
            tipo_fonte="dfp",
            ano=2026,
            arquivo="dfp_cia_aberta_2026.zip",
            url="http://exemplo/dfp-2026",
            status="em_execucao",
            tipo_execucao="arquivo_zip",
            total_rejeitados=2,
        )
    )
    db_session.add(
        IngestionRun(
            id=run_id,
            execucao_sincronizacao_id=execucao_id,
            tipo_fonte="dfp",
            ano=2026,
            status="em_execucao",
            phase="promote",
            requested_by_task_id="task-dfp-2026",
            quality_summary={"quarantine_total": 2, "members_processados": 3},
        )
    )
    db_session.flush()
    db_session.add(
        IngestionPhaseExecution(
            ingestion_run_id=run_id,
            execucao_sincronizacao_id=execucao_id,
            phase="promote",
            status="running",
            attempt=1,
            lease_owner="task-dfp-2026",
            task_id="task-dfp-2026",
            started_at=agora,
            heartbeat_at=agora - timedelta(hours=1),
            input_artifact_uri="/tmp/input.csv",
            output_artifact_uri="/tmp/output.csv",
            metrics={
                "members_processados": 3,
                "artifacts": [{"uri": "/tmp/output.csv", "role": "raw_member_payload"}],
            },
        )
    )
    db_session.add(
        IngestionCancellationRequest(
            scope_type="execucao_sincronizacao",
            scope_id=str(execucao_id),
            execucao_sincronizacao_id=execucao_id,
            ingestion_run_id=run_id,
            requested_by="api_admin",
            reason="janela operacional",
            terminate_immediately=True,
            status="propagated",
            affected_task_ids=["task-dfp-2026"],
            created_at=agora,
            propagated_at=agora,
        )
    )
    db_session.commit()

    resposta_runs = client.get("/ingestion/runs")
    assert resposta_runs.status_code == 200
    run_payload = resposta_runs.json()["dados"][0]
    assert run_payload["state"] == "stale"
    assert run_payload["liveness"]["is_stale"] is True
    assert run_payload["blocking"]["reason_code"] == "stale"
    assert run_payload["cancellation"]["status"] == "propagated"
    assert run_payload["next_action"] == "recover"
    assert run_payload["links"]["run_phases"] == f"/ingestion/runs/{run_id}/phases"

    resposta_run = client.get(f"/ingestion/runs/{run_id}")
    assert resposta_run.status_code == 200
    assert resposta_run.json()["state"] == "stale"

    resposta_execucao = client.get(f"/ingestion/sincronizacoes/{execucao_id}")
    assert resposta_execucao.status_code == 200
    execucao_payload = resposta_execucao.json()
    assert execucao_payload["state"] == "stale"
    assert execucao_payload["cancellation"]["status"] == "propagated"
    assert execucao_payload["next_action"] == "recover"

    resposta_fases = client.get(f"/ingestion/runs/{run_id}/phases")
    assert resposta_fases.status_code == 200
    fases_payload = resposta_fases.json()["dados"]
    assert len(fases_payload) == 1
    assert fases_payload[0]["phase"] == "promote"
    assert fases_payload[0]["status"] == "running"
    assert fases_payload[0]["task_id"] == "task-dfp-2026"
    assert fases_payload[0]["input_artifact_uri"] == "/tmp/input.csv"
    assert fases_payload[0]["output_artifact_uri"] == "/tmp/output.csv"
    assert fases_payload[0]["metrics"]["artifacts"][0]["uri"] == "/tmp/output.csv"


def test_admin_run_members_e_operations_expoem_snapshot_operacional(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agora = datetime.now(UTC)
    execucao_id = uuid.uuid4()
    run_id = uuid.uuid4()
    ingestion_file_id = uuid.uuid4()
    member_id = uuid.uuid4()
    artifact_snapshot_id = uuid.uuid4()
    db_session.add(
        ExecucaoSincronizacao(
            id=execucao_id,
            tipo_fonte="itr",
            ano=2026,
            arquivo="itr_cia_aberta_2026.zip",
            url="http://exemplo/itr-2026",
            status="em_execucao",
            tipo_execucao="arquivo_zip",
        )
    )
    db_session.add(
        IngestionRun(
            id=run_id,
            execucao_sincronizacao_id=execucao_id,
            tipo_fonte="itr",
            ano=2026,
            status="em_execucao",
            phase="promote",
            requested_by_task_id="task-itr-2026",
            quality_summary={"members_processados": 1},
        )
    )
    db_session.add(
        IngestionFile(
            id=ingestion_file_id,
            ingestion_run_id=run_id,
            source_url="http://exemplo/itr-2026.zip",
            source_filename="itr_cia_aberta_2026.zip",
            content_sha256="sha-zip",
            content_length_bytes=100,
            is_zip=True,
            already_seen_success=False,
        )
    )
    db_session.add(
        IngestionFileMember(
            id=member_id,
            ingestion_file_id=ingestion_file_id,
            member_name="itr_cia_aberta_BPA_con_2026.csv",
            member_sha256="sha-member",
            member_size_bytes=50,
            encoding="latin1",
            delimiter=";",
            header=["CNPJ_CIA", "DT_REFER"],
            row_count=10,
            schema_status="ok",
            schema_message=None,
        )
    )
    db_session.add(
        SourceArtifactSnapshot(
            id=artifact_snapshot_id,
            ingestion_run_id=run_id,
            tipo_fonte="itr",
            ano=2026,
            resource_url="http://exemplo/itr-2026.zip",
            source_filename="itr_cia_aberta_2026.zip",
            storage_uri="/tmp/artifacts/itr_cia_aberta_2026.zip",
            storage_role="raw_zip",
            storage_content_type="application/zip",
            storage_size_bytes=100,
            status="downloaded",
            download_required=True,
        )
    )
    db_session.add(
        SourceMemberSnapshot(
            artifact_snapshot_id=artifact_snapshot_id,
            ingestion_file_member_id=member_id,
            member_name="itr_cia_aberta_BPA_con_2026.csv",
            member_sha256="sha-member",
            raw_artifact_uri="/tmp/artifacts/itr_cia_aberta_BPA_con_2026.csv",
            raw_artifact_content_type="text/csv",
            raw_artifact_size_bytes=50,
            normalized_artifact_uri="/tmp/normalized/itr_cia_aberta_BPA_con_2026.csv",
            normalized_artifact_format="typed_csv",
            normalized_artifact_content_sha256="sha-normalized",
            normalized_artifact_size_bytes=40,
            row_count=10,
            header=["CNPJ_CIA", "DT_REFER"],
            row_kind="itr_demonstracao",
            destino_promovido="demonstracoes_financeiras",
            required_member=True,
            schema_status="ok",
            schema_message=None,
            delivery_index_role="none",
            lifecycle_status="processed",
        )
    )
    db_session.add(
        SourceDeliverySnapshot(
            artifact_snapshot_id=artifact_snapshot_id,
            ingestion_file_member_id=member_id,
            member_name="itr_cia_aberta_BPA_con_2026.csv",
            identity_hash="delivery-1",
            status="captured",
        )
    )
    db_session.add(
        IngestionPhaseExecution(
            ingestion_run_id=run_id,
            execucao_sincronizacao_id=execucao_id,
            phase="promote",
            status="running",
            attempt=1,
            lease_owner="task-itr-2026",
            task_id="task-itr-2026",
            started_at=agora,
            heartbeat_at=agora,
        )
    )
    db_session.commit()

    class _FakeInspect:
        def active(self) -> dict[str, list[dict[str, str]]]:
            return {"worker-a": [{"name": "app.worker.tasks.sincronizar_itr_task"}]}

        def reserved(self) -> dict[str, list[dict[str, str]]]:
            return {"worker-a": []}

        def scheduled(self) -> dict[str, list[dict[str, str]]]:
            return {"worker-a": [{"name": "app.worker.tasks.pre_processar_sincronizacao_task"}]}

    monkeypatch.setattr("app.api.routers.admin.celery_app.control.inspect", lambda timeout=1.0: _FakeInspect())

    resposta_run = client.get(f"/ingestion/runs/{run_id}")
    assert resposta_run.status_code == 200
    run_payload = resposta_run.json()
    assert run_payload["artifact_snapshot"]["storage_uri"] == "/tmp/artifacts/itr_cia_aberta_2026.zip"
    assert run_payload["artifact_snapshot"]["storage_role"] == "raw_zip"
    assert run_payload["member_snapshot_summary"]["members"][0]["raw_artifact_uri"] == "/tmp/artifacts/itr_cia_aberta_BPA_con_2026.csv"
    assert run_payload["member_snapshot_summary"]["members"][0]["normalized_artifact_uri"] == "/tmp/normalized/itr_cia_aberta_BPA_con_2026.csv"
    assert run_payload["member_snapshot_summary"]["members"][0]["normalized_artifact_format"] == "typed_csv"

    resposta_members = client.get(f"/ingestion/runs/{run_id}/members")
    assert resposta_members.status_code == 200
    members_payload = resposta_members.json()["dados"]
    assert len(members_payload) == 1
    assert members_payload[0]["member_name"] == "itr_cia_aberta_BPA_con_2026.csv"
    assert members_payload[0]["state"] == "processed"
    assert members_payload[0]["delivery_total"] == 1
    assert members_payload[0]["links"]["cancel"] == f"/ingestion/runs/{run_id}/members/{member_id}/cancel"

    resposta_operations = client.get("/ingestion/operations")
    assert resposta_operations.status_code == 200
    payload = resposta_operations.json()
    assert payload["task_counts"]["ingestion_active"] == 1
    assert payload["task_counts"]["ingestion_scheduled"] == 1
    assert payload["materialization_gate"]["status"] in {"green", "red"}


def test_admin_run_failed_retryable_expoe_next_action_recover(client: TestClient, db_session: Session) -> None:
    agora = datetime.now(UTC)
    execucao_id = uuid.uuid4()
    run_id = uuid.uuid4()
    db_session.add(
        ExecucaoSincronizacao(
            id=execucao_id,
            tipo_fonte="itr",
            ano=2026,
            arquivo="itr_cia_aberta_2026.zip",
            url="http://exemplo/itr-2026",
            status="falha",
            tipo_execucao="arquivo_zip",
            mensagem_erro="falha recuperavel",
            finalizada_em=agora,
        )
    )
    db_session.add(
        IngestionRun(
            id=run_id,
            execucao_sincronizacao_id=execucao_id,
            tipo_fonte="itr",
            ano=2026,
            status="falha",
            phase="promote",
            requested_by_task_id="task-itr-2026",
            message="falha recuperavel",
        )
    )
    db_session.flush()
    db_session.add(
        IngestionPhaseExecution(
            ingestion_run_id=run_id,
            execucao_sincronizacao_id=execucao_id,
            phase="promote",
            status="failed_final",
            attempt=1,
            lease_owner="task-itr-2026",
            task_id="task-itr-2026",
            started_at=agora - timedelta(minutes=10),
            heartbeat_at=agora - timedelta(minutes=5),
            finished_at=agora,
            error_type="stale_phase",
            error_message="falha recuperavel",
            error_retryable=True,
        )
    )
    db_session.commit()

    resposta_run = client.get(f"/ingestion/runs/{run_id}")
    assert resposta_run.status_code == 200
    assert resposta_run.json()["state"] == "failed"
    assert resposta_run.json()["next_action"] == "recover"


def test_admin_run_cancel_member_cancel_e_recover(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agora = datetime.now(UTC)
    parent_execucao_id = uuid.uuid4()
    child_execucao_id = uuid.uuid4()
    run_id = uuid.uuid4()
    ingestion_file_id = uuid.uuid4()
    member_id = uuid.uuid4()
    revoked: list[str] = []
    replay_calls: list[str] = []

    db_session.add(
        ExecucaoSincronizacao(
            id=parent_execucao_id,
            id_tarefa="task-parent",
            tipo_fonte="dfp",
            ano=2026,
            arquivo="dfp_cia_aberta_2026.zip",
            url="http://exemplo/dfp-2026",
            status="em_execucao",
            tipo_execucao="arquivo_zip",
        )
    )
    db_session.add(
        ExecucaoSincronizacao(
            id=child_execucao_id,
            parent_execucao_id=parent_execucao_id,
            id_tarefa="task-child",
            tipo_fonte="dfp",
            ano=2026,
            arquivo="dfp_cia_aberta_BPA_con_2026.csv",
            url="http://exemplo/dfp-2026",
            status="em_execucao",
            tipo_execucao="arquivo_membro",
        )
    )
    db_session.add(
        IngestionRun(
            id=run_id,
            execucao_sincronizacao_id=parent_execucao_id,
            tipo_fonte="dfp",
            ano=2026,
            status="em_execucao",
            phase="promote",
            requested_by_task_id="task-parent",
        )
    )
    db_session.add(
        IngestionFile(
            id=ingestion_file_id,
            ingestion_run_id=run_id,
            source_url="http://exemplo/dfp-2026.zip",
            source_filename="dfp_cia_aberta_2026.zip",
            content_sha256="sha-zip",
            content_length_bytes=100,
            is_zip=True,
            already_seen_success=False,
        )
    )
    db_session.add(
        IngestionFileMember(
            id=member_id,
            ingestion_file_id=ingestion_file_id,
            member_name="dfp_cia_aberta_BPA_con_2026.csv",
            member_sha256="sha-member",
            member_size_bytes=50,
            encoding="latin1",
            delimiter=";",
            header=["CNPJ_CIA"],
            row_count=10,
            schema_status="ok",
            schema_message=None,
        )
    )
    db_session.add(
        IngestionPhaseExecution(
            ingestion_run_id=run_id,
            execucao_sincronizacao_id=parent_execucao_id,
            phase="promote",
            status="running",
            attempt=1,
            lease_owner="task-parent",
            task_id="task-parent",
            started_at=agora,
            heartbeat_at=agora - timedelta(hours=1),
        )
    )
    db_session.commit()

    monkeypatch.setattr(
        "app.api.routers.admin.celery_app.control.revoke",
        lambda task_id, terminate, signal: revoked.append(task_id),
    )

    def _fake_replay(db: Session, run_id: uuid.UUID) -> dict[str, str]:
        replay_calls.append(str(run_id))
        return {"status": "replayed", "run_id": str(run_id)}

    monkeypatch.setattr(
        "app.api.routers.admin.replay_ingestion_run_service",
        _fake_replay,
    )

    resposta_member_cancel = client.post(f"/ingestion/runs/{run_id}/members/{member_id}/cancel")
    assert resposta_member_cancel.status_code == 200
    assert resposta_member_cancel.json()["id_execucao"] == str(child_execucao_id)
    assert "task-child" in revoked

    resposta_run_cancel = client.post(f"/ingestion/runs/{run_id}/cancel")
    assert resposta_run_cancel.status_code == 200
    assert resposta_run_cancel.json()["id_execucao"] == str(parent_execucao_id)
    assert "task-parent" in revoked

    db_session.query(IngestionPhaseExecution).delete()
    db_session.add(
        IngestionPhaseExecution(
            ingestion_run_id=run_id,
            execucao_sincronizacao_id=parent_execucao_id,
            phase="promote",
            status="running",
            attempt=2,
            lease_owner="task-parent",
            task_id="task-parent",
            started_at=agora,
            heartbeat_at=agora - timedelta(hours=1),
        )
    )
    run = db_session.get(IngestionRun, run_id)
    assert run is not None
    run.status = "em_execucao"
    execucao = db_session.get(ExecucaoSincronizacao, parent_execucao_id)
    assert execucao is not None
    execucao.status = "em_execucao"
    db_session.commit()

    resposta_recover = client.post(f"/ingestion/runs/{run_id}/recover")
    assert resposta_recover.status_code == 200
    assert replay_calls == [str(run_id)]
    assert resposta_recover.json()["detalhe"]["status"] == "replayed"


def test_admin_pre_processar_cadastro_agenda_tarefa(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.api.routers.admin.pre_processar_sincronizacao_task.delay",
        lambda tipo_fonte, force_reimport: SimpleNamespace(id=f"task-preprocess-{tipo_fonte}-{force_reimport}"),
    )

    resposta = client.post("/ingestion/sincronizacoes/pre-processar/cadastro?force_reimport=true")
    assert resposta.status_code == 200
    assert resposta.json() == {"id_tarefa": "task-preprocess-cadastro-True", "status": "agendada"}


def test_admin_pre_processar_fonte_anual_agenda_tarefa(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.api.routers.admin.pre_processar_sincronizacao_task.delay",
        lambda tipo_fonte, ano, force_reimport: SimpleNamespace(id=f"task-preprocess-{tipo_fonte}-{ano}-{force_reimport}"),
    )

    resposta = client.post("/ingestion/sincronizacoes/pre-processar/dfp/2025?force_reimport=true")
    assert resposta.status_code == 200
    assert resposta.json() == {"id_tarefa": "task-preprocess-dfp-2025-True", "status": "agendada"}

    # Unsupported source path
    resposta_invalid = client.post("/ingestion/sincronizacoes/pre-processar/invalid_source/2025")
    assert resposta_invalid.status_code == 422


def test_admin_ingerir_fonte_pre_processada_route(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, db_session: Session
) -> None:
    exec_uuid = uuid.uuid4()
    # 1. Non-existent execution
    resposta_404 = client.post(f"/ingestion/sincronizacoes/{exec_uuid}/ingerir")
    assert resposta_404.status_code == 404

    # 2. Execution with wrong status
    exec_wrong = ExecucaoSincronizacao(
        id=exec_uuid,
        tipo_fonte="dfp",
        ano=2024,
        arquivo="dfp_cia_aberta_2024.zip",
        url="http://example.com/dfp",
        status="em_execucao",
        tipo_execucao="arquivo_zip",
    )
    db_session.add(exec_wrong)
    db_session.commit()

    resposta_400 = client.post(f"/ingestion/sincronizacoes/{exec_uuid}/ingerir")
    assert resposta_400.status_code == 400
    assert "esta com status 'em_execucao'" in resposta_400.json()["detail"]

    # 3. Execution in "aguardando_ingestao"
    exec_wrong.status = "aguardando_ingestao"
    db_session.commit()

    monkeypatch.setattr(
        "app.api.routers.admin.ingerir_sincronizacao_task.delay",
        lambda execucao_id, force_reimport: SimpleNamespace(id=f"task-ingest-{execucao_id}-{force_reimport}"),
    )

    resposta_ok = client.post(f"/ingestion/sincronizacoes/{exec_uuid}/ingerir?force_reimport=true")
    assert resposta_ok.status_code == 200
    assert resposta_ok.json() == {"id_tarefa": f"task-ingest-{exec_uuid}-True", "status": "agendada"}
