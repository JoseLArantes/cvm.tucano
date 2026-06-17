import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.companhia import Companhia
from app.models.vlmo import VlmoConsolidado, VlmoDocumento


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
        hash_origem="companhia-vlmo-api",
        criado_em=agora,
        sincronizado_em=agora,
        alterado_em=agora,
    )


def _seed_vlmo(db: Session, companhia_id: uuid.UUID) -> None:
    agora = datetime.now(UTC)
    db.add(
        VlmoDocumento(
            companhia_id=companhia_id,
            cnpj_companhia="00000000000191",
            codigo_cvm=1023,
            nome_companhia="Banco do Brasil S.A.",
            data_referencia=date(2025, 1, 1),
            categoria="Negociacao Administradores",
            tipo="Consolidado",
            data_entrega=date(2025, 1, 15),
            tipo_apresentacao="Original",
            motivo_reapresentacao=None,
            protocolo_entrega="123456",
            versao=1,
            link_download="http://vlmo/documento",
            arquivo_origem="vlmo_cia_aberta_2025.csv",
            ano_origem=2025,
            linha_origem=2,
            hash_origem="hash-vlmo-documento",
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )
    db.add(
        VlmoConsolidado(
            companhia_id=companhia_id,
            cnpj_companhia="00000000000191",
            nome_companhia="Banco do Brasil S.A.",
            data_referencia=date(2025, 1, 1),
            versao=1,
            tipo_empresa="Pessoa Vinculada",
            empresa="Controlador",
            tipo_cargo="Diretor",
            tipo_movimentacao="Negociacao",
            descricao_movimentacao="Compra em mercado",
            tipo_operacao="Compra",
            tipo_ativo="Acao Ordinaria",
            caracteristica_valor_mobiliario="ON",
            intermediario="Corretora X",
            data_movimentacao=date(2025, 1, 10),
            quantidade=100,
            preco_unitario=Decimal("10.50"),
            volume=Decimal("1050.00"),
            indice_ocorrencia=1,
            arquivo_origem="vlmo_cia_aberta_con_2025.csv",
            ano_origem=2025,
            linha_origem=2,
            hash_origem="hash-vlmo-consolidado",
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )
    db.commit()


def test_endpoints_vlmo(client: TestClient, db_session: Session) -> None:
    companhia = _companhia()
    db_session.add(companhia)
    db_session.commit()
    _seed_vlmo(db_session, companhia.id)

    assert client.get("/vlmo/documentos?cnpj_companhia=00.000.000/0001-91").json()["paginacao"]["total"] == 1
    assert client.get("/vlmo/documentos?codigo_cvm=1023").json()["paginacao"]["total"] == 1
    assert client.get("/vlmo/documentos?categoria=Negociacao%20Administradores").json()["paginacao"]["total"] == 1
    assert client.get("/vlmo/documentos?tipo=Consolidado&ano_origem=2025&versao=1").json()["paginacao"]["total"] == 1
    assert client.get("/vlmo/documentos?ordenar_por=campo_invalido").status_code == 422

    assert client.get("/vlmo/consolidado?cnpj_companhia=00.000.000/0001-91").json()["paginacao"]["total"] == 1
    assert client.get("/vlmo/consolidado?tipo_ativo=Acao%20Ordinaria").json()["paginacao"]["total"] == 1
    assert client.get("/vlmo/consolidado?tipo_operacao=Compra&empresa=Controlador").json()["paginacao"]["total"] == 1
    assert client.get("/vlmo/consolidado?intermediario=Corretora%20X").json()["paginacao"]["total"] == 1
    assert client.get(
        "/vlmo/consolidado?data_movimentacao_inicio=2025-01-01&data_movimentacao_fim=2025-01-31"
    ).json()["paginacao"]["total"] == 1
    assert client.get("/vlmo/consolidado?tipo_operacao=Venda").json()["paginacao"]["total"] == 0
    assert client.get("/vlmo/consolidado?ordenar_por=campo_invalido").status_code == 422
