from __future__ import annotations

import csv
import hashlib
import io
import re
from collections import Counter
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.ingestion import (
    IngestionFile,
    IngestionFileMember,
    IngestionRun,
    SourceArtifactSnapshot,
    SourceDeliverySnapshot,
    SourceMemberSnapshot,
)
from app.services.ingestion.source_registry import DatasetFonte, dataset_por_member_name

_DELIVERY_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "cnpj_companhia": ("CNPJ_CIA", "CNPJ_Companhia", "CNPJ"),
    "codigo_cvm": ("CD_CVM", "Codigo_CVM"),
    "id_documento": ("ID_DOC", "ID_Documento"),
    "protocolo_entrega": ("Protocolo_Entrega", "PROTOCOLO_ENTREGA"),
    "data_referencia": ("DT_REFER", "Data_Referencia"),
    "data_entrega": ("DT_RECEB", "Data_Entrega"),
    "versao": ("VERSAO", "Versao"),
}


def _agora() -> datetime:
    return datetime.now(UTC)


def _sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _normalize_probe_sources(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _header_hash(header: list[str] | None) -> str | None:
    if not header:
        return None
    return _sha256_hex("|".join(header).encode("utf-8"))


def _decode_csv_payload(payload: bytes) -> tuple[str, str]:
    for encoding in ("utf-8-sig", "latin1"):
        try:
            return payload.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("csv", payload, 0, 1, "Falha ao decodificar CSV")


def _read_csv_dicts(payload: bytes, *, delimiter: str = ";") -> tuple[list[str], list[dict[str, str]]]:
    text, _ = _decode_csv_payload(payload)
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    return list(reader.fieldnames or []), list(reader)


def inspect_csv_member_payload(payload: bytes, *, delimiter: str = ";") -> tuple[list[str], int]:
    header, rows = _read_csv_dicts(payload, delimiter=delimiter)
    return header, len(rows)


def build_custom_remote_probe(*, source_url: str) -> dict[str, Any]:
    return {
        "dataset_url": None,
        "resource_url": source_url,
        "probe_sources": ["custom_downloader"],
        "decision": "unknown",
        "decision_reason": "custom_downloader",
        "confidence": "unknown",
        "download_required": True,
    }


def resolve_delivery_index_role(dataset: DatasetFonte | None) -> str:
    if dataset is None:
        return "none"
    if dataset.delivery_index_role != "auto":
        return dataset.delivery_index_role
    row_kind = dataset.row_kind or ""
    if row_kind.endswith("_documento") or dataset.dataset in {"documento_principal", "documentos", "original"}:
        return "document"
    return "none"


def extract_delivery_rows(
    *,
    payload: bytes,
    member_name: str,
    dataset: DatasetFonte | None,
) -> list[dict[str, Any]]:
    role = resolve_delivery_index_role(dataset)
    if role == "none":
        return []

    _, rows = _read_csv_dicts(payload)
    deliveries: list[dict[str, Any]] = []
    for row in rows:
        raw_identity: dict[str, Any] = {}
        for target_key, aliases in _DELIVERY_FIELD_ALIASES.items():
            for alias in aliases:
                value = row.get(alias)
                if value not in (None, ""):
                    raw_identity[target_key] = value
                    break
        if not raw_identity:
            continue
        identity_hash = _sha256_hex(
            "|".join(str(raw_identity.get(key, "")) for key in sorted(raw_identity)).encode("utf-8")
        )
        deliveries.append(
            {
                "member_name": member_name,
                "identity_hash": identity_hash,
                "cnpj_companhia": raw_identity.get("cnpj_companhia"),
                "codigo_cvm": raw_identity.get("codigo_cvm"),
                "id_documento": raw_identity.get("id_documento"),
                "protocolo_entrega": raw_identity.get("protocolo_entrega"),
                "data_referencia": raw_identity.get("data_referencia"),
                "data_entrega": raw_identity.get("data_entrega"),
                "versao": raw_identity.get("versao"),
                "raw_identity": raw_identity,
                "status": "captured",
            }
        )
    return deliveries


def latest_artifact_snapshot_reference(
    db: Session,
    *,
    tipo_fonte: str,
    ano: int | None,
    current_run_id: Any,
) -> SourceArtifactSnapshot | None:
    return db.scalar(
        select(SourceArtifactSnapshot)
        .join(IngestionRun, IngestionRun.id == SourceArtifactSnapshot.ingestion_run_id)
        .where(
            SourceArtifactSnapshot.tipo_fonte == tipo_fonte,
            SourceArtifactSnapshot.ano == ano,
            SourceArtifactSnapshot.ingestion_run_id != current_run_id,
            IngestionRun.status.in_(("sucesso", "sucesso_com_alerta", "sem_alteracao", "skipped")),
        )
        .order_by(IngestionRun.started_at.desc())
        .limit(1)
    )


def upsert_artifact_snapshot(
    db: Session,
    *,
    run: IngestionRun,
    source_url: str,
    source_filename: str | None,
    remote_probe: dict[str, Any] | None,
    ingestion_file: IngestionFile | None,
    status: str,
) -> SourceArtifactSnapshot:
    snapshot = db.scalar(select(SourceArtifactSnapshot).where(SourceArtifactSnapshot.ingestion_run_id == run.id))
    if snapshot is None:
        snapshot = SourceArtifactSnapshot(
            ingestion_run_id=run.id,
            tipo_fonte=run.tipo_fonte,
            ano=run.ano,
            resource_url=source_url,
            source_filename=source_filename,
            status=status,
        )
        db.add(snapshot)
    probe = remote_probe or {}
    snapshot.resource_url = source_url
    snapshot.source_filename = source_filename
    snapshot.content_sha256 = ingestion_file.content_sha256 if ingestion_file is not None else snapshot.content_sha256
    snapshot.remote_etag = probe.get("resource_etag") or (ingestion_file.etag if ingestion_file is not None else None)
    snapshot.remote_last_modified = probe.get("resource_last_modified") or (
        ingestion_file.last_modified if ingestion_file is not None else None
    )
    snapshot.remote_content_length = probe.get("resource_content_length") or (
        str(ingestion_file.content_length_bytes) if ingestion_file is not None else None
    )
    snapshot.package_metadata_modified = probe.get("package_metadata_modified")
    snapshot.probe_sources = _normalize_probe_sources(probe.get("probe_sources"))
    snapshot.probe_decision = probe.get("decision")
    snapshot.probe_decision_reason = probe.get("decision_reason")
    snapshot.probe_confidence = probe.get("confidence")
    snapshot.download_required = bool(probe.get("download_required"))
    snapshot.sha_confirmation_result = probe.get("sha_confirmation_result")
    snapshot.status = status
    db.flush()
    return snapshot


def record_member_snapshot(
    db: Session,
    *,
    artifact_snapshot: SourceArtifactSnapshot,
    member_name: str,
    member_sha256: str,
    row_count: int,
    header: list[str] | None,
    row_kind: str | None,
    required_member: bool,
    schema_status: str,
    schema_message: str | None,
    lifecycle_status: str,
    delivery_index_role: str,
    destino_promovido: str | None = None,
    ingestion_file_member_id: Any = None,
    delivery_rows: list[dict[str, Any]] | None = None,
) -> SourceMemberSnapshot:
    snapshot = db.scalar(
        select(SourceMemberSnapshot)
        .where(SourceMemberSnapshot.artifact_snapshot_id == artifact_snapshot.id)
        .where(SourceMemberSnapshot.member_name == member_name)
    )
    if snapshot is None:
        snapshot = SourceMemberSnapshot(
            artifact_snapshot_id=artifact_snapshot.id,
            member_name=member_name,
            member_sha256=member_sha256,
            row_count=row_count,
            header_hash=_header_hash(header),
            header=header,
            row_kind=row_kind,
            destino_promovido=destino_promovido,
            required_member=required_member,
            schema_status=schema_status,
            schema_message=schema_message,
            delivery_index_role=delivery_index_role,
            lifecycle_status=lifecycle_status,
            ingestion_file_member_id=ingestion_file_member_id,
        )
        db.add(snapshot)
        db.flush()
    else:
        db.execute(delete(SourceDeliverySnapshot).where(SourceDeliverySnapshot.member_snapshot_id == snapshot.id))
        snapshot.ingestion_file_member_id = ingestion_file_member_id
        snapshot.member_sha256 = member_sha256
        snapshot.row_count = row_count
        snapshot.header_hash = _header_hash(header)
        snapshot.header = header
        snapshot.row_kind = row_kind
        snapshot.destino_promovido = destino_promovido
        snapshot.required_member = required_member
        snapshot.schema_status = schema_status
        snapshot.schema_message = schema_message
        snapshot.delivery_index_role = delivery_index_role
        snapshot.lifecycle_status = lifecycle_status
        db.flush()

    for delivery in delivery_rows or []:
        db.add(
            SourceDeliverySnapshot(
                artifact_snapshot_id=artifact_snapshot.id,
                member_snapshot_id=snapshot.id,
                ingestion_file_member_id=ingestion_file_member_id,
                member_name=member_name,
                identity_hash=delivery["identity_hash"],
                cnpj_companhia=delivery.get("cnpj_companhia"),
                codigo_cvm=delivery.get("codigo_cvm"),
                id_documento=delivery.get("id_documento"),
                protocolo_entrega=delivery.get("protocolo_entrega"),
                data_referencia=delivery.get("data_referencia"),
                data_entrega=delivery.get("data_entrega"),
                versao=delivery.get("versao"),
                raw_identity=delivery.get("raw_identity"),
                status=delivery.get("status", "captured"),
            )
        )
    db.flush()
    return snapshot


def previous_member_snapshot(
    db: Session,
    *,
    tipo_fonte: str,
    ano: int | None,
    current_run_id: Any,
    member_name: str,
) -> SourceMemberSnapshot | None:
    return db.scalar(
        select(SourceMemberSnapshot)
        .join(SourceArtifactSnapshot, SourceArtifactSnapshot.id == SourceMemberSnapshot.artifact_snapshot_id)
        .join(IngestionRun, IngestionRun.id == SourceArtifactSnapshot.ingestion_run_id)
        .where(
            SourceArtifactSnapshot.tipo_fonte == tipo_fonte,
            SourceArtifactSnapshot.ano == ano,
            SourceArtifactSnapshot.ingestion_run_id != current_run_id,
            SourceMemberSnapshot.member_name == member_name,
            IngestionRun.status.in_(("sucesso", "sucesso_com_alerta", "sem_alteracao", "skipped")),
        )
        .order_by(IngestionRun.started_at.desc())
        .limit(1)
    )


def compare_delivery_snapshot(
    db: Session,
    *,
    previous_member_snapshot_id: Any | None,
    current_identity_hashes: set[str],
) -> dict[str, Any] | None:
    if previous_member_snapshot_id is None:
        if current_identity_hashes:
            return {
                "before_count": 0,
                "after_count": len(current_identity_hashes),
                "added": len(current_identity_hashes),
                "removed": 0,
            }
        return None
    previous_hashes = set(
        db.execute(
            select(SourceDeliverySnapshot.identity_hash).where(
                SourceDeliverySnapshot.member_snapshot_id == previous_member_snapshot_id
            )
        )
        .scalars()
        .all()
    )
    if previous_hashes == current_identity_hashes:
        return None
    return {
        "before_count": len(previous_hashes),
        "after_count": len(current_identity_hashes),
        "added": len(current_identity_hashes - previous_hashes),
        "removed": len(previous_hashes - current_identity_hashes),
    }


def capture_member_lifecycle_snapshot(
    db: Session,
    *,
    artifact_snapshot: SourceArtifactSnapshot,
    tipo_fonte: str,
    ano: int,
    current_run_id: Any,
    member_name: str,
    payload: bytes,
    row_kind: str | None,
    required_member: bool,
    schema_status: str,
    schema_message: str | None,
    lifecycle_status: str,
    ingestion_file_member_id: Any = None,
) -> dict[str, Any]:
    dataset = dataset_por_member_name(tipo_fonte, member_name, ano)
    header, row_count = inspect_csv_member_payload(payload)
    delivery_rows = extract_delivery_rows(payload=payload, member_name=member_name, dataset=dataset)
    previous_snapshot = previous_member_snapshot(
        db,
        tipo_fonte=tipo_fonte,
        ano=ano,
        current_run_id=current_run_id,
        member_name=member_name,
    )
    snapshot = record_member_snapshot(
        db,
        artifact_snapshot=artifact_snapshot,
        member_name=member_name,
        member_sha256=_sha256_hex(payload),
        row_count=row_count,
        header=header,
        row_kind=row_kind,
        required_member=required_member,
        schema_status=schema_status,
        schema_message=schema_message,
        lifecycle_status=lifecycle_status,
        delivery_index_role=resolve_delivery_index_role(dataset),
        destino_promovido=None if dataset is None else dataset.destino_promovido,
        ingestion_file_member_id=ingestion_file_member_id,
        delivery_rows=delivery_rows,
    )
    delivery_delta = compare_delivery_snapshot(
        db,
        previous_member_snapshot_id=None if previous_snapshot is None else previous_snapshot.id,
        current_identity_hashes={item["identity_hash"] for item in delivery_rows},
    )
    return {"member_snapshot": snapshot, "delivery_delta": delivery_delta}


def build_artifact_snapshot_response(db: Session, *, run_id: Any) -> dict[str, Any] | None:
    snapshot = db.scalar(select(SourceArtifactSnapshot).where(SourceArtifactSnapshot.ingestion_run_id == run_id))
    if snapshot is None:
        return None
    return {
        "id": str(snapshot.id),
        "tipo_fonte": snapshot.tipo_fonte,
        "ano": snapshot.ano,
        "resource_url": snapshot.resource_url,
        "source_filename": snapshot.source_filename,
        "content_sha256": snapshot.content_sha256,
        "remote_etag": snapshot.remote_etag,
        "remote_last_modified": snapshot.remote_last_modified,
        "remote_content_length": snapshot.remote_content_length,
        "package_metadata_modified": snapshot.package_metadata_modified,
        "probe_sources": snapshot.probe_sources or [],
        "probe_decision": snapshot.probe_decision,
        "probe_decision_reason": snapshot.probe_decision_reason,
        "probe_confidence": snapshot.probe_confidence,
        "download_required": snapshot.download_required,
        "sha_confirmation_result": snapshot.sha_confirmation_result,
        "status": snapshot.status,
    }


def build_member_snapshot_summary(db: Session, *, run_id: Any) -> dict[str, Any] | None:
    artifact_snapshot = db.scalar(select(SourceArtifactSnapshot).where(SourceArtifactSnapshot.ingestion_run_id == run_id))
    if artifact_snapshot is None:
        return None
    members = list(
        db.execute(
            select(SourceMemberSnapshot).where(SourceMemberSnapshot.artifact_snapshot_id == artifact_snapshot.id)
        ).scalars()
    )
    if not members:
        return None
    statuses = Counter(member.lifecycle_status for member in members)
    schemas = Counter(member.schema_status for member in members)
    return {
        "total": len(members),
        "by_status": dict(statuses),
        "by_schema_status": dict(schemas),
        "members": [
            {
                "member_name": member.member_name,
                "member_sha256": member.member_sha256,
                "row_count": member.row_count,
                "required_member": member.required_member,
                "schema_status": member.schema_status,
                "schema_message": member.schema_message,
                "lifecycle_status": member.lifecycle_status,
                "delivery_index_role": member.delivery_index_role,
                "row_kind": member.row_kind,
                "destino_promovido": member.destino_promovido,
            }
            for member in sorted(members, key=lambda item: item.member_name)
        ],
    }


def build_delivery_snapshot_summary(db: Session, *, run_id: Any) -> dict[str, Any] | None:
    artifact_snapshot = db.scalar(select(SourceArtifactSnapshot).where(SourceArtifactSnapshot.ingestion_run_id == run_id))
    if artifact_snapshot is None:
        return None
    deliveries = list(
        db.execute(
            select(SourceDeliverySnapshot).where(SourceDeliverySnapshot.artifact_snapshot_id == artifact_snapshot.id)
        ).scalars()
    )
    if not deliveries:
        return None
    status_counts = Counter(item.status for item in deliveries)
    member_counts = Counter(item.member_name for item in deliveries)
    return {
        "total": len(deliveries),
        "by_status": dict(status_counts),
        "by_member": dict(member_counts),
        "sample": [
            {
                "member_name": item.member_name,
                "cnpj_companhia": item.cnpj_companhia,
                "codigo_cvm": item.codigo_cvm,
                "id_documento": item.id_documento,
                "protocolo_entrega": item.protocolo_entrega,
                "data_referencia": item.data_referencia,
                "data_entrega": item.data_entrega,
                "versao": item.versao,
            }
            for item in deliveries[:10]
        ],
    }


def fetch_cvm_novidades_summary(*, timeout: float = 20.0) -> dict[str, Any] | None:
    url = "https://dados.cvm.gov.br/pages/novidades"
    try:
        response = httpx.get(url, timeout=timeout)
        response.raise_for_status()
    except Exception:
        return None
    text = re.sub(r"<[^>]+>", "\n", response.text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    highlights = [
        line
        for line in lines
        if any(token in line.lower() for token in ("altera", "inclu", "exclu", "histor", "arquivo", "coluna"))
    ][:20]
    return {
        "source_url": url,
        "retrieved_at": _agora().isoformat(),
        "highlights": highlights,
        "total_highlights": len(highlights),
    }
