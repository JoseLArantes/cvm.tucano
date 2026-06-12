import io
import zipfile
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.companhia import Companhia
from app.models.fca import FcaDepartamentoAcionistas, FcaDocumento, FcaEndereco, FcaGeral
from app.models.ingestion import IngestionRow, QuarantineItem
from app.services.ingestion.fca import sincronizar_fca


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


def _build_zip(*, endereco_email: str = "secex@bb.com.br", nome_empresarial: str = "BCO BRASIL S.A.") -> bytes:
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
    assert resultado2["status"] == "skipped"
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
    assert staged
    assert all(item.promoted_entity is None for item in staged)
    staged_departamento = list(
        db_session.execute(
            select(IngestionRow).where(IngestionRow.row_kind == "fca_departamento_acionistas")
        ).scalars()
    )
    assert staged_departamento
    assert all(item.promoted_entity == "fca_departamentos_acionistas" for item in staged_departamento)


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
    quarentena = list(
        db_session.execute(select(QuarantineItem).where(QuarantineItem.row_kind == "fca_geral")).scalars()
    )
    assert quarentena
