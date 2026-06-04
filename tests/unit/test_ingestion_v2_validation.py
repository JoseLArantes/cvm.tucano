from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models import companhia, identidade, financeiro, fre, ingestion, sincronizacao, usuario  # noqa: F401
from app.models.ingestion import IngestionRowEvent
from app.services.ingestion.staging import create_run, register_file, stage_csv_payload
from app.services.ingestion.validation import (
    ValidationResult,
    build_natural_key,
    classify_duplicate,
    update_member_schema_validation,
    validate_member_header,
    write_validation_result,
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


def _staged_row(session: Session):
    run = create_run(session, tipo_fonte="dfp", ano=2025)
    ingestion_file = register_file(
        session,
        ingestion_run=run,
        source_url="https://example.test/dfp.zip",
        source_filename="dfp.zip",
        payload=b"fake",
        is_zip=True,
    )
    member, rows = stage_csv_payload(
        session,
        ingestion_run=run,
        ingestion_file=ingestion_file,
        payload=b"CNPJ_CIA;DT_REFER;VERSAO;ID_DOC\n08.773.135/0001-00;2025-12-31;1;10\n",
        member_name="dfp_cia_aberta_2025.csv",
        arquivo_origem="dfp_cia_aberta_2025.csv",
        ano_origem=2025,
        row_kind="dfp_documento",
    )
    return member, rows[0]


def test_validation_result_serializes_details_to_json() -> None:
    result = ValidationResult(
        status="invalid",
        reason_code="schema_inesperado",
        severity="error",
        details={"missing": ["ID_DOC"]},
        repairable=True,
    )

    payload = result.to_json_payload()

    assert payload["details"]["missing"] == ["ID_DOC"]
    assert payload["repairable"] is True


def test_validate_member_header_missing_required_column_returns_schema_inesperado() -> None:
    result = validate_member_header("dfp_documento", ["CNPJ_CIA", "DT_REFER", "VERSAO"])

    assert result.status == "invalid"
    assert result.reason_code == "schema_inesperado"
    assert result.repairable is True
    assert result.details["missing_required_columns"] == ["ID_DOC"]


def test_build_natural_key_for_dfp_demonstracao_fre_auditor_and_cadastro() -> None:
    demonstracao = build_natural_key(
        "dfp_demonstracao",
        {
            "tipo_formulario": "DFP",
            "tipo_demonstracao": "BPA",
            "escopo_demonstracao": "CON",
            "cnpj_companhia": "08773135000100",
            "data_referencia": "2025-12-31",
            "versao": 1,
            "grupo_demonstracao": "Ativo",
            "ordem_exercicio": "ÚLTIMO",
            "data_fim_exercicio": "2025-12-31",
            "codigo_conta": "1.01",
        },
    )
    fre_auditor = build_natural_key(
        "fre_auditor",
        {
            "id_documento": 10,
            "versao": 1,
            "data_referencia": "2025-12-31",
            "cnpj_companhia": "07857093000114",
            "id_auditor": 3,
        },
    )
    cadastro = build_natural_key(
        "cadastro_registro_cvm",
        {
            "fonte_cadastro": "cad_cia_aberta",
            "cnpj_companhia": "08773135000100",
            "codigo_cvm": 25224,
            "hash_sem_mercado": "abc",
        },
    )

    assert demonstracao["codigo_conta"] == "1.01"
    assert fre_auditor["id_auditor"] == 3
    assert cadastro["hash_sem_mercado"] == "abc"


def test_classify_duplicate_ignores_exact_duplicate() -> None:
    seen_by_key = {}
    natural_key = {"id_documento": 10, "versao": 1}
    normalized_data = {"id_documento": 10, "versao": 1, "valor": "A"}

    first = classify_duplicate(
        natural_key=natural_key,
        normalized_hash="hash-a",
        normalized_data=normalized_data,
        seen_by_key=seen_by_key,
    )
    second = classify_duplicate(
        natural_key=natural_key,
        normalized_hash="hash-a",
        normalized_data=normalized_data,
        seen_by_key=seen_by_key,
    )

    assert first.status == "valid"
    assert second.status == "ignored_duplicate"
    assert second.reason_code == "ignored_duplicate"


def test_classify_duplicate_quarantines_conflict_with_field_diff() -> None:
    seen_by_key = {}
    natural_key = {"id_documento": 10, "versao": 1}

    classify_duplicate(
        natural_key=natural_key,
        normalized_hash="hash-a",
        normalized_data={"id_documento": 10, "versao": 1, "valor": "A"},
        seen_by_key=seen_by_key,
    )
    conflict = classify_duplicate(
        natural_key=natural_key,
        normalized_hash="hash-b",
        normalized_data={"id_documento": 10, "versao": 1, "valor": "B"},
        seen_by_key=seen_by_key,
    )

    assert conflict.status == "invalid"
    assert conflict.reason_code == "chave_natural_duplicada_conflitante"
    assert conflict.details["field_diff"]["valor"] == {"before": "A", "after": "B"}


def test_write_validation_result_updates_row_and_event_and_member_schema() -> None:
    session = _session()
    try:
        member, row = _staged_row(session)
        schema_result = validate_member_header("dfp_documento", member.header)
        update_member_schema_validation(member, result=schema_result)

        result = ValidationResult(
            status="invalid",
            reason_code="schema_inesperado",
            severity="error",
            details={"missing": ["ID_DOC"]},
            repairable=True,
        )
        write_validation_result(
            session,
            ingestion_row=row,
            result=result,
            normalized_data={"tipo_formulario": "DFP", "id_documento": 10},
            natural_key={"tipo_formulario": "DFP", "id_documento": 10},
        )
        session.commit()
        session.refresh(row)
        session.refresh(member)

        assert row.validation_status == "invalid"
        assert row.validation_reason_code == "schema_inesperado"
        assert row.validation_details["details"]["missing"] == ["ID_DOC"]
        assert member.schema_status == "valid"
        event = session.query(IngestionRowEvent).one()
        assert event.event_type == "quarantined"
    finally:
        session.close()
