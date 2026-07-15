import json
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

from app.api.routers import analise as analise_router
from app.core.cache import cache as delivery_cache
from app.models.analise import AnaliseFundamentalistaSnapshot
from app.models.companhia import Companhia
from app.models.financeiro import DemonstracaoFinanceira, DocumentoFinanceiro
from app.models.ipe import IpeDocumento
from app.services.analise import (
    clear_analysis_session_cache,
    materializar_analise_companhia,
    obter_fundamentalista_com_metadata,
)


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
    scope: str = "consolidado",
) -> DemonstracaoFinanceira:
    return DemonstracaoFinanceira(
        companhia_id=cia.id,
        tipo_formulario=form,
        tipo_demonstracao=statement_type,
        escopo_demonstracao=scope,
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
        _doc(cia, agora, form="ITR", ref=date(2023, 9, 30), version=1, document_id=7103, filed_at=date(2023, 11, 8)),
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
        _row(cia, agora, form="DFP", ref=date(2024, 12, 31), version=1, account="1", value="500000000", statement_type="balanco_patrimonial_ativo", start=None, end=date(2024, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2024, 12, 31), version=1, account="2.03", value="200000000", statement_type="balanco_patrimonial_passivo", start=None, end=date(2024, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2025, 12, 31), version=1, account="1", value="550000000", statement_type="balanco_patrimonial_ativo", start=None, end=date(2025, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2025, 12, 31), version=1, account="2.03", value="220000000", statement_type="balanco_patrimonial_passivo", start=None, end=date(2025, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2025, 12, 31), version=2, account="1", value="550000000", statement_type="balanco_patrimonial_ativo", start=None, end=date(2025, 12, 31)),
        _row(cia, agora, form="DFP", ref=date(2025, 12, 31), version=2, account="2.03", value="220000000", statement_type="balanco_patrimonial_passivo", start=None, end=date(2025, 12, 31)),
        _row(cia, agora, form="ITR", ref=date(2025, 9, 30), version=1, account="1", value="540000000", statement_type="balanco_patrimonial_ativo", start=None, end=date(2025, 9, 30)),
        _row(cia, agora, form="ITR", ref=date(2025, 9, 30), version=1, account="2.03", value="215000000", statement_type="balanco_patrimonial_passivo", start=None, end=date(2025, 9, 30)),
        _row(cia, agora, form="ITR", ref=date(2024, 9, 30), version=1, account="1", value="480000000", statement_type="balanco_patrimonial_ativo", start=None, end=date(2024, 9, 30)),
        _row(cia, agora, form="ITR", ref=date(2024, 9, 30), version=1, account="2.03", value="195000000", statement_type="balanco_patrimonial_passivo", start=None, end=date(2024, 9, 30)),
        _row(cia, agora, form="ITR", ref=date(2024, 9, 30), version=1, account="3.01", value="360000000", start=date(2024, 1, 1), end=date(2024, 9, 30)),
        _row(cia, agora, form="ITR", ref=date(2024, 9, 30), version=1, account="3.11", value="18000000", start=date(2024, 1, 1), end=date(2024, 9, 30)),
        _row(cia, agora, form="ITR", ref=date(2023, 9, 30), version=1, account="1", value="460000000", statement_type="balanco_patrimonial_ativo", start=None, end=date(2023, 9, 30)),
        _row(cia, agora, form="ITR", ref=date(2023, 9, 30), version=1, account="2.03", value="180000000", statement_type="balanco_patrimonial_passivo", start=None, end=date(2023, 9, 30)),
        _row(cia, agora, form="ITR", ref=date(2023, 9, 30), version=1, account="3.01", value="330000000", start=date(2023, 1, 1), end=date(2023, 9, 30)),
        _row(cia, agora, form="ITR", ref=date(2023, 9, 30), version=1, account="3.11", value="21000000", start=date(2023, 1, 1), end=date(2023, 9, 30)),

        # Seed rows for scope="individual" YTD Q3
        _row(cia, agora, form="ITR", ref=date(2025, 9, 30), version=1, account="3.01", value="350000000", start=date(2025, 1, 1), end=date(2025, 9, 30), scope="individual"),
        _row(cia, agora, form="ITR", ref=date(2025, 9, 30), version=1, account="3.05", value="82000000", start=date(2025, 1, 1), end=date(2025, 9, 30), scope="individual"),
        _row(cia, agora, form="ITR", ref=date(2025, 9, 30), version=1, account="3.11", value="22000000", start=date(2025, 1, 1), end=date(2025, 9, 30), scope="individual"),
        _row(cia, agora, form="ITR", ref=date(2025, 9, 30), version=1, account="1.01.01", value="34000000", statement_type="balanco_patrimonial_ativo", start=None, end=date(2025, 9, 30), scope="individual"),
        _row(cia, agora, form="ITR", ref=date(2025, 9, 30), version=1, account="2.01.04", value="36500000", statement_type="balanco_patrimonial_passivo", start=None, end=date(2025, 9, 30), scope="individual"),
        _row(cia, agora, form="ITR", ref=date(2025, 9, 30), version=1, account="2.02.01", value="87500000", statement_type="balanco_patrimonial_passivo", start=None, end=date(2025, 9, 30), scope="individual"),
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
    assert data["report_version"] == "1.1.0"
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
    assert caixa["ponte_caixa"]
    available_bridge = next(item for item in caixa["ponte_caixa"] if item["items"])
    bridge_roles = {item["role"] for item in available_bridge["items"]}
    assert {"operating_cash", "capex", "free_cash"}.issubset(bridge_roles)
    assert all(item["evidence_ids"] for item in available_bridge["items"])
    painel = caixa["painel_posicao_financeira"]
    assert painel["monetary_series"]
    assert all(obs["unit"] == "BRL" for obs in painel["monetary_series"])
    assert painel["ratio_series"]
    assert all(obs["unit"] in {"ratio", "percentage_point", "index"} for obs in painel["ratio_series"])

    # Stage 4: Governança e Conclusão
    gov = etapas["governanca_conclusao"]
    assert len(gov["eventos_ipe"]) > 0
    assert gov["eventos_ipe"][0]["family"] == "IPE"
    restatement_accounts = [
        account
        for item in caixa["reapresentacoes"] + gov["reapresentacoes"]
        for account in item["changed_accounts"]
    ]
    assert restatement_accounts
    assert all(account["display_rank"] > 0 for account in restatement_accounts)
    assert all("account_label" in account for account in restatement_accounts)
    assert all("statement_label" in account for account in restatement_accounts)
    assert all("is_focus" in account for account in restatement_accounts)

    # Evidence index
    assert "evidence_index" in data
    assert len(data["evidence_index"]) > 0
    assert data["event_buckets"]
    assert data["event_buckets"][0]["total"] >= 1
    assert data["evidence_dossier"]
    dossier_groups = {item["group"] for item in data["evidence_dossier"]}
    assert {"available", "attention"}.issubset(dossier_groups)


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

    trail_response = client.get(
        f"/analise/companhias/{cia.codigo_cvm}/fundamentalista/evidencias/{metric_ev_id}/trilha",
        headers=headers,
    )
    assert trail_response.status_code == 200
    trail = trail_response.json()
    assert trail["root_evidence_id"] == metric_ev_id
    assert len(trail["nodes"]) >= 1
    assert len(trail["nodes"]) <= 12

    receita_ev_id = [e_id for e_id in evidence_ids if "::metric::" in e_id and "::receita_liquida::" in e_id][0]
    isolated_response = client.get(
        f"/analise/companhias/{cia.codigo_cvm}/fundamentalista/evidencias/{receita_ev_id}/trilha",
        params={"types": ["signal"]},
        headers=headers,
    )
    assert isolated_response.status_code == 200
    assert isolated_response.json()["nodes"] == []


def test_fundamentalista_cash_bridge_unavailable_when_component_missing(client: TestClient, db_session: Session) -> None:
    cia = _seed_analise_v2(db_session)
    headers = _ops_headers(client)
    db_session.query(DemonstracaoFinanceira).filter(
        DemonstracaoFinanceira.codigo_cvm == cia.codigo_cvm,
        DemonstracaoFinanceira.codigo_conta == "6.02.01",
    ).delete(synchronize_session=False)
    db_session.commit()

    response = client.get(
        f"/analise/companhias/{cia.codigo_cvm}/fundamentalista",
        params={"periodicidade": "annual", "base_periodo": "fy", "horizonte_anos": 5},
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    bridges = data["etapas"]["caixa_solidez"]["ponte_caixa"]
    unavailable = [item for item in bridges if item["unavailable_reason"]]
    assert unavailable
    assert unavailable[0]["unavailable_reason"]["reason_code"] == "MISSING_CASH_COMPONENT"


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


def test_fundamentalista_as_of_events_and_context_propagation(client: TestClient, db_session: Session) -> None:
    cia = _seed_analise_v2(db_session)
    headers = _ops_headers(client)

    # 1. Fetch report with as_of = 2025-06-01
    response = client.get(
        f"/analise/companhias/{cia.codigo_cvm}/fundamentalista",
        params={
            "periodicidade": "annual",
            "base_periodo": "fy",
            "as_of": "2025-06-01"
        },
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()

    # The IPE event delivered on 2025-11-20 should NOT be present (since as_of is 2025-06-01)
    eventos_ipe = data["etapas"]["governanca_conclusao"]["eventos_ipe"]
    ipe_titles = {evt["title"] for evt in eventos_ipe}
    assert "Atualização operacional" not in ipe_titles

    # Check evidence ID structure is: ev::{codigo_cvm}::metric::consolidated::2025-06-01::fy::...
    evidence_ids = list(data["evidence_index"].keys())
    metric_ev_ids = [e_id for e_id in evidence_ids if "::metric::" in e_id]
    assert len(metric_ev_ids) > 0
    
    first_ev_id = metric_ev_ids[0]
    assert "::consolidated::2025-06-01::fy::" in first_ev_id

    # 2. Query evidence detail for this specific context-propagated ID
    ev_response = client.get(
        f"/analise/companhias/{cia.codigo_cvm}/fundamentalista/evidencias/{first_ev_id}",
        headers=headers,
    )
    assert ev_response.status_code == 200
    ev_data = ev_response.json()
    assert ev_data["evidence_id"] == first_ev_id


def test_fundamentalista_eventos_endpoint_filters_and_paginates(client: TestClient, db_session: Session) -> None:
    cia = _seed_analise_v2(db_session)
    headers = _ops_headers(client)

    response = client.get(
        f"/analise/companhias/{cia.codigo_cvm}/fundamentalista/eventos",
        params={
            "periodicidade": "annual",
            "base_periodo": "fy",
            "horizonte_anos": 5,
            "bucket": "2025",
            "familias": ["IPE"],
            "severidades": ["warning"],
            "limit": 1,
        },
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["items"]
    assert data["items"][0]["family"] == "IPE"
    assert data["items"][0]["severity"] == "warning"
    assert data["items"][0]["occurred_at"] <= "2026-07-10"
    assert data["next_cursor"] is None


def test_fundamentalista_quarterly_ytd_context_propagation(client: TestClient, db_session: Session) -> None:
    cia = _seed_analise_v2(db_session)
    headers = _ops_headers(client)

    # 1. Fetch report with scope=individual, base_periodo=ytd, and as_of historical (after filing on 2025-11-08)
    response = client.get(
        f"/analise/companhias/{cia.codigo_cvm}/fundamentalista",
        params={
            "periodicidade": "quarterly",
            "base_periodo": "ytd",
            "escopo": "individual",
            "as_of": "2025-11-15"
        },
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()

    # Verify context resolution metadata
    assert data["contexto"]["escopo"] == "individual"
    
    # Locate a YTD period evidence id in the index (e.g. for period_id = "2025-YTDQ3")
    evidence_ids = list(data["evidence_index"].keys())
    ytd_metric_ev_ids = [e_id for e_id in evidence_ids if "::metric::" in e_id and "2025-YTDQ3" in e_id]
    assert len(ytd_metric_ev_ids) > 0

    first_ytd_ev_id = ytd_metric_ev_ids[0]
    # Check that it propagated scope, as_of and base_periodo
    assert "::individual::2025-11-15::ytd::" in first_ytd_ev_id

    # 2. Query evidence detail for this YTD context-propagated ID
    ev_response = client.get(
        f"/analise/companhias/{cia.codigo_cvm}/fundamentalista/evidencias/{first_ytd_ev_id}",
        headers=headers,
    )
    assert ev_response.status_code == 200
    ev_data = ev_response.json()
    assert ev_data["evidence_id"] == first_ytd_ev_id
    assert ev_data["period_id"] == "2025-YTDQ3"
    assert ev_data["observation"] is not None


def test_fundamentalista_openapi_exposes_additive_contract_without_causal_language(client: TestClient) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    openapi = response.json()
    serialized = json.dumps(openapi, ensure_ascii=False).lower()
    assert "causal" not in serialized

    paths = openapi["paths"]
    assert "/analise/companhias/{codigo_cvm}/fundamentalista/eventos" in paths
    assert "/analise/companhias/{codigo_cvm}/fundamentalista/evidencias/{evidence_id}/trilha" in paths
    schemas = openapi["components"]["schemas"]
    assert "AnalisePonteCaixaPeriodo" in schemas
    assert "AnalisePainelPosicaoFinanceira" in schemas
    assert "AnaliseEvidenceDossierItem" in schemas
    assert "AnaliseEvidenceTrailResponse" in schemas


def test_fundamentalista_additive_blocks_and_ttm_verification(db_session: Session, client: TestClient) -> None:
    cia = _seed_analise_v2(db_session)
    headers = _ops_headers(client)

    # 1. Fetch annual report
    response = client.get(
        f"/analise/companhias/{cia.codigo_cvm}/fundamentalista",
        params={
            "periodicidade": "annual",
            "base_periodo": "fy",
            "escopo": "consolidated",
            "as_of": "2026-06-01"
        },
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()

    # Verify all 14 blocks are present in the response
    assert "diagnostico_fundamental" in data
    assert "result_bridge" in data
    assert "margin_stack" in data
    assert "segment_panel" in data
    assert "comparability_items" in data
    assert "cash_reconciliation" in data
    assert "working_capital_panel" in data
    assert "debt_profile" in data
    assert "provision_panel" in data
    assert "capital_allocation" in data
    assert "accounting_judgments" in data
    assert "material_changes" in data
    assert "neutral_conclusion" in data
    assert "next_filing_watchlist" in data

    # 2. Check diagnostico_fundamental
    diag = data["diagnostico_fundamental"]
    assert diag["status"] in ("available", "partial")
    assert diag["scope"] == "consolidated"
    assert len(diag["dimensoes"]) > 0
    dim_names = [d["dimension"] for d in diag["dimensoes"]]
    assert "crescimento" in dim_names
    assert "rentabilidade" in dim_names
    assert "conversao_caixa" in dim_names
    assert "solidez_financeira" in dim_names
    assert "alocacao_capital" in dim_names
    assert "qualidade_comparabilidade" in dim_names

    # 3. Check result_bridge
    bridge = data["result_bridge"]
    assert bridge["status"] in ("available", "partial")
    assert len(bridge["items"]) > 0

    # 4. Check margin_stack
    margin = data["margin_stack"]
    assert margin["status"] in ("available", "partial")
    margins_types = [m["margin_type"] for m in margin["margins"]]
    assert "bruta" in margins_types
    assert "ebitda" in margins_types
    assert "ebit" in margins_types
    assert "liquida" in margins_types

    # 5. Check segment_panel
    seg = data["segment_panel"]
    assert seg["status"] == "unavailable"
    assert len(seg["limitations"]) > 0

    # 6. Check comparability_items
    comp = data["comparability_items"]
    assert comp["status"] in ("available", "partial", "not_applicable")

    # 7. Check cash_reconciliation
    cash_recon = data["cash_reconciliation"]
    assert cash_recon["status"] in ("available", "partial")

    # 8. Check working_capital_panel
    wc = data["working_capital_panel"]
    assert wc["status"] in ("available", "partial")
    assert wc["net_operating_working_capital"] is None

    # 9. Check debt_profile
    debt = data["debt_profile"]
    assert debt["status"] in ("available", "partial")
    assert debt["divida_bruta"] is not None
    assert debt["divida_liquida"] is not None

    # 10. Check provision_panel
    prov = data["provision_panel"]
    assert prov["status"] == "unavailable"
    assert len(prov["limitations"]) > 0

    # 11. Check capital_allocation
    cap = data["capital_allocation"]
    assert cap["status"] in ("available", "partial")

    # 12. Check accounting_judgments
    judgment = data["accounting_judgments"]
    assert judgment["status"] == "unavailable"
    assert len(judgment["limitations"]) > 0

    # 13. Check neutral_conclusion (Verify neutrality and absence of opinion/valuation/score)
    conc = data["neutral_conclusion"]
    assert conc["status"] in ("available", "partial")
    for text in conc["supported_fundamentals"] + conc["pressure_points"] + conc["analysis_limits"] + conc.get("observed_changes", []):
        lower_text = text.lower()
        # Verify no buy/sell recommendation keywords
        assert "compra" not in lower_text
        assert "venda" not in lower_text
        assert "recomendação" not in lower_text
        assert "barato" not in lower_text
        assert "caro" not in lower_text

    # 14. Check next_filing_watchlist
    watch = data["next_filing_watchlist"]
    assert watch["status"] in ("available", "partial", "not_applicable")


def test_fundamentalista_ttm_roe_roa_mathematical_precision(db_session: Session, client: TestClient) -> None:
    cia = _seed_analise_v2(db_session)
    headers = _ops_headers(client)

    # 1. Fetch quarterly TTM report
    response = client.get(
        f"/analise/companhias/{cia.codigo_cvm}/fundamentalista",
        params={
            "periodicidade": "quarterly",
            "base_periodo": "ytd",
            "escopo": "consolidated",
            "as_of": "2025-11-15"
        },
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()

    # Verify TTM Margins are recalculated and not summed
    margin_stack = data["margin_stack"]
    margins = {m["margin_type"]: m for m in margin_stack["margins"]}
    liquida = margins["liquida"]
    assert liquida["current_value"] is not None
    # Numerator TTM (lucro) = 24M + 36.734M - 18M = 42,734,000
    # Denominator TTM (receita) = 370.178M + 490.829M - 360M = 501,007,000
    # Expected TTM Margin = 42,734,000 / 501,007,000 = 0.085296213...
    assert abs(float(liquida["current_value"]) - 0.085296213) < 1e-5
    # Comparison TTM Margin (2024-YTDQ3) = 28,000,000 / 485,000,000 = 0.057731958...
    assert abs(float(liquida["comparison_value"]) - 0.057731958) < 1e-5
    assert abs(float(liquida["change_pp"]) - 0.02756425) < 1e-5

    # Verify TTM ROE and ROA under etapas.resultado_eficiencia.series
    series = {s["metric_id"]: s for s in data["etapas"]["resultado_eficiencia"]["series"] if s["period_id"] == "2025-YTDQ3"}
    # TTM ROE = 42,734,000 / average(215M, 195M) = 42,734,000 / 205,000,000 = 0.208458536...
    assert abs(float(series["roe"]["value"]) - 0.208458536) < 1e-5
    # TTM ROA = 42,734,000 / average(540M, 480M) = 42,734,000 / 510,000,000 = 0.083792156...
    assert abs(float(series["roa"]["value"]) - 0.083792156) < 1e-5

    # 2. Fetch annual report to verify annual ROE and ROA averages
    response_ann = client.get(
        f"/analise/companhias/{cia.codigo_cvm}/fundamentalista",
        params={
            "periodicidade": "annual",
            "base_periodo": "fy",
            "escopo": "consolidated",
            "as_of": "2026-06-01"
        },
        headers=headers,
    )
    assert response_ann.status_code == 200
    data_ann = response_ann.json()

    series_ann = {s["metric_id"]: s for s in data_ann["etapas"]["resultado_eficiencia"]["series"] if s["period_id"] == "FY2025"}
    # Profit FY2025 = 38,100,000
    # Patrimonio FY2025 = 220,000,000, Patrimonio FY2024 = 200,000,000, Average = 210,000,000
    # Annual ROE = 38,100,000 / 210,000,000 = 0.181428571...
    assert abs(float(series_ann["roe"]["value"]) - 0.181428571) < 1e-5
    # Ativo FY2025 = 550,000,000, Ativo FY2024 = 500,000,000, Average = 525,000,000
    # Annual ROA = 38,100,000 / 525,000,000 = 0.072571428...
    assert abs(float(series_ann["roa"]["value"]) - 0.072571428) < 1e-5

    # 3. Verify neutral observed_changes
    conc = data["neutral_conclusion"]
    assert conc["status"] == "available"
    assert len(conc["observed_changes"]) > 0
    for text in conc["observed_changes"]:
        assert "variação" in text or "variou" in text
        # Confirm no universal thresholds
        assert "alerta" not in text
        assert "sob controle" not in text


def test_fundamentalista_openapi_includes_new_block_schemas(client: TestClient) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    openapi = response.json()
    schemas = openapi["components"]["schemas"]
    
    assert "DiagnosticoFundamental" in schemas
    assert "ResultBridge" in schemas
    assert "MarginStack" in schemas
    assert "SegmentPanel" in schemas
    assert "ComparabilityItems" in schemas
    assert "CashReconciliation" in schemas
    assert "WorkingCapitalPanel" in schemas
    assert "DebtProfile" in schemas
    assert "ProvisionPanel" in schemas
    assert "CapitalAllocation" in schemas
    assert "AccountingJudgments" in schemas
    assert "MaterialChanges" in schemas
    assert "NeutralConclusion" in schemas
    assert "NextFilingWatchlist" in schemas

    operation = openapi["paths"]["/analise/companhias/{codigo_cvm}/fundamentalista"]["get"]
    assert "304" in operation["responses"]
    headers = operation["responses"]["200"]["headers"]
    assert {"ETag", "Cache-Control", "X-Analise-Source", "X-Analise-Generation"} <= set(headers)


def test_materializacao_prewarm_persiste_e_reutiliza_snapshot(
    db_session: Session,
    client: TestClient,
) -> None:
    cia = _seed_analise_v2(db_session)
    execution = materializar_analise_companhia(db_session, cia, scope="consolidated")

    snapshot = db_session.scalar(
        select(AnaliseFundamentalistaSnapshot).where(
            AnaliseFundamentalistaSnapshot.codigo_cvm == cia.codigo_cvm,
            AnaliseFundamentalistaSnapshot.source_execution_id == execution.id,
            AnaliseFundamentalistaSnapshot.periodicidade == "annual",
            AnaliseFundamentalistaSnapshot.base_periodo == "fy",
            AnaliseFundamentalistaSnapshot.horizonte_anos == 5,
            AnaliseFundamentalistaSnapshot.as_of_key == "latest",
            AnaliseFundamentalistaSnapshot.include_key == "none",
        )
    )
    assert snapshot is not None
    assert execution.summary is not None
    assert execution.summary["fundamentalista_snapshot_status"] == "success"

    clear_analysis_session_cache(db_session)
    result = obter_fundamentalista_com_metadata(
        db_session,
        cia,
        scope="consolidated",
        periodicidade="annual",
        base_periodo="fy",
        horizonte_anos=5,
    )
    assert result.source == "db_snapshot"
    assert result.generation == str(execution.id)
    assert result.response.resolution.materialization_execution_id == str(execution.id)

    headers = _ops_headers(client)
    response = client.get(
        f"/analise/companhias/{cia.codigo_cvm}/fundamentalista",
        headers=headers,
    )
    assert response.status_code == 200
    assert response.headers["x-analise-source"] == "db_snapshot"
    assert response.headers["x-analise-generation"] == str(execution.id)
    assert response.headers["etag"].startswith('"')
    assert response.headers["cache-control"].startswith("private")


def test_snapshot_canonico_reduz_leitura_para_duas_consultas(
    db_session: Session,
) -> None:
    cia = _seed_analise_v2(db_session)
    materializar_analise_companhia(db_session, cia, scope="consolidated")
    clear_analysis_session_cache(db_session)
    statements: list[str] = []
    bind = db_session.get_bind()

    def capture_selects(
        _conn: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: bool,
    ) -> None:
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(bind, "before_cursor_execute", capture_selects)
    try:
        result = obter_fundamentalista_com_metadata(
            db_session,
            cia,
            scope="consolidated",
            periodicidade="annual",
            base_periodo="fy",
            horizonte_anos=5,
        )
    finally:
        event.remove(bind, "before_cursor_execute", capture_selects)

    assert result.source == "db_snapshot"
    assert len(statements) <= 2


def test_runtime_fallback_nao_persiste_snapshot_sem_execucao_canonica(
    db_session: Session,
) -> None:
    cia = _seed_analise_v2(db_session)
    result = obter_fundamentalista_com_metadata(
        db_session,
        cia,
        scope="consolidated",
        periodicidade="annual",
        base_periodo="fy",
        horizonte_anos=5,
    )

    assert result.source == "compiled_runtime"
    assert db_session.scalar(select(func.count(AnaliseFundamentalistaSnapshot.id))) == 0


def test_nova_materializacao_substitui_a_geracao_do_snapshot(
    db_session: Session,
) -> None:
    cia = _seed_analise_v2(db_session)
    first_execution = materializar_analise_companhia(db_session, cia, scope="consolidated")
    second_execution = materializar_analise_companhia(db_session, cia, scope="consolidated")

    snapshots = db_session.scalars(
        select(AnaliseFundamentalistaSnapshot).where(
            AnaliseFundamentalistaSnapshot.codigo_cvm == cia.codigo_cvm,
            AnaliseFundamentalistaSnapshot.escopo == "consolidated",
            AnaliseFundamentalistaSnapshot.periodicidade == "annual",
            AnaliseFundamentalistaSnapshot.base_periodo == "fy",
            AnaliseFundamentalistaSnapshot.horizonte_anos == 5,
            AnaliseFundamentalistaSnapshot.as_of_key == "latest",
            AnaliseFundamentalistaSnapshot.include_key == "none",
        )
    ).all()

    assert first_execution.id != second_execution.id
    assert len(snapshots) == 1
    assert snapshots[0].source_execution_id == second_execution.id


def _cache_set(values: dict[str, str], key: str, value: str, _ttl: int) -> bool:
    values[key] = value
    return True


def test_fundamentalista_redis_cache_e_etag_304(
    db_session: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cia = _seed_analise_v2(db_session)
    headers = _ops_headers(client)
    values: dict[str, str] = {}

    monkeypatch.setattr(analise_router._settings, "analise_fundamentalista_cache_enabled", True)
    monkeypatch.setattr(delivery_cache, "get", lambda key: values.get(key))
    monkeypatch.setattr(
        delivery_cache,
        "set",
        lambda key, value, ttl: _cache_set(values, key, value, ttl),
    )
    monkeypatch.setattr(delivery_cache, "acquire_lock", lambda _key, _ttl: "lock-token")
    monkeypatch.setattr(delivery_cache, "release_lock", lambda _key, _token: None)

    first = client.get(
        f"/analise/companhias/{cia.codigo_cvm}/fundamentalista",
        headers=headers,
    )
    assert first.status_code == 200
    assert first.headers["x-analise-source"] == "compiled_runtime"
    assert values

    conditional_headers = {**headers, "If-None-Match": first.headers["etag"]}
    second = client.get(
        f"/analise/companhias/{cia.codigo_cvm}/fundamentalista",
        headers=conditional_headers,
    )
    assert second.status_code == 304
    assert second.content == b""
    assert second.headers["x-analise-source"] == "redis_cache"
