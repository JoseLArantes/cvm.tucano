import uuid
from datetime import UTC, date, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.companhia import Companhia
from app.models.ipe import IpeDocumento


def _companhia() -> Companhia:
    agora = datetime.now(UTC)
    return Companhia(
        cnpj_companhia="00000000000191",
        codigo_cvm=1023,
        denominacao_social="Banco do Brasil",
        denominacao_comercial="Banco do Brasil",
        situacao_registro="ATIVA",
        data_registro=date(2020, 1, 1),
        data_constituicao=date(1808, 10, 12),
        data_inicio_situacao=date(2020, 1, 1),
        setor_atividade="Bancos",
        tipo_mercado="Categoria A",
        categoria_registro="Categoria A",
        data_inicio_categoria=date(2020, 1, 1),
        situacao_emissor="ATIVO",
        data_inicio_situacao_emissor=date(2020, 1, 1),
        controle_acionario="ESTATAL",
        endereco={"municipio": "Brasilia"},
        responsavel={"nome_responsavel": "Fulano"},
        auditor="KPMG",
        cnpj_auditor="57755217001281",
        arquivo_origem="cad_cia_aberta.csv",
        ano_origem=None,
        linha_origem=2,
        hash_origem="companhia-ipe",
        criado_em=agora,
        sincronizado_em=agora,
        alterado_em=agora,
    )


def _seed_ipe(db: Session, companhia_id: uuid.UUID) -> None:
    agora = datetime.now(UTC)
    db.add(
        IpeDocumento(
            companhia_id=companhia_id,
            cnpj_companhia="00000000000191",
            codigo_cvm=1023,
            nome_companhia="Banco do Brasil S.A.",
            data_referencia=date(2025, 1, 1),
            categoria="Categoria X",
            tipo="Tipo X",
            especie="Especie X",
            assunto="Assunto X",
            data_entrega=date(2025, 1, 15),
            tipo_apresentacao="Apresentacao",
            protocolo_entrega="123456",
            versao=1,
            link_download="http://ipe",
            arquivo_origem="ipe_cia_aberta_2025.csv",
            ano_origem=2025,
            linha_origem=2,
            hash_origem="hash-ipe",
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )
    db.commit()


def test_endpoints_ipe(client: TestClient, db_session: Session) -> None:
    companhia = _companhia()
    db_session.add(companhia)
    db_session.commit()
    _seed_ipe(db_session, companhia.id)

    assert client.get("/ipe/documentos?cnpj_companhia=00.000.000/0001-91").json()["paginacao"]["total"] == 1
    assert client.get("/ipe/documentos?codigo_cvm=1023").json()["paginacao"]["total"] == 1
    assert client.get("/ipe/documentos?data_entrega_inicio=2025-01-01&data_entrega_fim=2025-12-31").json()[
        "paginacao"
    ]["total"] == 1
    assert client.get("/ipe/documentos?categoria=Categoria%20X").json()["paginacao"]["total"] == 1
    assert client.get("/ipe/documentos?categoria=Outro").json()["paginacao"]["total"] == 0
    assert client.get("/ipe/documentos?tipo=Tipo%20X&assunto=Assunto%20X").json()["paginacao"]["total"] == 1
    assert client.get("/ipe/documentos?ano_origem=2025&versao=1").json()["paginacao"]["total"] == 1
    assert client.get("/ipe/documentos?ordenar_por=campo_invalido").status_code == 422
