from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models import companhia, financeiro, fre, identidade, ingestion, sincronizacao, usuario  # noqa: F401
from app.models.companhia import Companhia
from app.models.identidade import CompanhiaIdentificador, CompanhiaMercado, CompanhiaRegistroCvm
from app.models.ingestion import SourceArtifactSnapshot, SourceMemberSnapshot
from app.services.ingestion.cadastro import (
    ARQUIVO_CADASTRO_ABERTA,
    ARQUIVO_CADASTRO_ESTRANGEIRA,
    normalizar_linha_cadastro_aberta,
    normalizar_linha_cadastro_estrangeira,
    promover_registros_cadastro,
    selecionar_registro_canonico,
    sincronizar_cadastro_companhias,
)
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
        assert session.query(Companhia).count() == 1
        assert session.query(CompanhiaRegistroCvm).count() == 2
        assert session.query(CompanhiaMercado).count() == 3
        assert session.query(CompanhiaIdentificador).count() == 3
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
    finally:
        session.close()
