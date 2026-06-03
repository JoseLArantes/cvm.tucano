from datetime import UTC, date, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.companhia import Companhia


def _nova_companhia(cnpj: str, codigo_cvm: int, nome: str) -> Companhia:
    agora = datetime.now(UTC)
    return Companhia(
        cnpj_companhia=cnpj,
        codigo_cvm=codigo_cvm,
        denominacao_social=nome,
        denominacao_comercial=nome,
        situacao_registro="ATIVA",
        data_registro=date(2020, 1, 1),
        data_constituicao=date(2000, 1, 1),
        data_cancelamento=None,
        motivo_cancelamento=None,
        data_inicio_situacao=date(2020, 1, 1),
        setor_atividade="Energia",
        tipo_mercado="Categoria A",
        categoria_registro="Categoria A",
        data_inicio_categoria=date(2020, 1, 1),
        situacao_emissor="ATIVO",
        data_inicio_situacao_emissor=date(2020, 1, 1),
        controle_acionario="PRIVADO",
        endereco={"municipio": "Sao Paulo"},
        responsavel={"nome_responsavel": "Fulano"},
        auditor="Auditoria X",
        cnpj_auditor="10830108000165",
        arquivo_origem="cad_cia_aberta.csv",
        ano_origem=None,
        linha_origem=1,
        hash_origem="abc",
        criado_em=agora,
        sincronizado_em=agora,
        alterado_em=agora,
    )


def test_get_companhias_paginado(client: TestClient, db_session: Session) -> None:
    db_session.add(_nova_companhia("08773135000100", 25224, "Empresa A"))
    db_session.add(_nova_companhia("11396633000187", 21954, "Empresa B"))
    db_session.commit()

    resp = client.get("/companhias?pagina=1&tamanho_pagina=1")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["paginacao"]["pagina"] == 1
    assert payload["paginacao"]["tamanho_pagina"] == 1
    assert payload["paginacao"]["total"] == 2
    assert len(payload["dados"]) == 1


def test_get_companhia_por_cnpj(client: TestClient, db_session: Session) -> None:
    db_session.add(_nova_companhia("08773135000100", 25224, "Empresa A"))
    db_session.commit()

    resp = client.get("/companhias/08.773.135/0001-00")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["cnpj_companhia"] == "08773135000100"
    assert payload["codigo_cvm"] == 25224


def test_get_companhia_por_codigo_cvm(client: TestClient, db_session: Session) -> None:
    db_session.add(_nova_companhia("08773135000100", 25224, "Empresa A"))
    db_session.commit()

    resp = client.get("/companhias/codigo-cvm/25224")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["cnpj_companhia"] == "08773135000100"
