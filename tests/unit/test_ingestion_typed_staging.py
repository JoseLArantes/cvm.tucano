import tempfile
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.db.base import Base
from app.models import companhia, ingestion  # noqa: F401
from app.models.companhia import Companhia
from app.models.financeiro import DocumentoFinanceiro
from app.models.ingestion import IngestionFile, IngestionFileMember, IngestionFinanceiroStageRow, IngestionRun
from app.services.ingestion.financeiro import (
    _filtrar_payload_promocao_por_modelo,
    _promote_financeiro_member_from_stage,
)
from app.services.ingestion.normalized_artifacts import NormalizedArtifactWriter
from app.services.ingestion.typed_staging import load_financeiro_artifact_to_stage


def _session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    local_session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return local_session()


def test_load_financeiro_artifact_to_stage_persists_typed_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _session()
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            monkeypatch.setattr(get_settings(), "storage_dir", tmp_dir)
            run = IngestionRun(
                id=uuid.uuid4(),
                tipo_fonte="itr",
                ano=2026,
                status="em_execucao",
                phase="promote",
                started_at=datetime.now(UTC),
            )
            session.add(run)
            session.flush()
            ingestion_file = IngestionFile(
                id=uuid.uuid4(),
                ingestion_run_id=run.id,
                source_url="https://example.test/itr.zip",
                source_filename="itr_cia_aberta_2026.zip",
                content_sha256="zip-hash",
                content_length_bytes=10,
                is_zip=True,
                already_seen_success=False,
            )
            session.add(ingestion_file)
            session.flush()
            member = IngestionFileMember(
                id=uuid.uuid4(),
                ingestion_file_id=ingestion_file.id,
                member_name="itr_cia_aberta_BPA_con_2026.csv",
                member_sha256="member-hash",
                member_size_bytes=100,
                encoding="utf-8",
                delimiter=";",
                header=["row_kind"],
                row_count=1,
                schema_status="ok",
            )
            session.add(member)
            session.flush()

            writer = NormalizedArtifactWriter(
                run_id=str(run.id),
                member_id=str(member.id),
                member_name=member.member_name,
                row_kind="itr_demonstracao",
            )
            writer.write_row(
                {
                    "row_kind": "itr_demonstracao",
                    "linha_origem": 2,
                    "arquivo_origem": member.member_name,
                    "ano_origem": 2026,
                    "companhia_id": "",
                    "normalized_hash": "hash-a",
                    "natural_key": {"codigo_conta": "1.01"},
                    "tipo_formulario": "ITR",
                    "cnpj_companhia": "00000000000191",
                    "codigo_cvm": 1023,
                    "data_referencia": "2026-03-31",
                    "versao": 1,
                    "denominacao_companhia": "Banco do Brasil",
                    "tipo_demonstracao": "BPA",
                    "escopo_demonstracao": "consolidado",
                    "grupo_demonstracao": "DF Consolidado",
                    "moeda": "BRL",
                    "escala_moeda": "MIL",
                    "ordem_exercicio": "ULT",
                    "data_inicio_exercicio": "2026-01-01",
                    "data_fim_exercicio": "2026-03-31",
                    "codigo_conta": "1.01",
                    "coluna_df": "valor",
                    "descricao_conta": "Caixa",
                    "valor_conta": "100.50",
                    "conta_fixa": "true",
                }
            )
            artifact = writer.close()

            load_result = load_financeiro_artifact_to_stage(
                session,
                ingestion_run_id=run.id,
                ingestion_file_member_id=member.id,
                artifact_uri=str(artifact["uri"]),
                use_copy=False,
            )
            session.commit()

            row = session.scalar(select(IngestionFinanceiroStageRow))

            assert load_result.rows_loaded == 1
            assert load_result.rows_replaced == 0
            assert load_result.bytes_loaded > 0
            assert load_result.copy_used is False
            assert row is not None
            assert row.row_kind == "itr_demonstracao"
            assert row.cnpj_companhia == "00000000000191"
            assert row.codigo_cvm == 1023
            assert row.escala_moeda == "MIL"
            assert str(row.valor_conta) == "100.5000000000"
            assert row.natural_key == {"codigo_conta": "1.01"}
    finally:
        session.close()


def test_load_financeiro_artifact_to_stage_replaces_previous_member_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _session()
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            monkeypatch.setattr(get_settings(), "storage_dir", tmp_dir)
            run = IngestionRun(
                id=uuid.uuid4(),
                tipo_fonte="itr",
                ano=2026,
                status="em_execucao",
                phase="promote",
                started_at=datetime.now(UTC),
            )
            session.add(run)
            session.flush()
            ingestion_file = IngestionFile(
                id=uuid.uuid4(),
                ingestion_run_id=run.id,
                source_url="https://example.test/itr.zip",
                source_filename="itr_cia_aberta_2026.zip",
                content_sha256="zip-hash",
                content_length_bytes=10,
                is_zip=True,
                already_seen_success=False,
            )
            session.add(ingestion_file)
            session.flush()
            member = IngestionFileMember(
                id=uuid.uuid4(),
                ingestion_file_id=ingestion_file.id,
                member_name="itr_cia_aberta_BPA_con_2026.csv",
                member_sha256="member-hash",
                member_size_bytes=100,
                encoding="utf-8",
                delimiter=";",
                header=["row_kind"],
                row_count=1,
                schema_status="ok",
            )
            session.add(member)
            session.flush()

            first_writer = NormalizedArtifactWriter(
                run_id=str(run.id),
                member_id=str(member.id),
                member_name=member.member_name,
                row_kind="itr_documento",
            )
            first_writer.write_row(
                {
                    "row_kind": "itr_documento",
                    "linha_origem": 2,
                    "arquivo_origem": member.member_name,
                    "ano_origem": 2026,
                    "normalized_hash": "hash-a",
                    "tipo_formulario": "ITR",
                }
            )
            first_artifact = first_writer.close()
            first_load = load_financeiro_artifact_to_stage(
                session,
                ingestion_run_id=run.id,
                ingestion_file_member_id=member.id,
                artifact_uri=str(first_artifact["uri"]),
                use_copy=False,
            )

            second_writer = NormalizedArtifactWriter(
                run_id=str(run.id),
                member_id=str(member.id),
                member_name=member.member_name,
                row_kind="itr_documento",
            )
            second_writer.write_row(
                {
                    "row_kind": "itr_documento",
                    "linha_origem": 3,
                    "arquivo_origem": member.member_name,
                    "ano_origem": 2026,
                    "normalized_hash": "hash-b",
                    "tipo_formulario": "ITR",
                }
            )
            second_artifact = second_writer.close()
            second_load = load_financeiro_artifact_to_stage(
                session,
                ingestion_run_id=run.id,
                ingestion_file_member_id=member.id,
                artifact_uri=str(second_artifact["uri"]),
                use_copy=False,
            )
            session.commit()

            assert first_load.rows_loaded == 1
            assert first_load.rows_replaced == 0
            assert second_load.rows_loaded == 1
            assert second_load.rows_replaced == 1
            rows = list(
                session.execute(
                    select(IngestionFinanceiroStageRow).order_by(IngestionFinanceiroStageRow.linha_origem.asc())
                ).scalars()
            )

            assert len(rows) == 1
            assert rows[0].normalized_hash == "hash-b"
            assert rows[0].linha_origem == 3
    finally:
        session.close()


def test_promote_financeiro_member_from_stage_inserts_documentos(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _session()
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            monkeypatch.setattr(get_settings(), "storage_dir", tmp_dir)
            run = IngestionRun(
                id=uuid.uuid4(),
                tipo_fonte="itr",
                ano=2026,
                status="em_execucao",
                phase="promote",
                started_at=datetime.now(UTC),
            )
            session.add(run)
            session.flush()
            company = Companhia(
                id=uuid.uuid4(),
                cnpj_companhia="00000000000191",
                codigo_cvm=1023,
                denominacao_social="Banco do Brasil",
                denominacao_comercial="Banco do Brasil",
                situacao_registro="ATIVA",
                data_registro=datetime(2020, 1, 1, tzinfo=UTC).date(),
                data_constituicao=datetime(1908, 10, 12, tzinfo=UTC).date(),
                data_inicio_situacao=datetime(2020, 1, 1, tzinfo=UTC).date(),
                setor_atividade="Bancos",
                tipo_mercado="Categoria A",
                categoria_registro="Categoria A",
                data_inicio_categoria=datetime(2020, 1, 1, tzinfo=UTC).date(),
                situacao_emissor="ATIVO",
                data_inicio_situacao_emissor=datetime(2020, 1, 1, tzinfo=UTC).date(),
                controle_acionario="ESTATAL",
                endereco={"municipio": "Brasilia"},
                responsavel={"nome_responsavel": "Fulano"},
                auditor="KPMG",
                cnpj_auditor="57755217001281",
                arquivo_origem="cad.csv",
                ano_origem=None,
                linha_origem=2,
                hash_origem="companhia-hash",
                criado_em=datetime.now(UTC),
                sincronizado_em=datetime.now(UTC),
                alterado_em=datetime.now(UTC),
            )
            session.add(company)
            session.flush()
            ingestion_file = IngestionFile(
                id=uuid.uuid4(),
                ingestion_run_id=run.id,
                source_url="https://example.test/itr.zip",
                source_filename="itr_cia_aberta_2026.zip",
                content_sha256="zip-hash",
                content_length_bytes=10,
                is_zip=True,
                already_seen_success=False,
            )
            session.add(ingestion_file)
            session.flush()
            member = IngestionFileMember(
                id=uuid.uuid4(),
                ingestion_file_id=ingestion_file.id,
                member_name="itr_cia_aberta_2026.csv",
                member_sha256="member-hash",
                member_size_bytes=100,
                encoding="utf-8",
                delimiter=";",
                header=["row_kind"],
                row_count=1,
                schema_status="ok",
            )
            session.add(member)
            session.flush()

            writer = NormalizedArtifactWriter(
                run_id=str(run.id),
                member_id=str(member.id),
                member_name=member.member_name,
                row_kind="itr_documento",
            )
            writer.write_row(
                {
                    "row_kind": "itr_documento",
                    "linha_origem": 2,
                    "arquivo_origem": member.member_name,
                    "ano_origem": 2026,
                    "companhia_id": str(company.id),
                    "normalized_hash": "hash-doc",
                    "natural_key": {"id_documento": 123},
                    "tipo_formulario": "ITR",
                    "cnpj_companhia": "00000000000191",
                    "codigo_cvm": 1023,
                    "data_referencia": "2026-03-31",
                    "versao": 1,
                    "denominacao_companhia": "Banco do Brasil",
                    "categoria_documento": "ITR",
                    "id_documento": 123,
                    "data_recebimento": "2026-04-01",
                    "link_documento": "http://exemplo",
                }
            )
            artifact = writer.close()
            load_financeiro_artifact_to_stage(
                session,
                ingestion_run_id=run.id,
                ingestion_file_member_id=member.id,
                artifact_uri=str(artifact["uri"]),
                use_copy=False,
            )

            contadores = {"inseridos": 0, "atualizados": 0, "inalterados": 0, "rejeitados": 0}
            _promote_financeiro_member_from_stage(
                session,
                member_id=member.id,
                execucao_id=uuid.uuid4(),
                contadores=contadores,
                chunk_size=100,
            )
            session.commit()

            documento = session.scalar(select(DocumentoFinanceiro))

            assert documento is not None
            assert documento.id_documento == 123
            assert documento.companhia_id == company.id
            assert contadores["inseridos"] == 1
    finally:
        session.close()


def test_filtrar_payload_promocao_financeiro_remove_colunas_estranhas_por_modelo() -> None:
    payload = {
        "tipo_formulario": "DFP",
        "id_documento": 123,
        "versao": 1,
        "data_referencia": "2025-12-31",
        "categoria_documento": "Categoria X",
        "tipo_demonstracao": "DRE",
        "escopo_demonstracao": "consolidado",
        "codigo_conta": "1.01",
        "valor_conta": "100.00",
        "arquivo_origem": "dfp_cia_aberta_2025.csv",
    }

    filtrado = _filtrar_payload_promocao_por_modelo(DocumentoFinanceiro, payload)

    assert "tipo_formulario" in filtrado
    assert "id_documento" in filtrado
    assert "categoria_documento" in filtrado
    assert "arquivo_origem" in filtrado
    assert "tipo_demonstracao" not in filtrado
    assert "escopo_demonstracao" not in filtrado
    assert "codigo_conta" not in filtrado
    assert "valor_conta" not in filtrado
