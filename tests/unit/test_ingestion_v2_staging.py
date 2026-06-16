import io
import uuid
import zipfile

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.ingestion import (
    IngestionAttempt,
    IngestionFile,
    IngestionFileMember,
    IngestionRow,
    IngestionRowEvent,
    QuarantineItem,
)
from app.services.ingestion.staging import (
    create_run,
    get_member_payload,
    iter_staged_member_chunks,
    purge_member_success_rows,
    read_staged_csv_rows,
    register_attempt,
    register_file,
    register_row_event,
    save_member_payload,
    stage_csv_payload,
    stage_csv_payload_streaming,
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


def test_stage_csv_payload_streaming_persists_rows_and_chunk_iteration() -> None:
    session = _session()
    try:
        run = create_run(session, tipo_fonte="itr", ano=2022)
        ingestion_file = register_file(
            session,
            ingestion_run=run,
            source_url="https://example.test/itr.zip",
            source_filename="itr.zip",
            payload=b"fake",
        )

        member = stage_csv_payload_streaming(
            session,
            ingestion_run=run,
            ingestion_file=ingestion_file,
            payload=b"col_a;col_b\n1;2\n3;4\n5;6\n",
            member_name="itr_cia_aberta_2022.csv",
            arquivo_origem="itr_cia_aberta_2022.csv",
            ano_origem=2022,
            row_kind="itr_documento",
            chunk_size=2,
        )
        session.commit()

        chunks = list(iter_staged_member_chunks(session, member_id=member.id, chunk_size=2))

        assert member.row_count == 3
        assert session.query(IngestionRow).count() == 3
        assert [len(chunk) for chunk in chunks] == [2, 1]
        assert [row.linha_origem for chunk in chunks for row in chunk] == [2, 3, 4]
    finally:
        session.close()


def test_member_payload_is_upserted_and_readable() -> None:
    session = _session()
    try:
        execution_id = uuid.uuid4()
        save_member_payload(session, execution_id, b"primeiro")
        save_member_payload(session, execution_id, b"segundo")
        session.commit()

        assert get_member_payload(session, execution_id) == b"segundo"
    finally:
        session.close()


def test_purge_member_success_rows_preserves_quarantine_rows() -> None:
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
            payload=b"col_a;col_b\n1;2\n3;4\n",
            member_name="dfp_cia_aberta_2021.csv",
            arquivo_origem="dfp_cia_aberta_2021.csv",
            ano_origem=2021,
            row_kind="dfp_documento",
        )
        session.add(
            QuarantineItem(
                ingestion_run_id=run.id,
                ingestion_row_id=rows[1].id,
                arquivo_origem="dfp_cia_aberta_2021.csv",
                ano_origem=2021,
                linha_origem=rows[1].linha_origem,
                row_kind="dfp_documento",
                status="pendente",
                motivo_codigo="companhia_nao_encontrada",
                severidade="error",
                reparavel=True,
                tentativas_reprocessamento=0,
            )
        )
        session.commit()

        removidas = purge_member_success_rows(session, ingestion_file_member_id=member.id)
        session.commit()

        assert removidas == 1
        restantes = session.query(IngestionRow).order_by(IngestionRow.linha_origem.asc()).all()
        assert [row.linha_origem for row in restantes] == [3]
    finally:
        session.close()


def test_purge_member_success_rows_flushes_pending_quarantine_before_delete() -> None:
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
            payload=b"col_a;col_b\n1;2\n3;4\n",
            member_name="dfp_cia_aberta_2021.csv",
            arquivo_origem="dfp_cia_aberta_2021.csv",
            ano_origem=2021,
            row_kind="dfp_documento",
        )
        register_row_event(
            session,
            ingestion_row=rows[1],
            event_type="quarantined",
            event_payload={"motivo_codigo": "companhia_nao_encontrada"},
            created_by="validation",
        )
        session.add(
            QuarantineItem(
                ingestion_run_id=run.id,
                ingestion_row_id=rows[1].id,
                arquivo_origem="dfp_cia_aberta_2021.csv",
                ano_origem=2021,
                linha_origem=rows[1].linha_origem,
                row_kind="dfp_documento",
                status="pendente",
                motivo_codigo="companhia_nao_encontrada",
                severidade="error",
                reparavel=True,
                tentativas_reprocessamento=0,
            )
        )

        removidas = purge_member_success_rows(session, ingestion_file_member_id=member.id)
        session.commit()

        assert removidas == 1
        restantes = session.query(IngestionRow).order_by(IngestionRow.linha_origem.asc()).all()
        assert [row.linha_origem for row in restantes] == [3]
        assert session.query(IngestionRowEvent).count() == 1
        assert session.query(QuarantineItem).count() == 1
    finally:
        session.close()


def test_register_file_cleanup_removes_quarantine_rows_from_child_runs() -> None:
    session = _session()
    try:
        old_parent_run = create_run(session, tipo_fonte="dfp", ano=2025, status="falha")
        old_file = register_file(
            session,
            ingestion_run=old_parent_run,
            source_url="https://example.test/dfp-2025.zip",
            source_filename="dfp-2025.zip",
            payload=b"conteudo-antigo",
        )
        old_member, old_rows = stage_csv_payload(
            session,
            ingestion_run=old_parent_run,
            ingestion_file=old_file,
            payload=b"col_a;col_b\n1;2\n",
            member_name="dfp_cia_aberta_DMPL_con_2025.csv",
            arquivo_origem="dfp_cia_aberta_DMPL_con_2025.csv",
            ano_origem=2025,
            row_kind="dfp_demonstracao",
        )
        child_run = create_run(session, tipo_fonte="dfp", ano=2025, status="falha")
        session.add(
            QuarantineItem(
                ingestion_run_id=child_run.id,
                ingestion_row_id=old_rows[0].id,
                arquivo_origem="dfp_cia_aberta_DMPL_con_2025.csv",
                ano_origem=2025,
                linha_origem=old_rows[0].linha_origem,
                row_kind="dfp_demonstracao",
                status="pendente",
                motivo_codigo="chave_natural_duplicada_conflitante",
                severidade="error",
                reparavel=True,
                tentativas_reprocessamento=0,
            )
        )
        session.commit()

        new_run = create_run(session, tipo_fonte="dfp", ano=2025)
        register_file(
            session,
            ingestion_run=new_run,
            source_url="https://example.test/dfp-2025.zip",
            source_filename="dfp-2025.zip",
            payload=b"conteudo-antigo",
        )
        session.commit()

        assert session.query(QuarantineItem).count() == 0
        assert session.query(IngestionRow).count() == 0
        assert session.query(IngestionFileMember).count() == 0
    finally:
        session.close()
