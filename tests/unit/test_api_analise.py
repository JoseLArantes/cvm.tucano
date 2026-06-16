import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.companhia import Companhia
from app.models.financeiro import DocumentoFinanceiro, DemonstracaoFinanceira, ComposicaoCapital
from app.models.fre import (
    FreDocumento,
    FreRemuneracaoTotalOrgao,
    FreAdministradorMembroConselhoFiscal,
    FreAdministradorDeclaracaoGenero,
    FreCapitalSocialAumento
)
from app.models.ipe import IpeDocumento
from app.models.vlmo import VlmoDocumento, VlmoConsolidado
from app.models.cgvn import CgvnDocumento, CgvnPratica


def _seed_analise_dados(db: Session) -> Companhia:
    agora = datetime.now(UTC)
    cia = Companhia(
        cnpj_companhia="08773135000100",
        codigo_cvm=25224,
        denominacao_social="Empresa Teste A",
        denominacao_comercial="Empresa Teste A Fantasia",
        situacao_registro="ATIVO",
        arquivo_origem="cad_cia_aberta.csv",
        hash_origem="abc",
        criado_em=agora, sincronizado_em=agora, alterado_em=agora
    )
    db.add(cia)
    db.commit()

    # Seed DocumentoFinanceiro & DemonstracaoFinanceira
    docs = [
        DocumentoFinanceiro(
            companhia_id=cia.id, tipo_formulario="DFP", cnpj_companhia="08773135000100",
            codigo_cvm=25224, data_referencia=date(2024, 12, 31), versao=1,
            id_documento=111, data_recebimento=date(2025, 3, 20),
            arquivo_origem="dfp.csv", hash_origem="a", ano_origem=2024, criado_em=agora, sincronizado_em=agora, alterado_em=agora
        ),
        DocumentoFinanceiro(
            companhia_id=cia.id, tipo_formulario="DFP", cnpj_companhia="08773135000100",
            codigo_cvm=25224, data_referencia=date(2023, 12, 31), versao=1,
            id_documento=222, data_recebimento=date(2024, 3, 15),
            arquivo_origem="dfp.csv", hash_origem="b", ano_origem=2023, criado_em=agora, sincronizado_em=agora, alterado_em=agora
        )
    ]
    for d in docs:
        db.add(d)
    db.commit()

    # Receita Líquida (3.01) e Lucro Líquido (3.11)
    df_rows = [
        DemonstracaoFinanceira(
            companhia_id=cia.id, tipo_formulario="DFP", tipo_demonstracao="demonstracao_resultado",
            escopo_demonstracao="consolidado", cnpj_companhia="08773135000100", codigo_cvm=25224,
            data_referencia=date(2024, 12, 31), versao=1, codigo_conta="3.01",
            valor_conta=Decimal("150000000.00"), escala_moeda="UNIDADE", ordem_exercicio="ÚLTIMO",
            arquivo_origem="dre.csv", hash_origem="x", ano_origem=2024, criado_em=agora, sincronizado_em=agora, alterado_em=agora
        ),
        DemonstracaoFinanceira(
            companhia_id=cia.id, tipo_formulario="DFP", tipo_demonstracao="demonstracao_resultado",
            escopo_demonstracao="consolidado", cnpj_companhia="08773135000100", codigo_cvm=25224,
            data_referencia=date(2023, 12, 31), versao=1, codigo_conta="3.01",
            valor_conta=Decimal("100000000.00"), escala_moeda="UNIDADE", ordem_exercicio="ÚLTIMO",
            arquivo_origem="dre.csv", hash_origem="y", ano_origem=2023, criado_em=agora, sincronizado_em=agora, alterado_em=agora
        ),
        # Lucro Líquido
        DemonstracaoFinanceira(
            companhia_id=cia.id, tipo_formulario="DFP", tipo_demonstracao="demonstracao_resultado",
            escopo_demonstracao="consolidado", cnpj_companhia="08773135000100", codigo_cvm=25224,
            data_referencia=date(2024, 12, 31), versao=1, codigo_conta="3.11",
            valor_conta=Decimal("20000000.00"), escala_moeda="UNIDADE", ordem_exercicio="ÚLTIMO",
            arquivo_origem="dre.csv", hash_origem="z", ano_origem=2024, criado_em=agora, sincronizado_em=agora, alterado_em=agora
        )
    ]
    for r in df_rows:
        db.add(r)
    db.commit()

    # Seed ComposicaoCapital
    db.add(ComposicaoCapital(
        companhia_id=cia.id, tipo_formulario="DFP", cnpj_companhia="08773135000100",
        codigo_cvm=25224, data_referencia=date(2024, 12, 31), versao=1,
        quantidade_total_acoes_capital_integralizado=Decimal("10000000.0"),
        quantidade_total_acoes_tesouraria=Decimal("50000.0"),
        arquivo_origem="cc.csv", hash_origem="c", ano_origem=2024, criado_em=agora, sincronizado_em=agora, alterado_em=agora
    ))
    db.add(ComposicaoCapital(
        companhia_id=cia.id, tipo_formulario="DFP", cnpj_companhia="08773135000100",
        codigo_cvm=25224, data_referencia=date(2023, 12, 31), versao=1,
        quantidade_total_acoes_capital_integralizado=Decimal("10000000.0"),
        quantidade_total_acoes_tesouraria=Decimal("10000.0"),
        arquivo_origem="cc.csv", hash_origem="d", ano_origem=2023, criado_em=agora, sincronizado_em=agora, alterado_em=agora
    ))

    # Seed FreRemuneracaoTotalOrgao
    db.add(FreRemuneracaoTotalOrgao(
        companhia_id=cia.id, cnpj_companhia="08773135000100", data_referencia=date(2024, 12, 31),
        versao=1, id_documento=99, orgao_administracao="Conselho de Administração",
        numero_membros=5, total_remuneracao_orgao=Decimal("1000000.0"),
        data_inicio_exercicio_social=date(2024, 1, 1), data_fim_exercicio_social=date(2024, 12, 31),
        arquivo_origem="rem.csv", hash_origem="e", ano_origem=2024, criado_em=agora, sincronizado_em=agora, alterado_em=agora
    ))

    # Seed FreAdministradorDeclaracaoGenero
    db.add(FreAdministradorDeclaracaoGenero(
        companhia_id=cia.id, cnpj_companhia="08773135000100", data_referencia=date(2024, 12, 31),
        versao=1, id_documento=99, orgao_administracao="Conselho de Administração",
        quantidade_feminino=1, quantidade_masculino=4,
        arquivo_origem="gen.csv", hash_origem="f", ano_origem=2024, criado_em=agora, sincronizado_em=agora, alterado_em=agora
    ))

    # Seed VlmoConsolidado (Insider Trading)
    db.add(VlmoConsolidado(
        companhia_id=cia.id, cnpj_companhia="08773135000100", data_referencia=date(2024, 12, 31),
        versao=1, tipo_operacao="COMPRA", tipo_ativo="AÇÕES", quantidade=10000,
        preco_unitario=Decimal("15.50"), volume=Decimal("155000.0"), tipo_cargo="Diretor",
        data_movimentacao=date(2024, 6, 15), indice_ocorrencia=1,
        arquivo_origem="vlmo.csv", hash_origem="g", ano_origem=2024, criado_em=agora, sincronizado_em=agora, alterado_em=agora
    ))

    # Seed CgvnPratica
    db.add(CgvnPratica(
        companhia_id=cia.id, cnpj_companhia="08773135000100", data_referencia=date(2024, 12, 31),
        id_documento=88, versao=1, id_item="1.1.1", pratica_recomendada="...",
        pratica_adotada="Adotada", capitulo="Cap 1", principio="Princ 1",
        arquivo_origem="cgvn.csv", hash_origem="h", ano_origem=2024, criado_em=agora, sincronizado_em=agora, alterado_em=agora
    ))

    db.commit()
    return cia


def test_search_filters_and_active_first(client: TestClient, db_session: Session) -> None:
    # Seed Active and Suspended companies
    agora = datetime.now(UTC)
    c1 = Companhia(
        cnpj_companhia="11111111111111", denominacao_social="ALFA S.A.",
        situacao_registro="ATIVO", arquivo_origem="cad_cia_aberta.csv", hash_origem="abc",
        criado_em=agora, sincronizado_em=agora, alterado_em=agora
    )
    c2 = Companhia(
        cnpj_companhia="22222222222222", denominacao_social="BETA S.A.",
        situacao_registro="SUSPENSO(A) - DECISAO ADM", arquivo_origem="cad_cia_aberta.csv", hash_origem="abc",
        criado_em=agora, sincronizado_em=agora, alterado_em=agora
    )
    c3 = Companhia(
        cnpj_companhia="33333333333333", denominacao_social="GAMA S.A.",
        situacao_registro="ATIVO", arquivo_origem="cad_cia_aberta.csv", hash_origem="abc",
        criado_em=agora, sincronizado_em=agora, alterado_em=agora
    )
    db_session.add_all([c1, c2, c3])
    db_session.commit()

    # Test sorting by activa_nome (Active-first)
    # Expected order: ALFA S.A. (Active), GAMA S.A. (Active), then BETA S.A. (Suspended)
    resp = client.get("/companhias?ordenar=ativa_nome&tamanho_pagina=10")
    assert resp.status_code == 200
    dados = resp.json()["dados"]
    assert len(dados) == 3
    assert dados[0]["denominacao_social"] == "ALFA S.A."
    assert dados[1]["denominacao_social"] == "GAMA S.A."
    assert dados[2]["denominacao_social"] == "BETA S.A."

    # Test filtering by nome
    resp_search = client.get("/companhias?nome=BETA")
    assert len(resp_search.json()["dados"]) == 1
    assert resp_search.json()["dados"][0]["denominacao_social"] == "BETA S.A."

    # Test filtering by situacao_registro
    resp_sit = client.get("/companhias?situacao_registro=ATIVO")
    assert len(resp_sit.json()["dados"]) == 2


def test_analise_overview(client: TestClient, db_session: Session) -> None:
    _seed_analise_dados(db_session)
    
    resp = client.get("/companhias/25224/analise/overview")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["codigo_cvm"] == 25224
    assert payload["status_ativo"] is True
    assert "2024" in payload["cobertura"]
    assert "2024" in payload["periodos_disponiveis"]["DFP"]


def test_analise_financeiro(client: TestClient, db_session: Session) -> None:
    _seed_analise_dados(db_session)
    
    resp = client.get("/companhias/25224/analise/financeiro")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["codigo_cvm"] == 25224
    
    dados = payload["dados"]
    # We should have DFP 2023 and DFP 2024
    assert len(dados) == 2
    
    # Check DFP 2024 Receita Líquida (3.01)
    p2024 = next(p for p in dados if p["ano"] == 2024)
    assert p2024["metrics"]["receita_liquida"]["valor_normalizado"] == 150000000.0
    # YoY of 2024 receita should be (150M - 100M)/100M = 0.50 (50% growth)
    assert p2024["metrics"]["receita_liquida"]["yoy"] == 0.50


def test_analise_comparativo(client: TestClient, db_session: Session) -> None:
    _seed_analise_dados(db_session)
    
    resp = client.get("/companhias/25224/analise/comparativo?ano_base=2024&ano_comparacao=2023")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["ano_base"] == 2024
    assert payload["ano_comparacao"] == 2023
    
    # Financial metrics delta
    rec_delta = payload["financeiro"]["receita_liquida"]
    assert rec_delta["valor_base"] == 150000000.0
    assert rec_delta["valor_comparacao"] == 100000000.0
    assert rec_delta["delta_absoluto"] == 50000000.0
    assert rec_delta["delta_percentual"] == 0.50

    # Capital delta
    tes_delta = payload["capital"]["quantidade_total_acoes_tesouraria"]
    assert tes_delta["valor_base"] == 50000.0
    assert tes_delta["valor_comparacao"] == 10000.0
    assert tes_delta["delta_absoluto"] == 40000.0
    assert tes_delta["delta_percentual"] == 4.00


def test_analise_eventos(client: TestClient, db_session: Session) -> None:
    _seed_analise_dados(db_session)
    
    resp = client.get("/companhias/25224/analise/eventos")
    assert resp.status_code == 200
    payload = resp.json()
    # Should find the insider trade event (volume > 100k)
    assert len(payload) >= 1
    match_insider = next((e for e in payload if e["familia_evento"] == "VLMO"), None)
    assert match_insider is not None
    assert "Diretor" in match_insider["explicacao"]


def test_analise_pessoas_remuneracao(client: TestClient, db_session: Session) -> None:
    _seed_analise_dados(db_session)
    
    resp = client.get("/companhias/25224/analise/pessoas-remuneracao")
    assert resp.status_code == 200
    payload = resp.json()
    dados = payload["dados"]
    assert len(dados) == 1
    assert dados[0]["ano"] == 2024
    assert dados[0]["total_remuneracao_conselho"] == 1000000.0
    assert dados[0]["membros_conselho"] == 5
    assert dados[0]["remuneracao_media_conselho"] == 200000.0
    assert dados[0]["proporcao_feminino_conselho"] == 0.20


def test_analise_mercado_insiders(client: TestClient, db_session: Session) -> None:
    _seed_analise_dados(db_session)
    
    resp = client.get("/companhias/25224/analise/mercado-insiders")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["cnpj_companhia"] == "08773135000100"
    
    # Insider trades
    movs = payload["movimentacoes"]
    assert len(movs) == 1
    assert movs[0]["total_volume"] == 155000.0
    
    # Treasury
    tes = payload["tesouraria"]
    assert len(tes) == 2
    
    # Governance practices
    gov = payload["governanca_resumo"]
    assert gov["Adotada"] == 1


def test_analise_consolidada(client: TestClient, db_session: Session) -> None:
    _seed_analise_dados(db_session)
    
    resp = client.get("/companhias/25224/analise?ano_base=2024&ano_comparacao=2023")
    assert resp.status_code == 200
    payload = resp.json()
    assert "companhia" in payload
    assert "financeiro" in payload
    assert len(payload["financeiro"]) == 2
    assert "eventos" in payload
