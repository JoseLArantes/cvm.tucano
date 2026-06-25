import io
import zipfile
from datetime import UTC, date, datetime
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.companhia import Companhia
from app.models.financeiro import ComposicaoCapital, DemonstracaoFinanceira, DocumentoFinanceiro, ParecerFinanceiro
from app.models.sincronizacao import ExecucaoSincronizacao, HistoricoAlteracaoCampo, RegistroQuarentena
from app.services.financeiro_mapas import arquivos_demonstracao
from app.services.sincronizacao_financeiro import sincronizar_dfp, sincronizar_itr


class FakeResponse:
    def __init__(self, content: bytes) -> None:
        self.content = content

    def raise_for_status(self) -> None:
        return None


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


def _zip_financeiro(prefixo: str, ano: int, *, valor_conta: str, cnpj: str = "08.773.135/0001-00") -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr(
            f"{prefixo}_cia_aberta_{ano}.csv",
            (
                "CNPJ_CIA;DT_REFER;VERSAO;DENOM_CIA;CD_CVM;CATEG_DOC;ID_DOC;DT_RECEB;LINK_DOC\n"
                f"{cnpj};2025-12-31;1;EMPRESA A;25224;DFP;123;2026-01-01;http://exemplo\n"
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
            zip_file.writestr(
                nome_arquivo,
                (
                    "CNPJ_CIA;DT_REFER;VERSAO;DENOM_CIA;CD_CVM;GRUPO_DFP;MOEDA;ESCALA_MOEDA;ORDEM_EXERC;"
                    "DT_INI_EXERC;DT_FIM_EXERC;CD_CONTA;DS_CONTA;VL_CONTA;ST_CONTA_FIXA\n"
                    f"{cnpj};2025-12-31;1;EMPRESA A;25224;GRUPO;REAL;UNIDADE;ULTIMO;2025-01-01;2025-12-31;"
                    f"1.01;Caixa;{valor_conta};S\n"
                ).encode("latin1"),
            )
    return buffer.getvalue()


def test_sincronizacao_dfp_idempotencia_e_alteracao(db_session: Session, monkeypatch: Any) -> None:
    db_session.add(_companhia())
    db_session.commit()

    respostas = [
        FakeResponse(_zip_financeiro("dfp", 2025, valor_conta="1000.00")),
        FakeResponse(_zip_financeiro("dfp", 2025, valor_conta="1000.00")),
        FakeResponse(_zip_financeiro("dfp", 2025, valor_conta="2000.00")),
    ]

    def fake_get(*_: Any, **__: Any) -> FakeResponse:
        return respostas.pop(0)

    monkeypatch.setattr("app.services.sincronizacao_financeiro.httpx.get", fake_get)

    resultado_1 = sincronizar_dfp(db_session, 2025)
    assert resultado_1["status"] == "sucesso"
    assert resultado_1["total_inseridos"] == 19

    resultado_2 = sincronizar_dfp(db_session, 2025)
    assert resultado_2["status"] == "skipped"

    resultado_3 = sincronizar_dfp(db_session, 2025)
    assert resultado_3["status"] == "sucesso"
    assert resultado_3["total_atualizados"] >= 1

    assert db_session.query(DocumentoFinanceiro).count() == 1
    assert db_session.query(DemonstracaoFinanceira).count() == 16
    assert db_session.query(ComposicaoCapital).count() == 1
    assert db_session.query(ParecerFinanceiro).count() == 1

    historicos = (
        db_session.execute(
            select(HistoricoAlteracaoCampo).where(HistoricoAlteracaoCampo.entidade == "demonstracoes_financeiras")
        )
        .scalars()
        .all()
    )
    assert any(item.campo == "valor_conta" for item in historicos)

    execucoes = (
        db_session.execute(select(ExecucaoSincronizacao).where(ExecucaoSincronizacao.tipo_fonte == "dfp"))
        .scalars()
        .all()
    )
    assert len(execucoes) == 3


def test_sincronizacao_itr_exige_cadastro(db_session: Session, monkeypatch: Any) -> None:
    monkeypatch.setattr(
        "app.services.sincronizacao_financeiro.httpx.get",
        lambda *args, **kwargs: FakeResponse(_zip_financeiro("itr", 2025, valor_conta="1000.00")),
    )
    with pytest.raises(ValueError, match="cadastro_companhias_nao_ingestado"):
        sincronizar_itr(db_session, 2025)


def test_sincronizacao_dfp_envia_para_quarentena_quando_sem_companhia(db_session: Session, monkeypatch: Any) -> None:
    db_session.add(_companhia())
    db_session.commit()
    monkeypatch.setattr(
        "app.services.sincronizacao_financeiro.httpx.get",
        lambda *args, **kwargs: FakeResponse(
            _zip_financeiro("dfp", 2025, valor_conta="1000.00", cnpj="11.111.111/1111-11")
        ),
    )
    resultado = sincronizar_dfp(db_session, 2025)
    assert resultado["status"] == "sucesso"
    assert resultado["total_rejeitados"] == 19
    assert db_session.query(RegistroQuarentena).count() == 19
