import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.companhia import Companhia
from app.models.financeiro import ComposicaoCapital, DemonstracaoFinanceira, DocumentoFinanceiro, ParecerFinanceiro


def _base_companhia() -> Companhia:
    agora = datetime.now(UTC)
    return Companhia(
        cnpj_companhia="08773135000100",
        codigo_cvm=25224,
        denominacao_social="Empresa A",
        denominacao_comercial="Empresa A",
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
        linha_origem=2,
        hash_origem="hash",
        criado_em=agora,
        sincronizado_em=agora,
        alterado_em=agora,
    )


def _popular_financeiro(db: Session, companhia_id: uuid.UUID) -> None:
    agora = datetime.now(UTC)
    db.add(
        DocumentoFinanceiro(
            companhia_id=companhia_id,
            tipo_formulario="DFP",
            cnpj_companhia="08773135000100",
            codigo_cvm=25224,
            data_referencia=date(2025, 12, 31),
            versao=1,
            denominacao_companhia="EMPRESA A",
            categoria_documento="DFP",
            id_documento=100,
            data_recebimento=date(2026, 1, 1),
            link_documento="http://doc",
            arquivo_origem="dfp_cia_aberta_2025.csv",
            ano_origem=2025,
            linha_origem=2,
            hash_origem="hash-doc",
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )
    db.add(
        DemonstracaoFinanceira(
            companhia_id=companhia_id,
            tipo_formulario="DFP",
            tipo_demonstracao="demonstracao_resultado",
            escopo_demonstracao="consolidado",
            cnpj_companhia="08773135000100",
            codigo_cvm=25224,
            data_referencia=date(2025, 12, 31),
            versao=1,
            denominacao_companhia="EMPRESA A",
            grupo_demonstracao="GRUPO",
            moeda="REAL",
            escala_moeda="UNIDADE",
            ordem_exercicio="ULTIMO",
            data_inicio_exercicio=date(2025, 1, 1),
            data_fim_exercicio=date(2025, 12, 31),
            codigo_conta="3.01",
            descricao_conta="Lucro",
            valor_conta=Decimal("123.45"),
            conta_fixa=True,
            arquivo_origem="dfp_cia_aberta_DRE_con_2025.csv",
            ano_origem=2025,
            linha_origem=2,
            hash_origem="hash-dem",
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )
    db.add(
        DemonstracaoFinanceira(
            companhia_id=companhia_id,
            tipo_formulario="DFP",
            tipo_demonstracao="demonstracao_resultado",
            escopo_demonstracao="consolidado",
            cnpj_companhia="08773135000100",
            codigo_cvm=25224,
            data_referencia=date(2024, 12, 31),
            versao=1,
            denominacao_companhia="EMPRESA A",
            grupo_demonstracao="GRUPO",
            moeda="REAL",
            escala_moeda="MIL",
            ordem_exercicio="ULTIMO",
            data_inicio_exercicio=date(2024, 1, 1),
            data_fim_exercicio=date(2024, 12, 31),
            codigo_conta="3.02",
            descricao_conta="Receita Líquida",
            valor_conta=Decimal("740500"),
            conta_fixa=True,
            arquivo_origem="dfp_cia_aberta_DRE_con_2024.csv",
            ano_origem=2024,
            linha_origem=3,
            hash_origem="hash-dem-mil",
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )
    db.add(
        ComposicaoCapital(
            companhia_id=companhia_id,
            tipo_formulario="ITR",
            cnpj_companhia="08773135000100",
            codigo_cvm=25224,
            data_referencia=date(2025, 9, 30),
            versao=2,
            denominacao_companhia="EMPRESA A",
            quantidade_acoes_ordinarias_capital_integralizado=Decimal("1"),
            quantidade_acoes_preferenciais_capital_integralizado=Decimal("2"),
            quantidade_total_acoes_capital_integralizado=Decimal("3"),
            quantidade_acoes_ordinarias_tesouraria=Decimal("0"),
            quantidade_acoes_preferenciais_tesouraria=Decimal("0"),
            quantidade_total_acoes_tesouraria=Decimal("0"),
            arquivo_origem="itr_cia_aberta_composicao_capital_2025.csv",
            ano_origem=2025,
            linha_origem=2,
            hash_origem="hash-comp",
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )
    db.add(
        ParecerFinanceiro(
            companhia_id=companhia_id,
            tipo_formulario="ITR",
            cnpj_companhia="08773135000100",
            codigo_cvm=25224,
            data_referencia=date(2025, 9, 30),
            versao=2,
            denominacao_companhia="EMPRESA A",
            tipo_relatorio_auditor="SEM RESSALVA",
            tipo_parecer_declaracao="PARECER",
            numero_item_parecer_declaracao="1",
            texto_parecer_declaracao="Texto",
            arquivo_origem="itr_cia_aberta_parecer_2025.csv",
            ano_origem=2025,
            linha_origem=2,
            hash_origem="hash-par",
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )
    db.commit()


def test_endpoint_dfp_demonstracao_filtra_por_conta_periodo_versao(client: TestClient, db_session: Session) -> None:
    companhia = _base_companhia()
    db_session.add(companhia)
    db_session.commit()
    _popular_financeiro(db_session, companhia.id)

    resposta = client.get(
        "/dfp/demonstracao-resultado/consolidado"
        "?codigo_conta=3.01&versao=1&data_referencia_inicio=2025-01-01&data_referencia_fim=2025-12-31"
    )
    assert resposta.status_code == 200
    payload = resposta.json()
    assert payload["paginacao"]["total"] == 1
    assert payload["dados"][0]["codigo_conta"] == "3.01"
    assert payload["dados"][0]["valor_conta"] == 123.45
    assert payload["dados"][0]["valor_conta_reportado"] == 123.45
    assert payload["dados"][0]["fator_escala_moeda"] == 1


def test_endpoint_dfp_demonstracao_returns_adjusted_values_and_sorts_by_adjusted_amount(
    client: TestClient, db_session: Session
) -> None:
    companhia = _base_companhia()
    db_session.add(companhia)
    db_session.commit()
    _popular_financeiro(db_session, companhia.id)

    resposta = client.get("/dfp/demonstracao-resultado/consolidado?ordenar_por=-valor_conta")
    assert resposta.status_code == 200
    payload = resposta.json()
    assert payload["paginacao"]["total"] == 2
    assert payload["dados"][0]["codigo_conta"] == "3.02"
    assert payload["dados"][0]["valor_conta"] == 740500000.0
    assert payload["dados"][0]["valor_conta_reportado"] == 740500.0
    assert payload["dados"][0]["fator_escala_moeda"] == 1000
    assert payload["dados"][1]["codigo_conta"] == "3.01"


def test_endpoint_documentos_dfp_filtra_por_id_documento(client: TestClient, db_session: Session) -> None:
    companhia = _base_companhia()
    db_session.add(companhia)
    db_session.commit()
    _popular_financeiro(db_session, companhia.id)

    resposta = client.get("/dfp/documentos?id_documento=100&cnpj_companhia=08.773.135/0001-00")
    assert resposta.status_code == 200
    payload = resposta.json()
    assert payload["paginacao"]["total"] == 1
    assert payload["dados"][0]["id_documento"] == 100


def test_endpoint_itr_filtra_pareceres_e_composicao(client: TestClient, db_session: Session) -> None:
    companhia = _base_companhia()
    db_session.add(companhia)
    db_session.commit()
    _popular_financeiro(db_session, companhia.id)

    resposta_parecer = client.get("/itr/pareceres?versao=2")
    assert resposta_parecer.status_code == 200
    assert resposta_parecer.json()["paginacao"]["total"] == 1

    resposta_comp = client.get("/itr/composicao-capital?data_referencia_inicio=2025-09-01")
    assert resposta_comp.status_code == 200
    assert resposta_comp.json()["paginacao"]["total"] == 1
