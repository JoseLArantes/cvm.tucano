from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.companhia import Companhia
from app.models.financeiro import DemonstracaoFinanceira, DocumentoFinanceiro
from app.models.ipe import IpeDocumento
from app.services.analise import materializar_analise_companhia


def _ops_headers(client: TestClient) -> dict[str, str]:
    criado = client.post(
        "/usuarios",
        json={
            "username": "operador-materializacao",
            "password": "senha-operador",
            "nome": "Operador Materializacao",
            "is_admin": False,
            "pode_operar_materializacao": True,
            "ativo": True,
        },
    )
    assert criado.status_code == 201
    login = client.post(
        "/auth/login",
        json={"username": "operador-materializacao", "password": "senha-operador"},
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _doc(
    cia: Companhia,
    agora: datetime,
    *,
    form: str,
    ref: date,
    version: int,
    document_id: int,
    filed_at: date,
) -> DocumentoFinanceiro:
    return DocumentoFinanceiro(
        companhia_id=cia.id,
        tipo_formulario=form,
        cnpj_companhia=cia.cnpj_companhia,
        codigo_cvm=cia.codigo_cvm,
        data_referencia=ref,
        versao=version,
        id_documento=document_id,
        data_recebimento=filed_at,
        link_documento=f"https://dados.cvm.gov.br/{form.lower()}/{ref.isoformat()}/v{version}.zip",
        arquivo_origem=f"{form.lower()}.csv",
        hash_origem=f"{form}-{ref.isoformat()}-{version}",
        ano_origem=ref.year,
        criado_em=agora,
        sincronizado_em=agora,
        alterado_em=agora,
    )


def _row(
    cia: Companhia,
    agora: datetime,
    *,
    form: str,
    ref: date,
    version: int,
    account: str,
    value: str,
    scale: str = "MIL",
    order: str = "ÚLTIMO",
    start: date | None = None,
    end: date | None = None,
    statement_type: str = "demonstracao_resultado",
) -> DemonstracaoFinanceira:
    return DemonstracaoFinanceira(
        companhia_id=cia.id,
        tipo_formulario=form,
        tipo_demonstracao=statement_type,
        escopo_demonstracao="consolidado",
        cnpj_companhia=cia.cnpj_companhia,
        codigo_cvm=cia.codigo_cvm,
        data_referencia=ref,
        versao=version,
        codigo_conta=account,
        valor_conta=Decimal(value),
        escala_moeda=scale,
        ordem_exercicio=order,
        data_inicio_exercicio=start,
        data_fim_exercicio=end,
        coluna_df="VALOR",
        arquivo_origem=f"{form.lower()}_{account}.csv",
        hash_origem=f"{form}-{ref.isoformat()}-{version}-{account}-{order}-{start}",
        ano_origem=ref.year,
        criado_em=agora,
        sincronizado_em=agora,
        alterado_em=agora,
    )


def _seed_analise_v2(db: Session) -> Companhia:
    agora = datetime.now(UTC)
    cia = Companhia(
        cnpj_companhia="33000167000101",
        codigo_cvm=9512,
        denominacao_social="PETROLEO BRASILEIRO S.A. PETROBRAS",
        denominacao_comercial="PETROBRAS",
        situacao_registro="ATIVO",
        arquivo_origem="cad_cia_aberta.csv",
        hash_origem="companhia",
        criado_em=agora,
        sincronizado_em=agora,
        alterado_em=agora,
    )
    db.add(cia)
    db.commit()

    docs = [
        _doc(cia, agora, form="DFP", ref=date(2021, 12, 31), version=1, document_id=8998, filed_at=date(2022, 3, 15)),
        _doc(cia, agora, form="DFP", ref=date(2022, 12, 31), version=1, document_id=8999, filed_at=date(2023, 3, 15)),
        _doc(cia, agora, form="DFP", ref=date(2023, 12, 31), version=1, document_id=9000, filed_at=date(2024, 3, 15)),
        _doc(cia, agora, form="DFP", ref=date(2024, 12, 31), version=1, document_id=9001, filed_at=date(2025, 3, 15)),
        _doc(cia, agora, form="DFP", ref=date(2025, 12, 31), version=1, document_id=9002, filed_at=date(2026, 3, 1)),
        _doc(cia, agora, form="DFP", ref=date(2025, 12, 31), version=2, document_id=9002, filed_at=date(2026, 3, 10)),
        _doc(cia, agora, form="ITR", ref=date(2025, 3, 31), version=1, document_id=9101, filed_at=date(2025, 5, 10)),
        _doc(cia, agora, form="ITR", ref=date(2025, 6, 30), version=1, document_id=9102, filed_at=date(2025, 8, 8)),
        _doc(cia, agora, form="ITR", ref=date(2025, 9, 30), version=1, document_id=9103, filed_at=date(2025, 11, 8)),
        _doc(cia, agora, form="ITR", ref=date(2024, 9, 30), version=1, document_id=8103, filed_at=date(2024, 11, 8)),
    ]
    db.add_all(docs)
    db.commit()

    rows = [
        _row(cia, agora, form="DFP", ref=date(2021, 12, 31), version=1, account="3.01", value="390000000", start=date(2021, 1, 1), end=date(2021, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2021, 12, 31), version=1, account="3.05", value="64000000", start=date(2021, 1, 1), end=date(2021, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2021, 12, 31), version=1, account="3.11", value="21000000", start=date(2021, 1, 1), end=date(2021, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2021, 12, 31), version=1, account="6.01.01", value="78000000", statement_type="demonstracao_fluxo_caixa", start=date(2021, 1, 1), end=date(2021, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2021, 12, 31), version=1, account="6.01.01.02", value="11000000", statement_type="demonstracao_fluxo_caixa", start=date(2021, 1, 1), end=date(2021, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2021, 12, 31), version=1, account="6.02.01", value="-30000000", statement_type="demonstracao_fluxo_caixa", start=date(2021, 1, 1), end=date(2021, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2021, 12, 31), version=1, account="1.01.01", value="25000000", statement_type="balanco_patrimonial_ativo", start=None, end=date(2021, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2021, 12, 31), version=1, account="2.01.04", value="22000000", statement_type="balanco_patrimonial_passivo", start=None, end=date(2021, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2021, 12, 31), version=1, account="2.02.01", value="68000000", statement_type="balanco_patrimonial_passivo", start=None, end=date(2021, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2022, 12, 31), version=1, account="3.01", value="420000000", start=date(2022, 1, 1), end=date(2022, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2022, 12, 31), version=1, account="3.05", value="70000000", start=date(2022, 1, 1), end=date(2022, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2022, 12, 31), version=1, account="3.11", value="25000000", start=date(2022, 1, 1), end=date(2022, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2022, 12, 31), version=1, account="6.01.01", value="81000000", statement_type="demonstracao_fluxo_caixa", start=date(2022, 1, 1), end=date(2022, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2022, 12, 31), version=1, account="6.01.01.02", value="13000000", statement_type="demonstracao_fluxo_caixa", start=date(2022, 1, 1), end=date(2022, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2022, 12, 31), version=1, account="6.02.01", value="-32000000", statement_type="demonstracao_fluxo_caixa", start=date(2022, 1, 1), end=date(2022, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2022, 12, 31), version=1, account="1.01.01", value="27000000", statement_type="balanco_patrimonial_ativo", start=None, end=date(2022, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2022, 12, 31), version=1, account="2.01.04", value="26000000", statement_type="balanco_patrimonial_passivo", start=None, end=date(2022, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2022, 12, 31), version=1, account="2.02.01", value="70000000", statement_type="balanco_patrimonial_passivo", start=None, end=date(2022, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2023, 12, 31), version=1, account="3.01", value="455000000", start=date(2023, 1, 1), end=date(2023, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2023, 12, 31), version=1, account="3.05", value="76000000", start=date(2023, 1, 1), end=date(2023, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2023, 12, 31), version=1, account="3.11", value="31000000", start=date(2023, 1, 1), end=date(2023, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2023, 12, 31), version=1, account="6.01.01", value="86000000", statement_type="demonstracao_fluxo_caixa", start=date(2023, 1, 1), end=date(2023, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2023, 12, 31), version=1, account="6.01.01.02", value="14000000", statement_type="demonstracao_fluxo_caixa", start=date(2023, 1, 1), end=date(2023, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2023, 12, 31), version=1, account="6.02.01", value="-35000000", statement_type="demonstracao_fluxo_caixa", start=date(2023, 1, 1), end=date(2023, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2023, 12, 31), version=1, account="1.01.01", value="29000000", statement_type="balanco_patrimonial_ativo", start=None, end=date(2023, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2023, 12, 31), version=1, account="2.01.04", value="30000000", statement_type="balanco_patrimonial_passivo", start=None, end=date(2023, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2023, 12, 31), version=1, account="2.02.01", value="72000000", statement_type="balanco_patrimonial_passivo", start=None, end=date(2023, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2024, 12, 31), version=1, account="3.01", value="490829000", start=date(2024, 1, 1), end=date(2024, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2024, 12, 31), version=1, account="3.05", value="80000000", start=date(2024, 1, 1), end=date(2024, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2024, 12, 31), version=1, account="3.11", value="36734000", start=date(2024, 1, 1), end=date(2024, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2024, 12, 31), version=1, account="6.01.01", value="90000000", statement_type="demonstracao_fluxo_caixa", start=date(2024, 1, 1), end=date(2024, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2024, 12, 31), version=1, account="6.01.01.02", value="15000000", statement_type="demonstracao_fluxo_caixa", start=date(2024, 1, 1), end=date(2024, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2024, 12, 31), version=1, account="6.02.01", value="-40000000", statement_type="demonstracao_fluxo_caixa", start=date(2024, 1, 1), end=date(2024, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2024, 12, 31), version=1, account="1.01", value="150000000", statement_type="balanco_patrimonial_ativo", start=None, end=date(2024, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2024, 12, 31), version=1, account="1.01.01", value="32000000", statement_type="balanco_patrimonial_ativo", start=None, end=date(2024, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2024, 12, 31), version=1, account="2.01", value="140000000", statement_type="balanco_patrimonial_passivo", start=None, end=date(2024, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2024, 12, 31), version=1, account="2.01.04", value="35000000", statement_type="balanco_patrimonial_passivo", start=None, end=date(2024, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2024, 12, 31), version=1, account="2.02.01", value="85000000", statement_type="balanco_patrimonial_passivo", start=None, end=date(2024, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2025, 12, 31), version=1, account="3.01", value="490829000", start=date(2025, 1, 1), end=date(2025, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2025, 12, 31), version=1, account="3.01", value="480000000", order="PENÚLTIMO", start=date(2024, 1, 1), end=date(2024, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2025, 12, 31), version=1, account="3.05", value="81000000", start=date(2025, 1, 1), end=date(2025, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2025, 12, 31), version=1, account="3.11", value="38000000", start=date(2025, 1, 1), end=date(2025, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2025, 12, 31), version=1, account="6.01.01", value="95000000", statement_type="demonstracao_fluxo_caixa", start=date(2025, 1, 1), end=date(2025, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2025, 12, 31), version=1, account="6.01.01.02", value="16000000", statement_type="demonstracao_fluxo_caixa", start=date(2025, 1, 1), end=date(2025, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2025, 12, 31), version=1, account="6.02.01", value="-42000000", statement_type="demonstracao_fluxo_caixa", start=date(2025, 1, 1), end=date(2025, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2025, 12, 31), version=1, account="1.01", value="130000000", statement_type="balanco_patrimonial_ativo", start=None, end=date(2025, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2025, 12, 31), version=1, account="1.01.01", value="33000000", statement_type="balanco_patrimonial_ativo", start=None, end=date(2025, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2025, 12, 31), version=1, account="2.01", value="160000000", statement_type="balanco_patrimonial_passivo", start=None, end=date(2025, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2025, 12, 31), version=1, account="2.01.04", value="36000000", statement_type="balanco_patrimonial_passivo", start=None, end=date(2025, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2025, 12, 31), version=1, account="2.02.01", value="86000000", statement_type="balanco_patrimonial_passivo", start=None, end=date(2025, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2025, 12, 31), version=2, account="3.01", value="497549000", start=date(2025, 1, 1), end=date(2025, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2025, 12, 31), version=2, account="3.01", value="490829000", order="PENÚLTIMO", start=date(2024, 1, 1), end=date(2024, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2025, 12, 31), version=2, account="3.05", value="82000000", start=date(2025, 1, 1), end=date(2025, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2025, 12, 31), version=2, account="3.11", value="38100000", start=date(2025, 1, 1), end=date(2025, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2025, 12, 31), version=2, account="6.01.01", value="98000000", statement_type="demonstracao_fluxo_caixa", start=date(2025, 1, 1), end=date(2025, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2025, 12, 31), version=2, account="6.01.01.02", value="17000000", statement_type="demonstracao_fluxo_caixa", start=date(2025, 1, 1), end=date(2025, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2025, 12, 31), version=2, account="6.02.01", value="-43000000", statement_type="demonstracao_fluxo_caixa", start=date(2025, 1, 1), end=date(2025, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2025, 12, 31), version=2, account="1.01", value="130000000", statement_type="balanco_patrimonial_ativo", start=None, end=date(2025, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2025, 12, 31), version=2, account="1.01.01", value="34000000", statement_type="balanco_patrimonial_ativo", start=None, end=date(2025, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2025, 12, 31), version=2, account="2.01", value="160000000", statement_type="balanco_patrimonial_passivo", start=None, end=date(2025, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2025, 12, 31), version=2, account="2.01.04", value="36500000", statement_type="balanco_patrimonial_passivo", start=None, end=date(2025, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2025, 12, 31), version=2, account="2.02.01", value="87500000", statement_type="balanco_patrimonial_passivo", start=None, end=date(2025, 12, 31)),
        _row(cia, agora, form="ITR", ref=date(2025, 3, 31), version=1, account="3.01", value="123144000", start=date(2025, 1, 1), end=date(2025, 3, 31)),
        _row(cia, agora, form="ITR", ref=date(2025, 3, 31), version=1, account="3.11", value="9000000", start=date(2025, 1, 1), end=date(2025, 3, 31)),
        _row(cia, agora, form="ITR", ref=date(2025, 6, 30), version=1, account="3.01", value="242272000", start=date(2025, 1, 1), end=date(2025, 6, 30)),
        _row(cia, agora, form="ITR", ref=date(2025, 6, 30), version=1, account="3.01", value="119128000", start=date(2025, 4, 1), end=date(2025, 6, 30)),
        _row(cia, agora, form="ITR", ref=date(2025, 6, 30), version=1, account="3.11", value="17000000", start=date(2025, 1, 1), end=date(2025, 6, 30)),
        _row(cia, agora, form="ITR", ref=date(2025, 6, 30), version=1, account="3.11", value="8000000", start=date(2025, 4, 1), end=date(2025, 6, 30)),
        _row(cia, agora, form="ITR", ref=date(2025, 9, 30), version=1, account="3.01", value="370178000", start=date(2025, 1, 1), end=date(2025, 9, 30)),
        _row(cia, agora, form="ITR", ref=date(2025, 9, 30), version=1, account="3.01", value="127906000", start=date(2025, 7, 1), end=date(2025, 9, 30)),
        _row(cia, agora, form="ITR", ref=date(2025, 9, 30), version=1, account="3.01", value="360000000", order="PENÚLTIMO", start=date(2024, 1, 1), end=date(2024, 9, 30)),
        _row(cia, agora, form="ITR", ref=date(2025, 9, 30), version=1, account="3.01", value="120000000", order="PENÚLTIMO", start=date(2024, 7, 1), end=date(2024, 9, 30)),
        _row(cia, agora, form="ITR", ref=date(2025, 9, 30), version=1, account="3.11", value="24000000", start=date(2025, 1, 1), end=date(2025, 9, 30)),
        _row(cia, agora, form="ITR", ref=date(2025, 9, 30), version=1, account="3.11", value="7000000", start=date(2025, 7, 1), end=date(2025, 9, 30)),
        _row(cia, agora, form="ITR", ref=date(2024, 9, 30), version=1, account="3.01", value="120000000", start=date(2024, 7, 1), end=date(2024, 9, 30)),
        _row(cia, agora, form="ITR", ref=date(2024, 9, 30), version=1, account="3.11", value="18000000", start=date(2024, 7, 1), end=date(2024, 9, 30)),
    ]
    db.add_all(rows)

    db.add(
        IpeDocumento(
            companhia_id=cia.id,
            cnpj_companhia=cia.cnpj_companhia,
            codigo_cvm=cia.codigo_cvm,
            data_referencia=date(2025, 9, 30),
            versao=1,
            data_entrega=date(2025, 11, 20),
            categoria="Fato Relevante",
            tipo="Comunicado",
            assunto="Atualização operacional",
            link_download="https://dados.cvm.gov.br/ipe/2025-11-20.pdf",
            arquivo_origem="ipe.csv",
            hash_origem="ipe-1",
            ano_origem=2025,
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )
    db.commit()
    return cia


def test_fundamentalista_runtime_fallback(client: TestClient, db_session: Session) -> None:
    # 1. Seed data
    cia = _seed_analise_v2(db_session)
    headers = _ops_headers(client)

    # 2. Query endpoint without materialization (should fall back to runtime)
    response = client.get(
        f"/analise/companhias/{cia.codigo_cvm}/fundamentalista",
        params={"periodicidade": "annual", "base_periodo": "fy", "horizonte_anos": 5},
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()

    # 3. Assert response structure
    assert "report_id" in data
    assert data["report_version"] == "1.0.0"
    assert data["companhia"]["codigo_cvm"] == cia.codigo_cvm
    assert data["resolution"]["mode"] == "runtime_fallback"

    # Etapas
    etapas = data["etapas"]
    assert "ponto_partida" in etapas
    assert "resultado_eficiencia" in etapas
    assert "caixa_solidez" in etapas
    assert "governanca_conclusao" in etapas

    # Stage 1: Ponto Partida
    ponto = etapas["ponto_partida"]
    assert ponto["identidade_companhia"]["codigo_cvm"] == cia.codigo_cvm
    assert len(ponto["periodos_disponiveis"]) > 0

    # Stage 2: Resultado e Eficiência
    res = etapas["resultado_eficiencia"]
    assert len(res["series"]) > 0
    metric_ids = {obs["metric_id"] for obs in res["series"]}
    assert "receita_liquida" in metric_ids
    assert "lucro_liquido" in metric_ids

    # Stage 3: Caixa e Solidez
    caixa = etapas["caixa_solidez"]
    assert len(caixa["series"]) > 0
    cash_metric_ids = {obs["metric_id"] for obs in caixa["series"]}
    assert "caixa_operacional" in cash_metric_ids
    assert "capex" in cash_metric_ids

    # Stage 4: Governança e Conclusão
    gov = etapas["governanca_conclusao"]
    assert len(gov["eventos_ipe"]) > 0
    assert gov["eventos_ipe"][0]["family"] == "IPE"

    # Evidence index
    assert "evidence_index" in data
    assert len(data["evidence_index"]) > 0


def test_fundamentalista_canonical_mode(client: TestClient, db_session: Session) -> None:
    # 1. Seed data
    cia = _seed_analise_v2(db_session)
    headers = _ops_headers(client)

    # 2. Materialize the data to populate the canonical layer
    execucao = materializar_analise_companhia(db_session, cia, scope="consolidated")
    assert execucao.status == "success"

    # 3. Query endpoint (should resolve via canonical)
    response = client.get(
        f"/analise/companhias/{cia.codigo_cvm}/fundamentalista",
        params={"periodicidade": "annual", "base_periodo": "fy", "horizonte_anos": 5},
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()

    assert data["resolution"]["mode"] == "canonical"
    assert data["resolution"]["materialization_execution_id"] == str(execucao.id)


def test_fundamentalista_invalid_filters(client: TestClient, db_session: Session) -> None:
    cia = _seed_analise_v2(db_session)
    headers = _ops_headers(client)

    # Invalid combination: annual + quarter
    response = client.get(
        f"/analise/companhias/{cia.codigo_cvm}/fundamentalista",
        params={"periodicidade": "annual", "base_periodo": "quarter"},
        headers=headers,
    )
    assert response.status_code == 422

    # Invalid combination: quarterly + fy
    response = client.get(
        f"/analise/companhias/{cia.codigo_cvm}/fundamentalista",
        params={"periodicidade": "quarterly", "base_periodo": "fy"},
        headers=headers,
    )
    assert response.status_code == 422


def test_fundamentalista_include_graph(client: TestClient, db_session: Session) -> None:
    cia = _seed_analise_v2(db_session)
    headers = _ops_headers(client)

    # Request with include=evidence_graph
    response = client.get(
        f"/analise/companhias/{cia.codigo_cvm}/fundamentalista",
        params={"periodicidade": "annual", "base_periodo": "fy", "include": "evidence_graph"},
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()

    assert "evidence_graph" in data
    graph = data["evidence_graph"]
    assert "nodes" in graph
    assert "edges" in graph
    assert len(graph["nodes"]) > 0


def test_fundamentalista_evidencias_detail(client: TestClient, db_session: Session) -> None:
    cia = _seed_analise_v2(db_session)
    headers = _ops_headers(client)

    # 1. Fetch report to get valid evidence IDs
    response = client.get(
        f"/analise/companhias/{cia.codigo_cvm}/fundamentalista",
        params={"periodicidade": "annual", "base_periodo": "fy"},
        headers=headers,
    )
    assert response.status_code == 200
    report_data = response.json()
    evidence_ids = list(report_data["evidence_index"].keys())
    assert len(evidence_ids) > 0

    # Pick a metric evidence ID
    metric_ev_id = [e_id for e_id in evidence_ids if "metric" in e_id][0]

    # 2. Query evidence detail endpoint
    ev_response = client.get(
        f"/analise/companhias/{cia.codigo_cvm}/fundamentalista/evidencias/{metric_ev_id}",
        headers=headers,
    )
    assert ev_response.status_code == 200
    ev_data = ev_response.json()

    assert ev_data["evidence_id"] == metric_ev_id
    assert ev_data["type"] == "observation"
    assert ev_data["metric"] is not None
    assert ev_data["observation"] is not None
    assert ev_data["document"] is not None


def test_fundamentalista_evidencias_authorization_validation(client: TestClient, db_session: Session) -> None:
    cia = _seed_analise_v2(db_session)
    headers = _ops_headers(client)

    # Try to request an evidence ID with a mismatching company CVM code (e.g. 9999 instead of 9512)
    mismatch_ev_id = "ev::9999::metric::receita_liquida::FY2025"

    response = client.get(
        f"/analise/companhias/{cia.codigo_cvm}/fundamentalista/evidencias/{mismatch_ev_id}",
        headers=headers,
    )
    # Should return 403 Forbidden because it doesn't belong to the requested company
    assert response.status_code == 403
