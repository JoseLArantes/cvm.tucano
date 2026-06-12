from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models import financeiro, fre, identidade, ingestion, sincronizacao, usuario  # noqa: F401
from app.models.companhia import Companhia
from app.models.identidade import CompanhiaIdentificador, RepairRule
from app.models.ingestion import IngestionRow
from app.services.ingestion.resolver import (
    STATUS_AMBIGUOUS,
    STATUS_NOT_FOUND,
    STATUS_PROVISIONAL_CREATED,
    STATUS_RESOLVED,
    DocumentHeaderMap,
    ResolverInput,
    build_document_header_key,
    persist_resolution_result,
    register_document_header,
    resolve_companhia,
)
from app.services.ingestion.staging import create_run, register_file, stage_csv_payload


def _session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    local_session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return local_session()


def _companhia(
    session: Session,
    *,
    cnpj: str,
    codigo_cvm: int | None,
    denominacao: str,
) -> Companhia:
    empresa = Companhia(
        cnpj_companhia=cnpj,
        codigo_cvm=codigo_cvm,
        denominacao_social=denominacao,
        denominacao_comercial=denominacao,
        arquivo_origem="teste",
        ano_origem=2026,
        linha_origem=2,
        hash_origem=f"hash-{cnpj}-{codigo_cvm}",
    )
    session.add(empresa)
    session.flush()
    return empresa


def _identificador(
    session: Session,
    *,
    empresa: Companhia,
    tipo: str,
    valor_normalizado: str,
    fonte: str = "teste",
) -> None:
    session.add(
        CompanhiaIdentificador(
            companhia_id=empresa.id,
            tipo=tipo,
            valor=valor_normalizado,
            valor_normalizado=valor_normalizado,
            fonte=fonte,
            confianca="alta",
            ativo=True,
        )
    )
    session.flush()


def _staged_row(session: Session) -> IngestionRow:
    run = create_run(session, tipo_fonte="dfp", ano=2025)
    ingestion_file = register_file(
        session,
        ingestion_run=run,
        source_url="https://example.test/dfp.zip",
        source_filename="dfp.zip",
        payload=b"fake",
        is_zip=True,
    )
    _, rows = stage_csv_payload(
        session,
        ingestion_run=run,
        ingestion_file=ingestion_file,
        payload=b"CNPJ_CIA;CD_CVM\n08.773.135/0001-00;25224\n",
        member_name="dfp_cia_aberta_2025.csv",
        arquivo_origem="dfp_cia_aberta_2025.csv",
        ano_origem=2025,
        row_kind="dfp_documento",
    )
    return rows[0]


def test_resolve_companhia_by_exact_cnpj_single_company() -> None:
    session = _session()
    try:
        companhia = _companhia(session, cnpj="08773135000100", codigo_cvm=25224, denominacao="EMPRESA SA")
        _identificador(session, empresa=companhia, tipo="cnpj", valor_normalizado="08773135000100")

        result = resolve_companhia(
            session,
            ResolverInput(cnpj_companhia="08.773.135/0001-00", codigo_cvm=None, denominacao_companhia="EMPRESA SA"),
        )

        assert result.status == STATUS_RESOLVED
        assert result.companhia_id == companhia.id
        assert result.resolution_method == "cnpj_identificador_alta"
    finally:
        session.close()


def test_resolve_companhia_by_exact_cnpj_duplicate_rows_same_company() -> None:
    session = _session()
    try:
        companhia = _companhia(session, cnpj="08773135000100", codigo_cvm=25224, denominacao="EMPRESA SA")
        _identificador(
            session,
            empresa=companhia,
            tipo="cnpj",
            valor_normalizado="08773135000100",
            fonte="cad_cia_aberta",
        )
        _identificador(
            session,
            empresa=companhia,
            tipo="cnpj",
            valor_normalizado="08773135000100",
            fonte="cad_cia_estrang",
        )

        result = resolve_companhia(
            session,
            ResolverInput(cnpj_companhia="08.773.135/0001-00", codigo_cvm=None),
        )

        assert result.status == STATUS_RESOLVED
        assert result.companhia_id == companhia.id
    finally:
        session.close()


def test_resolve_companhia_returns_ambiguous_for_multiple_companies_same_cnpj() -> None:
    session = _session()
    try:
        companhia_a = _companhia(session, cnpj="11111111111111", codigo_cvm=10, denominacao="A SA")
        companhia_b = _companhia(session, cnpj="22222222222222", codigo_cvm=20, denominacao="B SA")
        _identificador(session, empresa=companhia_a, tipo="cnpj", valor_normalizado="08773135000100", fonte="fonte_a")
        _identificador(session, empresa=companhia_b, tipo="cnpj", valor_normalizado="08773135000100", fonte="fonte_b")

        result = resolve_companhia(session, ResolverInput(cnpj_companhia="08.773.135/0001-00"))

        assert result.status == STATUS_AMBIGUOUS
        assert result.companhia_id is None
        assert result.resolution_method == "companhia_ambigua"
    finally:
        session.close()


def test_resolve_companhia_by_zero_padded_codigo_cvm() -> None:
    session = _session()
    try:
        companhia = _companhia(session, cnpj="08773135000100", codigo_cvm=25224, denominacao="EMPRESA SA")
        _identificador(session, empresa=companhia, tipo="codigo_cvm", valor_normalizado="25224")

        result = resolve_companhia(session, ResolverInput(codigo_cvm="00025224"))

        assert result.status == STATUS_RESOLVED
        assert result.companhia_id == companhia.id
        assert result.resolution_method == "codigo_cvm_identificador_alta"
    finally:
        session.close()


def test_resolve_companhia_detects_conflict_between_cnpj_and_codigo() -> None:
    session = _session()
    try:
        companhia_a = _companhia(session, cnpj="08773135000100", codigo_cvm=25224, denominacao="A SA")
        companhia_b = _companhia(session, cnpj="07857093000114", codigo_cvm=80187, denominacao="B SA")
        _identificador(session, empresa=companhia_a, tipo="cnpj", valor_normalizado="08773135000100")
        _identificador(session, empresa=companhia_b, tipo="codigo_cvm", valor_normalizado="25224")

        result = resolve_companhia(
            session,
            ResolverInput(cnpj_companhia="08.773.135/0001-00", codigo_cvm=25224),
        )

        assert result.status == STATUS_AMBIGUOUS
        assert result.companhia_id is None
    finally:
        session.close()


def test_resolve_companhia_uses_document_header_map_for_child_row() -> None:
    session = _session()
    try:
        companhia = _companhia(session, cnpj="07857093000114", codigo_cvm=80187, denominacao="AURA")
        header_map: DocumentHeaderMap = {}
        register_document_header(
            header_map,
            tipo_formulario="FRE",
            id_documento=99,
            versao=3,
            data_referencia=date(2025, 12, 31),
            companhia_id=companhia.id,
            cnpj_companhia="07857093000114",
            codigo_cvm=80187,
        )

        result = resolve_companhia(
            session,
            ResolverInput(
                cnpj_companhia=None,
                codigo_cvm=None,
                tipo_formulario="FRE",
                id_documento=99,
                versao=3,
                data_referencia=date(2025, 12, 31),
            ),
            header_map=header_map,
        )

        assert result.status == STATUS_RESOLVED
        assert result.companhia_id == companhia.id
        assert (
            build_document_header_key(
                tipo_formulario="FRE",
                id_documento=99,
                versao=3,
                data_referencia=date(2025, 12, 31),
            )
            in header_map
        )
    finally:
        session.close()


def test_resolve_companhia_uses_repair_rule() -> None:
    session = _session()
    try:
        companhia = _companhia(session, cnpj="07857093000114", codigo_cvm=80187, denominacao="AURA")
        session.add(
            RepairRule(
                rule_type="identity_exact",
                enabled=True,
                match_payload={
                    "tipo_formulario": "FRE",
                    "id_documento": 3,
                    "versao": 1,
                    "data_referencia": "2025-12-31",
                    "nome_emissor_chave": "EMPRESA FINANCEIRA",
                },
                action_payload={"companhia_id": str(companhia.id)},
            )
        )
        session.flush()

        result = resolve_companhia(
            session,
            ResolverInput(
                tipo_formulario="FRE",
                id_documento=3,
                versao=1,
                data_referencia=date(2025, 12, 31),
                denominacao_companhia="EMPRESA FINANCEIRA",
            ),
        )

        assert result.status == STATUS_RESOLVED
        assert result.companhia_id == companhia.id
        assert result.resolution_method == "manual_identity_rule_media"
    finally:
        session.close()


def test_resolve_companhia_provisional_disabled_and_enabled() -> None:
    session = _session()
    try:
        missing = ResolverInput(
            cnpj_companhia="08.773.135/0001-00", codigo_cvm=25224, denominacao_companhia="EMPRESA SA"
        )

        result_disabled = resolve_companhia(session, missing, provisional_enabled=False)
        assert result_disabled.status == STATUS_NOT_FOUND

        result_enabled = resolve_companhia(session, missing, provisional_enabled=True)
        assert result_enabled.status == STATUS_PROVISIONAL_CREATED
        companhia = session.get(Companhia, result_enabled.companhia_id)
        assert companhia is not None
        assert companhia.tipo_emissor == "provisorio"
        assert companhia.qualidade_identidade == "baixa"
    finally:
        session.close()


def test_persist_resolution_result_updates_staging_row_and_event() -> None:
    session = _session()
    try:
        companhia = _companhia(session, cnpj="08773135000100", codigo_cvm=25224, denominacao="EMPRESA SA")
        row = _staged_row(session)

        result = resolve_companhia(
            session,
            ResolverInput(cnpj_companhia="08.773.135/0001-00", codigo_cvm=25224),
            provisional_enabled=True,
        )
        if result.status == STATUS_NOT_FOUND:
            _identificador(session, empresa=companhia, tipo="cnpj", valor_normalizado="08773135000100")
            result = resolve_companhia(
                session,
                ResolverInput(cnpj_companhia="08.773.135/0001-00", codigo_cvm=25224),
            )

        persist_resolution_result(session, ingestion_row=row, result=result)
        session.commit()
        session.refresh(row)

        assert row.resolved_companhia_id is not None
        assert row.resolution_method is not None
        assert row.resolution_confidence is not None
    finally:
        session.close()
