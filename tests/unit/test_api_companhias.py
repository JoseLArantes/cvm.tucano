from datetime import UTC, date, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.companhia import Companhia
from app.models.fca import FcaValorMobiliario


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


def _novo_valor_mobiliario(
    cnpj: str,
    *,
    codigo_negociacao: str,
    data_referencia: date,
    data_inicio_listagem: date | None = None,
    data_fim_listagem: date | None = None,
    versao: int = 1,
) -> FcaValorMobiliario:
    agora = datetime.now(UTC)
    return FcaValorMobiliario(
        companhia_id=None,
        cnpj_companhia=cnpj,
        data_referencia=data_referencia,
        versao=versao,
        id_documento=1000 + versao,
        nome_empresarial="Empresa",
        tipo_valor_mobiliario="Acoes Ordinarias",
        sigla_classe_acao_preferencial=None,
        classe_acao_preferencial=None,
        codigo_negociacao=codigo_negociacao,
        composicao_bdr_unit=None,
        mercado="BOVESPA",
        sigla_entidade_administradora="B3",
        entidade_administradora="B3",
        data_inicio_negociacao=data_inicio_listagem,
        data_fim_negociacao=data_fim_listagem,
        segmento="NOVO MERCADO",
        data_inicio_listagem=data_inicio_listagem,
        data_fim_listagem=data_fim_listagem,
        arquivo_origem="fca_cia_aberta_valor_mobiliario_2026.csv",
        ano_origem=2026,
        linha_origem=1,
        hash_origem=f"hash-{codigo_negociacao}-{versao}",
        criado_em=agora,
        sincronizado_em=agora,
        alterado_em=agora,
    )


def test_get_companhias_paginado(client: TestClient, db_session: Session) -> None:
    db_session.add(_nova_companhia("08773135000100", 25224, "Empresa A"))
    db_session.add(_nova_companhia("11396633000187", 21954, "Empresa B"))
    db_session.add(
        _novo_valor_mobiliario(
            "08773135000100",
            codigo_negociacao="PETR4",
            data_referencia=date(2026, 6, 1),
            data_inicio_listagem=date(2020, 1, 1),
        )
    )
    db_session.commit()

    resp = client.get("/companhias?pagina=1&tamanho_pagina=1")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["paginacao"]["pagina"] == 1
    assert payload["paginacao"]["tamanho_pagina"] == 1
    assert payload["paginacao"]["total"] == 2
    assert len(payload["dados"]) == 1
    assert payload["dados"][0]["logo_url"] == "https://pub-04fd7aefad4846c98bccc4719b2eaed1.r2.dev/png/P/PETR4.png"


def test_get_companhia_por_cnpj(client: TestClient, db_session: Session) -> None:
    db_session.add(_nova_companhia("08773135000100", 25224, "Empresa A"))
    db_session.add(
        _novo_valor_mobiliario(
            "08773135000100",
            codigo_negociacao="PETR3",
            data_referencia=date(2026, 6, 1),
            data_inicio_listagem=date(2020, 1, 1),
        )
    )
    db_session.commit()

    resp = client.get("/companhias/08.773.135/0001-00")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["cnpj_companhia"] == "08773135000100"
    assert payload["codigo_cvm"] == 25224
    assert payload["logo_url"] == "https://pub-04fd7aefad4846c98bccc4719b2eaed1.r2.dev/png/P/PETR3.png"


def test_get_companhia_por_codigo_cvm(client: TestClient, db_session: Session) -> None:
    db_session.add(_nova_companhia("08773135000100", 25224, "Empresa A"))
    db_session.add(
        _novo_valor_mobiliario(
            "08773135000100",
            codigo_negociacao="PETR4",
            data_referencia=date(2026, 6, 1),
            data_inicio_listagem=date(2020, 1, 1),
        )
    )
    db_session.commit()

    resp = client.get("/companhias/codigo-cvm/25224")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["cnpj_companhia"] == "08773135000100"
    assert payload["logo_url"] == "https://pub-04fd7aefad4846c98bccc4719b2eaed1.r2.dev/png/P/PETR4.png"


def test_get_companhia_sem_ticker_retorna_logo_url_nulo(client: TestClient, db_session: Session) -> None:
    db_session.add(_nova_companhia("08773135000100", 25224, "Empresa A"))
    db_session.commit()

    resp = client.get("/companhias/codigo-cvm/25224")
    assert resp.status_code == 200
    assert resp.json()["logo_url"] is None


def test_get_companhia_ignora_ticker_invalido_e_prioriza_ticker_listado_ativo(client: TestClient, db_session: Session) -> None:
    db_session.add(_nova_companhia("00000000000191", 1023, "Banco do Brasil"))
    db_session.add(
        _novo_valor_mobiliario(
            "00000000000191",
            codigo_negociacao="INVALIDO",
            data_referencia=date(2026, 6, 20),
            data_inicio_listagem=date(2020, 1, 1),
        )
    )
    db_session.add(
        _novo_valor_mobiliario(
            "00000000000191",
            codigo_negociacao="BBAS3",
            data_referencia=date(2026, 6, 19),
            data_inicio_listagem=date(2020, 1, 1),
        )
    )
    db_session.commit()

    resp = client.get("/companhias/codigo-cvm/1023")
    assert resp.status_code == 200
    assert resp.json()["logo_url"] == "https://pub-04fd7aefad4846c98bccc4719b2eaed1.r2.dev/png/B/BBAS3.png"
