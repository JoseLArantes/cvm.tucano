import io
import zipfile

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.ingestion import IngestionAttempt, IngestionFile, IngestionFileMember, IngestionRow, IngestionRowEvent
from app.services.ingestion.staging import (
    create_run,
    read_staged_csv_rows,
    register_attempt,
    register_file,
    register_row_event,
    stage_csv_payload,
    stage_zip_payload,
    update_row_validation,
    update_run_state,
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


def test_read_staged_csv_rows_tracks_header_and_line_numbers() -> None:
    payload = b"col_a;col_b\n1;2\n3;4\n"

    header, rows, encoding = read_staged_csv_rows(payload)

    assert header == ["col_a", "col_b"]
    assert encoding == "utf-8-sig"
    assert rows == [(2, {"col_a": "1", "col_b": "2"}), (3, {"col_a": "3", "col_b": "4"})]


def test_stage_csv_payload_persists_member_and_rows() -> None:
    session = _session()
    try:
        run = create_run(session, tipo_fonte="dfp", ano=2021)
        ingestion_file = register_file(
            session,
            ingestion_run=run,
            source_url="https://example.test/dfp.zip",
            source_filename="dfp.zip",
            payload=b"fake",
        )

        member, rows = stage_csv_payload(
            session,
            ingestion_run=run,
            ingestion_file=ingestion_file,
            payload=b"col_a;col_b\n1;2\n",
            member_name="dfp_cia_aberta_2021.csv",
            arquivo_origem="dfp_cia_aberta_2021.csv",
            ano_origem=2021,
            row_kind="dfp_documento",
        )
        update_row_validation(
            rows[0],
            validation_status="valid",
            validation_reason_code=None,
            validation_details={"ok": True},
            normalized_data={"col_a": "1"},
            normalized_hash="abc",
            natural_key={"id": 1},
        )
        register_row_event(
            session,
            ingestion_row=rows[0],
            event_type="validated",
            event_payload={"status": "valid"},
        )
        register_attempt(session, operation="stage", attempt_number=1, status="success", ingestion_run=run)
        update_run_state(run, phase="stage", status="sucesso")
        session.commit()

        assert session.query(IngestionFile).count() == 1
        assert session.query(IngestionFileMember).count() == 1
        assert session.query(IngestionRow).count() == 1
        assert session.query(IngestionRowEvent).count() == 1
        assert session.query(IngestionAttempt).count() == 1
        assert member.row_count == 1
        assert rows[0].validation_status == "valid"
        assert run.phase == "stage"
        assert run.status == "sucesso"
    finally:
        session.close()


def test_stage_zip_payload_stages_all_csv_members() -> None:
    session = _session()
    try:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("a.csv", "x;y\n1;2\n")
            archive.writestr("b.csv", "m;n\n3;4\n5;6\n")
            archive.writestr("notes.txt", "ignore")

        run = create_run(session, tipo_fonte="fre", ano=2021)
        ingestion_file = register_file(
            session,
            ingestion_run=run,
            source_url="https://example.test/fre.zip",
            source_filename="fre.zip",
            payload=buffer.getvalue(),
            is_zip=True,
        )
        staged = stage_zip_payload(
            session,
            ingestion_run=run,
            ingestion_file=ingestion_file,
            payload=buffer.getvalue(),
            ano_origem=2021,
            row_kind_by_member={"a.csv": "kind_a", "b.csv": "kind_b"},
        )
        session.commit()

        assert len(staged) == 2
        assert session.query(IngestionFileMember).count() == 2
        assert session.query(IngestionRow).count() == 3
        assert {member.member_name for member, _ in staged} == {"a.csv", "b.csv"}
    finally:
        session.close()
