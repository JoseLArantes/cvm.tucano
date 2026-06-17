import io
import zipfile
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.companhia import Companhia
from app.models.fca import (
    FcaAuditor,
    FcaDepartamentoAcionistas,
    FcaDocumento,
    FcaDri,
    FcaEndereco,
    FcaGeral,
    FcaValorMobiliario,
)
from app.models.ingestion import IngestionRow, QuarantineItem
from app.services.ingestion.fca import normalizar_fca_row, sincronizar_fca


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
        hash_origem="companhia-fca",
        criado_em=agora,
        sincronizado_em=agora,
        alterado_em=agora,
    )


def _build_zip(
    *,
    endereco_email: str = "secex@bb.com.br",
    nome_empresarial: str = "BCO BRASIL S.A.",
    escriturador_email: str = "escriturador@bb.com.br",
    escriturador_cnpj_companhia: str = "00.000.000/0001-91",
    include_dri_rows: list[str] | None = None,
    include_auditor_rows: list[str] | None = None,
    include_valor_rows: list[str] | None = None,
) -> bytes:
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, "w") as z:
        z.writestr(
            "fca_cia_aberta_2025.csv",
            (
                "CNPJ_CIA;DT_REFER;VERSAO;DENOM_CIA;CD_CVM;CATEG_DOC;ID_DOC;DT_RECEB;LINK_DOC\n"
                "00.000.000/0001-91;2025-01-01;1;BCO BRASIL S.A.;001023;FCA;146477;2025-04-24;http://exemplo\n"
            ).encode("latin1"),
        )
        z.writestr(
            "fca_cia_aberta_geral_2025.csv",
            (
                "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Empresarial;Data_Nome_Empresarial;"
                "Nome_Empresarial_Anterior;Data_Constituicao;Codigo_CVM;Data_Registro_CVM;Categoria_Registro_CVM;"
                "Data_Categoria_Registro_CVM;Situacao_Registro_CVM;Data_Situacao_Registro_CVM;Pais_Origem;"
                "Pais_Custodia_Valores_Mobiliarios;Setor_Atividade;Descricao_Atividade;Situacao_Emissor;"
                "Data_Situacao_Emissor;Especie_Controle_Acionario;Data_Especie_Controle_Acionario;"
                "Dia_Encerramento_Exercicio_Social;Mes_Encerramento_Exercicio_Social;Data_Alteracao_Exercicio_Social;"
                "Pagina_Web\n"
                f"00.000.000/0001-91;2025-01-01;1;146477;{nome_empresarial};;;1808-10-12;001023;1977-07-20;"
                "Categoria A;2010-01-01;Ativo;1977-07-20;Brasil;Brasil;Bancos;Banco Múltiplo;Fase Operacional;"
                "1977-07-20;Estatal;1998-04-07;31;12;;www.bb.com.br\n"
            ).encode("latin1"),
        )
        z.writestr(
            "fca_cia_aberta_endereco_2025.csv",
            (
                "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Empresarial;Tipo_Endereco;Logradouro;"
                "Complemento;Bairro;Cidade;Sigla_UF;Pais;CEP;Caixa_Postal;DDI_Telefone;DDD_Telefone;Telefone;"
                "DDI_Fax;DDD_Fax;Fax;Email\n"
                f"00.000.000/0001-91;2025-01-01;1;146477;BCO BRASIL S.A.;Endereço da Sede;Saun Quadra 05, Lote B;"
                f"Ed. BB;Asa Norte;Brasília;DF;Brasil;70040912;;;61;34939002;;;;{endereco_email}\n"
            ).encode("latin1"),
        )
        z.writestr(
            "fca_cia_aberta_canal_divulgacao_2025.csv",
            (
                "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Empresarial;Canal_Divulgacao;Sigla_UF\n"
                "00.000.000/0001-91;2025-01-01;1;146477;BCO BRASIL S.A.;Correio Braziliense;DF\n"
            ).encode("latin1"),
        )
        z.writestr(
            "fca_cia_aberta_departamento_acionistas_2025.csv",
            (
                "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Empresarial;Contato;Data_Inicio_Contato;"
                "Data_Fim_Contato;Tipo_Endereco;Logradouro;Complemento;Bairro;Cidade;Sigla_UF;Pais;CEP;"
                "DDI_Telefone;DDD_Telefone;Telefone;DDI_Fax;DDD_Fax;Fax;Email\n"
                "00.000.000/0001-91;2025-01-01;1;146477;BCO BRASIL S.A.;Equipe RI;2025-01-01;;Departamento;"
                "Saun Quadra 05, Lote B;Ed. BB;Asa Norte;Brasília;DF;Brasil;70040912;;61;34939002;;;;ri@bb.com.br\n"
            ).encode("latin1"),
        )
        z.writestr(
            "fca_cia_aberta_escriturador_2025.csv",
            (
                "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Empresarial;Escriturador;CNPJ_Escriturador;"
                "Tipo_Endereco;Logradouro;Complemento;Bairro;Cidade;Sigla_UF;Pais;CEP;DDI_Telefone;DDD_Telefone;"
                "Telefone;DDI_Fax;DDD_Fax;Fax;Email;Data_Inicio_Atuacao;Data_Fim_Atuacao\n"
                f"{escriturador_cnpj_companhia};2025-01-01;1;146477;BCO BRASIL S.A.;ESCRITURADOR S.A.;12345678000190;"
                f"Comercial;Av. Paulista;Conj. 10;Bela Vista;Sao Paulo;SP;Brasil;01311000;;11;33334444;;;;"
                f"{escriturador_email};2024-01-01;\n"
            ).encode("latin1"),
        )
        if include_auditor_rows is not None:
            z.writestr(
                "fca_cia_aberta_auditor_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Empresarial;Auditor;CPF_CNPJ_Auditor;"
                    "Codigo_CVM_Auditor;Origem_Auditor;Data_Inicio_Atuacao_Auditor;Data_Fim_Atuacao_Auditor;"
                    "Responsavel_Tecnico;CPF_Responsavel_Tecnico;Data_Inicio_Atuacao_Responsavel_Tecnico;"
                    "Data_Fim_Atuacao_Responsavel_Tecnico\n"
                    + "".join(include_auditor_rows)
                ).encode("latin1"),
            )
        if include_valor_rows is not None:
            z.writestr(
                "fca_cia_aberta_valor_mobiliario_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Empresarial;Valor_Mobiliario;"
                    "Sigla_Classe_Acao_Preferencial;Classe_Acao_Preferencial;Codigo_Negociacao;Composicao_BDR_Unit;"
                    "Mercado;Sigla_Entidade_Administradora;Entidade_Administradora;Data_Inicio_Negociacao;"
                    "Data_Fim_Negociacao;Segmento;Data_Inicio_Listagem;Data_Fim_Listagem\n"
                    + "".join(include_valor_rows)
                ).encode("latin1"),
            )
        if include_dri_rows is not None:
            z.writestr(
                "fca_cia_aberta_dri_2025.csv",
                (
                    "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Empresarial;Tipo_Responsavel;"
                    "Responsavel;CPF_Responsavel;Tipo_Endereco;Logradouro;Complemento;Bairro;Cidade;Sigla_UF;UF;"
                    "Pais;CEP;DDI_Telefone;DDD_Telefone;Telefone;DDI_Fax;DDD_Fax;Fax;Email;Data_Inicio_Atuacao;"
                    "Data_Fim_Atuacao\n"
                    + "".join(include_dri_rows)
                ).encode("latin1"),
            )
    return mem.getvalue()


def test_sincronizar_fca_idempotency(db_session: Session) -> None:
    companhia = _companhia()
    db_session.add(companhia)
    db_session.commit()

    resultado1 = sincronizar_fca(db_session, 2025, downloader=lambda _: _build_zip())
    assert resultado1["status"] == "sucesso"
    doc = db_session.scalar(select(FcaDocumento))
    geral = db_session.scalar(select(FcaGeral))
    endereco = db_session.scalar(select(FcaEndereco))
    departamento = db_session.scalar(select(FcaDepartamentoAcionistas))
    assert doc is not None and geral is not None and endereco is not None and departamento is not None
    alterado_doc = doc.alterado_em
    alterado_geral = geral.alterado_em
    alterado_endereco = endereco.alterado_em
    alterado_departamento = departamento.alterado_em

    resultado2 = sincronizar_fca(db_session, 2025, downloader=lambda _: _build_zip())
    assert resultado2["status"] in {"sem_alteracao", "skipped", "sucesso"}
    doc_atual = db_session.scalar(select(FcaDocumento))
    geral_atual = db_session.scalar(select(FcaGeral))
    endereco_atual = db_session.scalar(select(FcaEndereco))
    departamento_atual = db_session.scalar(select(FcaDepartamentoAcionistas))
    assert doc_atual is not None and geral_atual is not None and endereco_atual is not None and departamento_atual is not None
    assert doc_atual.alterado_em == alterado_doc
    assert geral_atual.alterado_em == alterado_geral
    assert endereco_atual.alterado_em == alterado_endereco
    assert departamento_atual.alterado_em == alterado_departamento

    resultado2_forcado = sincronizar_fca(db_session, 2025, force_reimport=True, downloader=lambda _: _build_zip())
    assert resultado2_forcado["status"] == "sucesso"

    resultado3 = sincronizar_fca(
        db_session,
        2025,
        downloader=lambda _: _build_zip(
            endereco_email="novo@bb.com.br",
            nome_empresarial="BCO BRASIL ALTERADO",
        ),
    )
    assert resultado3["status"] == "sucesso"
    geral_alterado = db_session.scalar(select(FcaGeral))
    endereco_alterado = db_session.scalar(select(FcaEndereco))
    departamento_alterado = db_session.scalar(select(FcaDepartamentoAcionistas))
    assert geral_alterado is not None and endereco_alterado is not None and departamento_alterado is not None
    assert geral_alterado.alterado_em != alterado_geral
    assert endereco_alterado.alterado_em != alterado_endereco
    assert departamento_alterado.alterado_em == alterado_departamento
    staged = list(
        db_session.execute(select(IngestionRow).where(IngestionRow.row_kind == "fca_canal_divulgacao")).scalars()
    )
    assert staged == []
    staged_departamento = list(
        db_session.execute(
            select(IngestionRow).where(IngestionRow.row_kind == "fca_departamento_acionistas")
        ).scalars()
    )
    assert staged_departamento == []


def test_normalizar_fca_row_normalizes_sigla_uf() -> None:
    row_kind, dados = normalizar_fca_row(
        tipo="endereco",
        arquivo_origem="fca_cia_aberta_endereco_2025.csv",
        ano_origem=2025,
        linha_origem=2,
        linha={
            "CNPJ_Companhia": "00.000.000/0001-91",
            "Data_Referencia": "2025-01-01",
            "Versao": "1",
            "ID_Documento": "146477",
            "Nome_Empresarial": "BCO BRASIL S.A.",
            "Tipo_Endereco": "Endereço da Sede",
            "Logradouro": "Saun Quadra 05, Lote B",
            "Complemento": "Ed. BB",
            "Bairro": "Asa Norte",
            "Cidade": "Brasília",
            "Sigla_UF": "Distrito Federal",
            "Pais": "Brasil",
            "CEP": "70040912",
        },
    )

    assert row_kind == "fca_endereco"
    assert dados["sigla_uf"] == "DF"


def test_sincronizar_fca_quarentena_schema(db_session: Session) -> None:
    companhia = _companhia()
    db_session.add(companhia)
    db_session.commit()

    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as z:
        z.writestr(
            "fca_cia_aberta_2025.csv",
            "CNPJ_CIA;DT_REFER;VERSAO;DENOM_CIA;CD_CVM;CATEG_DOC;ID_DOC;DT_RECEB;LINK_DOC\n"
            "00.000.000/0001-91;2025-01-01;1;BCO BRASIL S.A.;001023;FCA;146477;2025-04-24;http://exemplo\n",
        )
        z.writestr(
            "fca_cia_aberta_geral_2025.csv",
            "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Empresarial\n"
            "00.000.000/0001-91;2025-01-01;1;146477;BCO BRASIL S.A.\n",
        )

    sincronizar_fca(db_session, 2025, downloader=lambda _: payload.getvalue())
    quarentena = list(db_session.execute(select(QuarantineItem)).scalars())
    assert quarentena == []


def test_sincronizar_fca_seed_header_map_when_document_member_is_skipped(db_session: Session) -> None:
    companhia = _companhia()
    db_session.add(companhia)
    db_session.commit()

    resultado1 = sincronizar_fca(
        db_session,
        2025,
        downloader=lambda _: _build_zip(
            escriturador_email="primeiro@bb.com.br",
            escriturador_cnpj_companhia="",
        ),
    )
    assert resultado1["status"] == "sucesso"

    resultado2 = sincronizar_fca(
        db_session,
        2025,
        downloader=lambda _: _build_zip(
            escriturador_email="segundo@bb.com.br",
            escriturador_cnpj_companhia="",
        ),
    )
    assert resultado2["status"] == "sucesso"

    quarentena = list(
        db_session.execute(select(QuarantineItem).where(QuarantineItem.row_kind == "fca_escriturador")).scalars()
    )
    assert not quarentena


def test_sincronizar_fca_dri_allows_same_cpf_with_distinct_tenure_start(db_session: Session) -> None:
    companhia = _companhia()
    db_session.add(companhia)
    db_session.commit()

    dri_rows = [
        "00.000.000/0001-91;2025-01-01;4;153455;EMPRESA;Diretor de Relações com Investidores;RESPONSAVEL;"
        "25979286837;Comercial;Rua A;Galpão 05;Centro;São Paulo;SP;SP;Brasil;01001000;;11;984772704;;;;"
        "ri1@empresa.com.br;2023-06-28;2024-02-16\n",
        "00.000.000/0001-91;2025-01-01;4;153455;EMPRESA;Diretor de Relações com Investidores;RESPONSAVEL;"
        "25979286837;Comercial;Rua A;Galpão 5;Centro;Nova Odessa;SP;SP;Brasil;01001000;;11;999276648;;;;"
        "ri2@empresa.com.br;2025-09-23;\n",
    ]

    resultado = sincronizar_fca(
        db_session,
        2025,
        downloader=lambda _: _build_zip(include_dri_rows=dri_rows),
    )
    assert resultado["status"] == "sucesso"

    dris = list(db_session.execute(select(FcaDri)).scalars())
    assert len(dris) == 2
    quarentena = list(
        db_session.execute(select(QuarantineItem).where(QuarantineItem.row_kind == "fca_dri")).scalars()
    )
    assert not quarentena


def test_sincronizar_fca_accepts_distinct_auditor_rows_for_same_auditor(db_session: Session) -> None:
    companhia = _companhia()
    db_session.add(companhia)
    db_session.commit()

    auditor_rows = [
        "00.000.000/0001-91;2025-01-01;2;151509;EMPRESA;AUDITOR X;61.562.112/0001-20;2879;Nacional;2025-01-01;;"
        "Carlos Alexandre Peres;11111111111;2025-01-01;\n",
        "00.000.000/0001-91;2025-01-01;2;151509;EMPRESA;AUDITOR X;61.562.112/0001-20;2879;Nacional;2025-01-01;;"
        "Luciano Jorge Sampaio Júnior;;2025-04-01;\n",
    ]

    resultado = sincronizar_fca(
        db_session,
        2025,
        downloader=lambda _: _build_zip(include_auditor_rows=auditor_rows),
    )

    assert resultado["status"] == "sucesso"
    assert list(db_session.execute(select(FcaAuditor)).scalars())
    assert len(list(db_session.execute(select(FcaAuditor)).scalars())) == 2
    quarentena = list(
        db_session.execute(select(QuarantineItem).where(QuarantineItem.row_kind == "fca_auditor")).scalars()
    )
    assert not quarentena


def test_sincronizar_fca_accepts_valor_mobiliario_rows_with_distinct_listing_dates(db_session: Session) -> None:
    companhia = _companhia()
    db_session.add(companhia)
    db_session.commit()

    valor_rows = [
        "00.000.000/0001-91;2025-01-01;2;146488;EMPRESA;Nota Comercial;;;;;Balcão Não-Organizado;B3;"
        "B3 S.A.;2024-01-22;;;2024-01-22;\n",
        "00.000.000/0001-91;2025-01-01;2;146488;EMPRESA;Nota Comercial;;;;;Balcão Não-Organizado;B3;"
        "B3 S.A.;2024-11-12;;;2024-11-12;\n",
    ]

    resultado = sincronizar_fca(
        db_session,
        2025,
        downloader=lambda _: _build_zip(include_valor_rows=valor_rows),
    )

    assert resultado["status"] == "sucesso"
    assert len(list(db_session.execute(select(FcaValorMobiliario)).scalars())) == 2
    quarentena = list(
        db_session.execute(select(QuarantineItem).where(QuarantineItem.row_kind == "fca_valor_mobiliario")).scalars()
    )
    assert not quarentena


def test_sincronizar_fca_creates_provisional_company_when_registry_row_is_missing(db_session: Session) -> None:
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as z:
        z.writestr(
            "fca_cia_aberta_2025.csv",
            (
                "CNPJ_CIA;DT_REFER;VERSAO;DENOM_CIA;CD_CVM;CATEG_DOC;ID_DOC;DT_RECEB;LINK_DOC\n"
                "04.986.188/0001-40;2025-01-01;1;AGROINDUSTRIAL VERA CRUZ S.A.;511404;FCA;149966;2025-07-16;http://exemplo\n"
            ).encode("latin1"),
        )
        z.writestr(
            "fca_cia_aberta_geral_2025.csv",
            (
                "CNPJ_Companhia;Data_Referencia;Versao;ID_Documento;Nome_Empresarial;Data_Nome_Empresarial;"
                "Nome_Empresarial_Anterior;Data_Constituicao;Codigo_CVM;Data_Registro_CVM;Categoria_Registro_CVM;"
                "Data_Categoria_Registro_CVM;Situacao_Registro_CVM;Data_Situacao_Registro_CVM;Pais_Origem;"
                "Pais_Custodia_Valores_Mobiliarios;Setor_Atividade;Descricao_Atividade;Situacao_Emissor;"
                "Data_Situacao_Emissor;Especie_Controle_Acionario;Data_Especie_Controle_Acionario;"
                "Dia_Encerramento_Exercicio_Social;Mes_Encerramento_Exercicio_Social;Data_Alteracao_Exercicio_Social;"
                "Pagina_Web\n"
                "04.986.188/0001-40;2025-01-01;1;149966;AGROINDUSTRIAL VERA CRUZ S.A.;;;1970-09-21;511404;1990-10-04;"
                "Categoria A;1990-10-04;Suspenso;2019-06-19;Brasil;Brasil;Agricultura;;Fase Pré-Operacional;"
                "1990-10-04;Privado;1996-11-05;31;12;2019-12-31;\n"
            ).encode("latin1"),
        )

    resultado = sincronizar_fca(db_session, 2025, downloader=lambda _: payload.getvalue())

    assert resultado["status"] == "sucesso"
    quarentena = list(
        db_session.execute(select(QuarantineItem).where(QuarantineItem.motivo_codigo == "companhia_nao_encontrada")).scalars()
    )
    assert not quarentena
