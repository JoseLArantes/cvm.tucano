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
