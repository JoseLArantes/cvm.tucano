import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.companhia import Companhia
from app.models.financeiro import DemonstracaoFinanceira, DocumentoFinanceiro
from app.models.fre import FreResponsavel


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
        hash_origem="companhia-exportacao",
        criado_em=agora,
        sincronizado_em=agora,
        alterado_em=agora,
    )


def _seed_financeiro(db: Session, companhia_id: uuid.UUID) -> None:
    agora = datetime.now(UTC)
    # Seed a DocumentoFinanceiro for DFP
    db.add(
        DocumentoFinanceiro(
            companhia_id=companhia_id,
            tipo_formulario="DFP",
            cnpj_companhia="00000000000191",
            codigo_cvm=1023,
            data_referencia=date(2025, 12, 31),
            versao=1,
            denominacao_companhia="Banco do Brasil S.A.",
            id_documento=111,
            arquivo_origem="dfp_cia_aberta_2025.zip",
            ano_origem=2025,
            linha_origem=1,
            hash_origem="hash-doc-dfp",
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )

    # Seed a DocumentoFinanceiro for ITR
    db.add(
        DocumentoFinanceiro(
            companhia_id=companhia_id,
            tipo_formulario="ITR",
            cnpj_companhia="00000000000191",
            codigo_cvm=1023,
            data_referencia=date(2026, 6, 30),
            versao=1,
            denominacao_companhia="Banco do Brasil S.A.",
            id_documento=222,
            arquivo_origem="itr_cia_aberta_2026.zip",
            ano_origem=2026,
            linha_origem=1,
            hash_origem="hash-doc-itr",
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )

    # Seed dynamic DemonstracaoFinanceira for DFP - BPA - IND (Balanço Patrimonial Ativo - Individual)
    db.add(
        DemonstracaoFinanceira(
            companhia_id=companhia_id,
            tipo_formulario="DFP",
            tipo_demonstracao="balanco_patrimonial_ativo",
            escopo_demonstracao="individual",
            cnpj_companhia="00000000000191",
            codigo_cvm=1023,
            data_referencia=date(2025, 12, 31),
            versao=1,
            denominacao_companhia="Banco do Brasil S.A.",
            grupo_demonstracao="DFP",
            moeda="REAL",
            escala_moeda="UNIDADE",
            ordem_exercicio="ATUAL",
            data_inicio_exercicio=date(2025, 1, 1),
            data_fim_exercicio=date(2025, 12, 31),
            codigo_conta="1",
            descricao_conta="Ativo Total",
            valor_conta=Decimal("1500000.00"),
            conta_fixa=True,
            arquivo_origem="dfp_cia_aberta_BPA_ind_2025.csv",
            ano_origem=2025,
            linha_origem=2,
            hash_origem="hash-demo-dfp",
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
            escopo_demonstracao="individual",
            cnpj_companhia="00000000000191",
            codigo_cvm=1023,
            data_referencia=date(2025, 12, 31),
            versao=1,
            denominacao_companhia="Banco do Brasil S.A.",
            grupo_demonstracao="DFP",
            moeda="REAL",
            escala_moeda="MIL",
            ordem_exercicio="ATUAL",
            data_inicio_exercicio=date(2025, 1, 1),
            data_fim_exercicio=date(2025, 12, 31),
            codigo_conta="3.03",
            descricao_conta="Receita Líquida",
            valor_conta=Decimal("740500"),
            conta_fixa=True,
            arquivo_origem="dfp_cia_aberta_DRE_ind_2025.csv",
            ano_origem=2025,
            linha_origem=3,
            hash_origem="hash-demo-dre",
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )

    # Seed dynamic DemonstracaoFinanceira for DFP - BPA - CON (Balanço Patrimonial Ativo - Consolidado)
    db.add(
        DemonstracaoFinanceira(
            companhia_id=companhia_id,
            tipo_formulario="DFP",
            tipo_demonstracao="balanco_patrimonial_ativo",
            escopo_demonstracao="consolidado",
            cnpj_companhia="00000000000191",
            codigo_cvm=1023,
            data_referencia=date(2025, 12, 31),
            versao=1,
            denominacao_companhia="Banco do Brasil S.A.",
            grupo_demonstracao="DFP",
            moeda="REAL",
            escala_moeda="UNIDADE",
            ordem_exercicio="ATUAL",
            data_inicio_exercicio=date(2025, 1, 1),
            data_fim_exercicio=date(2025, 12, 31),
            codigo_conta="1",
            descricao_conta="Ativo Total Consolidado",
            valor_conta=Decimal("3000000.00"),
            conta_fixa=True,
            arquivo_origem="dfp_cia_aberta_BPA_con_2025.csv",
            ano_origem=2025,
            linha_origem=2,
            hash_origem="hash-demo-dfp-con",
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )

    db.add(
        FreResponsavel(
            companhia_id=companhia_id,
            cnpj_companhia="00000000000191",
            data_referencia=date(2025, 12, 31),
            id_documento=333,
            versao=1,
            nome_companhia="Banco do Brasil S.A.",
            nome_responsavel="Fulano",
            cargo_responsavel="DRI",
            arquivo_origem="fre_cia_aberta_responsavel_2025.csv",
            ano_origem=2025,
            linha_origem=2,
            hash_origem="hash-fre-responsavel",
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )

    db.commit()


def test_list_fontes_and_datasets(client: TestClient) -> None:
    # Test GET /fontes
    response = client.get("/fontes")
    assert response.status_code == 200
    fontes = response.json()
    assert isinstance(fontes, list)
    assert len(fontes) > 0
    # verify DFP exists
    dfp_fonte = next((f for f in fontes if f["fonte"] == "dfp"), None)
    assert dfp_fonte is not None
    assert dfp_fonte["tipo_distribuicao"] == "zip_anual"

    # Test GET /fontes/{fonte}/datasets
    response = client.get("/fontes/dfp/datasets")
    assert response.status_code == 200
    datasets = response.json()
    assert isinstance(datasets, list)
    assert len(datasets) > 0
    doc_dataset = next((d for d in datasets if d["dataset"] == "documento_principal"), None)
    assert doc_dataset is not None
    assert doc_dataset["status_suporte"] == "suportado"
    assert doc_dataset["exportavel"] is True

    response = client.get("/fontes/fca/datasets")
    assert response.status_code == 200
    fca_datasets = response.json()
    staged_only = next((d for d in fca_datasets if d["dataset"] == "escriturador"), None)
    assert staged_only is not None
    assert staged_only["exportavel"] is False

    # Test GET /fontes/invalid/datasets -> 404
    response = client.get("/fontes/invalid/datasets")
    assert response.status_code == 404


def test_bulk_export_json_and_csv(client: TestClient, db_session: Session) -> None:
    companhia = _companhia()
    db_session.add(companhia)
    db_session.commit()
    _seed_financeiro(db_session, companhia.id)

    # 1. Export DFP documento_principal in JSON format
    response = client.get("/exportacoes/dfp/documento_principal?formato=json")
    assert response.status_code == 200
    assert "application/json" in response.headers["content-type"]
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["id_documento"] == 111
    assert data[0]["cnpj_companhia"] == "00000000000191"

    # 2. Export DFP documento_principal in CSV format
    response = client.get("/exportacoes/dfp/documento_principal?formato=csv")
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]

    csv_text = response.text
    assert "id_documento" in csv_text
    assert "111" in csv_text
    assert "00000000000191" in csv_text

    # 3. Test alias resolution (bpa_ind -> demonstracao_balanco_patrimonial_ativo_individual)
    response = client.get("/exportacoes/dfp/bpa_ind?formato=json")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["descricao_conta"] == "Ativo Total"
    assert data[0]["valor_conta"] == 1500000.00

    # 4. Test dynamic resolution with prefix: /exportacoes/dfp/demonstracao_bpa_con
    response = client.get("/exportacoes/dfp/demonstracao_bpa_con?formato=json")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["descricao_conta"] == "Ativo Total Consolidado"
    assert data[0]["valor_conta"] == 3000000.00

    response = client.get("/exportacoes/dfp/dfc_mi_con?formato=json")
    assert response.status_code == 200
    assert response.json() == []

    response = client.get("/exportacoes/dfp/dre_ind?formato=json")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["valor_conta"] == 740500000.0
    assert data[0]["valor_conta_reportado"] == 740500.0
    assert data[0]["fator_escala_moeda"] == 1000

    response = client.get("/exportacoes/dfp/dre_ind?formato=csv")
    assert response.status_code == 200
    csv_text = response.text
    assert "valor_conta_reportado" in csv_text
    assert "fator_escala_moeda" in csv_text
    assert "740500000" in csv_text

    response = client.get("/exportacoes/dfp/demonstracao_dfc_mi_con?formato=json")
    assert response.status_code == 200
    assert response.json() == []

    # 5. Test year filters (ano_inicio, ano_fim)
    # 2025 documents exist, but let's query for 2026+ -> should be empty for DFP
    response = client.get("/exportacoes/dfp/documento_principal?ano_inicio=2026&formato=json")
    assert response.status_code == 200
    assert len(response.json()) == 0

    # DFP document exists for 2025
    response = client.get("/exportacoes/dfp/documento_principal?ano_inicio=2025&ano_fim=2025&formato=json")
    assert response.status_code == 200
    assert len(response.json()) == 1

    # 6. Test company filters (cnpj_companhia, codigo_cvm)
    # Valid company
    response = client.get("/exportacoes/dfp/documento_principal?cnpj_companhia=00.000.000/0001-91&formato=json")
    assert response.status_code == 200
    assert len(response.json()) == 1

    response = client.get("/exportacoes/fre/responsavel?codigo_cvm=1023&formato=json")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["cnpj_companhia"] == "00000000000191"

    # Invalid company
    response = client.get("/exportacoes/dfp/documento_principal?cnpj_companhia=99.999.999/9999-99&formato=json")
    assert response.status_code == 200
    assert len(response.json()) == 0

    # 7. Test invalid format -> 422
    response = client.get("/exportacoes/dfp/documento_principal?formato=invalid")
    assert response.status_code == 422
