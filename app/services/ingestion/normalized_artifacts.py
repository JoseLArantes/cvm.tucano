from __future__ import annotations

import csv
import hashlib
import json
from collections.abc import Iterator
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Protocol, cast

from app.core.config import get_settings

if TYPE_CHECKING:
    import pyarrow as pa
    import pyarrow.parquet as pq


NormalizedArtifactFormat = Literal["typed_csv", "parquet"]


def _serialize_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (date, datetime, Decimal)):
        return str(value)
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=True, sort_keys=True)
    return str(value)


def _import_pyarrow() -> tuple[Any, Any]:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Normalized artifact format 'parquet' requires optional dependency 'pyarrow'."
        ) from exc
    return pa, pq


class _ArtifactBackend(Protocol):
    path: Path
    fieldnames: list[str]
    row_count: int
    role: str
    content_type: str

    def write_row(self, row: dict[str, Any]) -> None: ...

    def close(self) -> dict[str, Any]: ...


class _TypedCsvBackend:
    role = "normalized_typed_csv"
    content_type = "text/csv"

    def __init__(self, path: Path) -> None:
        self.path = path
        self.fieldnames: list[str] = []
        self.row_count = 0
        self._file = self.path.open("w", encoding="utf-8", newline="")
        self._writer: csv.DictWriter[str] | None = None

    def write_row(self, row: dict[str, Any]) -> None:
        fieldnames = sorted(row.keys())
        if not self.fieldnames:
            self.fieldnames = fieldnames
            self._writer = csv.DictWriter(self._file, fieldnames=self.fieldnames, delimiter=";")
            self._writer.writeheader()
        elif fieldnames != self.fieldnames:
            raise ValueError("Normalized artifact schema changed within the same writer.")
        assert self._writer is not None
        self._writer.writerow({key: _serialize_cell(value) for key, value in row.items()})
        self.row_count += 1

    def close(self) -> dict[str, Any]:
        self._file.flush()
        self._file.close()
        return _build_artifact_metadata(
            path=self.path,
            role=self.role,
            content_type=self.content_type,
            row_count=self.row_count,
            fieldnames=self.fieldnames,
        )


class _ParquetBackend:
    role = "normalized_parquet"
    content_type = "application/parquet"

    def __init__(self, path: Path, *, batch_size: int = 10_000) -> None:
        self.path = path
        self.fieldnames: list[str] = []
        self.row_count = 0
        self._batch_size = batch_size
        self._pa, self._pq = _import_pyarrow()
        self._writer: pq.ParquetWriter | None = None
        self._schema: pa.Schema | None = None
        self._buffer: dict[str, list[str]] = {}

    def write_row(self, row: dict[str, Any]) -> None:
        fieldnames = sorted(row.keys())
        if not self.fieldnames:
            self.fieldnames = fieldnames
            self._schema = self._pa.schema([(field, self._pa.string()) for field in self.fieldnames])
            self._writer = self._pq.ParquetWriter(self.path, self._schema)
            self._buffer = {field: [] for field in self.fieldnames}
        elif fieldnames != self.fieldnames:
            raise ValueError("Normalized artifact schema changed within the same writer.")
        for field in self.fieldnames:
            self._buffer[field].append(_serialize_cell(row.get(field)))
        self.row_count += 1
        if self.row_count % self._batch_size == 0:
            self._flush_buffer()

    def _flush_buffer(self) -> None:
        if not self.fieldnames or not self._buffer or not self._buffer[self.fieldnames[0]]:
            return
        assert self._writer is not None
        batch = self._pa.record_batch(
            [self._pa.array(self._buffer[field], type=self._pa.string()) for field in self.fieldnames],
            names=self.fieldnames,
        )
        self._writer.write_batch(batch)
        self._buffer = {field: [] for field in self.fieldnames}

    def close(self) -> dict[str, Any]:
        try:
            self._flush_buffer()
        finally:
            if self._writer is not None:
                self._writer.close()
        return _build_artifact_metadata(
            path=self.path,
            role=self.role,
            content_type=self.content_type,
            row_count=self.row_count,
            fieldnames=self.fieldnames,
        )


def _build_artifact_metadata(
    *,
    path: Path,
    role: str,
    content_type: str,
    row_count: int,
    fieldnames: list[str],
) -> dict[str, Any]:
    content_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "uri": str(path),
        "role": role,
        "content_type": content_type,
        "logical_name": path.name,
        "size_bytes": path.stat().st_size,
        "content_sha256": content_sha256,
        "row_count": row_count,
        "fieldnames": fieldnames,
    }


def _resolve_backend(
    *,
    path: Path,
    artifact_format: NormalizedArtifactFormat,
) -> _ArtifactBackend:
    if artifact_format == "typed_csv":
        return _TypedCsvBackend(path)
    return _ParquetBackend(path)


def _artifact_suffix(artifact_format: NormalizedArtifactFormat) -> str:
    if artifact_format == "typed_csv":
        return ".typed.csv"
    return ".parquet"


class NormalizedArtifactWriter:
    def __init__(
        self,
        *,
        run_id: str,
        member_id: str,
        member_name: str,
        row_kind: str,
        base_dir: str | None = None,
        artifact_format: NormalizedArtifactFormat | None = None,
    ) -> None:
        self.artifact_format = artifact_format or get_settings().ingestion_normalized_artifact_format
        root = Path(base_dir or get_settings().storage_dir) / "artifacts" / "normalized" / run_id / member_id
        stem = Path(member_name).stem
        path = root / f"{stem}__{row_kind}{_artifact_suffix(self.artifact_format)}"
        path.parent.mkdir(parents=True, exist_ok=True)
        self._backend = _resolve_backend(path=path, artifact_format=self.artifact_format)

    @property
    def path(self) -> Path:
        return self._backend.path

    def write_row(self, row: dict[str, Any]) -> None:
        self._backend.write_row(row)

    def close(self) -> dict[str, Any]:
        return self._backend.close()


def iter_normalized_artifact_rows(*, artifact_uri: str | Path) -> Iterator[dict[str, str]]:
    path = Path(artifact_uri)
    if path.suffix == ".parquet":
        pa, pq = _import_pyarrow()
        parquet_file = pq.ParquetFile(path)
        for batch in parquet_file.iter_batches():
            batch_table = pa.Table.from_batches([batch]).to_pylist()
            for row in batch_table:
                yield {key: cast(str, value) for key, value in row.items()}
        return
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        for row in reader:
            yield dict(row)


def read_normalized_hashes(*, artifact_uri: str | Path) -> set[str]:
    return {
        row["normalized_hash"]
        for row in iter_normalized_artifact_rows(artifact_uri=artifact_uri)
        if row.get("normalized_hash")
    }
