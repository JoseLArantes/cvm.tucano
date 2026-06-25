import io
import zipfile
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models import financeiro, fre, identidade, ingestion, sincronizacao, usuario  # noqa: F401
from app.models.companhia import Companhia
from app.models.financeiro import ComposicaoCapital, DemonstracaoFinanceira, DocumentoFinanceiro, ParecerFinanceiro
from app.models.identidade import CompanhiaIdentificador
from app.models.ingestion import QuarantineItem
from app.models.sincronizacao import RegistroQuarentena
from app.services.financeiro_mapas import arquivos_demonstracao
from app.services.ingestion.cadastro import (
    normalizar_linha_cadastro_estrangeira,
    promover_registros_cadastro,
)
from app.services.ingestion.financeiro import (
    map_financeiro_members,
    normalizar_financeiro_row,
    sincronizar_dfp,
    sincronizar_itr,
)


def _session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    local_session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return local_session()


def _companhia() -> Companhia:
    agora = datetime.now(UTC)
    return Companhia(
        cnpj_companhia="08773135000100",
        codigo_cvm=25224,
        denominacao_social="Empresa A",
        denominacao_comercial="Empresa A",
        situacao_registro="ATIVA",
        data_registro=date(2020, 1, 1),
        data_constituicao=date(2000, 1, 1),
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
        tipo_emissor="aberta",
        fonte_identidade_principal="cad_cia_aberta",
        qualidade_identidade="alta",
        arquivo_origem="cad_cia_aberta.csv",
        ano_origem=None,
        linha_origem=2,
        hash_origem="hash",
        criado_em=agora,
        sincronizado_em=agora,
        alterado_em=agora,
    )


def _add_identifiers(session: Session, companhia: Companhia) -> None:
    session.add_all(
        [
            CompanhiaIdentificador(
                companhia_id=companhia.id,
                tipo="cnpj",
                valor="08773135000100",
                valor_normalizado="08773135000100",
                fonte="cad_cia_aberta",
                confianca="alta",
                ativo=True,
            ),
            CompanhiaIdentificador(
                companhia_id=companhia.id,
                tipo="codigo_cvm",
                valor="25224",
                valor_normalizado="25224",
                fonte="cad_cia_aberta",
                confianca="alta",
                ativo=True,
            ),
        ]
    )
    session.flush()


def _zip_financeiro(
    prefixo: str,
    ano: int,
    *,
    valor_conta: str,
    cnpj: str,
    codigo_cvm: str,
    empty_members: set[str] | None = None,
    demonstracao_member_rows: dict[str, list[str]] | None = None,
) -> bytes:
    empty_members = empty_members or set()
    demonstracao_member_rows = demonstracao_member_rows or {}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr(
            f"{prefixo}_cia_aberta_{ano}.csv",
            (
                "CNPJ_CIA;DT_REFER;VERSAO;DENOM_CIA;CD_CVM;CATEG_DOC;ID_DOC;DT_RECEB;LINK_DOC\n"
                f"{cnpj};2025-12-31;1;EMPRESA A;{codigo_cvm};DFP;123;2026-01-01;http://exemplo\n"
            ).encode("latin1"),
        )
        zip_file.writestr(
            f"{prefixo}_cia_aberta_composicao_capital_{ano}.csv",
            (
                "CNPJ_CIA;DT_REFER;VERSAO;DENOM_CIA;QT_ACAO_ORDIN_CAP_INTEGR;QT_ACAO_PREF_CAP_INTEGR;"
                "QT_ACAO_TOTAL_CAP_INTEGR;QT_ACAO_ORDIN_TESOURO;QT_ACAO_PREF_TESOURO;QT_ACAO_TOTAL_TESOURO\n"
                f"{cnpj};2025-12-31;1;EMPRESA A;100;200;300;10;20;30\n"
            ).encode("latin1"),
        )
        coluna_relatorio = "TP_RELAT_AUD" if prefixo == "dfp" else "TP_RELAT_ESP"
        zip_file.writestr(
            f"{prefixo}_cia_aberta_parecer_{ano}.csv",
            (
                f"CNPJ_CIA;DT_REFER;VERSAO;DENOM_CIA;{coluna_relatorio};TP_PARECER_DECL;"
                "NUM_ITEM_PARECER_DECL;TXT_PARECER_DECL\n"
                f"{cnpj};2025-12-31;1;EMPRESA A;SEM RESSALVA;PARECER;1;TEXTO\n"
            ).encode("latin1"),
        )
        for nome_arquivo, _, _ in arquivos_demonstracao(prefixo, ano):
            payload = (
                "CNPJ_CIA;DT_REFER;VERSAO;DENOM_CIA;CD_CVM;GRUPO_DFP;MOEDA;ESCALA_MOEDA;ORDEM_EXERC;"
                "DT_INI_EXERC;DT_FIM_EXERC;CD_CONTA;DS_CONTA;VL_CONTA;ST_CONTA_FIXA;COLUNA_DF\n"
            )
            if nome_arquivo not in empty_members:
                custom_rows = demonstracao_member_rows.get(nome_arquivo)
                if custom_rows is not None:
                    payload += "".join(custom_rows)
                else:
                    payload += (
                        f"{cnpj};2025-12-31;1;EMPRESA A;{codigo_cvm};GRUPO;REAL;UNIDADE;ULTIMO;2025-01-01;2025-12-31;"
                        f"1.01;Caixa;{valor_conta};S;\n"
                    )
            zip_file.writestr(nome_arquivo, payload.encode("latin1"))
    return buffer.getvalue()


def test_map_financeiro_members_maps_all_expected_files() -> None:
    member_map, required = map_financeiro_members("dfp", 2025)

    assert "dfp_cia_aberta_2025.csv" in member_map
    assert "dfp_cia_aberta_composicao_capital_2025.csv" in member_map
    assert "dfp_cia_aberta_parecer_2025.csv" in member_map
    assert len(required) == 19


def test_normalizar_financeiro_row_reuses_v1_mapping() -> None:
    row_kind, dados = normalizar_financeiro_row(
        prefixo="dfp",
        tipo_formulario="DFP",
        arquivo_origem="dfp_cia_aberta_2025.csv",
        ano_origem=2025,
        linha_origem=2,
        linha={
            "CNPJ_CIA": "08.773.135/0001-00",
            "DT_REFER": "2025-12-31",
            "VERSAO": "1",
            "DENOM_CIA": "EMPRESA A",
            "CD_CVM": "25224",
            "CATEG_DOC": "DFP",
            "ID_DOC": "123",
            "DT_RECEB": "2026-01-01",
            "LINK_DOC": "http://exemplo",
        },
    )

    assert row_kind == "dfp_documento"
    assert dados["cnpj_companhia"] == "08773135000100"
    assert dados["codigo_cvm"] == 25224
    assert dados["id_documento"] == 123


def test_sincronizar_itr_creates_provisional_company_when_financial_header_is_missing_from_registry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _session()
    monkeypatch.setattr("app.services.ingestion.financeiro.ensure_identity_graph_ready", lambda _db: None)
    companhia = _companhia()
    session.add(companhia)
    session.flush()
    _add_identifiers(session, companhia)
    session.commit()
    payload = _zip_financeiro(
        "itr",
        2021,
        valor_conta="1000",
        cnpj="33.066.408/0001-15",
        codigo_cvm="000003",
    )

    resultado = sincronizar_itr(session, 2021, downloader=lambda _: payload)

    assert resultado["status"] == "sucesso"
    quarentena = list(
        session.execute(select(QuarantineItem).where(QuarantineItem.motivo_codigo == "companhia_nao_encontrada")).scalars()
    )
    assert not quarentena
    companhia_provisoria = session.scalar(select(Companhia).where(Companhia.codigo_cvm == 3))
    assert companhia_provisoria is not None
    assert companhia_provisoria.tipo_emissor == "provisorio"


def test_normalizar_financeiro_row_accepts_live_dot_decimal_shape() -> None:
    row_kind, dados = normalizar_financeiro_row(
        prefixo="dfp",
        tipo_formulario="DFP",
        arquivo_origem="dfp_cia_aberta_DRE_ind_2025.csv",
        ano_origem=2025,
        linha_origem=2,
        linha={
            "CNPJ_CIA": "00.000.000/0001-91",
            "DT_REFER": "2025-12-31",
            "VERSAO": "1",
            "DENOM_CIA": "BCO BRASIL S.A.",
            "CD_CVM": "001023",
            "GRUPO_DFP": "DF Individual - Demonstração do Resultado",
            "MOEDA": "REAL",
            "ESCALA_MOEDA": "MIL",
            "ORDEM_EXERC": "ÚLTIMO",
            "DT_INI_EXERC": "2025-01-01",
            "DT_FIM_EXERC": "2025-12-31",
            "CD_CONTA": "3.01",
            "DS_CONTA": "Receitas de Intermediação Financeira",
            "VL_CONTA": "293379482.0000000000",
            "ST_CONTA_FIXA": "S",
            "COLUNA_DF": "",
        },
    )

    assert row_kind == "dfp_demonstracao"
    assert dados["valor_conta"] == Decimal("293379482.0000000000")


def test_normalizar_financeiro_row_rejeita_decimal_localizado_em_dado_estruturado() -> None:
    with pytest.raises(ValueError, match="Separador decimal invalido"):
        normalizar_financeiro_row(
            prefixo="dfp",
            tipo_formulario="DFP",
            arquivo_origem="dfp_cia_aberta_DRE_ind_2025.csv",
            ano_origem=2025,
            linha_origem=2,
            linha={
                "CNPJ_CIA": "00.000.000/0001-91",
                "DT_REFER": "2025-12-31",
                "VERSAO": "1",
                "DENOM_CIA": "BCO BRASIL S.A.",
                "CD_CVM": "001023",
                "GRUPO_DFP": "DF Individual - Demonstração do Resultado",
                "MOEDA": "REAL",
                "ESCALA_MOEDA": "MIL",
                "ORDEM_EXERC": "ÚLTIMO",
                "DT_INI_EXERC": "2025-01-01",
                "DT_FIM_EXERC": "2025-12-31",
                "CD_CONTA": "3.01",
                "DS_CONTA": "Receitas de Intermediação Financeira",
                "VL_CONTA": "1.000,00",
                "ST_CONTA_FIXA": "S",
                "COLUNA_DF": "",
            },
        )


def test_normalizar_financeiro_row_rejeita_escala_moeda_desconhecida() -> None:
    with pytest.raises(ValueError, match="escala_moeda_desconhecida"):
        normalizar_financeiro_row(
            prefixo="dfp",
            tipo_formulario="DFP",
            arquivo_origem="dfp_cia_aberta_DRE_ind_2025.csv",
            ano_origem=2025,
            linha_origem=2,
            linha={
                "CNPJ_CIA": "00.000.000/0001-91",
                "DT_REFER": "2025-12-31",
                "VERSAO": "1",
                "DENOM_CIA": "BCO BRASIL S.A.",
                "CD_CVM": "001023",
                "GRUPO_DFP": "DF Individual - Demonstração do Resultado",
                "MOEDA": "REAL",
                "ESCALA_MOEDA": "BILHAO",
                "ORDEM_EXERC": "ÚLTIMO",
                "DT_INI_EXERC": "2025-01-01",
                "DT_FIM_EXERC": "2025-12-31",
                "CD_CONTA": "3.01",
                "DS_CONTA": "Receitas de Intermediação Financeira",
                "VL_CONTA": "293379482.0000000000",
                "ST_CONTA_FIXA": "S",
                "COLUNA_DF": "",
            },
        )


def test_sincronizar_financeiro_inserts_same_counts_as_v1_for_dfp_and_itr() -> None:
    for prefixo, fn in (("dfp", sincronizar_dfp), ("itr", sincronizar_itr)):
        session = _session()
        try:
            companhia = _companhia()
            session.add(companhia)
            session.flush()
            _add_identifiers(session, companhia)
            session.commit()

            payload = _zip_financeiro(
                prefixo, 2025, valor_conta="1000.00", cnpj="08.773.135/0001-00", codigo_cvm="25224"
            )
            resultado = fn(
                session,
                2025,
                downloader=lambda _, payload=payload: payload,
            )

            assert resultado["status"] == "sucesso"
            assert resultado["total_inseridos"] == 19
            assert session.query(DocumentoFinanceiro).count() == 1
            assert session.query(DemonstracaoFinanceira).count() == 16
            assert session.query(ComposicaoCapital).count() == 1
            assert session.query(ParecerFinanceiro).count() == 1
            assert session.query(RegistroQuarentena).count() == 0
        finally:
            session.close()


def test_sincronizar_financeiro_accepts_large_valor_conta() -> None:
    session = _session()
    try:
        companhia = _companhia()
        session.add(companhia)
        session.flush()
        _add_identifiers(session, companhia)
        session.commit()

        payload = _zip_financeiro(
            "dfp",
            2025,
            valor_conta="44109150000000000.00",
            cnpj="08.773.135/0001-00",
            codigo_cvm="25224",
            demonstracao_member_rows={
                "dfp_cia_aberta_DRE_con_2025.csv": [
                    "08.773.135/0001-00;2025-12-31;1;EMPRESA A;25224;GRUPO;REAL;MIL;ULTIMO;2025-01-01;2025-12-31;"
                    "3.02;Custo dos Bens e/ou Serviços Vendidos;-44109150000000000.00;S;\n"
                ]
            },
        )

        resultado = sincronizar_dfp(session, 2025, downloader=lambda _, payload=payload: payload)

        assert resultado["status"] == "sucesso"
        demonstracao = (
            session.query(DemonstracaoFinanceira)
            .filter(DemonstracaoFinanceira.arquivo_origem == "dfp_cia_aberta_DRE_con_2025.csv")
            .one()
        )
        assert demonstracao.valor_conta == Decimal("-44109150000000000")
    finally:
        session.close()


def test_sincronizar_financeiro_preserves_live_dot_decimal_raw_value() -> None:
    session = _session()
    try:
        companhia = _companhia()
        session.add(companhia)
        session.flush()
        _add_identifiers(session, companhia)
        session.commit()

        payload = _zip_financeiro(
            "dfp",
            2025,
            valor_conta="293379482.0000000000",
            cnpj="08.773.135/0001-00",
            codigo_cvm="25224",
            demonstracao_member_rows={
                "dfp_cia_aberta_DRE_ind_2025.csv": [
                    "08.773.135/0001-00;2025-12-31;1;EMPRESA A;25224;DF Individual - Demonstração do Resultado;REAL;MIL;ÚLTIMO;2025-01-01;2025-12-31;3.01;Receitas de Intermediação Financeira;293379482.0000000000;S;\n"
                ]
            },
        )

        resultado = sincronizar_dfp(session, 2025, downloader=lambda _: payload)

        assert resultado["status"] == "sucesso"
        demonstracao = (
            session.query(DemonstracaoFinanceira)
            .filter(DemonstracaoFinanceira.arquivo_origem == "dfp_cia_aberta_DRE_ind_2025.csv")
            .one()
        )
        assert demonstracao.valor_conta == Decimal("293379482.0000000000")
        assert demonstracao.escala_moeda == "MIL"
    finally:
        session.close()


def test_sincronizar_financeiro_resolves_foreign_issuer_without_quarantine() -> None:
    for prefixo, fn in (("dfp", sincronizar_dfp), ("itr", sincronizar_itr)):
        session = _session()
        try:
            registro = normalizar_linha_cadastro_estrangeira(
                {
                    "CNPJ": "07.857.093/0001-14",
                    "DENOM_SOCIAL": "AURA MINERALS INC.",
                    "DENOM_COMERC": "AURA MINERALS INC.",
                    "PAIS_ORIGEM": "EXTERIOR",
                    "DT_REG": "2020-01-01",
                    "DT_CONST": "2000-01-01",
                    "DT_CANCEL": "",
                    "MOTIVO_CANCEL": "",
                    "SIT": "ATIVO",
                    "DT_INI_SIT": "2020-01-01",
                    "CD_CVM": "80187",
                    "SETOR_ATIV": "Mineracao",
                },
                linha_origem=2,
            )
            assert registro.data is not None
            promover_registros_cadastro(session, [registro.data])
            session.commit()

            payload = _zip_financeiro(
                prefixo,
                2025,
                valor_conta="1000.00",
                cnpj="07.857.093/0001-14",
                codigo_cvm="80187",
            )
            resultado = fn(session, 2025, downloader=lambda _, payload=payload: payload)

            assert resultado["status"] == "sucesso"
            assert resultado["total_rejeitados"] == 0
            assert session.query(RegistroQuarentena).count() == 0
            assert session.query(DocumentoFinanceiro).count() == 1
            assert session.query(DemonstracaoFinanceira).count() == 16
        finally:
            session.close()


def test_sincronizar_financeiro_idempotencia_e_alteracao() -> None:
    session = _session()
    try:
        companhia = _companhia()
        session.add(companhia)
        session.flush()
        _add_identifiers(session, companhia)
        session.commit()

        payload_1 = _zip_financeiro("dfp", 2025, valor_conta="1000.00", cnpj="08.773.135/0001-00", codigo_cvm="25224")
        resultado_1 = sincronizar_dfp(session, 2025, downloader=lambda _: payload_1)
        assert resultado_1["status"] == "sucesso"

        documento = session.query(DocumentoFinanceiro).one()
        demonstracao = session.query(DemonstracaoFinanceira).first()
        assert demonstracao is not None
        documento.alterado_em = documento.alterado_em.replace(year=documento.alterado_em.year - 1)
        demonstracao.alterado_em = demonstracao.alterado_em.replace(year=demonstracao.alterado_em.year - 1)
        documento_alterado_em = documento.alterado_em
        demonstracao_alterado_em = demonstracao.alterado_em
        session.commit()

        payload_2 = _zip_financeiro("dfp", 2025, valor_conta="1000.00", cnpj="08.773.135/0001-00", codigo_cvm="25224")
        resultado_2 = sincronizar_dfp(session, 2025, downloader=lambda _: payload_2)
        assert resultado_2["status"] == "sucesso"
        assert resultado_2["total_inalterados"] >= 19

        documento_igual = session.query(DocumentoFinanceiro).one()
        demonstracao_igual = session.query(DemonstracaoFinanceira).first()
        assert demonstracao_igual is not None
        assert documento_igual.alterado_em == documento_alterado_em
        assert demonstracao_igual.alterado_em == demonstracao_alterado_em

        payload_3 = _zip_financeiro("dfp", 2025, valor_conta="2000.00", cnpj="08.773.135/0001-00", codigo_cvm="25224")
        resultado_3 = sincronizar_dfp(session, 2025, downloader=lambda _: payload_3)
        assert resultado_3["status"] == "sucesso"
        assert resultado_3["total_atualizados"] >= 1

        demonstracao_alterada = session.query(DemonstracaoFinanceira).first()
        assert demonstracao_alterada is not None
        assert demonstracao_alterada.alterado_em > demonstracao_alterado_em
    finally:
        session.close()


def test_sincronizar_dfp_succeeds_when_dfc_md_members_have_only_header() -> None:
    session = _session()
    try:
        companhia = _companhia()
        session.add(companhia)
        session.flush()
        _add_identifiers(session, companhia)
        session.commit()

        payload = _zip_financeiro(
            "dfp",
            2026,
            valor_conta="1000.00",
            cnpj="08.773.135/0001-00",
            codigo_cvm="25224",
            empty_members={
                "dfp_cia_aberta_DFC_MD_con_2026.csv",
                "dfp_cia_aberta_DFC_MD_ind_2026.csv",
            },
        )
        resultado = sincronizar_dfp(session, 2026, downloader=lambda _: payload)

        assert resultado["status"] == "sucesso"
        assert session.query(DocumentoFinanceiro).count() == 1
        assert session.query(DemonstracaoFinanceira).count() == 14
        assert session.query(ComposicaoCapital).count() == 1
        assert session.query(ParecerFinanceiro).count() == 1
        assert session.query(RegistroQuarentena).count() == 0
    finally:
        session.close()


def test_sincronizar_dfp_does_not_run_reconcile_on_first_load(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _session()
    reconcile_calls: list[str] = []

    def _fake_reconcile(*args: Any, **kwargs: Any) -> int:
        reconcile_calls.append(kwargs["arquivo_origem"])
        return 0

    monkeypatch.setattr("app.services.ingestion.financeiro.reconcile_promoted_rows", _fake_reconcile)
    try:
        companhia = _companhia()
        session.add(companhia)
        session.flush()
        _add_identifiers(session, companhia)
        session.commit()

        payload = _zip_financeiro(
            "dfp",
            2025,
            valor_conta="1000.00",
            cnpj="08.773.135/0001-00",
            codigo_cvm="25224",
        )
        resultado = sincronizar_dfp(session, 2025, downloader=lambda _: payload)

        assert resultado["status"] == "sucesso"
        assert reconcile_calls == []
    finally:
        session.close()


def test_sincronizar_dfp_dmpl_rows_with_distinct_coluna_df_are_not_rejected() -> None:
    session = _session()
    try:
        companhia = _companhia()
        session.add(companhia)
        session.flush()
        _add_identifiers(session, companhia)
        session.commit()

        payload = _zip_financeiro(
            "dfp",
            2025,
            valor_conta="1000.00",
            cnpj="08.773.135/0001-00",
            codigo_cvm="25224",
            demonstracao_member_rows={
                "dfp_cia_aberta_DMPL_con_2025.csv": [
                    "08.773.135/0001-00;2025-12-31;1;EMPRESA A;25224;GRUPO;REAL;UNIDADE;ULTIMO;2025-01-01;2025-12-31;1.01;Caixa;1000.00;S;Reservas de Lucro\n",
                    "08.773.135/0001-00;2025-12-31;1;EMPRESA A;25224;GRUPO;REAL;UNIDADE;ULTIMO;2025-01-01;2025-12-31;1.01;Caixa;2000.00;S;Lucros ou Prejuizos Acumulados\n",
                ]
            },
        )

        resultado = sincronizar_dfp(session, 2025, downloader=lambda _: payload)

        assert resultado["status"] == "sucesso"
        assert resultado["total_rejeitados"] == 0
        assert session.query(RegistroQuarentena).count() == 0

        dmpl_rows = (
            session.query(DemonstracaoFinanceira)
            .filter(DemonstracaoFinanceira.arquivo_origem == "dfp_cia_aberta_DMPL_con_2025.csv")
            .order_by(DemonstracaoFinanceira.coluna_df.asc())
            .all()
        )
        assert len(dmpl_rows) == 2
        assert [row.coluna_df for row in dmpl_rows] == [
            "Lucros ou Prejuizos Acumulados",
            "Reservas de Lucro",
        ]
    finally:
        session.close()


def test_sincronizar_itr_dra_rows_with_distinct_data_inicio_exercicio_are_not_rejected() -> None:
    session = _session()
    try:
        companhia = _companhia()
        session.add(companhia)
        session.flush()
        _add_identifiers(session, companhia)
        session.commit()

        payload = _zip_financeiro(
            "itr",
            2025,
            valor_conta="0",
            cnpj="08.773.135/0001-00",
            codigo_cvm="25224",
            demonstracao_member_rows={
                "itr_cia_aberta_DRA_ind_2025.csv": [
                    "08.773.135/0001-00;2025-06-30;1;EMPRESA A;25224;DF Individual - Demonstração de Resultado Abrangente;REAL;UNIDADE;PENÚLTIMO;2024-01-01;2024-06-30;4.02.01.02;Conta;0;S;\n",
                    "08.773.135/0001-00;2025-06-30;1;EMPRESA A;25224;DF Individual - Demonstração de Resultado Abrangente;REAL;UNIDADE;PENÚLTIMO;2024-04-01;2024-06-30;4.02.01.02;Conta;0;S;\n",
                ]
            },
        )

        resultado = sincronizar_itr(session, 2025, downloader=lambda _: payload)

        assert resultado["status"] == "sucesso"
        assert resultado["total_rejeitados"] == 0
        assert session.query(RegistroQuarentena).count() == 0

        dra_rows = (
            session.query(DemonstracaoFinanceira)
            .filter(DemonstracaoFinanceira.arquivo_origem == "itr_cia_aberta_DRA_ind_2025.csv")
            .order_by(DemonstracaoFinanceira.data_inicio_exercicio.asc())
            .all()
        )
        assert len(dra_rows) == 2
        assert [row.data_inicio_exercicio for row in dra_rows] == [
            date(2024, 1, 1),
            date(2024, 4, 1),
        ]
    finally:
        session.close()


def test_sincronizar_itr_dmpl_prefers_non_zero_when_duplicate_key_has_zero_shadow_row() -> None:
    session = _session()
    try:
        companhia = _companhia()
        session.add(companhia)
        session.flush()
        _add_identifiers(session, companhia)
        session.commit()

        payload = _zip_financeiro(
            "itr",
            2025,
            valor_conta="0",
            cnpj="08.773.135/0001-00",
            codigo_cvm="25224",
            demonstracao_member_rows={
                "itr_cia_aberta_DMPL_ind_2025.csv": [
                    "08.773.135/0001-00;2025-03-31;1;EMPRESA A;25224;DF Individual - Demonstração das Mutações do Patrimônio Líquido;REAL;UNIDADE;ÚLTIMO;2025-01-01;2025-03-31;5.04;Transações de Capital com os Sócios;-2.0000000000;S;Reservas de Capital, Opções Outorgadas e Ações em Tesouraria\n",
                    "08.773.135/0001-00;2025-03-31;1;EMPRESA A;25224;DF Individual - Demonstração das Mutações do Patrimônio Líquido;REAL;UNIDADE;ÚLTIMO;2025-01-01;2025-03-31;5.04;Transações de Capital com os Sócios;0.0000000000;S;Reservas de Capital, Opções Outorgadas e Ações em Tesouraria\n",
                    "08.773.135/0001-00;2025-03-31;1;EMPRESA A;25224;DF Individual - Demonstração das Mutações do Patrimônio Líquido;REAL;UNIDADE;ÚLTIMO;2025-01-01;2025-03-31;5.04;Transações de Capital com os Sócios;-2.0000000000;S;Reservas de Capital, Opções Outorgadas e Ações em Tesouraria\n",
                ]
            },
        )

        resultado = sincronizar_itr(session, 2025, downloader=lambda _: payload)

        assert resultado["status"] == "sucesso"
        assert resultado["total_rejeitados"] == 0
        rows = (
            session.query(DemonstracaoFinanceira)
            .filter(DemonstracaoFinanceira.arquivo_origem == "itr_cia_aberta_DMPL_ind_2025.csv")
            .all()
        )
        assert len(rows) == 1
        assert rows[0].valor_conta == Decimal("-2.0000000000")
    finally:
        session.close()
