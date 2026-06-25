import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from _pytest.monkeypatch import MonkeyPatch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.analise import (
    AnaliseMaterializacaoCampanha,
    AnaliseMaterializacaoCampanhaItem,
    AnaliseMaterializacaoChunkExecucao,
    AnaliseMaterializacaoExecucao,
)
from app.models.cgvn import CgvnDocumento, CgvnPratica
from app.models.companhia import Companhia
from app.models.financeiro import DemonstracaoFinanceira, DocumentoFinanceiro
from app.models.fre import FreEmpregadoPosicaoGenero, FreRemuneracaoTotalOrgao
from app.models.ipe import IpeDocumento
from app.models.sincronizacao import ExecucaoSincronizacao
from app.models.vlmo import VlmoConsolidado
from app.services.analise import materializar_analise_companhia
from app.worker.celery_app import celery_app


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
    db.add(
        VlmoConsolidado(
            companhia_id=cia.id,
            cnpj_companhia=cia.cnpj_companhia,
            data_referencia=date(2025, 9, 30),
            versao=1,
            tipo_operacao="COMPRA",
            tipo_ativo="AÇÕES",
            quantidade=10000,
            preco_unitario=Decimal("12.00"),
            volume=Decimal("120000.00"),
            tipo_cargo="Diretor",
            data_movimentacao=date(2025, 10, 10),
            indice_ocorrencia=1,
            arquivo_origem="vlmo.csv",
            hash_origem="vlmo-1",
            ano_origem=2025,
            criado_em=agora,
            sincronizado_em=agora,
            alterado_em=agora,
        )
    )
    db.add_all(
        [
            CgvnDocumento(
                companhia_id=cia.id,
                cnpj_companhia=cia.cnpj_companhia,
                codigo_cvm=cia.codigo_cvm,
                nome_companhia=cia.denominacao_social,
                data_referencia=date(2024, 12, 31),
                data_entrega=date(2025, 3, 20),
                data_inicio_exercicio_social=date(2024, 1, 1),
                data_fim_exercicio_social=date(2024, 12, 31),
                id_documento=7001,
                versao=1,
                link_download="https://dados.cvm.gov.br/cgvn/2024-v1.zip",
                categoria="CGVN",
                motivo_reapresentacao=None,
                arquivo_origem="cgvn.csv",
                ano_origem=2024,
                linha_origem=1,
                hash_origem="cgvn-2024-v1",
                criado_em=agora,
                sincronizado_em=agora,
                alterado_em=agora,
            ),
            CgvnDocumento(
                companhia_id=cia.id,
                cnpj_companhia=cia.cnpj_companhia,
                codigo_cvm=cia.codigo_cvm,
                nome_companhia=cia.denominacao_social,
                data_referencia=date(2025, 12, 31),
                data_entrega=date(2026, 3, 21),
                data_inicio_exercicio_social=date(2025, 1, 1),
                data_fim_exercicio_social=date(2025, 12, 31),
                id_documento=7002,
                versao=2,
                link_download="https://dados.cvm.gov.br/cgvn/2025-v2.zip",
                categoria="CGVN",
                motivo_reapresentacao="Atualização de práticas",
                arquivo_origem="cgvn.csv",
                ano_origem=2025,
                linha_origem=1,
                hash_origem="cgvn-2025-v2",
                criado_em=agora,
                sincronizado_em=agora,
                alterado_em=agora,
            ),
            CgvnPratica(
                companhia_id=cia.id,
                cnpj_companhia=cia.cnpj_companhia,
                nome_companhia=cia.denominacao_social,
                data_referencia=date(2024, 12, 31),
                id_documento=7001,
                versao=1,
                id_item="1.1",
                pratica_recomendada="Prática 1",
                pratica_adotada="SIM",
                capitulo="1",
                principio="A",
                explicacao=None,
                arquivo_origem="cgvn_praticas.csv",
                ano_origem=2024,
                linha_origem=10,
                hash_origem="cgvn-pratica-2024-1",
                criado_em=agora,
                sincronizado_em=agora,
                alterado_em=agora,
            ),
            CgvnPratica(
                companhia_id=cia.id,
                cnpj_companhia=cia.cnpj_companhia,
                nome_companhia=cia.denominacao_social,
                data_referencia=date(2024, 12, 31),
                id_documento=7001,
                versao=1,
                id_item="1.2",
                pratica_recomendada="Prática 2",
                pratica_adotada="NAO",
                capitulo="1",
                principio="B",
                explicacao="Explicação 2024",
                arquivo_origem="cgvn_praticas.csv",
                ano_origem=2024,
                linha_origem=11,
                hash_origem="cgvn-pratica-2024-2",
                criado_em=agora,
                sincronizado_em=agora,
                alterado_em=agora,
            ),
            CgvnPratica(
                companhia_id=cia.id,
                cnpj_companhia=cia.cnpj_companhia,
                nome_companhia=cia.denominacao_social,
                data_referencia=date(2025, 12, 31),
                id_documento=7002,
                versao=2,
                id_item="1.1",
                pratica_recomendada="Prática 1",
                pratica_adotada="SIM",
                capitulo="1",
                principio="A",
                explicacao=None,
                arquivo_origem="cgvn_praticas.csv",
                ano_origem=2025,
                linha_origem=20,
                hash_origem="cgvn-pratica-2025-1",
                criado_em=agora,
                sincronizado_em=agora,
                alterado_em=agora,
            ),
            CgvnPratica(
                companhia_id=cia.id,
                cnpj_companhia=cia.cnpj_companhia,
                nome_companhia=cia.denominacao_social,
                data_referencia=date(2025, 12, 31),
                id_documento=7002,
                versao=2,
                id_item="1.2",
                pratica_recomendada="Prática 2",
                pratica_adotada="SIM",
                capitulo="1",
                principio="B",
                explicacao=None,
                arquivo_origem="cgvn_praticas.csv",
                ano_origem=2025,
                linha_origem=21,
                hash_origem="cgvn-pratica-2025-2",
                criado_em=agora,
                sincronizado_em=agora,
                alterado_em=agora,
            ),
            FreRemuneracaoTotalOrgao(
                companhia_id=cia.id,
                cnpj_companhia=cia.cnpj_companhia,
                data_referencia=date(2024, 12, 31),
                versao=1,
                id_documento=6001,
                nome_companhia=cia.denominacao_social,
                data_inicio_exercicio_social=date(2024, 1, 1),
                data_fim_exercicio_social=date(2024, 12, 31),
                total_remuneracao=Decimal("120000000"),
                orgao_administracao="Conselho de Administração",
                numero_membros=10,
                total_remuneracao_orgao=Decimal("120000000"),
                numero_membros_remunerados=10,
                arquivo_origem="fre_remuneracao.csv",
                ano_origem=2024,
                linha_origem=1,
                hash_origem="fre-rem-2024",
                criado_em=agora,
                sincronizado_em=agora,
                alterado_em=agora,
            ),
            FreRemuneracaoTotalOrgao(
                companhia_id=cia.id,
                cnpj_companhia=cia.cnpj_companhia,
                data_referencia=date(2025, 12, 31),
                versao=2,
                id_documento=6002,
                nome_companhia=cia.denominacao_social,
                data_inicio_exercicio_social=date(2025, 1, 1),
                data_fim_exercicio_social=date(2025, 12, 31),
                total_remuneracao=Decimal("150000000"),
                orgao_administracao="Conselho de Administração",
                numero_membros=11,
                total_remuneracao_orgao=Decimal("150000000"),
                numero_membros_remunerados=11,
                arquivo_origem="fre_remuneracao.csv",
                ano_origem=2025,
                linha_origem=1,
                hash_origem="fre-rem-2025",
                criado_em=agora,
                sincronizado_em=agora,
                alterado_em=agora,
            ),
            FreEmpregadoPosicaoGenero(
                companhia_id=cia.id,
                cnpj_companhia=cia.cnpj_companhia,
                data_referencia=date(2024, 12, 31),
                versao=1,
                id_documento=6101,
                nome_companhia=cia.denominacao_social,
                posicao="Consolidado",
                quantidade_feminino=12000,
                quantidade_masculino=28000,
                quantidade_nao_binario=100,
                quantidade_outros=50,
                quantidade_sem_resposta=20,
                arquivo_origem="fre_empregados.csv",
                ano_origem=2024,
                linha_origem=1,
                hash_origem="fre-emp-2024",
                criado_em=agora,
                sincronizado_em=agora,
                alterado_em=agora,
            ),
            FreEmpregadoPosicaoGenero(
                companhia_id=cia.id,
                cnpj_companhia=cia.cnpj_companhia,
                data_referencia=date(2025, 12, 31),
                versao=2,
                id_documento=6102,
                nome_companhia=cia.denominacao_social,
                posicao="Consolidado",
                quantidade_feminino=12500,
                quantidade_masculino=28200,
                quantidade_nao_binario=120,
                quantidade_outros=60,
                quantidade_sem_resposta=25,
                arquivo_origem="fre_empregados.csv",
                ano_origem=2025,
                linha_origem=1,
                hash_origem="fre-emp-2025",
                criado_em=agora,
                sincronizado_em=agora,
                alterado_em=agora,
            ),
        ]
    )

    db.commit()
    return cia


def _materializacao_execucao(
    cia: Companhia,
    *,
    status: str,
    escopo: str = "consolidated",
    source: str = "post_ingestion",
    materialization_mode: str = "full",
    invalidated_from: date | None = None,
    campanha_id: uuid.UUID | None = None,
    campanha_item_id: uuid.UUID | None = None,
    chunk_execucao_id: uuid.UUID | None = None,
    queue_name: str | None = None,
    position_in_chunk: int | None = None,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
    updated_at: datetime | None = None,
    coverage_complete: bool = False,
    summary: dict[str, object] | None = None,
) -> AnaliseMaterializacaoExecucao:
    agora = datetime.now(UTC)
    return AnaliseMaterializacaoExecucao(
        id=uuid.uuid4(),
        companhia_id=cia.id,
        codigo_cvm=cia.codigo_cvm,
        escopo=escopo,
        calculation_version="2026.2",
        status=status,
        coverage_complete=coverage_complete,
        source=source,
        materialization_mode=materialization_mode,
        invalidated_from=invalidated_from,
        campanha_id=campanha_id,
        campanha_item_id=campanha_item_id,
        chunk_execucao_id=chunk_execucao_id,
        queue_name=queue_name,
        position_in_chunk=position_in_chunk,
        summary=summary or {},
        started_at=started_at or agora,
        finished_at=finished_at,
        created_at=agora,
        updated_at=updated_at or started_at or agora,
    )


def _materializacao_campanha(
    *,
    source: str = "post_ingestion",
    status: str = "running",
    chunk_size: int = 25,
    started_at: datetime | None = None,
    updated_at: datetime | None = None,
    total_items: int = 0,
    pending_items: int = 0,
    running_items: int = 0,
    success_items: int = 0,
    failed_items: int = 0,
    skipped_items: int = 0,
    summary: dict[str, object] | None = None,
) -> AnaliseMaterializacaoCampanha:
    agora = datetime.now(UTC)
    return AnaliseMaterializacaoCampanha(
        source=source,
        status=status,
        chunk_size=chunk_size,
        total_items=total_items,
        pending_items=pending_items,
        running_items=running_items,
        success_items=success_items,
        failed_items=failed_items,
        skipped_items=skipped_items,
        summary=summary or {},
        started_at=started_at,
        updated_at=updated_at or agora,
    )


def _materializacao_campanha_item(
    campanha: AnaliseMaterializacaoCampanha,
    cia: Companhia,
    *,
    escopo: str,
    status: str,
    ordem: int,
    invalidated_from: date | None = None,
    chunk_execucao_id: uuid.UUID | None = None,
    started_at: datetime | None = None,
) -> AnaliseMaterializacaoCampanhaItem:
    agora = datetime.now(UTC)
    return AnaliseMaterializacaoCampanhaItem(
        campanha_id=campanha.id,
        codigo_cvm=cia.codigo_cvm,
        companhia_id=cia.id,
        escopo=escopo,
        status=status,
        ordem=ordem,
        invalidated_from=invalidated_from,
        chunk_execucao_id=chunk_execucao_id,
        started_at=started_at,
        updated_at=agora,
    )


def _materializacao_chunk_execucao(
    campanha: AnaliseMaterializacaoCampanha,
    *,
    status: str,
    lease_expires_at: datetime | None = None,
    heartbeat_at: datetime | None = None,
    item_count: int = 1,
    processed_items: int = 0,
    success_items: int = 0,
    failed_items: int = 0,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> AnaliseMaterializacaoChunkExecucao:
    agora = datetime.now(UTC)
    return AnaliseMaterializacaoChunkExecucao(
        campanha_id=campanha.id,
        status=status,
        lease_owner="celery-task-id",
        lease_expires_at=lease_expires_at,
        heartbeat_at=heartbeat_at,
        item_count=item_count,
        processed_items=processed_items,
        success_items=success_items,
        failed_items=failed_items,
        summary={},
        started_at=started_at,
        finished_at=finished_at,
        updated_at=updated_at or agora,
    )


def test_metricas_catalogo(client: TestClient) -> None:
    resp = client.get("/analise/metricas")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["calculation_version"] == "2026.2"
    margem = next(item for item in payload["metricas"] if item["id"] == "margem_liquida")
    assert margem["type"] == "ratio"
    assert margem["unit"] == "ratio"
    assert margem["formula"] == "lucro_liquido / receita_liquida"


def test_analise_manifesto(client: TestClient, db_session: Session) -> None:
    _seed_analise_v2(db_session)

    resp = client.get("/analise/companhias/9512")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["companhia"]["codigo_cvm"] == 9512
    assert payload["contexto_padrao"]["periodo_id"] == "FY2025"
    assert payload["qualidade"]["restatements"] == 1
    assert payload["resolution"]["mode"] == "runtime_fallback"
    assert payload["links"]["series"] == "/analise/companhias/9512/series"
    assert any(periodo["period_id"] == "2025-Q3" for periodo in payload["periodos_disponiveis"])


def test_analise_series_annual_selects_latest_current_exercise(client: TestClient, db_session: Session) -> None:
    _seed_analise_v2(db_session)

    resp = client.get("/analise/companhias/9512/series?metricas=receita_liquida&periodicidade=annual&base_periodo=fy")
    assert resp.status_code == 200
    payload = resp.json()

    fy2025 = next(obs for obs in payload["observacoes"] if obs["metric_id"] == "receita_liquida" and obs["period_id"] == "FY2025")
    assert fy2025["value"] == "497549000000"
    assert fy2025["form"] == "DFP"
    assert fy2025["version"] == 2
    assert fy2025["provenance"][0]["order"] == "ÚLTIMO"


def test_analise_series_annual_history_respects_horizonte_anos(client: TestClient, db_session: Session) -> None:
    _seed_analise_v2(db_session)

    resp = client.get("/analise/companhias/9512/series?metricas=receita_liquida&periodicidade=annual&base_periodo=fy&horizonte_anos=5")
    assert resp.status_code == 200
    payload = resp.json()

    period_ids = [obs["period_id"] for obs in payload["observacoes"] if obs["metric_id"] == "receita_liquida"]
    assert payload["horizonte_anos"] == 5
    assert period_ids == ["FY2021", "FY2022", "FY2023", "FY2024", "FY2025"]


def test_analise_series_quarterly_prefers_direct_quarter_over_ytd(client: TestClient, db_session: Session) -> None:
    _seed_analise_v2(db_session)

    resp = client.get("/analise/companhias/9512/series?metricas=receita_liquida&periodicidade=quarterly&base_periodo=quarter")
    assert resp.status_code == 200
    payload = resp.json()

    q3 = next(obs for obs in payload["observacoes"] if obs["metric_id"] == "receita_liquida" and obs["period_id"] == "2025-Q3")
    assert q3["value"] == "127906000000"
    assert q3["value_source"] == "reported"
    assert q3["form"] == "ITR"
    assert q3["start_date"] == "2025-07-01"
    assert q3["end_date"] == "2025-09-30"


def test_analise_series_q4_derives_from_dfp_minus_q3_ytd(client: TestClient, db_session: Session) -> None:
    _seed_analise_v2(db_session)

    resp = client.get("/analise/companhias/9512/series?metricas=receita_liquida&periodicidade=quarterly&base_periodo=quarter")
    assert resp.status_code == 200
    payload = resp.json()

    q4 = next(obs for obs in payload["observacoes"] if obs["metric_id"] == "receita_liquida" and obs["period_id"] == "2025-Q4")
    assert q4["value"] == "127371000000"
    assert q4["value_source"] == "derived_from_dfp_minus_ytd"
    assert q4["form"] == "DERIVED"
    assert len(q4["provenance"]) == 2


def test_analise_comparacoes_marks_qoq_unavailable_for_ytd_flow(client: TestClient, db_session: Session) -> None:
    _seed_analise_v2(db_session)

    resp = client.get("/analise/companhias/9512/comparacoes?metricas=receita_liquida&periodicidade=quarterly&base_periodo=ytd")
    assert resp.status_code == 200
    payload = resp.json()

    q3_qoq = next(
        item
        for item in payload["comparacoes"]
        if item["metric_id"] == "receita_liquida" and item["period_id"] == "2025-YTDQ3" and item["comparison_kind"] == "QoQ"
    )
    assert q3_qoq["status"] == "unavailable"
    assert q3_qoq["reason_code"] == "QOQ_NOT_SUPPORTED_FOR_YTD_FLOW"


def test_analise_comparacoes_base100_exposes_metric_and_comparison_units(client: TestClient, db_session: Session) -> None:
    _seed_analise_v2(db_session)

    resp = client.get("/analise/companhias/9512/comparacoes?metricas=receita_liquida&periodicidade=annual&base_periodo=fy&tipos=BASE100&horizonte_anos=5")
    assert resp.status_code == 200
    payload = resp.json()

    item = next(
        comp
        for comp in payload["comparacoes"]
        if comp["metric_id"] == "receita_liquida" and comp["period_id"] == "FY2025" and comp["comparison_kind"] == "BASE100"
    )
    assert payload["horizonte_anos"] == 5
    assert item["metric_unit"] == "BRL"
    assert item["comparison_unit"] == "index"
    assert item["current_value"] == "497549000000"
    assert item["comparable_value"] == "390000000000"


def test_analise_series_supports_derived_financial_metrics(client: TestClient, db_session: Session) -> None:
    _seed_analise_v2(db_session)

    resp = client.get(
        "/analise/companhias/9512/series?metricas=ebitda,caixa_livre,divida_bruta,divida_liquida,alavancagem,conversao_lucro_caixa&periodicidade=annual&base_periodo=fy&horizonte_anos=2"
    )
    assert resp.status_code == 200
    payload = resp.json()

    by_metric_period = {(obs["metric_id"], obs["period_id"]): obs for obs in payload["observacoes"]}
    assert by_metric_period[("ebitda", "FY2025")]["value"] == "99000000000"
    assert by_metric_period[("caixa_livre", "FY2025")]["value"] == "55000000000"
    assert by_metric_period[("divida_bruta", "FY2025")]["value"] == "124000000000"
    assert by_metric_period[("divida_liquida", "FY2025")]["value"] == "90000000000"
    assert by_metric_period[("alavancagem", "FY2025")]["value"] == "0.9090909090909090909090909091"
    assert by_metric_period[("conversao_lucro_caixa", "FY2025")]["value"] == "2.572178477690288713910761155"


def test_analise_restatements_reports_changed_accounts(client: TestClient, db_session: Session) -> None:
    _seed_analise_v2(db_session)

    resp = client.get("/analise/companhias/9512/restatements")
    assert resp.status_code == 200
    payload = resp.json()

    assert len(payload["restatements"]) == 1
    item = payload["restatements"][0]
    assert item["form"] == "DFP"
    assert item["period_id"] == "FY2025"
    account = next(
        changed for changed in item["changed_accounts"] if changed["account_code"] == "3.01" and changed["order"] == "ÚLTIMO"
    )
    assert account["before_value"] == "490829000000"
    assert account["after_value"] == "497549000000"
    assert account["absolute_change"] == "6720000000"


def test_analise_eventos_returns_structured_timeline(client: TestClient, db_session: Session) -> None:
    _seed_analise_v2(db_session)

    resp = client.get("/analise/companhias/9512/eventos")
    assert resp.status_code == 200
    payload = resp.json()

    assert payload["companhia"]["codigo_cvm"] == 9512
    families = {evento["family"] for evento in payload["eventos"]}
    assert "IPE" in families
    assert "VLMO" in families
    assert all(evento["event_id"] for evento in payload["eventos"])


def test_analise_governanca_returns_temporal_contract(client: TestClient, db_session: Session) -> None:
    _seed_analise_v2(db_session)

    resp = client.get("/analise/companhias/9512/governanca?horizonte_anos=2")
    assert resp.status_code == 200
    payload = resp.json()

    assert payload["horizonte_anos"] == 2
    ratio_2025 = next(obs for obs in payload["observacoes"] if obs["metric_id"] == "governanca_praticas_adotadas_ratio" and obs["period_id"] == "FY2025")
    explicacoes_2024 = next(obs for obs in payload["observacoes"] if obs["metric_id"] == "governanca_praticas_com_explicacao" and obs["period_id"] == "FY2024")
    assert ratio_2025["value"] == "1"
    assert ratio_2025["restated"] is True
    assert explicacoes_2024["value"] == "1"


def test_analise_pessoas_returns_temporal_contract(client: TestClient, db_session: Session) -> None:
    _seed_analise_v2(db_session)

    resp = client.get("/analise/companhias/9512/pessoas?horizonte_anos=2")
    assert resp.status_code == 200
    payload = resp.json()

    assert payload["horizonte_anos"] == 2
    remuneracao_2025 = next(obs for obs in payload["observacoes"] if obs["metric_id"] == "pessoas_remuneracao_total_orgao" and obs["period_id"] == "FY2025")
    empregados_2025 = next(obs for obs in payload["observacoes"] if obs["metric_id"] == "pessoas_empregados_total" and obs["period_id"] == "FY2025")
    assert remuneracao_2025["value"] == "150000000"
    assert remuneracao_2025["restated"] is True
    assert empregados_2025["value"] == "40905"


def test_analise_brief_returns_reference_periods_and_metrics(client: TestClient, db_session: Session) -> None:
    _seed_analise_v2(db_session)

    resp = client.get("/analise/companhias/9512/brief?metricas=receita_liquida,lucro_liquido")
    assert resp.status_code == 200
    payload = resp.json()

    assert payload["periodos_referencia"]["quarter_current"] == "2025-Q4"
    assert payload["periodos_referencia"]["quarter_previous"] == "2025-Q3"
    assert payload["periodos_referencia"]["quarter_yoy"] == "2024-Q4"
    assert payload["periodos_referencia"]["fy_current"] == "FY2025"
    assert payload["periodos_referencia"]["fy_previous"] == "FY2024"
    assert any(obs["period_id"] == "FY2025" for obs in payload["metricas"])
    assert any(comp["period_id"] == "FY2025" for comp in payload["comparacoes"])



def test_analise_removed_endpoints_return_404(client: TestClient, db_session: Session) -> None:
    _seed_analise_v2(db_session)

    for path in (
        "/companhias/9512/analise/v2",
        "/companhias/9512/analise/v2/series",
        "/companhias/9512/analise/v2/comparacoes",
        "/companhias/9512/analise/v2/qualidade",
        "/companhias/9512/analise/v2/sinais",
        "/companhias/9512/analise/v2/eventos",
        "/companhias/9512/analise/v2/restatements",
        "/companhias/9512/analise",
        "/companhias/9512/analise/overview",
        "/companhias/9512/analise/financeiro",
        "/companhias/9512/analise/comparativo?ano_base=2025&ano_comparacao=2024",
        "/companhias/9512/analise/eventos",
        "/companhias/9512/analise/pessoas-remuneracao",
        "/companhias/9512/analise/mercado-insiders",
    ):
        resp = client.get(path)
        assert resp.status_code == 404


def test_analise_series_reads_from_canonical_materialization(client: TestClient, db_session: Session) -> None:
    cia = _seed_analise_v2(db_session)
    execucao = materializar_analise_companhia(db_session, cia, scope="consolidated", source="test")
    assert execucao.status == "success"

    db_session.query(DemonstracaoFinanceira).delete()
    db_session.query(DocumentoFinanceiro).delete()
    db_session.commit()

    resp = client.get("/analise/companhias/9512/series?metricas=receita_liquida&periodicidade=annual&base_periodo=fy")
    assert resp.status_code == 200
    payload = resp.json()

    assert payload["resolution"]["mode"] == "canonical"
    assert payload["resolution"]["materialization_execution_id"] == str(execucao.id)
    fy2025 = next(obs for obs in payload["observacoes"] if obs["metric_id"] == "receita_liquida" and obs["period_id"] == "FY2025")
    assert fy2025["value"] == "497549000000"


def test_materializar_analise_companhia_pula_cancelada_por_padrao(db_session: Session) -> None:
    cia = _seed_analise_v2(db_session)
    cia.situacao_registro = "CANCELADA"
    db_session.commit()

    execucao = materializar_analise_companhia(db_session, cia, scope="consolidated", source="test")

    assert execucao.status == "success"
    assert execucao.coverage_complete is False
    assert execucao.summary is not None
    assert execucao.summary["skipped_reason"] == "COMPANHIA_CANCELADA"
    assert execucao.summary["company_status"] == "CANCELADA"


def test_materializar_analise_companhia_permita_cancelada_quando_explicito(db_session: Session) -> None:
    cia = _seed_analise_v2(db_session)
    cia.situacao_registro = "CANCELADA"
    db_session.commit()

    execucao = materializar_analise_companhia(
        db_session,
        cia,
        scope="consolidated",
        source="test",
        incluir_canceladas=True,
    )

    assert execucao.status == "success"
    assert execucao.summary is not None
    assert execucao.summary.get("skipped_reason") is None
    assert int(execucao.summary["knowledge_dates"]) > 0


def test_analise_series_as_of_uses_canonical_timeline(client: TestClient, db_session: Session) -> None:
    cia = _seed_analise_v2(db_session)
    materializar_analise_companhia(db_session, cia, scope="consolidated", source="test")

    db_session.query(DemonstracaoFinanceira).delete()
    db_session.query(DocumentoFinanceiro).delete()
    db_session.commit()

    resp = client.get(
        "/analise/companhias/9512/series?metricas=receita_liquida&periodicidade=annual&base_periodo=fy&as_of=2026-03-05"
    )
    assert resp.status_code == 200
    payload = resp.json()

    assert payload["resolution"]["mode"] == "canonical"
    fy2025 = next(obs for obs in payload["observacoes"] if obs["metric_id"] == "receita_liquida" and obs["period_id"] == "FY2025")
    assert fy2025["value"] == "490829000000"
    assert fy2025["version"] == 1


def test_analise_series_incremental_materialization_preserves_canonical_equivalence(client: TestClient, db_session: Session) -> None:
    cia = _seed_analise_v2(db_session)
    execucao_full = materializar_analise_companhia(db_session, cia, scope="consolidated", source="test")
    execucao_incremental = materializar_analise_companhia(
        db_session,
        cia,
        scope="consolidated",
        source="test",
        invalidated_from=date(2026, 3, 10),
    )

    assert execucao_full.materialization_mode == "full"
    assert execucao_incremental.materialization_mode == "incremental"
    assert execucao_incremental.invalidated_from == date(2026, 3, 10)

    resp_historico = client.get(
        "/analise/companhias/9512/series?metricas=receita_liquida&periodicidade=annual&base_periodo=fy&as_of=2026-03-05"
    )
    assert resp_historico.status_code == 200
    historico = resp_historico.json()
    historico_fy2025 = next(
        obs for obs in historico["observacoes"] if obs["metric_id"] == "receita_liquida" and obs["period_id"] == "FY2025"
    )
    assert historico["resolution"]["mode"] == "canonical"
    assert historico["resolution"]["materialization_execution_id"] == str(execucao_incremental.id)
    assert historico_fy2025["value"] == "490829000000"
    assert historico_fy2025["version"] == 1

    resp_atual = client.get(
        "/analise/companhias/9512/series?metricas=receita_liquida&periodicidade=annual&base_periodo=fy&as_of=2026-03-10"
    )
    assert resp_atual.status_code == 200
    atual = resp_atual.json()
    atual_fy2025 = next(obs for obs in atual["observacoes"] if obs["metric_id"] == "receita_liquida" and obs["period_id"] == "FY2025")
    assert atual["resolution"]["mode"] == "canonical"
    assert atual_fy2025["value"] == "497549000000"
    assert atual_fy2025["version"] == 2


def test_analise_materializacoes_list_and_detail(client: TestClient, db_session: Session) -> None:
    cia = _seed_analise_v2(db_session)
    campanha = _materializacao_campanha(status="running", total_items=2, pending_items=1, running_items=1)
    db_session.add(campanha)
    db_session.flush()
    chunk = _materializacao_chunk_execucao(
        campanha,
        status="running",
        lease_expires_at=datetime.now(UTC) + timedelta(minutes=5),
        heartbeat_at=datetime.now(UTC),
        item_count=1,
        processed_items=0,
        success_items=0,
        failed_items=0,
        started_at=datetime.now(UTC),
    )
    db_session.add(chunk)
    db_session.flush()
    started_at = datetime.now(UTC) - timedelta(seconds=20)
    running = _materializacao_execucao(
        cia,
        status="running",
        materialization_mode="incremental",
        invalidated_from=date(2026, 3, 10),
        campanha_id=campanha.id,
        chunk_execucao_id=chunk.id,
        queue_name="analise_materializacao",
        position_in_chunk=1,
        started_at=started_at,
        updated_at=started_at,
        summary={
            "window_total_knowledge_dates": 2,
            "window_processed_knowledge_dates": 1,
            "inserted_context_revisions": 1,
            "inserted_fact_revisions": 4,
            "closed_context_revisions": 1,
            "closed_fact_revisions": 4,
            "deleted_future_context_revisions": 1,
            "deleted_future_fact_revisions": 4,
            "progress": {
                "total_knowledge_dates": 2,
                "processed_knowledge_dates": 1,
                "current_known_from": "2026-03-10",
                "progress_ratio": 0.5,
                "context_revisions": 2,
                "fact_revisions": 11,
            }
        },
    )
    finished = _materializacao_execucao(
        cia,
        status="success",
        campanha_id=campanha.id,
        chunk_execucao_id=chunk.id,
        started_at=started_at,
        finished_at=started_at,
        updated_at=started_at,
        coverage_complete=True,
        summary={
            "knowledge_dates": 10,
            "context_revisions": 3,
            "fact_revisions": 12,
            "progress": {
                "total_knowledge_dates": 10,
                "processed_knowledge_dates": 10,
                "current_known_from": "2025-12-31",
                "progress_ratio": 1.0,
                "context_revisions": 3,
                "fact_revisions": 12,
            },
        },
    )
    db_session.add_all([running, finished])
    db_session.commit()

    resp = client.get("/analise/materializacoes?status=running")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["resumo"]["running"] == 1
    assert payload["resumo"]["total"] == 1
    assert payload["dados"][0]["id"] == str(running.id)
    assert payload["dados"][0]["materialization_mode"] == "incremental"
    assert payload["dados"][0]["invalidated_from"] == "2026-03-10"
    assert payload["dados"][0]["campanha_id"] == str(campanha.id)
    assert payload["dados"][0]["chunk_execucao_id"] == str(chunk.id)
    assert payload["dados"][0]["queue_name"] == "analise_materializacao"
    assert payload["dados"][0]["window_total_knowledge_dates"] == 2
    assert payload["dados"][0]["inserted_fact_revisions"] == 4
    assert payload["dados"][0]["progress"]["processed_knowledge_dates"] == 1
    assert payload["dados"][0]["estimated_remaining_seconds"] is not None

    detalhe = client.get(f"/analise/materializacoes/{running.id}")
    assert detalhe.status_code == 200
    detalhe_payload = detalhe.json()
    assert detalhe_payload["id"] == str(running.id)
    assert detalhe_payload["materialization_mode"] == "incremental"
    assert detalhe_payload["campanha_id"] == str(campanha.id)
    assert detalhe_payload["chunk_execucao_id"] == str(chunk.id)
    assert detalhe_payload["summary"]["window_total_knowledge_dates"] == 2

    filtrado = client.get(f"/analise/materializacoes?campanha_id={campanha.id}")
    assert filtrado.status_code == 200
    filtrado_payload = filtrado.json()
    assert len(filtrado_payload["dados"]) == 2


def test_analise_materializacoes_monitoramento_reports_worker_snapshot(
    client: TestClient,
    db_session: Session,
    monkeypatch: MonkeyPatch,
) -> None:
    cia = _seed_analise_v2(db_session)
    campanha = _materializacao_campanha(
        status="running",
        total_items=4,
        pending_items=1,
        running_items=1,
        success_items=1,
        failed_items=1,
        summary={"counts": {"progress_ratio": 0.75}},
    )
    db_session.add(campanha)
    db_session.flush()
    running_chunk = _materializacao_chunk_execucao(
        campanha,
        status="running",
        lease_expires_at=datetime.now(UTC) + timedelta(minutes=5),
        heartbeat_at=datetime.now(UTC),
        item_count=1,
        started_at=datetime.now(UTC),
    )
    db_session.add(running_chunk)
    db_session.flush()
    db_session.add_all(
        [
            _materializacao_campanha_item(
                campanha,
                cia,
                escopo="consolidated",
                status="running",
                ordem=1,
                invalidated_from=date(2026, 3, 10),
                chunk_execucao_id=running_chunk.id,
                started_at=datetime.now(UTC),
            ),
            _materializacao_campanha_item(
                campanha,
                cia,
                escopo="individual",
                status="pending",
                ordem=2,
                invalidated_from=date(2026, 3, 10),
            ),
        ]
    )
    started_at = datetime.now(UTC)
    stale = _materializacao_execucao(
        cia,
        status="running",
        materialization_mode="incremental",
        invalidated_from=date(2026, 3, 10),
        campanha_id=campanha.id,
        chunk_execucao_id=running_chunk.id,
        started_at=started_at,
        updated_at=started_at - timedelta(minutes=10),
        summary={
            "window_total_knowledge_dates": 2,
            "window_processed_knowledge_dates": 1,
            "inserted_context_revisions": 1,
            "inserted_fact_revisions": 4,
            "progress": {"total_knowledge_dates": 2, "processed_knowledge_dates": 1, "progress_ratio": 0.5},
        },
    )
    full_running = _materializacao_execucao(
        cia,
        status="running",
        materialization_mode="full",
        campanha_id=campanha.id,
        started_at=started_at,
        updated_at=started_at,
        summary={"progress": {"total_knowledge_dates": 8, "processed_knowledge_dates": 2, "progress_ratio": 0.25}},
    )
    db_session.add_all([stale, full_running])
    campanha_bloqueada = AnaliseMaterializacaoCampanha(
            source="post_ingestion",
            status="pending",
            chunk_size=25,
            total_items=2,
            pending_items=2,
            running_items=0,
            success_items=0,
            failed_items=0,
            skipped_items=0,
            summary={"wait_reason": "INGESTION_ACTIVE"},
            updated_at=datetime.now(UTC),
        )
    db_session.add(campanha_bloqueada)
    db_session.flush()
    stale_chunk = _materializacao_chunk_execucao(
        campanha_bloqueada,
        status="stale",
        lease_expires_at=datetime.now(UTC) - timedelta(minutes=5),
        heartbeat_at=datetime.now(UTC) - timedelta(minutes=5),
        item_count=2,
        processed_items=0,
        success_items=0,
        failed_items=0,
        started_at=datetime.now(UTC) - timedelta(minutes=10),
        updated_at=datetime.now(UTC) - timedelta(minutes=5),
    )
    db_session.add(stale_chunk)
    execucao_ingestao = ExecucaoSincronizacao(
        tipo_fonte="dfp",
        ano=2025,
        arquivo="dfp.zip",
        url="http://exemplo/dfp",
        status="em_execucao",
        iniciada_em=datetime.now(UTC),
    )
    db_session.add(execucao_ingestao)
    db_session.commit()

    class FakeInspect:
        def active(self) -> dict[str, list[dict[str, str]]]:
            return {
                "worker-a": [
                    {"name": "app.worker.tasks.materializar_analise_companhia_task"},
                    {"name": "app.worker.tasks.materializar_analise_campanha_task"},
                    {"name": "app.worker.tasks.materializar_analise_chunk_task"},
                ]
            }

        def reserved(self) -> dict[str, list[dict[str, str]]]:
            return {"worker-a": [{"name": "app.worker.tasks.materializar_analise_companhia_task"}]}

        def scheduled(self) -> dict[str, list[dict[str, dict[str, str]]]]:
            return {"worker-b": [{"request": {"name": "app.worker.tasks.materializar_analise_companhia_task"}}]}

    monkeypatch.setattr(celery_app.control, "inspect", lambda timeout=1.0: FakeInspect())

    resp = client.get("/analise/materializacoes/monitoramento")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["fila"]["workers_reporting"] == 2
    assert payload["fila"]["materialization_active_tasks"] == 3
    assert payload["fila"]["materialization_reserved_tasks"] == 1
    assert payload["fila"]["materialization_scheduled_tasks"] == 1
    assert payload["fila"]["materialization_orchestrator_active_tasks"] == 1
    assert payload["fila"]["materialization_chunk_active_tasks"] == 1
    assert payload["running_executions"] == 2
    assert payload["running_full_executions"] == 1
    assert payload["running_incremental_executions"] == 1
    assert payload["lowest_running_invalidated_from"] == "2026-03-10"
    assert payload["gate"]["status"] == "red"
    assert payload["gate"]["reason_code"] == "INGESTION_ACTIVE"
    assert payload["gate"]["blocking_ingestions"] == 1
    assert payload["running_campaigns"] == 1
    assert payload["waiting_for_gate_campaigns"] == 1
    assert payload["recovering_campaigns"] == 0
    assert payload["pending_items"] == 3
    assert payload["running_items"] == 1
    assert payload["success_items"] == 1
    assert payload["failed_items"] == 1
    assert payload["queued_chunks"] == 0
    assert payload["running_chunks"] == 1
    assert payload["stale_chunks"] == 1
    assert str(stale.id) in payload["stalled_incremental_execution_ids"]
    execution_previews = {item["id"]: item for item in payload["running_execution_previews"]}
    assert execution_previews[str(stale.id)]["materialization_mode"] == "incremental"
    assert execution_previews[str(stale.id)]["invalidated_from"] == "2026-03-10"
    campaigns_by_id = {item["campanha_id"]: item for item in payload["campaigns"]}
    assert str(campanha.id) in campaigns_by_id
    assert campaigns_by_id[str(campanha.id)]["active_chunk_id"] == str(running_chunk.id)
    assert payload["running_items_preview"][0]["campanha_id"] == str(campanha.id)
    assert payload["running_items_preview"][0]["materialization_mode"] == "incremental"
    assert payload["running_items_preview"][0]["chunk_execucao_id"] == str(running_chunk.id)
    assert payload["pending_items_preview"][0]["campanha_id"] == str(campanha.id)
    assert payload["pending_items_preview"][0]["invalidated_from"] == "2026-03-10"
    assert payload["stale_chunk_preview"][0]["chunk_execucao_id"] == str(stale_chunk.id)
    assert str(stale.id) in payload["stalled_execution_ids"]


def test_analise_materializacoes_controle_pause_resume(client: TestClient, db_session: Session) -> None:
    consulta_inicial = client.get("/analise/materializacoes/controle")
    assert consulta_inicial.status_code == 200
    assert consulta_inicial.json()["gate"]["manual_control"] == "auto"

    pausa = client.post("/analise/materializacoes/controle/pause?reason=janela+de+carga")
    assert pausa.status_code == 200
    pausa_payload = pausa.json()
    assert pausa_payload["gate"]["status"] == "red"
    assert pausa_payload["gate"]["reason_code"] == "MANUAL_PAUSE"
    assert pausa_payload["gate"]["manual_control"] == "paused"
    assert pausa_payload["gate"]["manual_reason"] == "janela de carga"

    resume = client.post("/analise/materializacoes/controle/resume")
    assert resume.status_code == 200
    resume_payload = resume.json()
    assert resume_payload["gate"]["manual_control"] == "auto"
    assert resume_payload["gate"]["reason_code"] in {"NO_BLOCKERS", "INGESTION_ACTIVE"}


def test_analise_materializacoes_recuperar_stale_endpoints(client: TestClient, db_session: Session) -> None:
    cia = _seed_analise_v2(db_session)
    campanha = _materializacao_campanha(status="pending", total_items=1, pending_items=1)
    db_session.add(campanha)
    db_session.flush()
    stale_chunk = _materializacao_chunk_execucao(
        campanha,
        status="queued",
        lease_expires_at=datetime.now(UTC) - timedelta(minutes=10),
        heartbeat_at=datetime.now(UTC) - timedelta(minutes=10),
        item_count=1,
        updated_at=datetime.now(UTC) - timedelta(minutes=10),
    )
    db_session.add(stale_chunk)
    db_session.flush()
    db_session.add(
        _materializacao_campanha_item(
            campanha,
            cia,
            escopo="consolidated",
            status="running",
            ordem=1,
            chunk_execucao_id=stale_chunk.id,
            started_at=datetime.now(UTC) - timedelta(minutes=10),
        )
    )
    db_session.commit()

    resp_all = client.post("/analise/materializacoes/recuperar-stale")
    assert resp_all.status_code == 200
    payload_all = resp_all.json()
    assert payload_all["recovered_chunks"] == 1
    assert str(campanha.id) in payload_all["affected_campaigns"]
    assert str(stale_chunk.id) in payload_all["chunk_ids"]

    stale_chunk_2 = _materializacao_chunk_execucao(
        campanha,
        status="queued",
        lease_expires_at=datetime.now(UTC) - timedelta(minutes=10),
        heartbeat_at=datetime.now(UTC) - timedelta(minutes=10),
        item_count=1,
        updated_at=datetime.now(UTC) - timedelta(minutes=10),
    )
    db_session.add(stale_chunk_2)
    db_session.flush()
    db_session.add(
        _materializacao_campanha_item(
            campanha,
            cia,
            escopo="individual",
            status="running",
            ordem=2,
            chunk_execucao_id=stale_chunk_2.id,
            started_at=datetime.now(UTC) - timedelta(minutes=10),
        )
    )
    db_session.commit()

    resp_campaign = client.post(f"/analise/materializacoes/campanhas/{campanha.id}/recuperar")
    assert resp_campaign.status_code == 200
    payload_campaign = resp_campaign.json()
    assert payload_campaign["recovered_chunks"] == 1
    assert payload_campaign["affected_campaigns"] == [str(campanha.id)]


def test_analise_openapi_exposes_only_versionless_paths(client: TestClient) -> None:
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    payload = resp.json()
    paths = payload["paths"]
    components = payload["components"]["schemas"]

    for path in (
        "/analise/metricas",
        "/analise/materializacoes",
        "/analise/materializacoes/monitoramento",
        "/analise/materializacoes/controle",
        "/analise/materializacoes/controle/pause",
        "/analise/materializacoes/controle/resume",
        "/analise/materializacoes/recuperar-stale",
        "/analise/materializacoes/campanhas/{campanha_id}/recuperar",
        "/analise/materializacoes/{execucao_id}",
        "/analise/companhias/{codigo_cvm}",
        "/analise/companhias/{codigo_cvm}/series",
        "/analise/companhias/{codigo_cvm}/comparacoes",
        "/analise/companhias/{codigo_cvm}/qualidade",
        "/analise/companhias/{codigo_cvm}/sinais",
        "/analise/companhias/{codigo_cvm}/eventos",
        "/analise/companhias/{codigo_cvm}/restatements",
        "/analise/companhias/{codigo_cvm}/governanca",
        "/analise/companhias/{codigo_cvm}/pessoas",
        "/analise/companhias/{codigo_cvm}/brief",
    ):
        assert path in paths

    for removed_path in (
        "/companhias/{codigo_cvm}/analise/v2",
        "/companhias/{codigo_cvm}/analise/v2/series",
        "/companhias/{codigo_cvm}/analise/v2/comparacoes",
        "/companhias/{codigo_cvm}/analise/v2/qualidade",
        "/companhias/{codigo_cvm}/analise/v2/sinais",
        "/companhias/{codigo_cvm}/analise/v2/eventos",
        "/companhias/{codigo_cvm}/analise/v2/restatements",
        "/companhias/{codigo_cvm}/analise",
        "/companhias/{codigo_cvm}/analise/overview",
        "/companhias/{codigo_cvm}/analise/financeiro",
        "/companhias/{codigo_cvm}/analise/comparativo",
        "/companhias/{codigo_cvm}/analise/pessoas-remuneracao",
        "/companhias/{codigo_cvm}/analise/mercado-insiders",
    ):
        assert removed_path not in paths

    assert "AnaliseLegadoRemovidoResposta" not in components
    assert paths["/analise/companhias/{codigo_cvm}"]["get"]["operationId"] == "obterAnaliseManifesto"
    assert paths["/analise/companhias/{codigo_cvm}/series"]["get"]["operationId"] == "obterAnaliseSeries"
    assert paths["/analise/companhias/{codigo_cvm}/comparacoes"]["get"]["operationId"] == "obterAnaliseComparacoes"
    execucao_schema = components["AnaliseMaterializacaoExecucaoResumo"]["properties"]
    assert "materialization_mode" in execucao_schema
    assert "invalidated_from" in execucao_schema
    assert "window_total_knowledge_dates" in execucao_schema
    materializacoes_params = {
        item["name"]
        for item in paths["/analise/materializacoes"]["get"]["parameters"]
    }
    assert "campanha_id" in materializacoes_params
    monitor_schema = components["AnaliseMaterializacaoMonitoramentoResposta"]["properties"]
    assert "gate" in monitor_schema
    assert "running_full_executions" in monitor_schema
    assert "running_incremental_executions" in monitor_schema
    assert "lowest_running_invalidated_from" in monitor_schema
    assert "waiting_for_gate_campaigns" in monitor_schema
    assert "recovering_campaigns" in monitor_schema
    assert "stale_chunks" in monitor_schema
    assert "stale_chunk_preview" in monitor_schema
    assert "running_execution_previews" in monitor_schema
    assert "campaigns" in monitor_schema
    assert "running_items_preview" in monitor_schema
