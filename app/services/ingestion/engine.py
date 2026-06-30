from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.models.ingestion import IngestionFile, IngestionFileMember, IngestionRun, SourceArtifactSnapshot
from app.services.ingestion.artifact_store import describe_member_artifact, member_artifact_exists
from app.services.ingestion.change_tracking import (
    compare_member_with_previous,
    finalize_member_change_summary,
    previous_successful_members,
)
from app.services.ingestion.lifecycle import (
    compare_delivery_snapshot,
    extract_delivery_rows,
    inspect_csv_member_payload,
    previous_member_snapshot,
    record_member_snapshot,
    resolve_delivery_index_role,
)
from app.services.ingestion.source_registry import dataset_por_member_name
from app.services.ingestion.staging import (
    member_has_successful_match,
    purge_member_success_rows,
    stage_csv_payload_streaming,
    update_run_state,
)
from app.services.ingestion.summary import build_contadores_quality_summary


@dataclass(frozen=True)
class ZipMemberContext:
    member: IngestionFileMember
    member_name: str
    row_kind: str
    ano: int
    reconcile_required: bool


@dataclass(frozen=True)
class ZipIngestionSpec:
    tipo_fonte: str
    ano: int
    ordered_members: Iterable[tuple[str, bytes]]
    required_members: set[str]
    optional_members: set[str]
    row_kind_by_member: dict[str, str]
    process_member: Callable[[Session, ZipMemberContext], None]
    commit_progress: Callable[[dict[str, int]], None] | None = None
    commit_after_stage: bool = True
    commit_after_process: bool = True


def process_zip_members(
    db: Session,
    *,
    run: IngestionRun,
    ingestion_file: IngestionFile,
    artifact_snapshot: SourceArtifactSnapshot,
    spec: ZipIngestionSpec,
    contadores: dict[str, int],
    stage_chunk_size: int,
) -> dict[str, Any]:
    run_id = run.id
    ordered_members = list(spec.ordered_members)
    staged_names: set[str] = set()
    members_skipped = 0
    staged_rows_purged = 0
    previous_members = previous_successful_members(
        db,
        tipo_fonte=spec.tipo_fonte,
        ano=spec.ano,
        current_run_id=run.id,
    )
    change_summary = finalize_member_change_summary(
        current_member_names=[],
        previous_members=previous_members,
        required_members=spec.required_members,
        optional_members=spec.optional_members,
    )

    for member_name, member_payload in ordered_members:
        raw_artifact = None
        if run.execucao_sincronizacao_id is not None and member_artifact_exists(
            execution_id=str(run.execucao_sincronizacao_id),
            member_name=member_name,
        ):
            raw_artifact = describe_member_artifact(
                execution_id=str(run.execucao_sincronizacao_id),
                member_name=member_name,
                content_sha256=hashlib.sha256(member_payload).hexdigest(),
            )
        staged_names.add(member_name)
        dataset = dataset_por_member_name(spec.tipo_fonte, member_name, spec.ano)
        header_preview, row_count_preview = inspect_csv_member_payload(member_payload)
        delivery_rows = extract_delivery_rows(payload=member_payload, member_name=member_name, dataset=dataset)
        delivery_hashes = {item["identity_hash"] for item in delivery_rows}
        delivery_index_role = resolve_delivery_index_role(dataset)
        previous_snapshot = previous_member_snapshot(
            db,
            tipo_fonte=spec.tipo_fonte,
            ano=spec.ano,
            current_run_id=run.id,
            member_name=member_name,
        )
        if member_has_successful_match(
            db,
            tipo_fonte=spec.tipo_fonte,
            ano=spec.ano,
            member_name=member_name,
            member_sha256=hashlib.sha256(member_payload).hexdigest(),
            current_run_id=run.id,
        ):
            members_skipped += 1
            record_member_snapshot(
                db,
                artifact_snapshot=artifact_snapshot,
                member_name=member_name,
                member_sha256=hashlib.sha256(member_payload).hexdigest(),
                row_count=row_count_preview,
                header=header_preview,
                row_kind=spec.row_kind_by_member.get(member_name, "desconhecido"),
                required_member=member_name in spec.required_members,
                schema_status="reused",
                schema_message="member_sha256_reused",
                lifecycle_status="member_skipped",
                delivery_index_role=delivery_index_role,
                destino_promovido=None if dataset is None else dataset.destino_promovido,
                delivery_rows=delivery_rows,
                raw_artifact=raw_artifact,
            )
            delivery_delta = compare_delivery_snapshot(
                db,
                previous_member_snapshot_id=None if previous_snapshot is None else previous_snapshot.id,
                current_identity_hashes=delivery_hashes,
            )
            if delivery_delta is not None:
                delivery_changed = list(change_summary.get("delivery_index_changed", []))
                delivery_changed.append({"member_name": member_name, **delivery_delta})
                change_summary["delivery_index_changed"] = delivery_changed
            run_atual = db.get(IngestionRun, run_id)
            if run_atual is None:
                raise ValueError("ingestion_run_nao_encontrado")
            update_run_state(
                run_atual,
                phase="stage",
                change_summary=change_summary,
                quality_summary=build_contadores_quality_summary(
                    contadores,
                    extras={
                        "members_total": len(staged_names),
                        "members_processados": len(staged_names) - members_skipped,
                        "members_skipped": members_skipped,
                        "members_invalid_schema": contadores.get("members_invalid_schema", 0),
                        "staged_rows_purged": staged_rows_purged,
                    },
                ),
            )
            db.commit()
            if spec.commit_progress is not None:
                spec.commit_progress(contadores)
            continue

        member = stage_csv_payload_streaming(
            db,
            ingestion_run=run,
            ingestion_file=ingestion_file,
            payload=member_payload,
            member_name=member_name,
            arquivo_origem=member_name,
            ano_origem=spec.ano,
            row_kind=spec.row_kind_by_member.get(member_name, "desconhecido"),
            chunk_size=stage_chunk_size,
        )
        run_atual = db.get(IngestionRun, run_id)
        if run_atual is None:
            raise ValueError("ingestion_run_nao_encontrado")
        update_run_state(
            run_atual,
            phase="stage",
            change_summary=change_summary,
            quality_summary=build_contadores_quality_summary(
                contadores,
                extras={
                    "members_total": len(staged_names),
                    "members_processados": len(staged_names) - members_skipped,
                    "members_skipped": members_skipped,
                    "members_invalid_schema": contadores.get("members_invalid_schema", 0),
                    "staged_rows_purged": staged_rows_purged,
                },
            ),
        )
        if spec.commit_after_stage:
            db.commit()
        if spec.commit_progress is not None:
            spec.commit_progress(contadores)

        spec.process_member(
            db,
            ZipMemberContext(
                member=member,
                member_name=member_name,
                row_kind=spec.row_kind_by_member.get(member_name, "desconhecido"),
                ano=spec.ano,
                reconcile_required=previous_snapshot is not None,
            ),
        )
        member_atual = db.get(IngestionFileMember, member.id)
        if member_atual is not None:
            record_member_snapshot(
                db,
                artifact_snapshot=artifact_snapshot,
                member_name=member_name,
                member_sha256=member_atual.member_sha256,
                row_count=member_atual.row_count,
                header=member_atual.header,
                row_kind=spec.row_kind_by_member.get(member_name, "desconhecido"),
                required_member=member_name in spec.required_members,
                schema_status=member_atual.schema_status,
                schema_message=member_atual.schema_message,
                lifecycle_status="processed",
                delivery_index_role=delivery_index_role,
                destino_promovido=None if dataset is None else dataset.destino_promovido,
                ingestion_file_member_id=member_atual.id,
                delivery_rows=delivery_rows,
                raw_artifact=raw_artifact,
            )
            change_summary = compare_member_with_previous(
                member=member_atual,
                previous_members=previous_members,
                change_summary=change_summary,
            )
            delivery_delta = compare_delivery_snapshot(
                db,
                previous_member_snapshot_id=None if previous_snapshot is None else previous_snapshot.id,
                current_identity_hashes=delivery_hashes,
            )
            if delivery_delta is not None:
                delivery_changed = list(change_summary.get("delivery_index_changed", []))
                delivery_changed.append({"member_name": member_name, **delivery_delta})
                change_summary["delivery_index_changed"] = delivery_changed
        if spec.commit_after_process:
            db.commit()
        staged_rows_purged += purge_member_success_rows(db, ingestion_file_member_id=member.id)
        if spec.commit_progress is not None:
            spec.commit_progress(contadores)

    faltando = sorted(spec.required_members - spec.optional_members - staged_names)
    if faltando:
        raise ValueError(f"arquivo_nao_esperado_ausente: {','.join(faltando)}")

    change_summary = finalize_member_change_summary(
        current_member_names=staged_names,
        previous_members=previous_members,
        required_members=spec.required_members,
        optional_members=spec.optional_members,
        change_summary=change_summary,
    )
    run_final = db.get(IngestionRun, run_id)
    if run_final is not None:
        update_run_state(run_final, change_summary=change_summary)

    return {
        "members_total": len(staged_names),
        "members_processados": len(staged_names) - members_skipped,
        "members_skipped": members_skipped,
        "staged_rows_purged": staged_rows_purged,
        "change_summary": change_summary,
    }
