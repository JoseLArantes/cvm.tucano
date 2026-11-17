import uuid
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models import companhia, financeiro, fre, identidade, ingestion, sincronizacao, usuario  # noqa: F401
from app.models.companhia import Companhia
from app.models.identidade import CompanhiaIdentificador, CompanhiaMercado, CompanhiaRegistroCvm
from app.models.ingestion import SourceArtifactSnapshot, SourceMemberSnapshot
from app.models.setores import SetorClassificacaoCompanhia
from app.schemas.companhia import CompanhiaResposta
from app.services.ingestion.cadastro import (
    ARQUIVO_CADASTRO_ABERTA,
    ARQUIVO_CADASTRO_ESTRANGEIRA,
    normalizar_linha_cadastro_aberta,
    normalizar_linha_cadastro_estrangeira,
    promover_registros_cadastro,
    selecionar_registro_canonico,
    sincronizar_cadastro_companhias,
)
from app.services.ingestion.cnpj_registry import cnpj_tem_digitos_validos
from app.services.ingestion.normalizers import normalizar_cnpj_opcional, normalizar_codigo_cvm


def _session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    local_session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return local_session()


def _row_aberta(
    *,
    cnpj: str = "12.528.708/0001-07",
    codigo_cvm: str = "25283",
    tipo_mercado: str = "BOLSA",
    situacao: str = "ATIVO",
    categoria_registro: str = "Categoria A",
) -> dict[str, str]:
    return {
        "CNPJ_CIA": cnpj,
        "DENOM_SOCIAL": "EMPRESA SA",
        "DENOM_COMERC": "EMPRESA SA",
        "DT_REG": "2020-01-01",
        "DT_CONST": "2000-01-01",
        "DT_CANCEL": "",
        "MOTIVO_CANCEL": "",
        "SIT": situacao,
        "DT_INI_SIT": "2020-01-01",
        "CD_CVM": codigo_cvm,
        "SETOR_ATIV": "Energia",
        "TP_MERC": tipo_mercado,
        "CATEG_REG": categoria_registro,
        "DT_INI_CATEG": "2020-01-01",
        "SIT_EMISSOR": "FASE OPERACIONAL",
        "DT_INI_SIT_EMISSOR": "2020-01-01",
        "CONTROLE_ACIONARIO": "PRIVADO",
        "TP_ENDER": "SEDE",
        "LOGRADOURO": "Rua A",
        "COMPL": "",
        "BAIRRO": "Centro",
        "MUN": "SAO PAULO",
        "UF": "SP",
        "PAIS": "BRASIL",
        "CEP": "01001000",
        "DDD_TEL": "11",
        "TEL": "11111111",
        "DDD_FAX": "",
        "FAX": "",
        "EMAIL": "",
        "TP_RESP": "DIRETOR",
        "RESP": "Fulano",
        "DT_INI_RESP": "2020-01-01",
        "LOGRADOURO_RESP": "Rua B",
        "COMPL_RESP": "",
        "BAIRRO_RESP": "Centro",
        "MUN_RESP": "SAO PAULO",
        "UF_RESP": "SP",
        "PAIS_RESP": "BRASIL",
        "CEP_RESP": "01001000",
        "DDD_TEL_RESP": "11",
        "TEL_RESP": "11111111",
        "DDD_FAX_RESP": "",
        "FAX_RESP": "",
        "EMAIL_RESP": "",
        "CNPJ_AUDITOR": "",
        "AUDITOR": "",
    }


def _row_estrangeira(
    *,
    cnpj: str = "07.857.093/0001-14",
    codigo_cvm: str = "80187",
    denominacao: str = "AURA MINERALS INC.",
) -> dict[str, str]:
    return {
        "CNPJ": cnpj,
        "DENOM_SOCIAL": denominacao,
        "DENOM_COMERC": denominacao,
        "PAIS_ORIGEM": "EXTERIOR",
        "DT_REG": "2020-01-01",
        "DT_CONST": "2000-01-01",
        "DT_CANCEL": "",
        "MOTIVO_CANCEL": "",
        "SIT": "ATIVO",
        "DT_INI_SIT": "2020-01-01",
        "CD_CVM": codigo_cvm,
        "SETOR_ATIV": "Mineracao",
    }


_ROW_CVM_80012_SOURCE_CNPJ_MISMATCH = {
    **_row_estrangeira(
        cnpj="05.714.446/0004-00",
        codigo_cvm="80012",
        denominacao="BRAZIL FAST FOOD CORP.",
    ),
    "DENOM_COMERC": "BOB'S",
    "PAIS_ORIGEM": "BRASIL",
    "DT_REG": "2000-07-10",
    "DT_CANCEL": "2002-12-23",
    "SIT": "CANCELADA",
}


def _csv_open(rows: list[dict[str, str]]) -> bytes:
    header = list(rows[0].keys())
    lines = [";".join(header)]
    for row in rows:
        lines.append(";".join(row.get(column, "") for column in header))
    return ("\n".join(lines) + "\n").encode("latin1")


def _csv_foreign(rows: list[dict[str, str]]) -> bytes:
    header = list(rows[0].keys())
    lines = [";".join(header)]
    for row in rows:
        lines.append(";".join(row.get(column, "") for column in header))
    return ("\n".join(lines) + "\n").encode("latin1")


def test_normalizar_linha_cadastro_aberta_valid() -> None:
    result = normalizar_linha_cadastro_aberta(_row_aberta(), linha_origem=2)

    assert result.status == "valid"
    assert result.data is not None
    assert result.data["arquivo_origem"] == ARQUIVO_CADASTRO_ABERTA
    assert result.data["cnpj_companhia"] == "12528708000107"
    assert result.data["codigo_cvm"] == 25283
    assert result.data["tipo_mercado"] == "BOLSA"


def test_normalizers_handle_blank_invalid_cnpj_and_zero_padded_codigo() -> None:
    assert normalizar_cnpj_opcional("") is None
    assert normalizar_codigo_cvm("000123") == 123

    try:
        normalizar_cnpj_opcional("11.111.111/1111-1")
    except ValueError as exc:
        assert str(exc).startswith("CNPJ invalido")
    else:
        raise AssertionError("Esperava ValueError para CNPJ invalido")


def test_normalizar_linha_cadastro_estrangeira_valid() -> None:
    result = normalizar_linha_cadastro_estrangeira(_row_estrangeira(), linha_origem=2)

    assert result.status == "valid"
    assert result.data is not None
    assert result.data["arquivo_origem"] == ARQUIVO_CADASTRO_ESTRANGEIRA
    assert result.data["cnpj_companhia"] == "07857093000114"
    assert result.data["codigo_cvm"] == 80187
    assert result.data["pais_origem"] == "EXTERIOR"


def test_registry_cnpj_check_digits_and_evidence_scoped_correction() -> None:
    assert cnpj_tem_digitos_validos("05714446000100")
    assert not cnpj_tem_digitos_validos("05714446000400")
    assert not cnpj_tem_digitos_validos("11111111111111")

    resultado = normalizar_linha_cadastro_estrangeira(
        _ROW_CVM_80012_SOURCE_CNPJ_MISMATCH,
        linha_origem=11,
    )

    assert resultado.status == "valid"
    assert resultado.data is not None
    assert resultado.data["cnpj_companhia"] == "05714446000100"
    assert resultado.data["cnpj_companhia_origem"] == "05714446000400"
    diagnostico = (resultado.details or {})["diagnostico_cnpj"]
    assert diagnostico["correcao_aplicada"] is True
    assert diagnostico["regra"] == "cvm-80012-brazil-fast-food-cnpj-carf"

    sem_evidencia = normalizar_linha_cadastro_estrangeira(
        _row_estrangeira(
            cnpj="05.714.446/0004-00",
            codigo_cvm="80013",
            denominacao="OTHER COMPANY",
        ),
        linha_origem=12,
    )
    assert sem_evidencia.status == "valid"
    assert sem_evidencia.data is not None
    assert sem_evidencia.data["cnpj_companhia"] is None
    assert sem_evidencia.data["cnpj_companhia_origem"] == "05714446000400"
    assert (sem_evidencia.details or {})["diagnostico_cnpj"]["correcao_aplicada"] is False


def test_selecionar_registro_canonico_prefere_ativo() -> None:
    cancelado = normalizar_linha_cadastro_aberta(
        _row_aberta(codigo_cvm="1716", tipo_mercado="", situacao="CANCELADA"), linha_origem=2
    ).data
    ativo = normalizar_linha_cadastro_aberta(
        _row_aberta(codigo_cvm="24600", tipo_mercado="BOLSA", situacao="ATIVO"), linha_origem=3
    ).data

    assert cancelado is not None
    assert ativo is not None
    escolhido = selecionar_registro_canonico([cancelado, ativo])
    assert escolhido["codigo_cvm"] == 24600


def test_promover_registros_cadastro_merge_tipo_mercado_and_multi_code() -> None:
    session = _session()
    try:
        mercado_bolsa = normalizar_linha_cadastro_aberta(_row_aberta(tipo_mercado="BOLSA"), linha_origem=2).data
        mercado_balcao = normalizar_linha_cadastro_aberta(
            _row_aberta(tipo_mercado="BALCAO ORGANIZADO"), linha_origem=3
        ).data
        outro_codigo = normalizar_linha_cadastro_aberta(
            _row_aberta(codigo_cvm="24600", tipo_mercado="BOLSA"), linha_origem=4
        ).data

        assert mercado_bolsa is not None
        assert mercado_balcao is not None
        assert outro_codigo is not None

        contadores = promover_registros_cadastro(session, [mercado_bolsa, mercado_balcao, outro_codigo])
        session.commit()

        assert contadores["companhias"] == 1
        assert contadores["inseridos"] == 3
        assert contadores["atualizados"] == 0
        assert contadores["inalterados"] == 0
        assert session.query(Companhia).count() == 1
        assert session.query(CompanhiaRegistroCvm).count() == 2
        assert session.query(CompanhiaMercado).count() == 3
        assert session.query(CompanhiaIdentificador).count() == 3

        repeticao = promover_registros_cadastro(session, [mercado_bolsa, mercado_balcao, outro_codigo])
        session.commit()

        assert repeticao["inseridos"] == 0
        assert repeticao["atualizados"] == 0
        assert repeticao["inalterados"] == 3
        assert session.query(CompanhiaRegistroCvm).count() == 2
        assert session.query(CompanhiaMercado).count() == 3
    finally:
        session.close()


def test_promover_registros_cadastro_classifies_business_change_as_updated() -> None:
    session = _session()
    try:
        original = normalizar_linha_cadastro_aberta(_row_aberta(), linha_origem=2).data
        alterado = normalizar_linha_cadastro_aberta(
            _row_aberta(categoria_registro="Categoria B"),
            linha_origem=2,
        ).data
        assert original is not None
        assert alterado is not None

        primeira = promover_registros_cadastro(session, [original])
        session.commit()
        segunda = promover_registros_cadastro(session, [alterado])
        session.commit()

        assert primeira["inseridos"] == 1
        assert segunda["inseridos"] == 0
        assert segunda["atualizados"] == 1
        assert segunda["inalterados"] == 0
        registro = session.query(CompanhiaRegistroCvm).one()
        assert registro.categoria_registro == "Categoria B"
    finally:
        session.close()


def test_promover_cadastro_publica_setor_e_preserva_rotulo_de_origem() -> None:
    session = _session()
    try:
        linha = _row_aberta()
        linha["SETOR_ATIV"] = "  Energia   Elétrica "
        resultado = normalizar_linha_cadastro_aberta(linha, linha_origem=42)
        assert resultado.data is not None

        contadores = promover_registros_cadastro(
            session,
            [resultado.data],
            referencia_fonte="cadastro-de-teste",
            checksum_fonte="a" * 64,
        )
        classificacao = session.query(SetorClassificacaoCompanhia).one()

        assert contadores["setores_publicados"] == 1
        assert contadores["classificacoes_setoriais"] == 1
        assert classificacao.rotulo_origem == "  Energia   Elétrica "
        assert classificacao.referencia_fonte == "cadastro-de-teste"
        assert classificacao.arquivo_origem == ARQUIVO_CADASTRO_ABERTA
        assert classificacao.linha_origem == 42
    finally:
        session.close()


def test_sincronizar_cadastro_companhias_downloads_open_and_foreign_sources() -> None:
    session = _session()
    try:
        aberta_payload = _csv_open([_row_aberta(cnpj="08.773.135/0001-00", codigo_cvm="25224")])
        estrangeira_payload = _csv_foreign([_row_estrangeira(cnpj="07.857.093/0001-14", codigo_cvm="80187")])
        payloads = {
            "https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv": aberta_payload,
            "https://dados.cvm.gov.br/dados/CIA_ESTRANG/CAD/DADOS/cad_cia_estrang.csv": estrangeira_payload,
        }

        def downloader(url: str) -> bytes:
            return payloads[url]

        resultado = sincronizar_cadastro_companhias(session, downloader=downloader)

        assert resultado["status"] == "sucesso"
        assert resultado["total_linhas_lidas"] == 2
        assert resultado["total_inseridos"] == 2
        assert resultado["total_atualizados"] == 0
        assert resultado["total_inalterados"] == 0
        assert session.query(Companhia).count() == 2
        assert session.query(CompanhiaRegistroCvm).count() == 2
        assert session.query(CompanhiaIdentificador).count() == 4
        estrangeira = session.query(Companhia).filter(Companhia.codigo_cvm == 80187).one()
        assert estrangeira.tipo_emissor == "estrangeira"
        assert estrangeira.qualidade_identidade == "alta"
        artifact_snapshot = session.query(SourceArtifactSnapshot).one()
        assert artifact_snapshot.tipo_fonte == "cadastro"
        assert artifact_snapshot.content_sha256 is not None
        member_snapshots = (
            session.query(SourceMemberSnapshot)
            .order_by(SourceMemberSnapshot.member_name.asc())
            .all()
        )
        assert [item.member_name for item in member_snapshots] == [
            ARQUIVO_CADASTRO_ABERTA,
            ARQUIVO_CADASTRO_ESTRANGEIRA,
        ]
        assert all(item.member_sha256 for item in member_snapshots)
        assert [item.row_count for item in member_snapshots] == [1, 1]
        assert all(item.header_hash for item in member_snapshots)
        assert all(item.required_member is True for item in member_snapshots)
        assert all(item.row_kind == "cadastro_registro_cvm" for item in member_snapshots)
        alterado_em_original = estrangeira.alterado_em

        repeticao = sincronizar_cadastro_companhias(
            session,
            force_reimport=True,
            downloader=downloader,
        )

        assert repeticao["total_linhas_lidas"] == 2
        assert repeticao["total_inseridos"] == 0
        assert repeticao["total_atualizados"] == 0
        assert repeticao["total_inalterados"] == 2
        session.refresh(estrangeira)
        assert estrangeira.alterado_em == alterado_em_original
    finally:
        session.close()


def test_registry_sync_corrects_cnpj_without_changing_provider_identity(caplog: Any) -> None:
    session = _session()
    try:
        provider_id = uuid.UUID("3588500f-eb75-4db4-a4f9-5b7cb94eac5a")
        companhia_existente = Companhia(
            id=provider_id,
            cnpj_companhia="05714446000400",
            codigo_cvm=80012,
            denominacao_social="BRAZIL FAST FOOD CORP.",
            tipo_emissor="estrangeira",
            qualidade_identidade="alta",
            endereco={},
            responsavel={},
            arquivo_origem=ARQUIVO_CADASTRO_ESTRANGEIRA,
            linha_origem=11,
            hash_origem="old-source-hash",
        )
        identificador_antigo = CompanhiaIdentificador(
            id=uuid.uuid4(),
            companhia_id=provider_id,
            tipo="cnpj",
            valor="05714446000400",
            valor_normalizado="05714446000400",
            fonte="cad_cia_estrang",
            confianca="alta",
            ativo=True,
        )
        session.add_all([companhia_existente, identificador_antigo])
        session.commit()

        aberta_payload = _csv_open([_row_aberta()])
        estrangeira_payload = _csv_foreign(
            [
                dict(_ROW_CVM_80012_SOURCE_CNPJ_MISMATCH),
                _row_estrangeira(
                    cnpj="05.714.446/0004-00",
                    codigo_cvm="80013",
                    denominacao="OTHER COMPANY",
                ),
            ]
        )
        payloads = {
            "https://dados.cvm.gov.br/dados/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv": aberta_payload,
            "https://dados.cvm.gov.br/dados/CIA_ESTRANG/CAD/DADOS/cad_cia_estrang.csv": estrangeira_payload,
        }

        resultado = sincronizar_cadastro_companhias(
            session,
            downloader=lambda url: payloads[url],
        )

        assert resultado["status"] == "sucesso"
        session.refresh(companhia_existente)
        resposta = CompanhiaResposta.model_validate(companhia_existente)
        assert resposta.id == provider_id
        assert resposta.cnpj_companhia == "05714446000100"
        assert cnpj_tem_digitos_validos(resposta.cnpj_companhia)

        registro_origem = (
            session.query(CompanhiaRegistroCvm)
            .filter(CompanhiaRegistroCvm.codigo_cvm == 80012)
            .one()
        )
        assert registro_origem.cnpj_companhia == "05714446000400"
        assert registro_origem.arquivo_origem == ARQUIVO_CADASTRO_ESTRANGEIRA
        assert registro_origem.linha_origem == 2

        session.refresh(identificador_antigo)
        assert identificador_antigo.ativo is False
        assert identificador_antigo.valid_to is not None
        identificador_correto = (
            session.query(CompanhiaIdentificador)
            .filter(
                CompanhiaIdentificador.companhia_id == provider_id,
                CompanhiaIdentificador.tipo == "cnpj",
                CompanhiaIdentificador.ativo.is_(True),
            )
            .one()
        )
        assert identificador_correto.valor_normalizado == "05714446000100"

        diagnosticos = [
            record
            for record in caplog.records
            if getattr(record, "event_code", None) == "cvm_registry_cnpj_source_mismatch"
        ]
        assert len(diagnosticos) == 2
        assert all(not hasattr(record, "cnpj_origem") for record in diagnosticos)
        assert all(record.cnpj_origem_sufixo == "0400" for record in diagnosticos)

        repeticao = sincronizar_cadastro_companhias(
            session,
            force_reimport=True,
            downloader=lambda url: payloads[url],
        )
        assert repeticao["status"] == "sucesso"
        assert session.query(Companhia).filter(Companhia.codigo_cvm == 80012).count() == 1
        session.refresh(companhia_existente)
        resposta_repetida = CompanhiaResposta.model_validate(companhia_existente)
        assert resposta_repetida.id == provider_id
        assert resposta_repetida.cnpj_companhia == "05714446000100"
        assert session.query(CompanhiaRegistroCvm).filter(CompanhiaRegistroCvm.codigo_cvm == 80012).count() == 1
    finally:
        session.close()
