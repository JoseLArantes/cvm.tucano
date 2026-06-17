import uuid
from datetime import UTC, date, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.cgvn import CgvnDocumento, CgvnPratica
from app.models.companhia import Companhia


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
        hash_origem="companhia-cgvn-api",
        criado_em=agora,
        sincronizado_em=agora,
        alterado_em=agora,
    )


def _seed_cgvn(db: Session, companhia_id: uuid.UUID) -> None:
    agora = datetime.now(UTC)
    db.add(
        CgvnDocumento(
            companhia_id=companhia_id,
            cnpj_companhia="00000000000191",
            codigo_cvm=1023,
            nome_companhia="Banco do Brasil S.A.",
            data_referencia=date(2025, 1, 1),
            data_entrega=date(2025, 1, 15),
            data_inicio_exercicio_social=date(2025, 1, 1),
            data_fim_exercicio_social=date(2025, 12, 31),
            id_documento=123456,
            versao=1,
            link_download="http://cgvn/documento",
            categoria="Informe de Governança",
            motivo_reapresentacao=None,
            arquivo_origem="cgvn_cia_aberta_2025.csv",
            ano_origem=2025,
            linha_origem=2,
            hash_origem="hash-cgvn-documento",
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )
    db.add(
        CgvnPratica(
            companhia_id=companhia_id,
            cnpj_companhia="00000000000191",
            nome_companhia="Banco do Brasil S.A.",
            data_referencia=date(2025, 1, 1),
            id_documento=123456,
            versao=1,
            id_item="1.1.1",
            pratica_recomendada="Recomendacao 1.1.1",
            pratica_adotada="Sim",
            capitulo="Capitulo 1",
            principio="Principio 1",
            explicacao="Adotado integralmente.",
            arquivo_origem="cgvn_cia_aberta_praticas_2025.csv",
            ano_origem=2025,
            linha_origem=2,
            hash_origem="hash-cgvn-pratica",
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )
    db.commit()


def test_endpoints_cgvn(client: TestClient, db_session: Session) -> None:
    companhia = _companhia()
    db_session.add(companhia)
    db_session.commit()
    _seed_cgvn(db_session, companhia.id)

    assert client.get("/cgvn/documentos?cnpj_companhia=00.000.000/0001-91").json()["paginacao"]["total"] == 1
    assert client.get("/cgvn/documentos?codigo_cvm=1023").json()["paginacao"]["total"] == 1
    assert client.get("/cgvn/documentos?categoria=Informe%20de%20Governan%C3%A7a").json()["paginacao"]["total"] == 1
    assert client.get("/cgvn/documentos?id_documento=123456&ano_origem=2025&versao=1").json()["paginacao"]["total"] == 1
    assert client.get("/cgvn/documentos?ordenar_por=campo_invalido").status_code == 422

    assert client.get("/cgvn/praticas?cnpj_companhia=00.000.000/0001-91").json()["paginacao"]["total"] == 1
    assert client.get("/cgvn/praticas?id_item=1.1.1").json()["paginacao"]["total"] == 1
    assert client.get("/cgvn/praticas?pratica_adotada=Sim").json()["paginacao"]["total"] == 1
    assert client.get("/cgvn/praticas?id_documento=123456").json()["paginacao"]["total"] == 1
    assert client.get("/cgvn/praticas?pratica_adotada=Não").json()["paginacao"]["total"] == 0
    assert client.get("/cgvn/praticas?ordenar_por=campo_invalido").status_code == 422
