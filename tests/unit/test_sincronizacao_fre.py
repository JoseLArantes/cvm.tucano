import io
import zipfile
from datetime import UTC, date, datetime
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.companhia import Companhia
from app.models.fre import (
    FreAuditor,
    FreCapitalSocial,
    FreDocumento,
    FreEmpregadoPosicaoGenero,
    FrePosicaoAcionaria,
    FreRemuneracaoTotalOrgao,
)
from app.models.sincronizacao import ExecucaoSincronizacao, HistoricoAlteracaoCampo, RegistroQuarentena
from app.services.sincronizacao_fre import sincronizar_fre


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


def _zip_fre(
    ano: int,
    *,
    cnpj: str = "08.773.135/0001-00",
    remuneracao_auditor: str = "1000,00",
    incluir_empregados_genero: bool = True,
) -> bytes:
    b = io.BytesIO()
    with zipfile.ZipFile(b, mode="w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr(
            f"fre_cia_aberta_{ano}.csv",
            (
                "CNPJ_CIA;DT_REFER;VERSAO;DENOM_CIA;CD_CVM;CATEG_DOC;ID_DOC;DT_RECEB;LINK_DOC\n"
                f"{cnpj};2025-12-31;1;EMPRESA A;25224;FRE;123;2026-01-01;http://doc\n"
            ).encode("latin1"),
        )
        z.writestr(
            f"fre_cia_aberta_auditor_{ano}.csv",
            (
                "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;ID_Auditor;Auditor;CPF_Auditor;"
                "CNPJ_Auditor;Codigo_CVM_Auditor;Tipo_Origem_Auditor;Data_Inicio_Contratacao;Data_Fim_Contratacao;"
                "Data_Inicio_Prestacao_Servico;Servico_Contratado;Remuneracao_Auditor;Justificativa_Substituicao;"
                "Razao_Apresentada\n"
                f"{cnpj};2025-12-31;1;123;EMPRESA A;1;AUDITOR X;12345678900;10.830.108/0001-65;100;"
                f"ORIGEM;2020-01-01;;2020-01-01;SERVICO;{remuneracao_auditor};JUSTIFICATIVA;RAZAO\n"
            ).encode("latin1"),
        )
        z.writestr(
            f"fre_cia_aberta_capital_social_{ano}.csv",
            (
                "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;ID_Capital_Social;Tipo_Capital;"
                "Data_Autorizacao_Aprovacao;Valor_Capital;Prazo_Integralizacao;Quantidade_Acoes_Ordinarias;"
                "Quantidade_Acoes_Preferenciais;Quantidade_Total_Acoes\n"
                f"{cnpj};2025-12-31;1;123;EMPRESA A;1;SUBSCRITO;2025-01-01;1000,00;12M;100;200;300\n"
            ).encode("latin1"),
        )
        z.writestr(
            f"fre_cia_aberta_posicao_acionaria_{ano}.csv",
            (
                "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;ID_Acionista;Acionista;"
                "Tipo_Pessoa_Acionista;CPF_CNPJ_Acionista;ID_Acionista_Relacionado;Acionista_Relacionado;"
                "Tipo_Pessoa_Acionista_Relacionado;CPF_CNPJ_Acionista_Relacionado;"
                "Quantidade_Acao_Ordinaria_Circulacao;Percentual_Acao_Ordinaria_Circulacao;"
                "Quantidade_Acao_Preferencial_Circulacao;Percentual_Acao_Preferencial_Circulacao;"
                "Quantidade_Total_Acoes_Circulacao;Percentual_Total_Acoes_Circulacao;Nacionalidade;Sigla_UF;"
                "Residente_Exterior;Representante_Legal;Tipo_Pessoa_Representante_Legal;"
                "CPF_CNPJ_Representante_legal;Data_Composicao_Capital_Social;Data_Ultima_Alteracao;"
                "Acionista_Controlador;Participante_Acordo_Acionistas\n"
                f"{cnpj};2025-12-31;1;123;EMPRESA A;1;ACIONISTA X;PF;12345678900;;;;;"
                "10;1,5;20;2,5;30;4,0;BRASIL;SP;N;REP X;PF;12345678901;2025-01-01;2025-12-31;S;N\n"
            ).encode("latin1"),
        )
        z.writestr(
            f"fre_cia_aberta_remuneracao_total_orgao_{ano}.csv",
            (
                "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;Data_Inicio_Exercicio_Social;"
                "Data_Fim_Exercicio_Social;Total_Remuneracao;Orgao_Administracao;Numero_Membros;"
                "Total_Remuneracao_Orgao;Numero_Membros_Remunerados;Salario;Beneficios_Diretos_Indiretos;"
                "Participacoes_Comites;Outros_Valores_Fixos;Descricao_Outros_Remuneracoes_Fixas;Bonus;"
                "Participacao_Resultados;Participacao_Reunioes;Outros_Valores_Variaveis;Comissoes;"
                "Descricao_Outros_Remuneracoes_Variaveis;Pos_emprego;Cessacao_Cargo;Baseada_Acoes;Observacao\n"
                f"{cnpj};2025-12-31;1;123;EMPRESA A;2025-01-01;2025-12-31;1000,00;Conselho;5;1000,00;5;500,00;"
                "100,00;10,00;5,00;DESC F;50,00;20,00;10,00;5,00;1,00;DESC V;0,00;0,00;0,00;OBS\n"
            ).encode("latin1"),
        )
        if incluir_empregados_genero:
            z.writestr(
                f"fre_cia_aberta_empregado_posicao_declaracao_genero_{ano}.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;Posicao;"
                    "Quantidade_Feminino;Quantidade_Masculino;Quantidade_Nao_Binario;Quantidade_Outros;"
                    "Quantidade_Sem_Resposta\n"
                    f"{cnpj};2025-12-31;1;123;EMPRESA A;Diretoria;10;20;1;0;0\n"
                ).encode("latin1"),
            )
    return b.getvalue()


def test_sincronizacao_fre_mvp(db_session: Session, monkeypatch: Any) -> None:
    db_session.add(_companhia())
    db_session.commit()
    respostas = [
        FakeResponse(_zip_fre(2025, remuneracao_auditor="1000,00")),
        FakeResponse(_zip_fre(2025, remuneracao_auditor="1000,00")),
        FakeResponse(_zip_fre(2025, remuneracao_auditor="2000,00")),
    ]

    monkeypatch.setattr("app.services.sincronizacao_fre.httpx.get", lambda *a, **k: respostas.pop(0))
    r1 = sincronizar_fre(db_session, 2025)
    assert r1["status"] == "sucesso"
    assert r1["total_inseridos"] == 6

    r2 = sincronizar_fre(db_session, 2025)
    assert r2["status"] == "skipped"

    r3 = sincronizar_fre(db_session, 2025)
    assert r3["status"] == "sucesso"
    assert r3["total_atualizados"] >= 1

    assert db_session.query(FreDocumento).count() == 1
    assert db_session.query(FreAuditor).count() == 1
    assert db_session.query(FreCapitalSocial).count() == 1
    assert db_session.query(FrePosicaoAcionaria).count() == 1
    assert db_session.query(FreRemuneracaoTotalOrgao).count() == 1
    assert db_session.query(FreEmpregadoPosicaoGenero).count() == 1

    historicos = (
        db_session.execute(select(HistoricoAlteracaoCampo).where(HistoricoAlteracaoCampo.entidade == "fre_auditores"))
        .scalars()
        .all()
    )
    assert any(h.campo == "remuneracao_auditor" for h in historicos)


def test_fre_quarentena_quando_sem_companhia(db_session: Session, monkeypatch: Any) -> None:
    db_session.add(_companhia())
    db_session.commit()
    monkeypatch.setattr(
        "app.services.sincronizacao_fre.httpx.get",
        lambda *a, **k: FakeResponse(_zip_fre(2025, cnpj="11.111.111/0001-11")),
    )
    r = sincronizar_fre(db_session, 2025)
    assert r["status"] == "sucesso"
    assert r["total_rejeitados"] == 6
    assert db_session.query(RegistroQuarentena).count() == 6


def test_fre_aceita_arquivo_empregados_genero_ausente(db_session: Session, monkeypatch: Any) -> None:
    db_session.add(_companhia())
    db_session.commit()
    monkeypatch.setattr(
        "app.services.sincronizacao_fre.httpx.get",
        lambda *a, **k: FakeResponse(_zip_fre(2021, incluir_empregados_genero=False)),
    )

    resultado = sincronizar_fre(db_session, 2021)

    assert resultado["status"] == "sucesso"
    assert resultado["total_inseridos"] == 5
    assert db_session.query(FreDocumento).count() == 1
    assert db_session.query(FreAuditor).count() == 1
    assert db_session.query(FreCapitalSocial).count() == 1
    assert db_session.query(FrePosicaoAcionaria).count() == 1
    assert db_session.query(FreRemuneracaoTotalOrgao).count() == 1
    assert db_session.query(FreEmpregadoPosicaoGenero).count() == 0


def test_fre_exige_cadastro(db_session: Session, monkeypatch: Any) -> None:
    monkeypatch.setattr("app.services.sincronizacao_fre.httpx.get", lambda *a, **k: FakeResponse(_zip_fre(2025)))
    with pytest.raises(ValueError, match="cadastro_companhias_nao_ingestado"):
        sincronizar_fre(db_session, 2025)

    execucoes = (
        db_session.execute(select(ExecucaoSincronizacao).where(ExecucaoSincronizacao.tipo_fonte == "fre"))
        .scalars()
        .all()
    )
    assert len(execucoes) == 0
