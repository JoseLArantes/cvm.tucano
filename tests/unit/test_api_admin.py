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

    monkeypatch.setattr(
        "app.api.routers.admin.sincronizar_cadastro_companhias_task.delay",
        lambda: SimpleNamespace(id="task-cadastro"),
    )
    monkeypatch.setattr(
        "app.api.routers.admin.sincronizar_dfp_task.delay",
        lambda ano: SimpleNamespace(id=f"task-dfp-{ano}"),
    )
    monkeypatch.setattr(
        "app.api.routers.admin.sincronizar_itr_task.delay",
        lambda ano: SimpleNamespace(id=f"task-itr-{ano}"),
    )
    monkeypatch.setattr(
        "app.api.routers.admin.sincronizar_fre_task.delay",
        lambda ano: SimpleNamespace(id=f"task-fre-{ano}"),
    )

    resposta = client.post("/admin/sincronizacoes/tudo")
    assert resposta.status_code == 200
    payload = resposta.json()
    assert payload["status"] == "agendada"
    assert len(payload["tarefas"]) == 4


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


def test_admin_cancelar_sincronizacao_por_execucao(client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_admin_cancelar_sincronizacao_por_tarefa_sem_execucao(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
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
