import io
import zipfile
from datetime import UTC, date, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models import companhia, identidade, financeiro, fre, ingestion, sincronizacao, usuario  # noqa: F401
from app.models.companhia import Companhia
from app.models.fre import (
    FreAuditor,
    FreCapitalSocial,
    FreDocumento,
    FreEmpregadoPosicaoGenero,
    FrePosicaoAcionaria,
    FreRemuneracaoTotalOrgao,
)
from app.models.identidade import CompanhiaIdentificador
from app.models.sincronizacao import RegistroQuarentena
from app.services.ingestion.cadastro import (
    normalizar_linha_cadastro_estrangeira_v2,
    promover_registros_cadastro_v2,
)
from app.services.ingestion.fre import map_fre_members, normalizar_fre_row, sincronizar_fre_v2


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


def _zip_fre(
    ano: int,
    *,
    cnpj_documento: str = "08.773.135/0001-00",
    cnpj_filho: str = "08.773.135/0001-00",
    incluir_empregados_genero: bool = True,
) -> bytes:
    b = io.BytesIO()
    with zipfile.ZipFile(b, mode="w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr(
            f"fre_cia_aberta_{ano}.csv",
            (
                "CNPJ_CIA;DT_REFER;VERSAO;DENOM_CIA;CD_CVM;CATEG_DOC;ID_DOC;DT_RECEB;LINK_DOC\n"
                f"{cnpj_documento};2025-12-31;1;EMPRESA A;25224;FRE;123;2026-01-01;http://doc\n"
            ).encode("latin1"),
        )
        z.writestr(
            f"fre_cia_aberta_auditor_{ano}.csv",
            (
                "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;ID_Auditor;Auditor;CPF_Auditor;"
                "CNPJ_Auditor;Codigo_CVM_Auditor;Tipo_Origem_Auditor;Data_Inicio_Contratacao;Data_Fim_Contratacao;"
                "Data_Inicio_Prestacao_Servico;Servico_Contratado;Remuneracao_Auditor;Justificativa_Substituicao;"
                "Razao_Apresentada\n"
                f"{cnpj_filho};2025-12-31;1;123;EMPRESA A;1;AUDITOR X;12345678900;10.830.108/0001-65;100;"
                "ORIGEM;2020-01-01;;2020-01-01;SERVICO;1000,00;JUSTIFICATIVA;RAZAO\n"
            ).encode("latin1"),
        )
        z.writestr(
            f"fre_cia_aberta_capital_social_{ano}.csv",
            (
                "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;ID_Capital_Social;Tipo_Capital;"
                "Data_Autorizacao_Aprovacao;Valor_Capital;Prazo_Integralizacao;Quantidade_Acoes_Ordinarias;"
                "Quantidade_Acoes_Preferenciais;Quantidade_Total_Acoes\n"
                f"{cnpj_filho};2025-12-31;1;123;EMPRESA A;1;SUBSCRITO;2025-01-01;1000,00;12M;100;200;300\n"
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
                f"{cnpj_filho};2025-12-31;1;123;EMPRESA A;1;ACIONISTA X;PF;12345678900;;;;;"
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
                f"{cnpj_filho};2025-12-31;1;123;EMPRESA A;2025-01-01;2025-12-31;1000,00;Conselho;5;1000,00;5;500,00;"
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
                    f"{cnpj_filho};2025-12-31;1;123;EMPRESA A;Diretoria;10;20;1;0;0\n"
                ).encode("latin1"),
            )
    return b.getvalue()


def test_map_fre_members_preserves_optional_file() -> None:
    member_map, required, optional = map_fre_members(2025)

    assert "fre_cia_aberta_2025.csv" in member_map
    assert "fre_cia_aberta_empregado_posicao_declaracao_genero_2025.csv" in member_map
    assert "fre_cia_aberta_empregado_posicao_declaracao_genero_2025.csv" in optional
    assert len(required) == 6


def test_normalizar_fre_row_allows_child_without_cnpj_for_header_map() -> None:
    row_kind, dados = normalizar_fre_row(
        tipo="auditores",
        arquivo_origem="fre_cia_aberta_auditor_2025.csv",
        ano_origem=2025,
        linha_origem=2,
        linha={
            "CNPJ_Companhia": "",
            "Data_Referencia": "2025-12-31",
            "Versao": "1",
            "ID_Documento": "123",
            "Nome_Companhia": "EMPRESA A",
            "ID_Auditor": "1",
            "Auditor": "AUDITOR X",
            "CPF_Auditor": "12345678900",
            "CNPJ_Auditor": "10.830.108/0001-65",
            "Codigo_CVM_Auditor": "100",
            "Tipo_Origem_Auditor": "ORIGEM",
            "Data_Inicio_Contratacao": "2020-01-01",
            "Data_Fim_Contratacao": "",
            "Data_Inicio_Prestacao_Servico": "2020-01-01",
            "Servico_Contratado": "SERVICO",
            "Remuneracao_Auditor": "1000,00",
            "Justificativa_Substituicao": "JUSTIFICATIVA",
            "Razao_Apresentada": "RAZAO",
        },
    )

    assert row_kind == "fre_auditor"
    assert dados["cnpj_companhia"] is None
    assert dados["id_documento"] == 123


def test_sincronizar_fre_v2_matches_v1_counts_and_optional_behavior() -> None:
    for incluir_empregados, total_inseridos, empregado_count in ((True, 6, 1), (False, 5, 0)):
        session = _session()
        try:
            companhia = _companhia()
            session.add(companhia)
            session.flush()
            _add_identifiers(session, companhia)
            session.commit()

            payload = _zip_fre(2025, incluir_empregados_genero=incluir_empregados)
            resultado = sincronizar_fre_v2(session, 2025, downloader=lambda _: payload)

            assert resultado["status"] == "sucesso"
            assert resultado["total_inseridos"] == total_inseridos
            assert session.query(FreDocumento).count() == 1
            assert session.query(FreAuditor).count() == 1
            assert session.query(FreCapitalSocial).count() == 1
            assert session.query(FrePosicaoAcionaria).count() == 1
            assert session.query(FreRemuneracaoTotalOrgao).count() == 1
            assert session.query(FreEmpregadoPosicaoGenero).count() == empregado_count
            assert session.query(RegistroQuarentena).count() == 0
        finally:
            session.close()


def test_sincronizar_fre_v2_resolves_foreign_child_rows_through_header_map() -> None:
    session = _session()
    try:
        registro = normalizar_linha_cadastro_estrangeira_v2(
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
        promover_registros_cadastro_v2(session, [registro.data])
        session.commit()

        payload = _zip_fre(
            2025,
            cnpj_documento="07.857.093/0001-14",
            cnpj_filho="",
            incluir_empregados_genero=True,
        )
        resultado = sincronizar_fre_v2(session, 2025, downloader=lambda _: payload)

        assert resultado["status"] == "sucesso"
        assert resultado["total_rejeitados"] == 0
        assert session.query(RegistroQuarentena).count() == 0
        assert session.query(FreDocumento).count() == 1
        assert session.query(FreAuditor).count() == 1
        assert session.query(FreCapitalSocial).count() == 1
        assert session.query(FrePosicaoAcionaria).count() == 1
        assert session.query(FreRemuneracaoTotalOrgao).count() == 1
        assert session.query(FreEmpregadoPosicaoGenero).count() == 1
    finally:
        session.close()
