import io
import zipfile
from datetime import UTC, date, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models import financeiro, fre, identidade, ingestion, sincronizacao, usuario  # noqa: F401
from app.models.companhia import Companhia
from app.models.fre import (
    FreAcaoEntregue,
    FreAuditor,
    FreCapitalSocial,
    FreCapitalSocialClasseAcao,
    FreCapitalSocialTituloConversivel,
    FreDistribuicaoCapital,
    FreDistribuicaoCapitalClasseAcao,
    FreDocumento,
    FreEmpregadoPosicaoGenero,
    FrePosicaoAcionaria,
    FrePosicaoAcionariaClasseAcao,
    FreRemuneracaoAcao,
    FreRemuneracaoMaximaMinimaMedia,
    FreRemuneracaoTotalOrgao,
    FreRemuneracaoVariavel,
    FreResponsavel,
    FreAdministradorMembroConselhoFiscal,
    FreMembroComite,
    FreRelacaoFamiliar,
    FreRelacaoSubordinacao,
    FreTransacaoParteRelacionada,
)
from app.models.identidade import CompanhiaIdentificador
from app.models.sincronizacao import RegistroQuarentena
from app.services.ingestion.cadastro import (
    normalizar_linha_cadastro_estrangeira,
    promover_registros_cadastro,
)
from app.services.ingestion.fre import map_fre_members, normalizar_fre_row, sincronizar_fre


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
    assert len(required) == 61


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


def test_normalizar_fre_row_normalizes_sigla_uf_and_uf_sede() -> None:
    row_kind, dados_posicao = normalizar_fre_row(
        tipo="posicao_acionaria",
        arquivo_origem="fre_cia_aberta_posicao_acionaria_2025.csv",
        ano_origem=2025,
        linha_origem=2,
        linha={
            "CNPJ_Companhia": "08.773.135/0001-00",
            "Data_Referencia": "2025-12-31",
            "Versao": "1",
            "ID_Documento": "123",
            "Nome_Companhia": "EMPRESA A",
            "ID_Acionista": "1",
            "Acionista": "ACIONISTA X",
            "Tipo_Pessoa_Acionista": "PF",
            "CPF_CNPJ_Acionista": "12345678900",
            "Quantidade_Acao_Ordinaria_Circulacao": "10",
            "Percentual_Acao_Ordinaria_Circulacao": "1,5",
            "Quantidade_Acao_Preferencial_Circulacao": "20",
            "Percentual_Acao_Preferencial_Circulacao": "2,5",
            "Quantidade_Total_Acoes_Circulacao": "30",
            "Percentual_Total_Acoes_Circulacao": "4,0",
            "Nacionalidade": "BRASIL",
            "Sigla_UF": "São Paulo",
        },
    )
    row_kind_sociedade, dados_sociedade = normalizar_fre_row(
        tipo="participacao_sociedade",
        arquivo_origem="fre_cia_aberta_participacao_sociedade_2025.csv",
        ano_origem=2025,
        linha_origem=3,
        linha={
            "CNPJ_Companhia": "08.773.135/0001-00",
            "Data_Referencia": "2025-12-31",
            "Versao": "1",
            "ID_Documento": "123",
            "Nome_Companhia": "EMPRESA A",
            "ID_Sociedade": "1",
            "Razao_Social": "SOCIEDADE X",
            "Pais_Sede": "Canada",
            "UF_Sede": "EXTERIOR",
        },
    )

    assert row_kind == "fre_posicao_acionaria"
    assert dados_posicao["sigla_uf"] == "SP"
    assert row_kind_sociedade == "fre_participacao_sociedade"
    assert dados_sociedade["uf_sede"] is None


def test_sincronizar_fre_matches_v1_counts_and_optional_behavior() -> None:
    for incluir_empregados, total_inseridos, empregado_count in ((True, 6, 1), (False, 5, 0)):
        session = _session()
        try:
            companhia = _companhia()
            session.add(companhia)
            session.flush()
            _add_identifiers(session, companhia)
            session.commit()

            payload = _zip_fre(2025, incluir_empregados_genero=incluir_empregados)
            resultado = sincronizar_fre(session, 2025, downloader=lambda _, payload=payload: payload)

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


def test_sincronizar_fre_resolves_foreign_child_rows_through_header_map() -> None:
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

        payload = _zip_fre(
            2025,
            cnpj_documento="07.857.093/0001-14",
            cnpj_filho="",
            incluir_empregados_genero=True,
        )
        resultado = sincronizar_fre(session, 2025, downloader=lambda _: payload)

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


def test_sincronizar_fre_accepts_distinct_rows_that_share_old_narrow_keys() -> None:
    session = _session()
    try:
        companhia = _companhia()
        session.add(companhia)
        session.flush()
        _add_identifiers(session, companhia)
        session.commit()

        payload = io.BytesIO()
        with zipfile.ZipFile(payload, mode="w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr(
                "fre_cia_aberta_2025.csv",
                (
                    "CNPJ_CIA;DT_REFER;VERSAO;DENOM_CIA;CD_CVM;CATEG_DOC;ID_DOC;DT_RECEB;LINK_DOC\n"
                    "08.773.135/0001-00;2025-12-31;1;EMPRESA A;25224;FRE;123;2026-01-01;http://doc\n"
                ).encode("latin1"),
            )
            z.writestr(
                "fre_cia_aberta_administrador_membro_conselho_fiscal_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;Orgao_Administracao;Nome;CPF;Profissao;"
                    "Cargo_Eletivo_Ocupado;Complemento_Cargo_Eletivo_Ocupado;Data_Eleicao;Data_Posse;Data_Inicio_Primeiro_Mandato;"
                    "Prazo_Mandato;Eleito_Controlador;Outro_Cargo_Funcao;Experiencia_Profissional;Data_Nascimento;"
                    "Numero_Mandatos_Consecutivos;Percentual_Participacao_Reunioes\n"
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;Diretoria;NOME A;44041497787;Administrador;;;"
                    "2023-04-28;2023-04-30;2013-09-30;2 anos;N;;;1951-05-23;1;100\n"
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;Diretoria;NOME A;44041497787;Administrador;"
                    "Diretor Presidente;;2025-04-30;2025-04-30;2013-09-30;2 anos;N;;;1951-05-23;1;100\n"
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;Diretoria;NOME A;44041497787;Administrador;"
                    "Outros Diretores;;2025-04-30;2025-04-30;2013-09-30;2 anos;N;Diretor Financeiro;;1951-05-23;1;100\n"
                ).encode("latin1"),
            )
            z.writestr(
                "fre_cia_aberta_auditor_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;ID_Auditor;Auditor;CPF_Auditor;"
                    "CNPJ_Auditor;Codigo_CVM_Auditor;Tipo_Origem_Auditor;Data_Inicio_Contratacao;Data_Fim_Contratacao;"
                    "Data_Inicio_Prestacao_Servico;Servico_Contratado;Remuneracao_Auditor;Justificativa_Substituicao;"
                    "Razao_Apresentada\n"
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;1;AUDITOR X;12345678900;10.830.108/0001-65;100;"
                    "ORIGEM;2020-01-01;;2020-01-01;SERVICO;1000,00;JUSTIFICATIVA;RAZAO\n"
                ).encode("latin1"),
            )
            z.writestr(
                "fre_cia_aberta_capital_social_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;ID_Capital_Social;Tipo_Capital;"
                    "Data_Autorizacao_Aprovacao;Valor_Capital;Prazo_Integralizacao;Quantidade_Acoes_Ordinarias;"
                    "Quantidade_Acoes_Preferenciais;Quantidade_Total_Acoes\n"
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;1;SUBSCRITO;2025-01-01;1000,00;12M;100;200;300\n"
                ).encode("latin1"),
            )
            z.writestr(
                "fre_cia_aberta_posicao_acionaria_2025.csv",
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
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;1;ACIONISTA X;PF;12345678900;;;;;"
                    "10;1,5;20;2,5;30;4,0;BRASIL;SP;N;REP X;PF;12345678901;2025-01-01;2025-12-31;S;N\n"
                ).encode("latin1"),
            )
            z.writestr(
                "fre_cia_aberta_membro_comite_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;Nome;CPF;Profissao;Tipo_Comite;"
                    "Descricao_Outros_Comites;Cargo_Ocupado;Descricao_Outro_Cargo_Ocupado;Data_Eleicao;Data_Posse;"
                    "Data_Inicio_Primeiro_Mandato;Prazo_Mandato;Outro_Cargo_Funcao;Experiencia_Profissional;Data_Nascimento;"
                    "Numero_Mandatos_Consecutivos;Percentual_Participacao_Reunioes\n"
                    "08.773.135/0001-00;2025-12-31;10;123;EMPRESA A;DAVID FEFFER;88273962849;Administrador;Outros Comitês;"
                    "Pessoas;;;2026-04-29;2026-04-29;2019-05-01;2 anos;;;1956-11-13;1;100\n"
                    "08.773.135/0001-00;2025-12-31;10;123;EMPRESA A;DAVID FEFFER;88273962849;Administrador;Outros Comitês;"
                    "Sustentabilidade;;;2026-04-29;2026-04-29;2019-05-01;2 anos;;;1956-11-13;1;100\n"
                ).encode("latin1"),
            )
            z.writestr(
                "fre_cia_aberta_remuneracao_total_orgao_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;Data_Inicio_Exercicio_Social;"
                    "Data_Fim_Exercicio_Social;Total_Remuneracao;Orgao_Administracao;Numero_Membros;"
                    "Total_Remuneracao_Orgao;Numero_Membros_Remunerados;Salario;Beneficios_Diretos_Indiretos;"
                    "Participacoes_Comites;Outros_Valores_Fixos;Descricao_Outros_Remuneracoes_Fixas;Bonus;"
                    "Participacao_Resultados;Participacao_Reunioes;Outros_Valores_Variaveis;Comissoes;"
                    "Descricao_Outros_Remuneracoes_Variaveis;Pos_emprego;Cessacao_Cargo;Baseada_Acoes;Observacao\n"
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;2025-01-01;2025-12-31;1000,00;Conselho;5;1000,00;5;"
                    "500,00;100,00;10,00;5,00;DESC F;50,00;20,00;10,00;5,00;1,00;DESC V;0,00;0,00;0,00;OBS\n"
                ).encode("latin1"),
            )
            z.writestr(
                "fre_cia_aberta_relacao_familiar_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;Nome_Administrador;CPF_Administrador;"
                    "Nome_Emissor;CNPJ_Emissor;Cargo_Administrador;Nome_Pessoa_Relacionada;CPF_Pessoa_Relacionada;"
                    "Nome_Emissor_Pessoa_Relacionada;CNPJ_Emissor_Pessoa_Relacionada;Cargo_Pessoa_Relacionada;Tipo_Parentesco;"
                    "Observacao\n"
                    "08.773.135/0001-00;2025-12-31;9;123;EMPRESA A;JOSE A;11111111111;EMPRESA A;08773135000100;Diretor;"
                    "THEREZA A;22222222222;Companhia X;01938783000111;CONTROLADORA;Sogra ou Sogro (2º grau por afinidade);Obs 1\n"
                    "08.773.135/0001-00;2025-12-31;9;123;EMPRESA A;JOSE A;11111111111;Sociedade Agrícola Santa Tereza Ltda;13591565000132;ADMINISTRADORA;"
                    "THEREZA A;22222222222;Companhia X;01938783000111;CONTROLADORA;Sogra ou Sogro (2º grau por afinidade);Obs 2\n"
                ).encode("latin1"),
            )
            z.writestr(
                "fre_cia_aberta_relacao_subordinacao_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;Data_Inicio_Exercicio_Social;"
                    "Data_Fim_Exercicio_Social;Nome_Administrador;CPF_Administrador;Cargo_Administrador;Nome_Pessoa_Relacionada;"
                    "Tipo_Pessoa_Relacionada;Documento_Pessoa_Relacionada;Cargo_Pessoa_Relacionada;Categoria_Pessoa_Relacionada;"
                    "Tipo_Relacao;Observacao\n"
                    "08.773.135/0001-00;2025-12-31;31;123;EMPRESA A;2022-01-01;2022-12-31;DARIO A;33333333333;Diretor;"
                    "CARTAO BRB S.A.;PJ;00000208000100;;;Controle;Obs 1\n"
                    "08.773.135/0001-00;2025-12-31;31;123;EMPRESA A;2023-01-01;2023-12-31;DARIO A;33333333333;Diretor;"
                    "CARTAO BRB S.A.;PJ;00000208000100;;;Controle;Obs 2\n"
                ).encode("latin1"),
            )
            z.writestr(
                "fre_cia_aberta_transacao_parte_relacionada_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;Parte_Relacionada;Tipo_Pessoa;"
                    "Documento_Parte_Relacionada;Relacao_Emissor;Data_Transacao;Objeto_Contrato;Montante_Envolvido;"
                    "Saldo_Existente;Montante_Interesse_Parte_Relacionada;Garantia_Seguro;Duracao_Transacao;Emprestimo_Divida;"
                    "Rescisao;Natureza_Razao_Operacao;Taxa_Juros;Posicao_Contratual_Emissor;Especificacao_Posicao_Contratual_Emissor\n"
                    "08.773.135/0001-00;2025-12-31;2;123;EMPRESA A;Volkswagen do Brasil;PJ;00389481000179;Coligada;2024-12-31;"
                    "Saldo existente na conta de Clientes;1639900000;R$ 587.997 mil;100% do montante envolvido no negócio.;;;;;Saldo conta clientes;TJLP + 1,72% a.a.;Credor;\n"
                    "08.773.135/0001-00;2025-12-31;2;123;EMPRESA A;Volkswagen do Brasil;PJ;00389481000179;Coligada;2024-12-31;"
                    "Saldo existente na conta de Fornecedores;69170400000;691704000.00;691704000.00;;;;;Saldo conta fornecedores;;Devedor;\n"
                ).encode("latin1"),
            )

        resultado = sincronizar_fre(session, 2025, downloader=lambda _: payload.getvalue())

        assert resultado["status"] == "sucesso"
        assert resultado["total_rejeitados"] == 0
        assert session.query(FreAdministradorMembroConselhoFiscal).count() == 3
        assert session.query(FreMembroComite).count() == 2
        assert session.query(FreRelacaoFamiliar).count() == 2
        assert session.query(FreRelacaoSubordinacao).count() == 2
        assert session.query(FreTransacaoParteRelacionada).count() == 2
        assert session.query(RegistroQuarentena).count() == 0
    finally:
        session.close()


def test_sincronizar_fre_completo() -> None:
    session = _session()
    try:
        companhia = _companhia()
        session.add(companhia)
        session.flush()
        _add_identifiers(session, companhia)
        session.commit()

        b = io.BytesIO()
        with zipfile.ZipFile(b, mode="w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr(
                "fre_cia_aberta_2025.csv",
                (
                    "CNPJ_CIA;DT_REFER;VERSAO;DENOM_CIA;CD_CVM;CATEG_DOC;ID_DOC;DT_RECEB;LINK_DOC\n"
                    "08.773.135/0001-00;2025-12-31;1;EMPRESA A;25224;FRE;123;2026-01-01;http://doc\n"
                ).encode("latin1"),
            )
            z.writestr(
                "fre_cia_aberta_auditor_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;ID_Auditor;Auditor;CPF_Auditor;"
                    "CNPJ_Auditor;Codigo_CVM_Auditor;Tipo_Origem_Auditor;Data_Inicio_Contratacao;Data_Fim_Contratacao;"
                    "Data_Inicio_Prestacao_Servico;Servico_Contratado;Remuneracao_Auditor;Justificativa_Substituicao;"
                    "Razao_Apresentada\n"
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;1;AUDITOR X;12345678900;10.830.108/0001-65;100;"
                    "ORIGEM;2020-01-01;;2020-01-01;SERVICO;1000,00;JUSTIFICATIVA;RAZAO\n"
                ).encode("latin1"),
            )
            z.writestr(
                "fre_cia_aberta_capital_social_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;ID_Capital_Social;Tipo_Capital;"
                    "Data_Autorizacao_Aprovacao;Valor_Capital;Prazo_Integralizacao;Quantidade_Acoes_Ordinarias;"
                    "Quantidade_Acoes_Preferenciais;Quantidade_Total_Acoes\n"
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;1;SUBSCRITO;2025-01-01;1000,00;12M;100;200;300\n"
                ).encode("latin1"),
            )
            z.writestr(
                "fre_cia_aberta_posicao_acionaria_2025.csv",
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
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;1;ACIONISTA X;PF;12345678900;;;;;"
                    "10;1,5;20;2,5;30;4,0;BRASIL;SP;N;REP X;PF;12345678901;2025-01-01;2025-12-31;S;N\n"
                ).encode("latin1"),
            )
            z.writestr(
                "fre_cia_aberta_remuneracao_total_orgao_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;Data_Inicio_Exercicio_Social;"
                    "Data_Fim_Exercicio_Social;Total_Remuneracao;Orgao_Administracao;Numero_Membros;"
                    "Total_Remuneracao_Orgao;Numero_Membros_Remunerados;Salario;Beneficios_Diretos_Indiretos;"
                    "Participacoes_Comites;Outros_Valores_Fixos;Descricao_Outros_Remuneracoes_Fixas;Bonus;"
                    "Participacao_Resultados;Participacao_Reunioes;Outros_Valores_Variaveis;Comissoes;"
                    "Descricao_Outros_Remuneracoes_Variaveis;Pos_emprego;Cessacao_Cargo;Baseada_Acoes;Observacao\n"
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;2025-01-01;2025-12-31;"
                    "1000,00;Conselho;5;1000,00;5;500,00;"
                    "100,00;10,00;5,00;DESC F;50,00;20,00;10,00;5,00;1,00;DESC V;0,00;0,00;0,00;OBS\n"
                ).encode("latin1"),
            )
            z.writestr(
                "fre_cia_aberta_empregado_posicao_declaracao_genero_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;Posicao;"
                    "Quantidade_Feminino;Quantidade_Masculino;Quantidade_Nao_Binario;Quantidade_Outros;"
                    "Quantidade_Sem_Resposta\n"
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;Diretoria;10;20;1;0;0\n"
                ).encode("latin1"),
            )
            z.writestr(
                "fre_cia_aberta_responsavel_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;Nome_Responsavel;Cargo_Responsavel\n"
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;Fulano;Diretor\n"
                ).encode("latin1"),
            )
            z.writestr(
                "fre_cia_aberta_capital_social_classe_acao_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;ID_Capital_Social;"
                    "Tipo_Classe_Acao_Preferencial;Quantidade_Acoes\n"
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;1;A;50\n"
                ).encode("latin1"),
            )
            z.writestr(
                "fre_cia_aberta_capital_social_titulo_conversivel_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;ID_Capital_Social;"
                    "Titulo_Conversivel_Acao;Condicoes_Conversao\n"
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;1;Debenture;Condicoes X\n"
                ).encode("latin1"),
            )
            z.writestr(
                "fre_cia_aberta_distribuicao_capital_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;Data_Ultima_Assembleia;"
                    "Quantidade_Acoes_Ordinarias_Circulacao;Percentual_Acoes_Ordinarias_Circulacao;"
                    "Quantidade_Acoes_Preferenciais_Circulacao;Percentual_Acoes_Preferenciais_Circulacao;"
                    "Quantidade_Total_Acoes_Circulacao;Percentual_Total_Acoes_Circulacao;Quantidade_Acionistas_PF;"
                    "Quantidade_Acionistas_PJ;Quantidade_Acionistas_Investidores_Institucionais\n"
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;2025-04-30;100;10;200;20;300;30;50;5;2\n"
                ).encode("latin1"),
            )
            z.writestr(
                "fre_cia_aberta_distribuicao_capital_classe_acao_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;Classe_Acoes_Preferenciais;"
                    "Sigla_Classe_Acoes_Preferenciais;Quantidade_Acoes_Preferenciais_Circulacao;"
                    "Percentual_Acoes_Preferenciais_Circulacao\n"
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;A;PNA;10;1\n"
                ).encode("latin1"),
            )
            z.writestr(
                "fre_cia_aberta_posicao_acionaria_classe_acao_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;ID_Acionista;"
                    "Tipo_Classe_Acao_Preferencial;Quantidade_Acoes;Percentual_Acoes\n"
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;1;A;20;2\n"
                ).encode("latin1"),
            )
            z.writestr(
                "fre_cia_aberta_remuneracao_maxima_minima_media_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;Data_Inicio_Exercicio_Social;"
                    "Data_Fim_Exercicio_Social;Orgao_Administracao;Numero_Membros;Numero_Membros_Remunerados;"
                    "Valor_Maior_Remuneracao;Valor_Medio_Remuneracao;Valor_Menor_Remuneracao;Observacao\n"
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;2025-01-01;2025-12-31;Conselho;5;5;100;50;10;Obs\n"
                ).encode("latin1"),
            )
            z.writestr(
                "fre_cia_aberta_remuneracao_variavel_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;Data_Inicio_Exercicio_Social;"
                    "Data_Fim_Exercicio_Social;Orgao_Administracao;Quantidade_Total_Membros;"
                    "Quantidade_Membros_Remunerados;Bonus_Valor_Minimo;Bonus_Valor_Maximo;Bonus_Valor_Metas_Atingidas;"
                    "Bonus_Valor_Efetivo;Participacao_Valor_Minimo;Participacao_Valor_Maximo;"
                    "Participacao_Valor_Metas_Atingidas;Participacao_Valor_Efetivo\n"
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;2025-01-01;2025-12-31;"
                    "Conselho;5;5;10;50;40;45;5;20;15;18\n"
                ).encode("latin1"),
            )
            z.writestr(
                "fre_cia_aberta_remuneracao_acao_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;Data_Inicio_Exercicio_Social;"
                    "Data_Fim_Exercicio_Social;Orgao_Administracao;Quantidade_Total_Membros;"
                    "Quantidade_Membros_Remunerados;Preco_Medio_Ponderado_Opcoes_Em_Aberto;"
                    "Preco_Medio_Ponderado_Opcoes_Exercidas;Preco_Medio_Ponderado_Opcoes_Perdidas;Diluicao_Potencial\n"
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;2025-01-01;2025-12-31;Conselho;5;5;10;12;0;0,01\n"
                ).encode("latin1"),
            )
            z.writestr(
                "fre_cia_aberta_acao_entregue_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;Data_Inicio_Exercicio_Social;"
                    "Data_Fim_Exercicio_Social;Orgao_Administracao;Quantidade_Total_Membros;"
                    "Quantidade_Membros_Remunerados;Quantidade_Acoes;Preco_Medio_Ponderado_Aquisicao;"
                    "Preco_Medio_Ponderado_Mercado;Valor_Diferenca_Aquisicao_Mercado\n"
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;2025-01-01;2025-12-31;Conselho;5;5;100;10;15;5\n"
                ).encode("latin1"),
            )

        payload = b.getvalue()
        resultado = sincronizar_fre(session, 2025, downloader=lambda _: payload)

        assert resultado["status"] == "sucesso"
        assert resultado["total_inseridos"] == 16
        assert session.query(FreDocumento).count() == 1
        assert session.query(FreAuditor).count() == 1
        assert session.query(FreCapitalSocial).count() == 1
        assert session.query(FrePosicaoAcionaria).count() == 1
        assert session.query(FreRemuneracaoTotalOrgao).count() == 1
        assert session.query(FreEmpregadoPosicaoGenero).count() == 1
        assert session.query(FreResponsavel).count() == 1
        assert session.query(FreCapitalSocialClasseAcao).count() == 1
        assert session.query(FreCapitalSocialTituloConversivel).count() == 1
        assert session.query(FreDistribuicaoCapital).count() == 1
        assert session.query(FreDistribuicaoCapitalClasseAcao).count() == 1
        assert session.query(FrePosicaoAcionariaClasseAcao).count() == 1
        assert session.query(FreRemuneracaoMaximaMinimaMedia).count() == 1
        assert session.query(FreRemuneracaoVariavel).count() == 1
        assert session.query(FreRemuneracaoAcao).count() == 1
        assert session.query(FreAcaoEntregue).count() == 1
    finally:
        session.close()


def test_sincronizar_fre_idempotency() -> None:
    session = _session()
    try:
        companhia = _companhia()
        session.add(companhia)
        session.flush()
        _add_identifiers(session, companhia)
        session.commit()

        def build_zip(
            *,
            responsavel_nome_companhia: str = "EMPRESA A",
            classe_acao_qtd: int = 50,
            conversivel_cond: str = "Condicoes X",
            dist_capital_perc: float = 10,
            dist_capital_classe_qtd: int = 10,
            pos_acionaria_classe_qtd: int = 20,
            rem_max_min_media_valor: float = 50,
            rem_var_bonus: float = 45,
            rem_acao_preco: float = 10,
            acao_entregue_qtd: int = 100,
        ) -> bytes:
            b = io.BytesIO()
            with zipfile.ZipFile(b, mode="w", compression=zipfile.ZIP_DEFLATED) as z:
                z.writestr(
                    "fre_cia_aberta_2025.csv",
                    (
                        "CNPJ_CIA;DT_REFER;VERSAO;DENOM_CIA;CD_CVM;CATEG_DOC;ID_DOC;DT_RECEB;LINK_DOC\n"
                        "08.773.135/0001-00;2025-12-31;1;EMPRESA A;25224;FRE;123;2026-01-01;http://doc\n"
                    ).encode("latin1"),
                )
                z.writestr(
                    "fre_cia_aberta_auditor_2025.csv",
                    (
                        "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;ID_Auditor;Auditor;CPF_Auditor;"
                        "CNPJ_Auditor;Codigo_CVM_Auditor;Tipo_Origem_Auditor;Data_Inicio_Contratacao;Data_Fim_Contratacao;"
                        "Data_Inicio_Prestacao_Servico;Servico_Contratado;Remuneracao_Auditor;Justificativa_Substituicao;"
                        "Razao_Apresentada\n"
                        "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;1;AUDITOR X;12345678900;10.830.108/0001-65;100;"
                        "ORIGEM;2020-01-01;;2020-01-01;SERVICO;1000,00;JUSTIFICATIVA;RAZAO\n"
                    ).encode("latin1"),
                )
                z.writestr(
                    "fre_cia_aberta_capital_social_2025.csv",
                    (
                        "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;ID_Capital_Social;Tipo_Capital;"
                        "Data_Autorizacao_Aprovacao;Valor_Capital;Prazo_Integralizacao;Quantidade_Acoes_Ordinarias;"
                        "Quantidade_Acoes_Preferenciais;Quantidade_Total_Acoes\n"
                        "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;1;SUBSCRITO;2025-01-01;1000,00;12M;100;200;300\n"
                    ).encode("latin1"),
                )
                z.writestr(
                    "fre_cia_aberta_posicao_acionaria_2025.csv",
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
                        "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;1;ACIONISTA X;PF;12345678900;;;;;"
                        "10;1,5;20;2,5;30;4,0;BRASIL;SP;N;REP X;PF;12345678901;2025-01-01;2025-12-31;S;N\n"
                    ).encode("latin1"),
                )
                z.writestr(
                    "fre_cia_aberta_remuneracao_total_orgao_2025.csv",
                    (
                        "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;Data_Inicio_Exercicio_Social;"
                        "Data_Fim_Exercicio_Social;Total_Remuneracao;Orgao_Administracao;Numero_Membros;"
                        "Total_Remuneracao_Orgao;Numero_Membros_Remunerados;Salario;Beneficios_Diretos_Indiretos;"
                        "Participacoes_Comites;Outros_Valores_Fixos;Descricao_Outros_Remuneracoes_Fixas;Bonus;"
                        "Participacao_Resultados;Participacao_Reunioes;Outros_Valores_Variaveis;Comissoes;"
                        "Descricao_Outros_Remuneracoes_Variaveis;Pos_emprego;Cessacao_Cargo;Baseada_Acoes;Observacao\n"
                        "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;2025-01-01;2025-12-31;"
                        "1000,00;Conselho;5;1000,00;5;500,00;"
                        "100,00;10,00;5,00;DESC F;50,00;20,00;10,00;5,00;1,00;DESC V;0,00;0,00;0,00;OBS\n"
                    ).encode("latin1"),
                )
                z.writestr(
                    "fre_cia_aberta_empregado_posicao_declaracao_genero_2025.csv",
                    (
                        "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;Posicao;"
                        "Quantidade_Feminino;Quantidade_Masculino;Quantidade_Nao_Binario;Quantidade_Outros;"
                        "Quantidade_Sem_Resposta\n"
                        "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;Diretoria;10;20;1;0;0\n"
                    ).encode("latin1"),
                )
                z.writestr(
                    "fre_cia_aberta_responsavel_2025.csv",
                    (
                        f"CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;Nome_Responsavel;Cargo_Responsavel\n"
                        f"08.773.135/0001-00;2025-12-31;1;123;{responsavel_nome_companhia};Fulano;Diretor\n"
                    ).encode("latin1"),
                )
                z.writestr(
                    "fre_cia_aberta_capital_social_classe_acao_2025.csv",
                    (
                        f"CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;ID_Capital_Social;"
                        f"Tipo_Classe_Acao_Preferencial;Quantidade_Acoes\n"
                        f"08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;1;A;{classe_acao_qtd}\n"
                    ).encode("latin1"),
                )
                z.writestr(
                    "fre_cia_aberta_capital_social_titulo_conversivel_2025.csv",
                    (
                        f"CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;ID_Capital_Social;"
                        f"Titulo_Conversivel_Acao;Condicoes_Conversao\n"
                        f"08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;1;Debenture;{conversivel_cond}\n"
                    ).encode("latin1"),
                )
                z.writestr(
                    "fre_cia_aberta_distribuicao_capital_2025.csv",
                    (
                        f"CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;Data_Ultima_Assembleia;"
                        f"Quantidade_Acoes_Ordinarias_Circulacao;Percentual_Acoes_Ordinarias_Circulacao;"
                        f"Quantidade_Acoes_Preferenciais_Circulacao;Percentual_Acoes_Preferenciais_Circulacao;"
                        f"Quantidade_Total_Acoes_Circulacao;Percentual_Total_Acoes_Circulacao;Quantidade_Acionistas_PF;"
                        f"Quantidade_Acionistas_PJ;Quantidade_Acionistas_Investidores_Institucionais\n"
                        "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;2025-04-30;"
                        f"100;{dist_capital_perc};200;20;300;30;50;5;2\n"
                    ).encode("latin1"),
                )
                z.writestr(
                    "fre_cia_aberta_distribuicao_capital_classe_acao_2025.csv",
                    (
                        f"CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;Classe_Acoes_Preferenciais;"
                        f"Sigla_Classe_Acoes_Preferenciais;Quantidade_Acoes_Preferenciais_Circulacao;"
                        f"Percentual_Acoes_Preferenciais_Circulacao\n"
                        f"08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;A;PNA;{dist_capital_classe_qtd};1\n"
                    ).encode("latin1"),
                )
                z.writestr(
                    "fre_cia_aberta_posicao_acionaria_classe_acao_2025.csv",
                    (
                        f"CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;ID_Acionista;"
                        f"Tipo_Classe_Acao_Preferencial;Quantidade_Acoes;Percentual_Acoes\n"
                        f"08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;1;A;{pos_acionaria_classe_qtd};2\n"
                    ).encode("latin1"),
                )
                z.writestr(
                    "fre_cia_aberta_remuneracao_maxima_minima_media_2025.csv",
                    (
                        f"CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;Data_Inicio_Exercicio_Social;"
                        f"Data_Fim_Exercicio_Social;Orgao_Administracao;Numero_Membros;Numero_Membros_Remunerados;"
                        f"Valor_Maior_Remuneracao;Valor_Medio_Remuneracao;Valor_Menor_Remuneracao;Observacao\n"
                        "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;2025-01-01;2025-12-31;"
                        f"Conselho;5;5;100;{rem_max_min_media_valor};10;Obs\n"
                    ).encode("latin1"),
                )
                z.writestr(
                    "fre_cia_aberta_remuneracao_variavel_2025.csv",
                    (
                        f"CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;Data_Inicio_Exercicio_Social;"
                        f"Data_Fim_Exercicio_Social;Orgao_Administracao;Quantidade_Total_Membros;"
                        f"Quantidade_Membros_Remunerados;Bonus_Valor_Minimo;Bonus_Valor_Maximo;Bonus_Valor_Metas_Atingidas;"
                        f"Bonus_Valor_Efetivo;Participacao_Valor_Minimo;Participacao_Valor_Maximo;"
                        f"Participacao_Valor_Metas_Atingidas;Participacao_Valor_Efetivo\n"
                        f"08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;2025-01-01;2025-12-31;"
                        f"Conselho;5;5;10;50;40;{rem_var_bonus};5;20;15;18\n"
                    ).encode("latin1"),
                )
                z.writestr(
                    "fre_cia_aberta_remuneracao_acao_2025.csv",
                    (
                        f"CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;Data_Inicio_Exercicio_Social;"
                        f"Data_Fim_Exercicio_Social;Orgao_Administracao;Quantidade_Total_Membros;"
                        f"Quantidade_Membros_Remunerados;Preco_Medio_Ponderado_Opcoes_Em_Aberto;"
                        f"Preco_Medio_Ponderado_Opcoes_Exercidas;Preco_Medio_Ponderado_Opcoes_Perdidas;Diluicao_Potencial\n"
                        "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;2025-01-01;2025-12-31;"
                        f"Conselho;5;5;{rem_acao_preco};12;0;0,01\n"
                    ).encode("latin1"),
                )
                z.writestr(
                    "fre_cia_aberta_acao_entregue_2025.csv",
                    (
                        f"CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;Data_Inicio_Exercicio_Social;"
                        f"Data_Fim_Exercicio_Social;Orgao_Administracao;Quantidade_Total_Membros;"
                        f"Quantidade_Membros_Remunerados;Quantidade_Acoes;Preco_Medio_Ponderado_Aquisicao;"
                        f"Preco_Medio_Ponderado_Mercado;Valor_Diferenca_Aquisicao_Mercado\n"
                        "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;2025-01-01;2025-12-31;"
                        f"Conselho;5;5;{acao_entregue_qtd};10;15;5\n"
                    ).encode("latin1"),
                )
            return b.getvalue()

        # Ingestion 1
        p1 = build_zip()
        res1 = sincronizar_fre(session, 2025, downloader=lambda _: p1)
        assert res1["status"] == "sucesso"

        # Record timestamps
        models_to_test = [
            FreResponsavel,
            FreCapitalSocialClasseAcao,
            FreCapitalSocialTituloConversivel,
            FreDistribuicaoCapital,
            FreDistribuicaoCapitalClasseAcao,
            FrePosicaoAcionariaClasseAcao,
            FreRemuneracaoMaximaMinimaMedia,
            FreRemuneracaoVariavel,
            FreRemuneracaoAcao,
            FreAcaoEntregue,
        ]

        # Record timestamps and artificially backdate them in DB
        import datetime as dt
        import typing
        original_timestamps = {}
        inst_any: typing.Any = None
        for m in models_to_test:
            inst = session.query(m).first()
            assert inst is not None
            inst_any = inst
            original_timestamps[m] = inst_any.alterado_em
            inst_any.alterado_em = inst_any.alterado_em - dt.timedelta(seconds=10)
        session.commit()

        # Ingestion 2 (unchanged data)
        p2 = build_zip()
        res2 = sincronizar_fre(session, 2025, downloader=lambda _: p2)
        assert res2["status"] in ("sucesso", "skipped", "sem_alteracao")

        # Verify timestamps unchanged (still backdated)
        for m in models_to_test:
            inst = session.query(m).first()
            assert inst is not None
            inst_any = inst
            assert inst_any.alterado_em == original_timestamps[m] - dt.timedelta(seconds=10)

        # Ingestion 3 (changed data)
        p3 = build_zip(
            responsavel_nome_companhia="EMPRESA A MODIFIED",
            classe_acao_qtd=99,
            conversivel_cond="Condicoes Y",
            dist_capital_perc=15,
            dist_capital_classe_qtd=22,
            pos_acionaria_classe_qtd=45,
            rem_max_min_media_valor=90,
            rem_var_bonus=88,
            rem_acao_preco=15,
            acao_entregue_qtd=150,
        )
        res3 = sincronizar_fre(session, 2025, downloader=lambda _: p3)
        assert res3["status"] == "sucesso"

        # Verify alterado_em updated to a new timestamp (greater than the backdated one)
        for m in models_to_test:
            inst = session.query(m).first()
            assert inst is not None
            inst_any = inst
            assert inst_any.alterado_em > original_timestamps[m] - dt.timedelta(seconds=10)
    finally:
        session.close()


def test_sincronizar_fre_phase_1_datasets() -> None:
    session = _session()
    try:
        companhia = _companhia()
        session.add(companhia)
        session.flush()
        _add_identifiers(session, companhia)
        session.commit()

        base_zip = _zip_fre(2025, incluir_empregados_genero=True)
        b = io.BytesIO(base_zip)
        with zipfile.ZipFile(b, mode="a") as z:
            z.writestr(
                "fre_cia_aberta_administrador_membro_conselho_fiscal_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;Orgao_Administracao;Nome;CPF;"
                    "Profissao;Cargo_Eletivo_Ocupado;Complemento_Cargo_Eletivo_Ocupado;Data_Eleicao;Data_Posse;"
                    "Data_Inicio_Primeiro_Mandato;Prazo_Mandato;Eleito_Controlador;Outro_Cargo_Funcao;"
                    "Experiencia_Profissional;Data_Nascimento;Numero_Mandatos_Consecutivos;Percentual_Participacao_Reunioes\n"
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;Conselho;Conselheiro A;12345678901;Engenheiro;"
                    "Presidente;;2025-01-01;2025-01-02;2025-01-01;2 anos;N;Nenhum;Experiencia;1980-01-01;1;95.5\n"
                ).encode("latin1"),
            )
            z.writestr(
                "fre_cia_aberta_membro_comite_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;Nome;CPF;Profissao;Tipo_Comite;"
                    "Descricao_Outros_Comites;Cargo_Ocupado;Descricao_Outro_Cargo_Ocupado;Data_Eleicao;Data_Posse;"
                    "Data_Inicio_Primeiro_Mandato;Prazo_Mandato;Outro_Cargo_Funcao;Experiencia_Profissional;"
                    "Data_Nascimento;Numero_Mandatos_Consecutivos;Percentual_Participacao_Reunioes\n"
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;Membro C;12345678902;Administrador;Auditoria;"
                    ";Membro;;2025-01-01;2025-01-02;2025-01-01;1 ano;Nenhum;Experiencia;1985-01-01;2;100.0\n"
                ).encode("latin1"),
            )
            z.writestr(
                "fre_cia_aberta_relacao_familiar_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;Nome_Administrador;"
                    "CPF_Administrador;Nome_Emissor;CNPJ_Emissor;Cargo_Administrador;Nome_Pessoa_Relacionada;"
                    "CPF_Pessoa_Relacionada;Nome_Emissor_Pessoa_Relacionada;CNPJ_Emissor_Pessoa_Relacionada;"
                    "Cargo_Pessoa_Relacionada;Tipo_Parentesco;Observacao\n"
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;Admin A;12345678903;;;Diretor;Parente A;"
                    "12345678904;;;Membro;Pai;Nenhuma\n"
                ).encode("latin1"),
            )
            z.writestr(
                "fre_cia_aberta_relacao_subordinacao_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;Data_Inicio_Exercicio_Social;"
                    "Data_Fim_Exercicio_Social;Nome_Administrador;CPF_Administrador;Cargo_Administrador;"
                    "Nome_Pessoa_Relacionada;Tipo_Pessoa_Relacionada;Documento_Pessoa_Relacionada;Cargo_Pessoa_Relacionada;"
                    "Categoria_Pessoa_Relacionada;Tipo_Relacao;Observacao\n"
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;2025-01-01;2025-12-31;Admin A;12345678903;Diretor;"
                    "Subordinado A;PF;12345678905;Analista;TI;Subordinacao;Nenhuma\n"
                ).encode("latin1"),
            )
            z.writestr(
                "fre_cia_aberta_transacao_parte_relacionada_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;Parte_Relacionada;Tipo_Pessoa;"
                    "Documento_Parte_Relacionada;Relacao_Emissor;Data_Transacao;Objeto_Contrato;Montante_Envolvido;"
                    "Saldo_Existente;Montante_Interesse_Parte_Relacionada;Garantia_Seguro;Duracao_Transacao;"
                    "Emprestimo_Divida;Rescisao;Natureza_Razao_Operacao;Taxa_Juros;Posicao_Contratual_Emissor;"
                    "Especificacao_Posicao_Contratual_Emissor\n"
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;Parte A;PJ;12345678000100;Controlador;2025-06-01;"
                    "Contrato X;100000.00;R$ 587.997 mil;100% do montante envolvido no negócio.;Nenhuma;12 meses;N;N;Operacao normal;TJLP + 1,72% a.a.;Devedor;Ativo\n"
                ).encode("latin1"),
            )

        payload = b.getvalue()
        resultado = sincronizar_fre(session, 2025, downloader=lambda _: payload)

        assert resultado["status"] == "sucesso"
        assert session.query(FreDocumento).count() == 1
        assert session.query(FreAdministradorMembroConselhoFiscal).count() == 1
        assert session.query(FreMembroComite).count() == 1
        assert session.query(FreRelacaoFamiliar).count() == 1
        assert session.query(FreRelacaoSubordinacao).count() == 1
        assert session.query(FreTransacaoParteRelacionada).count() == 1
    finally:
        session.close()


def test_sincronizar_fre_phase_2_datasets() -> None:
    from app.models.fre import (
        FreCapitalSocialAumento,
        FreCapitalSocialAumentoClasseAcao,
        FreCapitalSocialDesdobramento,
        FreCapitalSocialDesdobramentoClasseAcao,
        FreCapitalSocialReducao,
        FreCapitalSocialReducaoClasseAcao,
        FreDireitoAcao,
    )
    session = _session()
    try:
        companhia = _companhia()
        session.add(companhia)
        session.flush()
        _add_identifiers(session, companhia)
        session.commit()

        base_zip = _zip_fre(2025, incluir_empregados_genero=True)
        b = io.BytesIO(base_zip)
        with zipfile.ZipFile(b, mode="a") as z:
            z.writestr(
                "fre_cia_aberta_capital_social_aumento_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;ID_Capital_Social;Data_Deliberacao;"
                    "Valor_Aumento;Origem_Aumento;Quantidade_Acoes_Ordinarias;Quantidade_Acoes_Preferenciais;Quantidade_Total_Acoes\n"
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;1;2025-06-01;100000.00;Incorporacao;50000;50000;100000\n"
                ).encode("latin1"),
            )
            z.writestr(
                "fre_cia_aberta_capital_social_aumento_classe_acao_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;ID_Capital_Social;"
                    "Tipo_Classe_Acao_Preferencial;Quantidade_Acoes\n"
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;1;Classe A;50000\n"
                ).encode("latin1"),
            )
            z.writestr(
                "fre_cia_aberta_capital_social_desdobramento_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;ID_Capital_Social;Data_Deliberacao;"
                    "Tipo_Desdobramento;Proporcao_Acoes_Novas;Proporcao_Acoes_Antigas;Quantidade_Acoes_Ordinarias;"
                    "Quantidade_Acoes_Preferenciais;Quantidade_Total_Acoes\n"
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;1;2025-06-01;Desdobramento;2;1;50000;50000;100000\n"
                ).encode("latin1"),
            )
            z.writestr(
                "fre_cia_aberta_capital_social_desdobramento_classe_acao_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;ID_Capital_Social;"
                    "Tipo_Classe_Acao_Preferencial;Quantidade_Acoes\n"
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;1;Classe A;50000\n"
                ).encode("latin1"),
            )
            z.writestr(
                "fre_cia_aberta_capital_social_reducao_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;ID_Capital_Social;Data_Deliberacao;"
                    "Valor_Reducao;Motivo_Reducao;Quantidade_Acoes_Ordinarias;Quantidade_Acoes_Preferenciais;Quantidade_Total_Acoes\n"
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;1;2025-06-01;50000.00;Perdas;25000;25000;50000\n"
                ).encode("latin1"),
            )
            z.writestr(
                "fre_cia_aberta_capital_social_reducao_classe_acao_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;ID_Capital_Social;"
                    "Tipo_Classe_Acao_Preferencial;Quantidade_Acoes\n"
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;1;Classe A;25000\n"
                ).encode("latin1"),
            )
            z.writestr(
                "fre_cia_aberta_direito_acao_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;Tipo_Classe_Acao;"
                    "Direito_Voto;Outros_Direitos\n"
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;Ordinaria;Sim;Direito de voto integral\n"
                ).encode("latin1"),
            )

        payload = b.getvalue()
        resultado = sincronizar_fre(session, 2025, downloader=lambda _: payload)

        assert resultado["status"] == "sucesso"
        assert session.query(FreCapitalSocialAumento).count() == 1
        assert session.query(FreCapitalSocialAumentoClasseAcao).count() == 1
        assert session.query(FreCapitalSocialDesdobramento).count() == 1
        assert session.query(FreCapitalSocialDesdobramentoClasseAcao).count() == 1
        assert session.query(FreCapitalSocialReducao).count() == 1
        assert session.query(FreCapitalSocialReducaoClasseAcao).count() == 1
        assert session.query(FreDireitoAcao).count() == 1
    finally:
        session.close()


def test_sincronizar_fre_phase_3_datasets() -> None:
    from app.models.fre import (
        FreVolumeValorMobiliario,
        FreOutroValorMobiliario,
        FreTitularValorMobiliario,
        FreMercadoEstrangeiro,
        FreTituloExterior,
        FrePlanoRecompra,
        FrePlanoRecompraClasseAcao,
        FreValorMobiliarioTesourariaMovimentacao,
        FreValorMobiliarioTesourariaUltimoExercicio,
        FreAdministradorDeclaracaoGenero,
    )
    session = _session()
    try:
        companhia = _companhia()
        session.add(companhia)
        session.flush()
        _add_identifiers(session, companhia)
        session.commit()

        base_zip = _zip_fre(2025, incluir_empregados_genero=True)
        b = io.BytesIO(base_zip)
        with zipfile.ZipFile(b, mode="a") as z:
            z.writestr(
                "fre_cia_aberta_volume_valor_mobiliario_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;Classe_Valor_Mobiliario;"
                    "Sigla_Classe_Acoes_Preferenciais;Volume_Negociacao\n"
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;Acao;PN;10000\n"
                ).encode("latin1"),
            )
            z.writestr(
                "fre_cia_aberta_outro_valor_mobiliario_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;Nome_Valor_Mobiliario;"
                    "Caracteristicas_Valor_Mobiliario\n"
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;Debenture;Debenture conversivel\n"
                ).encode("latin1"),
            )
            z.writestr(
                "fre_cia_aberta_titular_valor_mobiliario_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;Nome_Titular;CPF_CNPJ_Titular;"
                    "Classe_Valor_Mobiliario;Quantidade_Valores_Mobiliarios;Percentual_Classe\n"
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;Titular X;12345678900;Acao;100;10.0\n"
                ).encode("latin1"),
            )
            z.writestr(
                "fre_cia_aberta_mercado_estrangeiro_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;Nome_Mercado;Orgao_Regulador;Data_Admissao\n"
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;NYSE;SEC;2020-01-01\n"
                ).encode("latin1"),
            )
            z.writestr(
                "fre_cia_aberta_titulo_exterior_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;Nome_Titulo;Pais_Emissao;Caracteristicas\n"
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;Bond;USA;Yield 5%\n"
                ).encode("latin1"),
            )
            z.writestr(
                "fre_cia_aberta_plano_recompra_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;ID_Plano_Recompra;Data_Deliberacao;"
                    "Objetivo_Plano;Limite_Prazo_Aquisicao;Quantidade_Total_Ordinarias_Adquiridas;Quantidade_Total_Preferenciais_Adquiridas\n"
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;1;2025-01-01;Tesouraria;365 dias;100;200\n"
                ).encode("latin1"),
            )
            z.writestr(
                "fre_cia_aberta_plano_recompra_classe_acao_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;ID_Plano_Recompra;"
                    "Tipo_Classe_Acao_Preferencial;Quantidade_Acoes_Adquiridas\n"
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;1;PN A;50\n"
                ).encode("latin1"),
            )
            z.writestr(
                "fre_cia_aberta_valor_mobiliario_tesouraria_movimentacao_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;Classe_Valor_Mobiliario;"
                    "Data_Movimentacao;Quantidade_Movimentada;Natureza_Movimentacao\n"
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;Acao;2025-06-01;1000;Aquisicao\n"
                ).encode("latin1"),
            )
            z.writestr(
                "fre_cia_aberta_valor_mobiliario_tesouraria_ultimo_exercicio_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;Classe_Valor_Mobiliario;"
                    "Historico_Exercicio;Quantidade_Acoes_Tesouraria\n"
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;Acao;Saldo final;1500\n"
                ).encode("latin1"),
            )
            z.writestr(
                "fre_cia_aberta_administrador_declaracao_genero_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;Orgao_Administracao;"
                    "Quantidade_Feminino;Quantidade_Masculino;Quantidade_Nao_Binario;Quantidade_Outros;"
                    "Quantidade_Sem_Resposta;Nao_Aplicavel\n"
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;Diretoria;10;20;1;0;0;Não\n"
                ).encode("latin1"),
            )

        payload = z_bytes = b.getvalue()
        resultado = sincronizar_fre(session, 2025, downloader=lambda _: payload)

        assert resultado["status"] == "sucesso"
        assert session.query(FreVolumeValorMobiliario).count() == 1
        assert session.query(FreOutroValorMobiliario).count() == 1
        assert session.query(FreTitularValorMobiliario).count() == 1
        assert session.query(FreMercadoEstrangeiro).count() == 1
        assert session.query(FreTituloExterior).count() == 1
        assert session.query(FrePlanoRecompra).count() == 1
        assert session.query(FrePlanoRecompraClasseAcao).count() == 1
        assert session.query(FreValorMobiliarioTesourariaMovimentacao).count() == 1
        assert session.query(FreValorMobiliarioTesourariaUltimoExercicio).count() == 1
        assert session.query(FreAdministradorDeclaracaoGenero).count() == 1
    finally:
        session.close()


def test_sincronizar_fre_supports_new_employee_and_sociedade_datasets() -> None:
    from app.models.fre import (
        FreAdministradorDeclaracaoRaca,
        FreEmpregadoLocalDeclaracaoGenero,
        FreEmpregadoLocalDeclaracaoRaca,
        FreEmpregadoLocalFaixaEtaria,
        FreAdministradorPcd,
        FreEmpregadoPcd,
        FreEmpregadoPosicaoDeclaracaoRaca,
        FreEmpregadoPosicaoFaixaEtaria,
        FreEmpregadoPosicaoLocal,
        FreParticipacaoSociedade,
        FreRelacaoFamiliar,
    )

    session = _session()
    try:
        companhia = _companhia()
        session.add(companhia)
        session.flush()
        _add_identifiers(session, companhia)
        session.commit()

        base_zip = _zip_fre(2025, incluir_empregados_genero=True)
        b = io.BytesIO(base_zip)
        with zipfile.ZipFile(b, mode="a") as z:
            z.writestr(
                "fre_cia_aberta_administrador_PCD_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;Orgao_Administracao;Quantidade_PCD;Quantidade_Nao_PCD;Quantidade_Sem_Resposta;Nao_Aplicavel\n"
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;Diretoria;1;4;0;N\n"
                ).encode("latin1"),
            )
            z.writestr(
                "fre_cia_aberta_administrador_declaracao_raca_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;Orgao_Administracao;Quantidade_Amarelo;Quantidade_Branco;Quantidade_Preto;Quantidade_Pardo;Quantidade_Indigena;Quantidade_Outros;Quantidade_Sem_Resposta;Nao_Aplicavel\n"
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;Diretoria;0;1;0;0;0;0;0;N\n"
                ).encode("latin1"),
            )
            z.writestr(
                "fre_cia_aberta_relacao_familiar_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;Nome_Administrador;CPF_Administrador;"
                    "Nome_Emissor;CNPJ_Emissor;Cargo_Administrador;Nome_Pessoa_Relacionada;CPF_Pessoa_Relacionada;"
                    "Nome_Emissor_Pessoa_Relacionada;CNPJ_Emissor_Pessoa_Relacionada;Cargo_Pessoa_Relacionada;Tipo_Parentesco;Observacao\n"
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;Administrador X;12345678900;Emissor A;08.773.135/0001-00;Diretor;"
                    "Pessoa Relacionada Y;12345678901;Emissor B;08.773.135/0001-00;Conselheira;Conjuge;Obs\n"
                ).encode("latin1"),
            )
            z.writestr(
                "fre_cia_aberta_participacao_sociedade_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;ID_Sociedade;Razao_Social;CNPJ;Tipo_Sociedade;"
                    "Descricao_Atividades;Pais_Sede;UF_Sede;Municipio_Sede;Participacao_Emissor;Possui_Registro_CVM;Codigo_CVM;"
                    "Razao_Aquisicao_Manutencao;Data_Valor_Mercado;Data_Valor_Contabil;Valor_Mercado;Valor_Contabil\n"
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;10;Sociedade XPTO;11.111.111/0001-11;Controlada;"
                    "Energia solar;Brasil;SP;Sao Paulo;75,5;Sim;25224;Expansao;2025-12-31;2025-12-31;1000,00;900,00\n"
                ).encode("latin1"),
            )
            z.writestr(
                "fre_cia_aberta_empregado_posicao_local_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;Posicao;Quantidade_Norte;Quantidade_Nordeste;"
                    "Quantidade_Centro_Oeste;Quantidade_Sudeste;Quantidade_Sul;Quantidade_Exterior\n"
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;Diretoria;1;2;3;4;5;6\n"
                ).encode("latin1"),
            )
            z.writestr(
                "fre_cia_aberta_empregado_posicao_faixa_etaria_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;Posicao;Quantidade_Ate30Anos;Quantidade_30a50Anos;Quantidade_Acima50Anos\n"
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;Diretoria;7;8;9\n"
                ).encode("latin1"),
            )
            z.writestr(
                "fre_cia_aberta_empregado_posicao_declaracao_raca_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;Posicao;Quantidade_Amarelo;Quantidade_Branco;"
                    "Quantidade_Preto;Quantidade_Pardo;Quantidade_Indigena;Quantidade_Outros;Quantidade_Sem_Resposta\n"
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;Diretoria;1;2;3;4;5;6;7\n"
                ).encode("latin1"),
            )
            z.writestr(
                "fre_cia_aberta_empregado_PCD_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;Codigo_Posicao;Posicao;Quantidade_PCD;Quantidade_Nao_PCD;Quantidade_Sem_Resposta\n"
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;99;Diretoria;2;20;1\n"
                ).encode("latin1"),
            )
            z.writestr(
                "fre_cia_aberta_empregado_local_faixa_etaria_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;Local;Quantidade_Ate30Anos;Quantidade_30a50Anos;Quantidade_Acima50Anos\n"
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;Brasil;11;12;13\n"
                ).encode("latin1"),
            )
            z.writestr(
                "fre_cia_aberta_empregado_local_declaracao_raca_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;Local;Quantidade_Amarelo;Quantidade_Branco;"
                    "Quantidade_Preto;Quantidade_Pardo;Quantidade_Indigena;Quantidade_Outros;Quantidade_Sem_Resposta\n"
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;Brasil;3;4;5;6;7;8;9\n"
                ).encode("latin1"),
            )
            z.writestr(
                "fre_cia_aberta_empregado_local_declaracao_genero_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Companhia;Local;Quantidade_Feminino;Quantidade_Masculino;"
                    "Quantidade_Nao_Binario;Quantidade_Outros;Quantidade_Sem_Resposta\n"
                    "08.773.135/0001-00;2025-12-31;1;123;EMPRESA A;Brasil;14;15;1;0;2\n"
                ).encode("latin1"),
            )

        resultado = sincronizar_fre(session, 2025, downloader=lambda _: b.getvalue())

        assert resultado["status"] == "sucesso"
        assert session.query(FreRelacaoFamiliar).count() == 1
        assert session.query(FreAdministradorPcd).count() == 1
        assert session.query(FreAdministradorDeclaracaoRaca).count() == 1
        assert session.query(FreParticipacaoSociedade).count() == 1
        assert session.query(FreEmpregadoPosicaoLocal).count() == 1
        assert session.query(FreEmpregadoPosicaoFaixaEtaria).count() == 1
        assert session.query(FreEmpregadoPosicaoDeclaracaoRaca).count() == 1
        assert session.query(FreEmpregadoPcd).count() == 1
        assert session.query(FreEmpregadoLocalFaixaEtaria).count() == 1
        assert session.query(FreEmpregadoLocalDeclaracaoRaca).count() == 1
        assert session.query(FreEmpregadoLocalDeclaracaoGenero).count() == 1
    finally:
        session.close()
