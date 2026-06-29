from __future__ import annotations

import csv
import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.core.config import get_settings


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


class NormalizedArtifactWriter:
    def __init__(
        self,
        *,
        run_id: str,
        member_id: str,
        member_name: str,
        row_kind: str,
        base_dir: str | None = None,
    ) -> None:
        root = Path(base_dir or get_settings().storage_dir) / "artifacts" / "normalized" / run_id / member_id
        stem = Path(member_name).stem
        self._path = root / f"{stem}__{row_kind}.typed.csv"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._fieldnames: list[str] | None = None
        self._row_count = 0
        self._file = self._path.open("w", encoding="utf-8", newline="")
        self._writer: csv.DictWriter[str] | None = None

    @property
    def path(self) -> Path:
        return self._path

    def write_row(self, row: dict[str, Any]) -> None:
        fieldnames = sorted(row.keys())
        if self._fieldnames is None:
            self._fieldnames = fieldnames
            self._writer = csv.DictWriter(self._file, fieldnames=self._fieldnames, delimiter=";")
            self._writer.writeheader()
        elif fieldnames != self._fieldnames:
            raise ValueError("Normalized artifact schema changed within the same writer.")
        assert self._writer is not None
        self._writer.writerow({key: _serialize_cell(value) for key, value in row.items()})
        self._row_count += 1

    def close(self) -> dict[str, Any]:
        self._file.flush()
        self._file.close()
        content_sha256 = hashlib.sha256(self._path.read_bytes()).hexdigest()
        return {
            "uri": str(self._path),
            "role": "normalized_typed_csv",
            "content_type": "text/csv",
            "logical_name": self._path.name,
            "size_bytes": self._path.stat().st_size,
            "content_sha256": content_sha256,
            "row_count": self._row_count,
            "fieldnames": self._fieldnames or [],
        }
