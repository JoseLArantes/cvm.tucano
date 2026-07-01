from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import gerar_hash_senha
from app.models.ingestion import (
    IngestionFile,
    IngestionFileMember,
    IngestionRun,
    SourceArtifactSnapshot,
    SourceMemberSnapshot,
)
from app.models.usuario import Usuario
from app.updates.models import PendingUpdate, PendingUpdateMember, UpdateScanRun, UpdateSessionItem
from app.updates.service import (
    add_session_item,
    create_scan_run,
    create_session,
    discard_update,
    get_latest_scan_run,
    remove_session_item,
    run_deep_analysis,
    run_scanner,
    trigger_update,
)


@pytest.fixture
def test_user(db_session: Session) -> Usuario:
    user = Usuario(
        username="updates-tester",
        nome="Tester",
        senha_hash=gerar_hash_senha("senha-forte-123"),
        is_admin=True,
        ativo=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(client: TestClient, test_user: Usuario) -> dict[str, str]:
    login = client.post("/auth/login", json={"username": "updates-tester", "password": "senha-forte-123"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@patch("app.updates.service.probe_remote_source")
@patch("app.updates.service.run_deep_analysis")
@patch("app.updates.service.listar_fontes")
@patch("app.updates.service.get_settings")
def test_scanner_detects_changes(
    mock_get_settings: MagicMock,
    mock_listar_fontes: MagicMock,
    mock_run_deep_analysis: MagicMock,
    mock_probe: MagicMock,
    db_session: Session
) -> None:
    # Mock settings
    settings_mock = MagicMock()
    settings_mock.anos_iniciais_dfp = "2025"
    settings_mock.parse_anos.return_value = [2025]
    settings_mock.cvm_base_url = "http://fake-cvm.gov.br"
    mock_get_settings.return_value = settings_mock

    # Mock source list
    source_mock = MagicMock()
    source_mock.fonte = "dfp"
    mock_listar_fontes.return_value = [source_mock]

    # Mock probe output: change detected
    mock_probe.return_value = {
        "decision": "changed",
        "download_required": True,
        "resource_etag": "etag-123",
        "resource_last_modified": "Mon, 15 Jun 2026 12:00:00 GMT",
        "resource_content_length": "1000",
    }
    mock_run_deep_analysis.side_effect = lambda db, pending_id: db.get(PendingUpdate, pending_id)

    # Run scanner
    detected = run_scanner(db_session)
    assert detected["detected_count"] == 1
    assert len(detected["items"]) == 1
    assert detected["items"][0]["fonte"] == "dfp"
    assert detected["items"][0]["ano"] == 2025
    assert detected["items"][0]["artifact_decision"] == "changed"
    assert detected["items"][0]["member_scan"]["analyzed"] is True

    # Check database persistence
    db_session.expire_all()
    db_pending = db_session.scalar(select(PendingUpdate).where(PendingUpdate.fonte == "dfp"))
    assert db_pending is not None
    assert db_pending.ano == 2025
    assert db_pending.status == "change_detected"


@patch("app.updates.service.probe_remote_source")
@patch("app.updates.service.listar_fontes")
@patch("app.updates.service.get_settings")
def test_scanner_does_not_flag_unknown_probe_as_artifact_changed(
    mock_get_settings: MagicMock,
    mock_listar_fontes: MagicMock,
    mock_probe: MagicMock,
    db_session: Session,
) -> None:
    settings_mock = MagicMock()
    settings_mock.anos_iniciais_dfp = "2025"
    settings_mock.parse_anos.return_value = [2025]
    settings_mock.cvm_base_url = "http://fake-cvm.gov.br"
    mock_get_settings.return_value = settings_mock

    source_mock = MagicMock()
    source_mock.fonte = "dfp"
    mock_listar_fontes.return_value = [source_mock]

    mock_probe.return_value = {
        "decision": "unknown",
        "download_required": True,
        "resource_etag": None,
        "resource_last_modified": None,
        "resource_content_length": None,
    }

    detected = run_scanner(db_session)

    assert detected["detected_count"] == 0
    assert detected["items"][0]["artifact_decision"] == "unknown"
    assert detected["items"][0]["member_scan"]["stop_reason"] == "probe_inconclusive"
    assert db_session.scalar(select(PendingUpdate).where(PendingUpdate.fonte == "dfp")) is None


@patch("app.updates.service._head_remote_resource")
@patch("app.updates.service.run_deep_analysis")
@patch("app.updates.service.listar_fontes")
@patch("app.updates.service.get_settings")
def test_scanner_cadastro_considers_both_files_before_creating_pending(
    mock_get_settings: MagicMock,
    mock_listar_fontes: MagicMock,
    mock_run_deep_analysis: MagicMock,
    mock_head: MagicMock,
    db_session: Session,
) -> None:
    settings_mock = MagicMock()
    settings_mock.cvm_base_url = "http://fake-cvm.gov.br"
    mock_get_settings.return_value = settings_mock

    source_mock = MagicMock()
    source_mock.fonte = "cadastro"
    mock_listar_fontes.return_value = [source_mock]

    run = IngestionRun(tipo_fonte="cadastro", ano=None, status="sucesso", phase="complete")
    db_session.add(run)
    db_session.flush()
    db_session.add_all(
        [
            IngestionFile(
                ingestion_run_id=run.id,
                source_url="http://fake-cvm.gov.br/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv",
                source_filename="cad_cia_aberta.csv",
                content_sha256="sha-a",
                content_length_bytes=100,
                etag="etag-a",
                last_modified="Mon, 15 Jun 2026 12:00:00 GMT",
                is_zip=False,
            ),
            IngestionFile(
                ingestion_run_id=run.id,
                source_url="http://fake-cvm.gov.br/CIA_ESTRANG/CAD/DADOS/cad_cia_estrang.csv",
                source_filename="cad_cia_estrang.csv",
                content_sha256="sha-b",
                content_length_bytes=200,
                etag="etag-b",
                last_modified="Mon, 15 Jun 2026 12:00:00 GMT",
                is_zip=False,
            ),
        ]
    )
    db_session.commit()

    mock_head.side_effect = [
        {
            "resource_etag": "etag-a",
            "resource_last_modified": "Mon, 15 Jun 2026 12:00:00 GMT",
            "resource_content_length": "100",
        },
        {
            "resource_etag": "etag-b-new",
            "resource_last_modified": "Mon, 15 Jun 2026 12:00:00 GMT",
            "resource_content_length": "200",
        },
    ]
    mock_run_deep_analysis.side_effect = lambda db, pending_id: db.get(PendingUpdate, pending_id)

    detected = run_scanner(db_session)

    assert detected["detected_count"] == 1
    assert detected["items"][0]["fonte"] == "cadastro"
    pending = db_session.scalar(select(PendingUpdate).where(PendingUpdate.fonte == "cadastro"))
    assert pending is not None
    assert pending.artifact_url.endswith("cad_cia_aberta.csv|http://fake-cvm.gov.br/CIA_ESTRANG/CAD/DADOS/cad_cia_estrang.csv")
    assert pending.change_summary is not None
    assert pending.change_summary["changed_sources"] == [
        "http://fake-cvm.gov.br/CIA_ESTRANG/CAD/DADOS/cad_cia_estrang.csv"
    ]


@patch("app.updates.service.probe_remote_source")
@patch("app.updates.service.listar_fontes")
@patch("app.updates.service.get_settings")
def test_scanner_marks_existing_pending_as_stale_when_probe_is_not_confirmed_change(
    mock_get_settings: MagicMock,
    mock_listar_fontes: MagicMock,
    mock_probe: MagicMock,
    db_session: Session,
) -> None:
    settings_mock = MagicMock()
    settings_mock.anos_iniciais_dfp = "2025"
    settings_mock.parse_anos.return_value = [2025]
    settings_mock.cvm_base_url = "http://fake-cvm.gov.br"
    mock_get_settings.return_value = settings_mock

    source_mock = MagicMock()
    source_mock.fonte = "dfp"
    mock_listar_fontes.return_value = [source_mock]

    pending = PendingUpdate(
        fonte="dfp",
        ano=2025,
        status="change_detected",
        artifact_url="http://fake-cvm.gov.br/dfp_2025.zip",
    )
    db_session.add(pending)
    db_session.commit()

    mock_probe.return_value = {
        "decision": "unknown",
        "download_required": True,
    }

    detected = run_scanner(db_session)

    db_session.refresh(pending)
    assert detected["detected_count"] == 0
    assert pending.status == "stale"
    assert pending.resolved_by == "scanner"
    assert pending.resolved_timestamp is not None


@patch("app.updates.service.download_file_to_disk")
@patch("app.updates.service.detect_encoding_and_delimiter")
@patch("app.updates.service.get_csv_header")
@patch("app.updates.service.count_csv_rows")
@patch("app.updates.service.listar_datasets")
@patch("app.updates.service.compute_file_sha256")
def test_deep_analyzer_processes_members(
    mock_compute_sha: MagicMock,
    mock_listar_datasets: MagicMock,
    mock_count_rows: MagicMock,
    mock_get_header: MagicMock,
    mock_detect_enc: MagicMock,
    mock_download: MagicMock,
    db_session: Session
) -> None:
    pending = PendingUpdate(
        fonte="dfp",
        ano=2025,
        status="change_detected",
        artifact_url="http://fake-cvm.gov.br/dfp_2025.zip",
    )
    db_session.add(pending)
    db_session.commit()

    # Mock helpers
    mock_compute_sha.return_value = "dummy-sha-256"
    mock_detect_enc.return_value = ("utf-8", ",")
    mock_get_header.return_value = ["CNPJ_CIA", "DENOM_CIA", "VERSAO"]
    mock_count_rows.return_value = 100

    # Mock datasets registry
    dataset_mock = MagicMock()
    dataset_mock.render_member_name.return_value = "dfp_cia_aberta_2025.csv"
    dataset_mock.obrigatorio = True
    dataset_mock.row_kind = "dfp_documento"
    dataset_mock.delivery_index_role = "header"
    mock_listar_datasets.return_value = [dataset_mock]

    # Mock zipfile extraction inside run_deep_analysis
    with patch("zipfile.ZipFile") as mock_zip:
        mock_zip_instance = MagicMock()
        mock_zip_instance.namelist.return_value = ["dfp_cia_aberta_2025.csv"]
        mock_zip.return_value.__enter__.return_value = mock_zip_instance

        # Run deep analysis
        analyzed = run_deep_analysis(db_session, pending.id)
        
        assert analyzed.status == "ready_for_ingestion"
        assert analyzed.change_summary is not None
        assert "dfp_cia_aberta_2025.csv" in analyzed.change_summary["members_added"]

        # Check members in database
        members = db_session.scalars(
            select(PendingUpdateMember).where(PendingUpdateMember.pending_update_id == pending.id)
        ).all()
        assert len(members) == 1
        assert members[0].member_name == "dfp_cia_aberta_2025.csv"
        assert members[0].change_category == "added"
        assert members[0].is_required is True


@patch("app.updates.service.download_file_to_disk")
@patch("app.updates.service.detect_encoding_and_delimiter")
@patch("app.updates.service.get_csv_header")
@patch("app.updates.service.count_csv_rows")
@patch("app.updates.service.listar_datasets")
@patch("app.updates.service.compute_file_sha256")
def test_deep_analysis_prefers_source_member_snapshot_baseline(
    mock_compute_sha: MagicMock,
    mock_listar_datasets: MagicMock,
    mock_count_rows: MagicMock,
    mock_get_header: MagicMock,
    mock_detect_enc: MagicMock,
    mock_download: MagicMock,
    db_session: Session,
) -> None:
    previous_run = IngestionRun(tipo_fonte="dfp", ano=2025, status="sucesso", phase="complete")
    db_session.add(previous_run)
    db_session.flush()
    ingestion_file = IngestionFile(
        ingestion_run_id=previous_run.id,
        source_url="http://fake-cvm.gov.br/dfp_2025.zip",
        source_filename="dfp_2025.zip",
        content_sha256="artifact-sha",
        content_length_bytes=100,
        is_zip=True,
    )
    db_session.add(ingestion_file)
    db_session.flush()
    db_session.add(
        IngestionFileMember(
            ingestion_file_id=ingestion_file.id,
            member_name="dfp_cia_aberta_2025.csv",
            member_sha256="file-member-sha",
            member_size_bytes=100,
            encoding="utf-8",
            delimiter=";",
            header=["COL_A"],
            row_count=10,
            schema_status="ok",
            schema_message=None,
        )
    )
    artifact_snapshot = SourceArtifactSnapshot(
        ingestion_run_id=previous_run.id,
        tipo_fonte="dfp",
        ano=2025,
        resource_url="http://fake-cvm.gov.br/dfp_2025.zip",
        source_filename="dfp_2025.zip",
        status="sucesso",
    )
    db_session.add(artifact_snapshot)
    db_session.flush()
    db_session.add(
        SourceMemberSnapshot(
            artifact_snapshot_id=artifact_snapshot.id,
            member_name="dfp_cia_aberta_2025.csv",
            member_sha256="snapshot-sha",
            row_count=12,
            header_hash="snapshot-header-hash",
            header=["COL_A", "COL_B"],
            row_kind="dfp_documento",
            required_member=True,
            schema_status="ok",
            schema_message=None,
            delivery_index_role="header",
            lifecycle_status="processed",
        )
    )
    pending = PendingUpdate(
        fonte="dfp",
        ano=2025,
        status="change_detected",
        artifact_url="http://fake-cvm.gov.br/dfp_2025.zip",
        last_successful_run_id=previous_run.id,
    )
    db_session.add(pending)
    db_session.commit()

    mock_download.return_value = "ignored"
    mock_compute_sha.return_value = "snapshot-sha"
    mock_detect_enc.return_value = ("utf-8", ";")
    mock_get_header.return_value = ["COL_A", "COL_B"]
    mock_count_rows.return_value = 12
    dataset_mock = MagicMock()
    dataset_mock.render_member_name.return_value = "dfp_cia_aberta_2025.csv"
    dataset_mock.obrigatorio = True
    dataset_mock.row_kind = "dfp_documento"
    dataset_mock.delivery_index_role = "header"
    mock_listar_datasets.return_value = [dataset_mock]

    with patch("zipfile.ZipFile") as mock_zip:
        mock_zip.return_value.__enter__.return_value.namelist.return_value = ["dfp_cia_aberta_2025.csv"]
        analyzed = run_deep_analysis(db_session, pending.id)

    assert analyzed.status == "ready_for_ingestion"
    members = db_session.scalars(
        select(PendingUpdateMember).where(PendingUpdateMember.pending_update_id == pending.id)
    ).all()
    assert len(members) == 1
    assert members[0].change_category == "unchanged"
    assert members[0].status == "unchanged"
    assert members[0].previous_member_sha256 == "snapshot-sha"
    assert members[0].previous_header_hash == "snapshot-header-hash"


@patch("app.updates.service.download_file_to_disk")
@patch("app.updates.service.detect_encoding_and_delimiter")
@patch("app.updates.service.get_csv_header")
@patch("app.updates.service.count_csv_rows")
@patch("app.updates.service.listar_datasets")
@patch("app.updates.service.compute_file_sha256")
def test_deep_analysis_falls_back_to_ingestion_file_member_when_snapshot_absent(
    mock_compute_sha: MagicMock,
    mock_listar_datasets: MagicMock,
    mock_count_rows: MagicMock,
    mock_get_header: MagicMock,
    mock_detect_enc: MagicMock,
    mock_download: MagicMock,
    db_session: Session,
) -> None:
    previous_run = IngestionRun(tipo_fonte="dfp", ano=2025, status="sucesso", phase="complete")
    db_session.add(previous_run)
    db_session.flush()
    ingestion_file = IngestionFile(
        ingestion_run_id=previous_run.id,
        source_url="http://fake-cvm.gov.br/dfp_2025.zip",
        source_filename="dfp_2025.zip",
        content_sha256="artifact-sha",
        content_length_bytes=100,
        is_zip=True,
    )
    db_session.add(ingestion_file)
    db_session.flush()
    db_session.add(
        IngestionFileMember(
            ingestion_file_id=ingestion_file.id,
            member_name="dfp_cia_aberta_2025.csv",
            member_sha256="fallback-sha",
            member_size_bytes=100,
            encoding="utf-8",
            delimiter=";",
            header=["COL_A", "COL_B"],
            row_count=12,
            schema_status="ok",
            schema_message=None,
        )
    )
    pending = PendingUpdate(
        fonte="dfp",
        ano=2025,
        status="change_detected",
        artifact_url="http://fake-cvm.gov.br/dfp_2025.zip",
        last_successful_run_id=previous_run.id,
    )
    db_session.add(pending)
    db_session.commit()

    mock_download.return_value = "ignored"
    mock_compute_sha.return_value = "fallback-sha"
    mock_detect_enc.return_value = ("utf-8", ";")
    mock_get_header.return_value = ["COL_A", "COL_B"]
    mock_count_rows.return_value = 12
    dataset_mock = MagicMock()
    dataset_mock.render_member_name.return_value = "dfp_cia_aberta_2025.csv"
    dataset_mock.obrigatorio = True
    dataset_mock.row_kind = "dfp_documento"
    dataset_mock.delivery_index_role = "header"
    mock_listar_datasets.return_value = [dataset_mock]

    with patch("zipfile.ZipFile") as mock_zip:
        mock_zip.return_value.__enter__.return_value.namelist.return_value = ["dfp_cia_aberta_2025.csv"]
        analyzed = run_deep_analysis(db_session, pending.id)

    assert analyzed.status == "ready_for_ingestion"
    member = db_session.scalar(select(PendingUpdateMember).where(PendingUpdateMember.pending_update_id == pending.id))
    assert member is not None
    assert member.change_category == "unchanged"
    assert member.previous_member_sha256 == "fallback-sha"
    assert member.previous_header_hash is not None


@patch("app.updates.service.download_file_to_disk")
@patch("app.updates.service.detect_encoding_and_delimiter")
@patch("app.updates.service.get_csv_header")
@patch("app.updates.service.count_csv_rows")
@patch("app.updates.service.listar_datasets")
@patch("app.updates.service.compute_file_sha256")
def test_deep_analysis_removed_members_preserve_previous_snapshot_metadata(
    mock_compute_sha: MagicMock,
    mock_listar_datasets: MagicMock,
    mock_count_rows: MagicMock,
    mock_get_header: MagicMock,
    mock_detect_enc: MagicMock,
    mock_download: MagicMock,
    db_session: Session,
) -> None:
    previous_run = IngestionRun(tipo_fonte="dfp", ano=2025, status="sucesso", phase="complete")
    db_session.add(previous_run)
    db_session.flush()
    artifact_snapshot = SourceArtifactSnapshot(
        ingestion_run_id=previous_run.id,
        tipo_fonte="dfp",
        ano=2025,
        resource_url="http://fake-cvm.gov.br/dfp_2025.zip",
        source_filename="dfp_2025.zip",
        status="sucesso",
    )
    db_session.add(artifact_snapshot)
    db_session.flush()
    db_session.add(
        SourceMemberSnapshot(
            artifact_snapshot_id=artifact_snapshot.id,
            member_name="dfp_cia_aberta_old_2025.csv",
            member_sha256="old-sha",
            row_count=9,
            header_hash="old-header-hash",
            header=["A", "B"],
            row_kind="dfp_documento",
            required_member=False,
            schema_status="ok",
            schema_message=None,
            delivery_index_role="dependent",
            lifecycle_status="processed",
        )
    )
    pending = PendingUpdate(
        fonte="dfp",
        ano=2025,
        status="change_detected",
        artifact_url="http://fake-cvm.gov.br/dfp_2025.zip",
        last_successful_run_id=previous_run.id,
    )
    db_session.add(pending)
    db_session.commit()

    mock_download.return_value = "ignored"
    mock_compute_sha.return_value = "current-sha"
    mock_detect_enc.return_value = ("utf-8", ";")
    mock_get_header.return_value = ["A", "B"]
    mock_count_rows.return_value = 5
    dataset_mock = MagicMock()
    dataset_mock.render_member_name.return_value = "dfp_cia_aberta_new_2025.csv"
    dataset_mock.obrigatorio = True
    dataset_mock.row_kind = "dfp_documento"
    dataset_mock.delivery_index_role = "header"
    mock_listar_datasets.return_value = [dataset_mock]

    with patch("zipfile.ZipFile") as mock_zip:
        mock_zip.return_value.__enter__.return_value.namelist.return_value = ["dfp_cia_aberta_new_2025.csv"]
        run_deep_analysis(db_session, pending.id)

    removed_member = db_session.scalar(
        select(PendingUpdateMember).where(PendingUpdateMember.member_name == "dfp_cia_aberta_old_2025.csv")
    )
    assert removed_member is not None
    assert removed_member.change_category == "removed"
    assert removed_member.member_role == "dependent"
    assert removed_member.row_kind == "dfp_documento"
    assert removed_member.previous_member_sha256 == "old-sha"
    assert removed_member.previous_header_hash == "old-header-hash"


@patch("app.updates.service.download_file_to_disk")
@patch("app.updates.service.detect_encoding_and_delimiter")
@patch("app.updates.service.get_csv_header")
@patch("app.updates.service.count_csv_rows")
@patch("app.updates.service.listar_datasets")
def test_deep_analysis_cadastro_uses_previous_snapshot_without_false_added(
    mock_listar_datasets: MagicMock,
    mock_count_rows: MagicMock,
    mock_get_header: MagicMock,
    mock_detect_enc: MagicMock,
    mock_download: MagicMock,
    db_session: Session,
) -> None:
    previous_run = IngestionRun(tipo_fonte="cadastro", ano=None, status="sucesso", phase="complete")
    db_session.add(previous_run)
    db_session.flush()
    artifact_snapshot = SourceArtifactSnapshot(
        ingestion_run_id=previous_run.id,
        tipo_fonte="cadastro",
        ano=None,
        resource_url="http://fake-cvm.gov.br/a|http://fake-cvm.gov.br/b",
        source_filename="cad_cia_aberta.csv+cad_cia_estrang.csv",
        status="sucesso",
    )
    db_session.add(artifact_snapshot)
    db_session.flush()
    db_session.add_all(
        [
            SourceMemberSnapshot(
                artifact_snapshot_id=artifact_snapshot.id,
                member_name="cad_cia_aberta.csv",
                member_sha256="sha-aberta",
                row_count=2675,
                header_hash="hash-aberta",
                header=["CNPJ_CIA", "CD_CVM"],
                row_kind="cadastro_registro_cvm",
                required_member=True,
                schema_status="ok",
                schema_message=None,
                delivery_index_role="none",
                lifecycle_status="processed",
            ),
            SourceMemberSnapshot(
                artifact_snapshot_id=artifact_snapshot.id,
                member_name="cad_cia_estrang.csv",
                member_sha256="sha-estrang",
                row_count=26,
                header_hash="hash-estrang",
                header=["CNPJ", "CD_CVM"],
                row_kind="cadastro_registro_cvm",
                required_member=True,
                schema_status="ok",
                schema_message=None,
                delivery_index_role="none",
                lifecycle_status="processed",
            ),
        ]
    )
    pending = PendingUpdate(
        fonte="cadastro",
        ano=None,
        status="change_detected",
        artifact_url="http://fake-cvm.gov.br/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv|http://fake-cvm.gov.br/CIA_ESTRANG/CAD/DADOS/cad_cia_estrang.csv",
        last_successful_run_id=previous_run.id,
    )
    db_session.add(pending)
    db_session.commit()

    mock_download.side_effect = ["sha-aberta", "sha-estrang"]
    mock_detect_enc.return_value = ("utf-8", ";")
    mock_get_header.side_effect = [["CNPJ_CIA", "CD_CVM"], ["CNPJ", "CD_CVM"]]
    mock_count_rows.side_effect = [2675, 26]
    aberta_dataset = MagicMock()
    aberta_dataset.render_member_name.side_effect = lambda ano=None: "cad_cia_aberta.csv"
    aberta_dataset.obrigatorio = True
    aberta_dataset.row_kind = "cadastro_registro_cvm"
    aberta_dataset.delivery_index_role = "none"
    estrang_dataset = MagicMock()
    estrang_dataset.render_member_name.side_effect = lambda ano=None: "cad_cia_estrang.csv"
    estrang_dataset.obrigatorio = True
    estrang_dataset.row_kind = "cadastro_registro_cvm"
    estrang_dataset.delivery_index_role = "none"
    mock_listar_datasets.return_value = [aberta_dataset, estrang_dataset]

    analyzed = run_deep_analysis(db_session, pending.id)

    assert analyzed.status == "ready_for_ingestion"
    assert analyzed.change_summary is not None
    assert analyzed.change_summary["members_added"] == []
    members = db_session.scalars(
        select(PendingUpdateMember)
        .where(PendingUpdateMember.pending_update_id == pending.id)
        .order_by(PendingUpdateMember.member_name.asc())
    ).all()
    assert [member.change_category for member in members] == ["unchanged", "unchanged"]


@patch("app.worker.tasks.sincronizar_dfp_task.delay")
def test_trigger_and_discard_updates(mock_dfp_delay: MagicMock, db_session: Session) -> None:
    pending = PendingUpdate(
        fonte="dfp",
        ano=2025,
        status="ready_for_ingestion",
        artifact_url="http://fake-cvm.gov.br/dfp_2025.zip",
    )
    db_session.add(pending)
    db_session.commit()

    # Trigger update
    mock_dfp_delay.return_value = MagicMock(id="task-uuid-123")
    task_id = trigger_update(db_session, pending.id, user="tester")
    
    assert task_id == "task-uuid-123"
    assert pending.status == "triggered"
    assert pending.resolved_by == "tester"
    assert pending.resolved_timestamp is not None

    # Discard update
    pending_discard = PendingUpdate(
        fonte="itr",
        ano=2025,
        status="ready_for_ingestion",
        artifact_url="http://fake-cvm.gov.br/itr_2025.zip",
    )
    db_session.add(pending_discard)
    db_session.commit()

    discarded = discard_update(db_session, pending_discard.id)
    assert discarded.status == "discarded"
    assert discarded.resolved_timestamp is not None


def test_session_management_flow(db_session: Session) -> None:
    pending = PendingUpdate(
        fonte="dfp",
        ano=2025,
        status="ready_for_ingestion",
        artifact_url="http://fake-cvm.gov.br/dfp_2025.zip",
    )
    db_session.add(pending)
    db_session.commit()

    # Create session
    sess = create_session(db_session, user_id="tester")
    assert sess.status == "active"
    assert sess.session_key is not None

    # Add item
    item = add_session_item(db_session, sess.session_key, pending.id)
    assert item.pending_update_id == pending.id
    assert item.action == "selected"

    # Remove item
    remove_session_item(db_session, sess.session_key, pending.id)
    stmt_item = select(UpdateSessionItem).where(UpdateSessionItem.session_id == sess.id)
    assert db_session.scalar(stmt_item) is None


# --- FastAPI Router Endpoint Tests ---

def test_api_scanner_endpoints(client: TestClient, auth_headers: dict[str, str], db_session: Session) -> None:
    # 1. Get status
    res = client.get("/updates/scanner/status", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["status"] == "idle"

    with patch("app.updates.router.run_daily_scanner_task.delay") as mock_delay:
        mock_delay.return_value = MagicMock(id="scanner-task-1")
        res_run = client.post("/updates/scanner/run", headers=auth_headers)
        assert res_run.status_code == 200
        payload = res_run.json()
        assert payload["status"] == "queued"
        assert payload["task_id"] == "scanner-task-1"
        assert "scan_run_id" in payload
        persisted = db_session.get(UpdateScanRun, uuid.UUID(payload["scan_run_id"]))
        assert persisted is not None

    scan_run = create_scan_run(db_session)
    scan_run.status = "completed"
    scan_run.summary = {"scanned_scopes": 1, "items": []}
    db_session.commit()

    res_latest = client.get("/updates/scanner/runs/latest", headers=auth_headers)
    assert res_latest.status_code == 200
    assert res_latest.json()["id"] == str(scan_run.id)
    assert res_latest.json()["summary"]["scanned_scopes"] == 1

    res_detail = client.get(f"/updates/scanner/runs/{scan_run.id}", headers=auth_headers)
    assert res_detail.status_code == 200
    assert res_detail.json()["id"] == str(scan_run.id)

    # 2. History
    pending = PendingUpdate(
        fonte="dfp",
        ano=2025,
        status="change_detected",
        artifact_url="http://fake-cvm.gov.br/dfp_2025.zip",
    )
    db_session.add(pending)
    db_session.commit()

    res_hist = client.get("/updates/scanner/history", headers=auth_headers)
    assert res_hist.status_code == 200
    assert len(res_hist.json()) >= 1
    assert res_hist.json()[0]["fonte"] == "dfp"


def test_service_create_and_get_latest_scan_run(db_session: Session) -> None:
    create_scan_run(db_session)
    second = create_scan_run(db_session)

    latest = get_latest_scan_run(db_session)

    assert latest is not None
    assert latest.id == second.id


def test_api_pending_endpoints(client: TestClient, auth_headers: dict[str, str], db_session: Session) -> None:
    pending = PendingUpdate(
        fonte="dfp",
        ano=2025,
        status="ready_for_ingestion",
        artifact_url="http://fake-cvm.gov.br/dfp_2025.zip",
    )
    db_session.add(pending)
    db_session.commit()

    # List pending
    res = client.get("/updates/pending", headers=auth_headers)
    assert res.status_code == 200
    assert len(res.json()) >= 1
    
    # Get pending details
    res_detail = client.get(f"/updates/pending/{pending.id}", headers=auth_headers)
    assert res_detail.status_code == 200
    assert res_detail.json()["fonte"] == "dfp"

    # Trigger via API
    with patch("app.updates.router.trigger_update") as mock_trig:
        mock_trig.return_value = "celery-task-id-abc"
        res_trig = client.post(f"/updates/pending/{pending.id}/trigger", headers=auth_headers)
        assert res_trig.status_code == 200
        assert res_trig.json()["status"] == "triggered"
        assert res_trig.json()["task_id"] == "celery-task-id-abc"


def test_api_session_endpoints(client: TestClient, auth_headers: dict[str, str], db_session: Session) -> None:
    pending = PendingUpdate(
        fonte="dfp",
        ano=2025,
        status="ready_for_ingestion",
        artifact_url="http://fake-cvm.gov.br/dfp_2025.zip",
    )
    db_session.add(pending)
    db_session.commit()

    # Create session
    res_sess = client.post("/updates/session", headers=auth_headers)
    assert res_sess.status_code == 200
    key = res_sess.json()["session_key"]

    # Add item to session
    res_item = client.post(f"/updates/session/{key}/items?pending_update_id={pending.id}", headers=auth_headers)
    assert res_item.status_code == 200
    assert res_item.json()["pending_update_id"] == str(pending.id)

    # Get session details
    res_get = client.get(f"/updates/session/{key}", headers=auth_headers)
    assert res_get.status_code == 200
    assert len(res_get.json()["items"]) == 1

    # Remove item from session
    res_del = client.delete(f"/updates/session/{key}/items/{pending.id}", headers=auth_headers)
    assert res_del.status_code == 204
