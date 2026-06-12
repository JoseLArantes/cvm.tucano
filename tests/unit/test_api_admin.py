import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.sincronizacao import ExecucaoSincronizacao, HistoricoAlteracaoCampo, RegistroQuarentena


def test_admin_sincronizacao_tudo_agenda_tarefas(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "anos_iniciais_dfp", "2024")
    monkeypatch.setattr(settings, "anos_iniciais_itr", "2025")
    monkeypatch.setattr(settings, "anos_iniciais_fre", "2026")
    monkeypatch.setattr(settings, "anos_iniciais_fca", "2027")
    monkeypatch.setattr(settings, "anos_iniciais_ipe", "2028")
    monkeypatch.setattr(settings, "anos_iniciais_vlmo", "2029")
    monkeypatch.setattr(settings, "anos_iniciais_cgvn", "2030")

    wf_applied = False

    class FakeWorkflow:
        def apply_async(self) -> None:
            nonlocal wf_applied
            wf_applied = True

    monkeypatch.setattr("app.api.routers.admin.chain", lambda *args, **kwargs: FakeWorkflow())
    monkeypatch.setattr("app.api.routers.admin.group", lambda *args, **kwargs: FakeWorkflow())

    resposta = client.post("/admin/sincronizacoes/tudo?force_reimport=true")
    assert resposta.status_code == 200
    payload = resposta.json()
    assert payload["status"] == "agendada"
    assert len(payload["tarefas"]) == 8
    assert wf_applied is True


def test_admin_fontes_endpoints_expoem_registry(client: TestClient) -> None:
    resposta_lista = client.get("/admin/fontes")
    resposta_detalhe = client.get("/admin/fontes/fre")
    resposta_inexistente = client.get("/admin/fontes/inexistente")

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

    resposta = client.post("/admin/sincronizacoes/vlmo/2025?force_reimport=true")

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
                    "ano": 2025,
                    "url": "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/FRE/DADOS/fre_cia_aberta_2025.zip",
                    "arquivo_principal": "fre_cia_aberta_2025.zip",
                    "acessivel": True,
                    "sha256": "abc",
                    "tamanho_bytes": 10,
                    "datasets_esperados": 6,
                    "datasets_encontrados": 6,
                    "datasets_faltantes": 0,
                    "datasets": [],
                    "observacoes": None,
                }
            ],
            "total_fontes": 1,
            "total_fontes_acessiveis": 1,
            "total_datasets_faltantes": 0,
        },
    )

    resposta = client.post("/admin/fontes/auditar", json={"ano": 2025, "fontes": ["fre"]})

    assert resposta.status_code == 200
    payload = resposta.json()
    assert payload["ano"] == 2025
    assert payload["total_fontes"] == 1
    assert payload["fontes"][0]["fonte"] == "fre"
    assert payload["fontes"][0]["datasets_faltantes"] == 0


def test_admin_reprocessar_arquivo_valida_registry_para_csv_e_zip(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, db_session: Session
) -> None:
    from app.models.ingestion import IngestionFile, IngestionRun

    # Seed parent executions for fre, ipe, vlmo
    for fonte in ("fre", "ipe", "vlmo"):
        exec_pai = ExecucaoSincronizacao(
            id=uuid.uuid4(),
            tipo_fonte=fonte,
            ano=2025,
            arquivo=f"{fonte}_cia_aberta_2025.zip",
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
            ano=2025,
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

    resposta_zip = client.post("/admin/sincronizacoes/reprocessar-arquivo", json={"arquivo": "dfp_cia_aberta_2025.zip"})
    resposta_csv = client.post(
        "/admin/sincronizacoes/reprocessar-arquivo",
        json={"arquivo": "fre_cia_aberta_2025.csv", "ano": 2025},
    )
    resposta_fca = client.post("/admin/sincronizacoes/reprocessar-arquivo", json={"arquivo": "fca_cia_aberta_2025.zip"})
    resposta_ipe_zip = client.post(
        "/admin/sincronizacoes/reprocessar-arquivo", json={"arquivo": "ipe_cia_aberta_2025.zip"}
    )
    resposta_ipe_csv = client.post(
        "/admin/sincronizacoes/reprocessar-arquivo",
        json={"arquivo": "ipe_cia_aberta_2025.csv", "ano": 2025},
    )
    resposta_vlmo_zip = client.post(
        "/admin/sincronizacoes/reprocessar-arquivo", json={"arquivo": "vlmo_cia_aberta_2025.zip"}
    )
    resposta_vlmo_csv = client.post(
        "/admin/sincronizacoes/reprocessar-arquivo",
        json={"arquivo": "vlmo_cia_aberta_con_2025.csv", "ano": 2025},
    )
    resposta_invalida = client.post(
        "/admin/sincronizacoes/reprocessar-arquivo",
        json={"arquivo": "arquivo_inexistente_2025.csv", "ano": 2025},
    )

    assert resposta_zip.status_code == 200
    assert resposta_zip.json()["tarefas"][0]["tipo_fonte"] == "dfp"
    assert resposta_zip.json()["tarefas"][0]["id_tarefa"] == "task-dfp-2025-False"
    assert resposta_csv.status_code == 200
    assert resposta_csv.json()["tarefas"][0]["tipo_fonte"] == "fre_membro"
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
        "/admin/sincronizacoes/reprocessar-arquivo",
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
    db_session.add(
        RegistroQuarentena(
            execucao_sincronizacao_id=execucao_id,
            arquivo_origem="dfp_cia_aberta_2025.csv",
            ano_origem=2025,
            linha_origem=5,
            motivo="companhia_nao_encontrada",
            dados_originais={"CNPJ_CIA": "000"},
            criado_em=agora,
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

    resposta_dashboard = client.get("/admin/dashboard")
    assert resposta_dashboard.status_code == 200
    assert resposta_dashboard.json()["total_execucoes"] == 1

    resposta_quarentena = client.get("/admin/quarentena")
    assert resposta_quarentena.status_code == 200
    assert resposta_quarentena.json()["paginacao"]["total"] == 1

    resposta_alteracoes = client.get("/admin/alteracoes")
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
        "/admin/sincronizacoes/cancelar",
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


def test_admin_cancelar_sincronizacao_por_tarefa_sem_execucao(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    chamadas: list[tuple[str, bool, str]] = []

    def fake_revoke(task_id: str, terminate: bool, signal: str) -> None:
        chamadas.append((task_id, terminate, signal))

    monkeypatch.setattr("app.api.routers.admin.celery_app.control.revoke", fake_revoke)

    resposta = client.post(
        "/admin/sincronizacoes/cancelar",
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
        "/admin/sincronizacoes/cancelar",
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
        "/admin/sincronizacoes/cancelar",
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


def test_openapi_documenta_cancelamento_sincronizacao(client: TestClient) -> None:
    resposta = client.get("/openapi.json")

    assert resposta.status_code == 200
    payload = resposta.json()
    operacao = payload["paths"]["/admin/sincronizacoes/cancelar"]["post"]
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

    assert "/admin/ingestion-v2/runs" not in payload["paths"]
    assert "/admin/ingestion-v2/quarantine" not in payload["paths"]

    rota_runs = payload["paths"]["/admin/ingestion/runs"]["get"]
    rota_quarantine = payload["paths"]["/admin/ingestion/quarantine"]["get"]
    rota_replay_quarantine = payload["paths"]["/admin/ingestion/replay/quarantine"]["post"]
    rota_replay_run = payload["paths"]["/admin/ingestion/runs/{run_id}/replay"]["post"]
    rota_identity = payload["paths"]["/admin/ingestion/identity/rebuild"]["post"]

    assert rota_runs["summary"] == "Listar Runs de Ingestion"
    assert "quality_summary" in rota_runs["description"]
    assert rota_quarantine["summary"] == "Listar Quarentena de Ingestion"
    assert "motivo_codigo" in rota_quarantine["description"]
    assert rota_replay_quarantine["summary"] == "Reprocessar Quarentena de Ingestion"
    assert "reason_code" in rota_replay_quarantine["description"]
    assert rota_replay_run["summary"] == "Reprocessar Run de Ingestion"
    assert rota_identity["summary"] == "Reconstruir Identidade de Ingestion"
    assert rota_runs["operationId"] == "listarIngestionRunsAdmin"
    assert rota_identity["operationId"] == "rebuildIngestionIdentityAdmin"

    esquema_run = payload["components"]["schemas"]["IngestionRunResumo"]
    esquema_quarentena = payload["components"]["schemas"]["QuarantineItemResposta"]
    esquema_replay_req = payload["components"]["schemas"]["ReplayQuarantineRequisicao"]

    assert "quality_summary" in esquema_run["properties"]
    assert "tentativas_reprocessamento" in esquema_quarentena["properties"]
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

    resposta = client.get(f"/admin/sincronizacoes/{execucao_id}")
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


def test_admin_pre_processar_cadastro_agenda_tarefa(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.api.routers.admin.pre_processar_sincronizacao_task.delay",
        lambda tipo_fonte, force_reimport: SimpleNamespace(id=f"task-preprocess-{tipo_fonte}-{force_reimport}"),
    )

    resposta = client.post("/admin/sincronizacoes/pre-processar/cadastro?force_reimport=true")
    assert resposta.status_code == 200
    assert resposta.json() == {"id_tarefa": "task-preprocess-cadastro-True", "status": "agendada"}


def test_admin_pre_processar_fonte_anual_agenda_tarefa(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.api.routers.admin.pre_processar_sincronizacao_task.delay",
        lambda tipo_fonte, ano, force_reimport: SimpleNamespace(id=f"task-preprocess-{tipo_fonte}-{ano}-{force_reimport}"),
    )

    resposta = client.post("/admin/sincronizacoes/pre-processar/dfp/2025?force_reimport=true")
    assert resposta.status_code == 200
    assert resposta.json() == {"id_tarefa": "task-preprocess-dfp-2025-True", "status": "agendada"}

    # Unsupported source path
    resposta_invalid = client.post("/admin/sincronizacoes/pre-processar/invalid_source/2025")
    assert resposta_invalid.status_code == 422


def test_admin_ingerir_fonte_pre_processada_route(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, db_session: Session
) -> None:
    exec_uuid = uuid.uuid4()
    # 1. Non-existent execution
    resposta_404 = client.post(f"/admin/sincronizacoes/{exec_uuid}/ingerir")
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

    resposta_400 = client.post(f"/admin/sincronizacoes/{exec_uuid}/ingerir")
    assert resposta_400.status_code == 400
    assert "esta com status 'em_execucao'" in resposta_400.json()["detail"]

    # 3. Execution in "aguardando_ingestao"
    exec_wrong.status = "aguardando_ingestao"
    db_session.commit()

    monkeypatch.setattr(
        "app.api.routers.admin.ingerir_sincronizacao_task.delay",
        lambda execucao_id, force_reimport: SimpleNamespace(id=f"task-ingest-{execucao_id}-{force_reimport}"),
    )

    resposta_ok = client.post(f"/admin/sincronizacoes/{exec_uuid}/ingerir?force_reimport=true")
    assert resposta_ok.status_code == 200
    assert resposta_ok.json() == {"id_tarefa": f"task-ingest-{exec_uuid}-True", "status": "agendada"}
