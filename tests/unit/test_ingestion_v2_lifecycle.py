import io
import tempfile
import uuid
import zipfile
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.db.base import Base
from app.models import (  # noqa: F401
    cgvn,
    financeiro,
    fre,
    identidade,
    ingestion,
    ipe,
    sincronizacao,
    usuario,
    vlmo,
)
from app.models.companhia import Companhia
from app.models.identidade import CompanhiaIdentificador
from app.models.ingestion import (
    IngestionFileMember,
    IngestionPhaseExecution,
    IngestionRow,
    SourceArtifactSnapshot,
    SourceDeliverySnapshot,
    SourceMemberSnapshot,
)
from app.models.ipe import IpeDocumento
from app.services.ingestion.acquisition import probe_remote_source
from app.services.ingestion.change_tracking import reconcile_promoted_rows
from app.services.ingestion.ipe import sincronizar_ipe
from app.services.ingestion.normalized_artifacts import NormalizedArtifactWriter
from app.services.ingestion.staging import create_run, register_file, stage_csv_payload_streaming


def _session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    local_session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return local_session()


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
        hash_origem="companhia-lifecycle",
        criado_em=agora,
        sincronizado_em=agora,
        alterado_em=agora,
    )


def _add_identifiers(session: Session, companhia: Companhia) -> None:
    session.add_all(
        [
            CompanhiaIdentificador(
                companhia_id=companhia.id,
                tipo="cnpj",
                valor="00000000000191",
                valor_normalizado="00000000000191",
                fonte="cad_cia_aberta",
                confianca="alta",
                ativo=True,
            ),
            CompanhiaIdentificador(
                companhia_id=companhia.id,
                tipo="codigo_cvm",
                valor="1023",
                valor_normalizado="1023",
                fonte="cad_cia_aberta",
                confianca="alta",
                ativo=True,
            ),
        ]
    )
    session.flush()


def _ipe_zip(*, protocolo: str = "123456", assunto: str = "Assunto X") -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zip_file:
        zip_file.writestr(
            "ipe_cia_aberta_2025.csv",
            (
                "CNPJ_Companhia;Nome_Companhia;Codigo_CVM;Data_Referencia;Categoria;Tipo;Especie;Assunto;"
                "Data_Entrega;Tipo_Apresentacao;Protocolo_Entrega;Versao;Link_Download\n"
                f"00.000.000/0001-91;Banco do Brasil S.A.;1023;2025-01-01;Categoria X;Tipo X;Especie X;{assunto};"
                f"2025-01-15;Apresentacao;{protocolo};1;http://ipe\n"
            ).encode("latin1"),
        )
    return buffer.getvalue()


def test_probe_remote_source_does_not_skip_on_content_length_only(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _session()
    try:
        previous_run = create_run(session, tipo_fonte="dfp", ano=2025, status="sucesso", phase="complete")
        register_file(
            session,
            ingestion_run=previous_run,
            source_url="https://example.test/dfp.zip",
            source_filename="dfp.zip",
            content_sha256="abc",
            content_length_bytes=1024,
        )
        current_run = create_run(session, tipo_fonte="dfp", ano=2025, status="em_execucao", phase="acquire")
        session.commit()

        monkeypatch.setattr(
            "app.services.ingestion.acquisition._fetch_ckan_package_metadata",
            lambda *args, **kwargs: None,
        )
        monkeypatch.setattr(
            "app.services.ingestion.acquisition._head_remote_resource",
            lambda *args, **kwargs: {
                "source_url": "https://example.test/dfp.zip",
                "probe_sources": ["head"],
                "resource_etag": None,
                "resource_last_modified": None,
                "resource_content_length": "1024",
                "resource_http_status_code": 200,
            },
        )

        probe = probe_remote_source(
            session,
            run=current_run,
            tipo_fonte="dfp",
            ano=2025,
            source_url="https://example.test/dfp.zip",
        )

        assert probe["decision"] == "unknown"
        assert probe["download_required"] is True
        assert probe["confidence"] == "unknown"
    finally:
        session.close()


def test_stage_csv_payload_streaming_atualiza_heartbeat_em_fronteiras_de_chunk() -> None:
    session = _session()
    try:
        run = create_run(session, tipo_fonte="ipe", ano=2025, status="em_execucao", phase="stage")
        ingestion_file = register_file(
            session,
            ingestion_run=run,
            source_url="https://example.test/ipe.zip",
            source_filename="ipe_cia_aberta_2025.zip",
            payload=b"fake",
            is_zip=True,
        )
        session.flush()
        phase = session.scalar(select(IngestionPhaseExecution).where(IngestionPhaseExecution.ingestion_run_id == run.id))
        assert phase is not None
        heartbeat_anterior = datetime.now(UTC) - timedelta(hours=1)
        phase.heartbeat_at = heartbeat_anterior
        session.commit()

        payload = (
            "CNPJ_Companhia;Nome_Companhia;Codigo_CVM\n"
            "00.000.000/0001-91;Banco do Brasil;1023\n"
            "00.000.000/0001-91;Banco do Brasil;1023\n"
        ).encode("latin1")
        stage_csv_payload_streaming(
            session,
            ingestion_run=run,
            ingestion_file=ingestion_file,
            payload=payload,
            member_name="ipe_cia_aberta_2025.csv",
            arquivo_origem="ipe_cia_aberta_2025.csv",
            ano_origem=2025,
            row_kind="ipe_documento",
            chunk_size=1,
        )

        phase_atualizada = session.scalar(select(IngestionPhaseExecution).where(IngestionPhaseExecution.ingestion_run_id == run.id))
        assert phase_atualizada is not None
        assert phase_atualizada.heartbeat_at is not None
        assert phase_atualizada.heartbeat_at > heartbeat_anterior
        assert phase_atualizada.metrics is not None
        assert phase_atualizada.metrics["staged_rows"] == 2
    finally:
        session.close()


def test_reconcile_promoted_rows_deletes_stale_rows_without_persisting_transient_hashes() -> None:
    session = _session()
    try:
        run = create_run(session, tipo_fonte="ipe", ano=2025)
        ingestion_file = register_file(
            session,
            ingestion_run=run,
            source_url="https://example.test/ipe.zip",
            source_filename="ipe_cia_aberta_2025.zip",
            payload=b"fake",
            is_zip=True,
        )
        member = IngestionFileMember(
            ingestion_file_id=ingestion_file.id,
            member_name="ipe_cia_aberta_2025.csv",
            member_sha256="member-hash",
            member_size_bytes=123,
            encoding="utf-8",
            delimiter=";",
            header=["COLUNA"],
            row_count=1,
            schema_status="ok",
        )
        session.add(member)
        company = _companhia()
        session.add(company)
        session.flush()
        session.add(
            IngestionRow(
                id=uuid.uuid4(),
                ingestion_run_id=run.id,
                ingestion_file_member_id=member.id,
                arquivo_origem="ipe_cia_aberta_2025.csv",
                ano_origem=2025,
                linha_origem=2,
                raw_data={"COLUNA": "valor"},
                raw_hash="raw-hash",
                row_kind="ipe_documento",
                validation_status="valid",
                normalized_hash="hash-a",
            )
        )
        current = IpeDocumento(
            companhia_id=company.id,
            cnpj_companhia="00000000000191",
            codigo_cvm=1023,
            nome_companhia="Banco do Brasil",
            data_referencia=date(2025, 1, 1),
            categoria="Categoria X",
            tipo="Tipo X",
            especie="Especie X",
            assunto="Atual",
            data_entrega=date(2025, 1, 15),
            tipo_apresentacao="Apresentacao",
            protocolo_entrega="123",
            versao=1,
            link_download="http://ipe/1",
            arquivo_origem="ipe_cia_aberta_2025.csv",
            ano_origem=2025,
            linha_origem=2,
            hash_origem="hash-a",
        )
        stale = IpeDocumento(
            companhia_id=company.id,
            cnpj_companhia="00000000000191",
            codigo_cvm=1023,
            nome_companhia="Banco do Brasil",
            data_referencia=date(2025, 1, 1),
            categoria="Categoria X",
            tipo="Tipo Y",
            especie="Especie X",
            assunto="Obsoleto",
            data_entrega=date(2025, 1, 15),
            tipo_apresentacao="Apresentacao",
            protocolo_entrega="456",
            versao=1,
            link_download="http://ipe/2",
            arquivo_origem="ipe_cia_aberta_2025.csv",
            ano_origem=2025,
            linha_origem=3,
            hash_origem="hash-b",
        )
        session.add_all([current, stale])
        session.commit()

        deleted = reconcile_promoted_rows(
            session,
            model=IpeDocumento,
            ingestion_run_id=run.id,
            ingestion_file_member_id=member.id,
            arquivo_origem="ipe_cia_aberta_2025.csv",
            ano_origem=2025,
            row_kinds={"ipe_documento"},
        )
        session.commit()

        assert deleted == 1
        assert session.scalar(select(IpeDocumento).where(IpeDocumento.hash_origem == "hash-a")) is not None
        assert session.scalar(select(IpeDocumento).where(IpeDocumento.hash_origem == "hash-b")) is None
    finally:
        session.close()


def test_reconcile_promoted_rows_can_use_normalized_artifact_hashes(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _session()
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            monkeypatch.setattr(get_settings(), "storage_dir", tmp_dir)
            run = create_run(session, tipo_fonte="ipe", ano=2025)
            ingestion_file = register_file(
                session,
                ingestion_run=run,
                source_url="https://example.test/ipe.zip",
                source_filename="ipe_cia_aberta_2025.zip",
                payload=b"fake",
                is_zip=True,
            )
            member = IngestionFileMember(
                ingestion_file_id=ingestion_file.id,
                member_name="ipe_cia_aberta_2025.csv",
                member_sha256="member-hash",
                member_size_bytes=123,
                encoding="utf-8",
                delimiter=";",
                header=["COLUNA"],
                row_count=1,
                schema_status="ok",
            )
            session.add(member)
            company = _companhia()
            session.add(company)
            session.flush()

            writer = NormalizedArtifactWriter(
                run_id=str(run.id),
                member_id=str(member.id),
                member_name=member.member_name,
                row_kind="ipe_documento",
            )
            writer.write_row(
                {
                    "normalized_hash": "hash-a",
                    "arquivo_origem": "ipe_cia_aberta_2025.csv",
                    "linha_origem": 2,
                }
            )
            artifact = writer.close()

            current = IpeDocumento(
                companhia_id=company.id,
                cnpj_companhia="00000000000191",
                codigo_cvm=1023,
                nome_companhia="Banco do Brasil",
                data_referencia=date(2025, 1, 1),
                categoria="Categoria X",
                tipo="Tipo X",
                especie="Especie X",
                assunto="Atual",
                data_entrega=date(2025, 1, 15),
                tipo_apresentacao="Apresentacao",
                protocolo_entrega="123",
                versao=1,
                link_download="http://ipe/1",
                arquivo_origem="ipe_cia_aberta_2025.csv",
                ano_origem=2025,
                linha_origem=2,
                hash_origem="hash-a",
            )
            stale = IpeDocumento(
                companhia_id=company.id,
                cnpj_companhia="00000000000191",
                codigo_cvm=1023,
                nome_companhia="Banco do Brasil",
                data_referencia=date(2025, 1, 1),
                categoria="Categoria X",
                tipo="Tipo Y",
                especie="Especie X",
                assunto="Obsoleto",
                data_entrega=date(2025, 1, 15),
                tipo_apresentacao="Apresentacao",
                protocolo_entrega="456",
                versao=1,
                link_download="http://ipe/2",
                arquivo_origem="ipe_cia_aberta_2025.csv",
                ano_origem=2025,
                linha_origem=3,
                hash_origem="hash-b",
            )
            session.add_all([current, stale])
            session.commit()

            deleted = reconcile_promoted_rows(
                session,
                model=IpeDocumento,
                ingestion_run_id=run.id,
                ingestion_file_member_id=member.id,
                arquivo_origem="ipe_cia_aberta_2025.csv",
                ano_origem=2025,
                row_kinds={"ipe_documento"},
                normalized_artifact_uri=str(artifact["uri"]),
            )
            session.commit()

            assert deleted == 1
            assert session.scalar(select(IpeDocumento).where(IpeDocumento.hash_origem == "hash-a")) is not None
            assert session.scalar(select(IpeDocumento).where(IpeDocumento.hash_origem == "hash-b")) is None
    finally:
        session.close()


def test_sync_persists_lifecycle_snapshots_for_delivery_index() -> None:
    session = _session()
    try:
        companhia = _companhia()
        session.add(companhia)
        session.flush()
        _add_identifiers(session, companhia)
        session.commit()

        result = sincronizar_ipe(session, 2025, downloader=lambda _: _ipe_zip())

        assert result["status"] == "sucesso"
        artifact = session.scalar(select(SourceArtifactSnapshot))
        member = session.scalar(select(SourceMemberSnapshot))
        delivery = session.scalar(select(SourceDeliverySnapshot))

        assert artifact is not None
        assert artifact.tipo_fonte == "ipe"
        assert artifact.status == "sucesso"
        assert member is not None
        assert member.member_name == "ipe_cia_aberta_2025.csv"
        assert member.lifecycle_status == "processed"
        assert delivery is not None
        assert delivery.protocolo_entrega == "123456"
        assert delivery.versao == "1"
    finally:
        session.close()
