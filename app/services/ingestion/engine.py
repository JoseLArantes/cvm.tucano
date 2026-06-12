from __future__ import annotations

import hashlib
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.models.ingestion import IngestionFile, IngestionFileMember, IngestionRun
from app.services.ingestion.staging import member_has_successful_match, stage_csv_payload_streaming, update_run_state
from app.services.ingestion.summary import build_contadores_quality_summary


@dataclass(frozen=True)
class ZipMemberContext:
    member: IngestionFileMember
    member_name: str
    row_kind: str
    ano: int


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
    spec: ZipIngestionSpec,
    contadores: dict[str, int],
    stage_chunk_size: int,
) -> dict[str, Any]:
    run_id = run.id
    staged_names: set[str] = set()
    members_skipped = 0

    for member_name, member_payload in spec.ordered_members:
        staged_names.add(member_name)
        if member_has_successful_match(
            db,
            tipo_fonte=spec.tipo_fonte,
            ano=spec.ano,
            member_name=member_name,
            member_sha256=hashlib.sha256(member_payload).hexdigest(),
            current_run_id=run.id,
        ):
            members_skipped += 1
            run_atual = db.get(IngestionRun, run_id)
            if run_atual is None:
                raise ValueError("ingestion_run_nao_encontrado")
            update_run_state(
                run_atual,
                phase="stage",
                quality_summary=build_contadores_quality_summary(
                    contadores,
                    extras={
                        "members_total": len(staged_names),
                        "members_processados": len(staged_names) - members_skipped,
                        "members_skipped": members_skipped,
                        "members_invalid_schema": contadores.get("members_invalid_schema", 0),
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
            quality_summary=build_contadores_quality_summary(
                contadores,
                extras={
                    "members_total": len(staged_names),
                    "members_processados": len(staged_names) - members_skipped,
                    "members_skipped": members_skipped,
                    "members_invalid_schema": contadores.get("members_invalid_schema", 0),
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
            ),
        )
        if spec.commit_after_process:
            db.commit()
        if spec.commit_progress is not None:
            spec.commit_progress(contadores)

    faltando = sorted(spec.required_members - spec.optional_members - staged_names)
    if faltando:
        raise ValueError(f"arquivo_nao_esperado_ausente: {','.join(faltando)}")

    return {
        "members_total": len(staged_names),
        "members_processados": len(staged_names) - members_skipped,
        "members_skipped": members_skipped,
    }
