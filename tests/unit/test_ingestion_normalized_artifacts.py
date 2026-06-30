import csv
import tempfile

import pytest

from app.core.config import get_settings
from app.services.ingestion.normalized_artifacts import (
    NormalizedArtifactWriter,
    iter_normalized_artifact_rows,
)


def test_normalized_artifact_writer_persists_typed_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        monkeypatch.setattr(get_settings(), "storage_dir", tmp_dir)
        writer = NormalizedArtifactWriter(
            run_id="run-1",
            member_id="member-1",
            member_name="itr_cia_aberta_BPA_con_2026.csv",
            row_kind="itr_demonstracao",
        )

        writer.write_row(
            {
                "row_kind": "itr_demonstracao",
                "linha_origem": 2,
                "arquivo_origem": "itr_cia_aberta_BPA_con_2026.csv",
                "ano_origem": 2026,
                "companhia_id": 123,
                "normalized_hash": "abc",
                "natural_key": {"codigo_conta": "1.01"},
                "valor": "100.55",
            }
        )
        metadata = writer.close()

        assert metadata["role"] == "normalized_typed_csv"
        assert metadata["content_type"] == "text/csv"
        assert metadata["row_count"] == 1
        with open(metadata["uri"], encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle, delimiter=";"))
        assert rows[0]["arquivo_origem"] == "itr_cia_aberta_BPA_con_2026.csv"
        assert rows[0]["companhia_id"] == "123"
        assert rows[0]["natural_key"] == '{"codigo_conta": "1.01"}'


def test_normalized_artifact_writer_rejects_parquet_without_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        monkeypatch.setattr(get_settings(), "storage_dir", tmp_dir)
        with pytest.raises(RuntimeError, match="pyarrow"):
            NormalizedArtifactWriter(
                run_id="run-1",
                member_id="member-1",
                member_name="itr_cia_aberta_BPA_con_2026.csv",
                row_kind="itr_demonstracao",
                artifact_format="parquet",
            )


def test_iter_normalized_artifact_rows_reads_typed_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        monkeypatch.setattr(get_settings(), "storage_dir", tmp_dir)
        writer = NormalizedArtifactWriter(
            run_id="run-1",
            member_id="member-1",
            member_name="itr_cia_aberta_BPA_con_2026.csv",
            row_kind="itr_demonstracao",
        )
        writer.write_row(
            {
                "row_kind": "itr_demonstracao",
                "linha_origem": 2,
                "arquivo_origem": "itr_cia_aberta_BPA_con_2026.csv",
                "ano_origem": 2026,
                "normalized_hash": "abc",
            }
        )
        metadata = writer.close()

        rows = list(iter_normalized_artifact_rows(artifact_uri=metadata["uri"]))

        assert rows == [
            {
                "ano_origem": "2026",
                "arquivo_origem": "itr_cia_aberta_BPA_con_2026.csv",
                "linha_origem": "2",
                "normalized_hash": "abc",
                "row_kind": "itr_demonstracao",
            }
        ]
