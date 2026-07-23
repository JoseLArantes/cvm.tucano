from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.ingestion import IngestionFile, IngestionFileMember, IngestionRun
from app.services.ingestion.events import list_operational_events, revision_for


def test_operational_events_expose_domain_envelope_and_resume(db_session: Session) -> None:
    run = IngestionRun(tipo_fonte="dfp", ano=2025, status="em_execucao", phase="promote")
    db_session.add(run)
    db_session.flush()
    ingestion_file = IngestionFile(ingestion_run_id=run.id, source_url="https://example.test/dfp.zip", source_filename="dfp.zip", content_sha256="a" * 64, content_length_bytes=1, is_zip=True)
    db_session.add(ingestion_file)
    db_session.flush()
    db_session.add(IngestionFileMember(ingestion_file_id=ingestion_file.id, member_name="dfp.csv", member_sha256="b" * 64, member_size_bytes=1, delimiter=";", row_count=0, schema_status="ok"))
    db_session.commit()

    events = list_operational_events(db_session, after_revision=None, scope="dfp:2025")
    event_types = {event["event_type"] for event in events}
    assert {"ingestion.run.updated", "ingestion.work_item.updated", "ingestion.member.updated", "ingestion.operations.updated", "ingestion.queue.updated"} <= event_types
    run_event = next(event for event in events if event["event_type"] == "ingestion.run.updated")
    assert run_event["entity_type"] == "run"
    assert run_event["data"]["run_id"] == str(run.id)
    assert list_operational_events(db_session, after_revision=run_event["revision"], scope="dfp:2025") == []


def test_revision_is_opaque_and_chronological() -> None:
    revision = revision_for(datetime(2026, 7, 21, tzinfo=UTC), entity_type="run", entity_id=str(uuid4()))
    assert revision.split(":", 1)[0].isdigit()
