from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models.ingestion import (
    IngestionFile,
    IngestionFileMember,
    IngestionOperationAudit,
    IngestionPhaseExecution,
    IngestionRun,
    QuarantineItem,
    SourceArtifactSnapshot,
    SourceMemberSnapshot,
)
from app.models.sincronizacao import ExecucaoSincronizacao
from app.schemas.admin import (
    IngestionActionTarget,
    IngestionAllowedAction,
    IngestionAttemptSummary,
    IngestionFailureDetail,
    IngestionIntegrityDetail,
    IngestionLogicalFileDetalhe,
    IngestionLogicalFileSummary,
    IngestionLogicalMemberSummary,
    IngestionRunPhaseExecutionResumo,
    IngestionVersionSummary,
)
from app.services.ingestion.source_registry import (
    DatasetFonte,
    dataset_por_member_name,
    listar_fontes,
    obter_fonte,
)
from app.updates.models import PendingUpdate


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def build_file_id(tipo_fonte: str, ano: int | None, arquivo_principal: str) -> str:
    """Gera identificador estavel e canonico para o arquivo logico principal."""
    fonte_clean = tipo_fonte.lower().strip()
    arq_clean = arquivo_principal.strip()
    if ano is not None:
        return f"{fonte_clean}:{ano}:{arq_clean}"
    return f"{fonte_clean}:{arq_clean}"


def parse_file_id(file_id: str) -> tuple[str, int | None, str]:
    """Extrai (tipo_fonte, ano, arquivo_principal) de um file_id estavel."""
    parts = file_id.strip().split(":")
    if len(parts) >= 3:
        try:
            return parts[0], int(parts[1]), ":".join(parts[2:])
        except ValueError:
            return parts[0], None, ":".join(parts[1:])
    elif len(parts) == 2:
        return parts[0], None, parts[1]
    return file_id, None, file_id


def build_member_id(file_id: str, member_name: str) -> str:
    """Gera identificador estavel e delimitado para um membro de arquivo."""
    return f"{file_id.strip()}:{member_name.strip()}"


def parse_member_id(member_id: str) -> tuple[str, str]:
    """Separa parent_file_id e member_name a partir de um member_id estavel."""
    parts = member_id.strip().rsplit(":", 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return "", member_id


def resolver_nome_arquivo_principal(tipo_fonte: str, ano: int | None, candidato: str | None = None) -> str:
    """Resolve o nome do arquivo principal a partir do catalogo ou candidato."""
    if candidato and (candidato.endswith(".zip") or not candidato.endswith(".csv")):
        return candidato.strip()
    fonte_reg = obter_fonte(tipo_fonte)
    if fonte_reg is not None:
        try:
            return fonte_reg.render_arquivo_principal(ano=ano)
        except Exception:
            return fonte_reg.arquivo_principal_template
    if candidato:
        return candidato.strip()
    if ano is not None:
        return f"{tipo_fonte}_cia_aberta_{ano}.zip"
    return f"{tipo_fonte}_dados.csv"


def is_container_file(tipo_fonte: str, arquivo_principal: str) -> bool:
    """Determina se o arquivo e um pacote de multiplos membros (ZIP) ou arquivo simples."""
    fonte_reg = obter_fonte(tipo_fonte)
    if fonte_reg is not None:
        return fonte_reg.tipo_distribuicao == "zip_anual"
    return arquivo_principal.lower().endswith(".zip")


def datasets_obrigatorios_para_fonte(tipo_fonte: str, ano: int | None) -> list[DatasetFonte]:
    """Retorna os datasets marcados como obrigatorios no catalogo para a fonte e ano."""
    fonte_reg = obter_fonte(tipo_fonte)
    if fonte_reg is None:
        return []
    return [ds for ds in fonte_reg.datasets if ds.obrigatorio]


def calcular_integridade(
    *,
    tipo_fonte: str,
    ano: int | None,
    is_container: bool,
    datasets_obrigatorios: list[DatasetFonte],
    members_present: dict[str, dict[str, Any]],
    root_execution: ExecucaoSincronizacao | None,
    root_run: IngestionRun | None,
    audit_operations: list[str],
    quarantine_total: int,
    quarantine_pendente: int,
    canonical_write_confirmed: bool,
    reused_proven: bool = False,
) -> IngestionIntegrityDetail:
    """Calcula server-side a integridade do arquivo com base em membros obrigatorios e evidencias."""
    motivos: list[str] = []
    evidence_refs: list[str] = []

    if root_run is not None:
        evidence_refs.append(f"run:{root_run.id}")
    if root_execution is not None:
        evidence_refs.append(f"execucao:{root_execution.id}")

    if not is_container:
        # Arquivo simples (ex: cadastro global)
        membros_esperados = 0
        membros_presentes_count = 0
        membros_processados = 0
        membros_faltantes: list[str] = []
        membros_com_falha: list[str] = []

        if root_execution is None and root_run is None:
            status = "nao_aplicado"
            motivos.append("Arquivo registrado no catalogo ou atualizacao, sem execucoes iniciadas.")
        elif root_execution is not None and root_execution.status == "sucesso" and canonical_write_confirmed:
            if quarantine_total > 0:
                status = "completo_com_ressalvas"
                motivos.append(f"Promocao concluida com sucesso, com {quarantine_total} item(ns) em quarentena.")
            else:
                status = "completo"
                motivos.append("Promocao concluida e escrita canonica confirmada sem ressalvas.")
        elif root_execution is not None and root_execution.status in ("em_execucao", "agendada"):
            status = "nao_aplicado"
            motivos.append("Processamento em andamento.")
        elif root_execution is not None and root_execution.status == "falha":
            status = "nao_aplicado"
            motivos.append(f"Execucao falhou: {root_execution.mensagem_erro or 'erro desconhecido'}.")
        elif root_run is not None and root_run.status in ("sucesso", "sucesso_com_alerta") and canonical_write_confirmed:
            status = "completo"
            motivos.append("Run concluida com sucesso e escrita confirmada.")
        else:
            status = "evidencia_insuficiente"
            motivos.append("Evidencias de promocao ausentes ou incompletas.")

        return IngestionIntegrityDetail(
            status=status,
            motivos=motivos,
            membros_obrigatorios_esperados=membros_esperados,
            membros_obrigatorios_presentes=membros_presentes_count,
            membros_processados=membros_processados,
            membros_faltantes=membros_faltantes,
            membros_com_falha=membros_com_falha,
            quarentena_total=quarantine_total,
            quarentena_pendente=quarantine_pendente,
            evidence_refs=evidence_refs,
        )

    # Arquivo container (ZIP anual)
    nomes_obrigatorios_esperados: list[str] = []
    for ds in datasets_obrigatorios:
        try:
            nomes_obrigatorios_esperados.append(ds.render_member_name(ano=ano))
        except Exception:
            nomes_obrigatorios_esperados.append(ds.member_name_template)

    membros_esperados = len(nomes_obrigatorios_esperados)
    membros_presentes_count = sum(1 for nome in nomes_obrigatorios_esperados if nome in members_present)

    membros_faltantes = [
        nome for nome in nomes_obrigatorios_esperados if nome not in members_present
    ]
    membros_com_falha = []
    membros_processados = 0

    for nome, info in members_present.items():
        st = info.get("status")
        write_ok = info.get("canonical_write_confirmed", False)
        if st in ("falha", "quality_fail", "schema_invalid"):
            membros_com_falha.append(nome)
        elif st in ("sucesso", "processed") or (st in ("skipped", "member_skipped") and (write_ok or reused_proven)):
            membros_processados += 1

    # Regras deterministas de completude
    if root_execution is None and root_run is None:
        status = "nao_aplicado"
        motivos.append("Arquivo detectado ou agendado, nenhuma tentativa executada.")
    elif membros_faltantes:
        status = "parcial"
        motivos.append(f"Membros obrigatorios faltantes no pacote: {', '.join(membros_faltantes)}.")
    elif membros_com_falha:
        status = "parcial"
        motivos.append(f"Membros com falha no processamento: {', '.join(membros_com_falha)}.")
    elif membros_processados >= membros_esperados and canonical_write_confirmed:
        if quarantine_total > 0:
            status = "completo_com_ressalvas"
            motivos.append(f"Membros obrigatorios promovidos com sucesso, com {quarantine_total} item(ns) em quarentena.")
        else:
            status = "completo"
            motivos.append("Todos os membros obrigatorios promovidos com sucesso e confirmados.")
    elif root_execution is not None and root_execution.status == "falha" and not members_present:
        status = "nao_aplicado"
        motivos.append("Falha ocorrida antes da extracao/descoberta de membros.")
    elif membros_processados > 0:
        status = "parcial"
        motivos.append(f"Apenas {membros_processados} de {membros_esperados} membros obrigatorios foram processados.")
    else:
        status = "evidencia_insuficiente"
        motivos.append("Evidencias insuficientes de conclusao de membros.")

    return IngestionIntegrityDetail(
        status=status,
        motivos=motivos,
        membros_obrigatorios_esperados=membros_esperados,
        membros_obrigatorios_presentes=membros_presentes_count,
        membros_processados=membros_processados,
        membros_faltantes=membros_faltantes,
        membros_com_falha=membros_com_falha,
        quarentena_total=quarantine_total,
        quarentena_pendente=quarantine_pendente,
        evidence_refs=evidence_refs,
    )


def calcular_resolucao_falha(
    *,
    failed_target_type: str,
    failed_target_id: str,
    latest_status: str,
    audit_operations: list[str],
    has_later_successful_attempt: bool,
    has_superseding_version: bool,
) -> str:
    """Calcula o estado de resolucao de uma falha operacional."""
    if "acknowledge-failure" in audit_operations:
        return "encerrada_sem_restauracao"
    if has_later_successful_attempt:
        return "restaurada_com_evidencia"
    if has_superseding_version:
        return "versao_substituida"
    if latest_status in ("em_execucao", "running", "agendada"):
        return "em_nova_tentativa"
    return "aberta"


def calcular_atividade_atual(
    *,
    root_status: str | None,
    children_statuses: list[str],
    is_paused: bool = False,
) -> str:
    """Calcula o estado de atividade operacional corrente do arquivo."""
    if is_paused:
        return "bloqueada"
    if root_status in ("em_execucao", "agendada"):
        return "em_processamento"
    if any(s in ("em_execucao", "agendada") for s in children_statuses):
        return "em_processamento"
    if any(s == "aguardando_ingestao" for s in children_statuses) and root_status in ("em_execucao", "agendada"):
        return "aguardando_parent_window"
    if root_status == "aguardando_ingestao":
        return "aguardando_ingestao"
    return "idle"


FileKey = tuple[str, int | None, str]
FileScope = tuple[str, int | None]


def _em_processamento_scopes(
    db: Session,
    file_keys: set[FileKey],
    latest_root_by_scope: dict[FileScope, tuple[uuid.UUID, str]],
) -> tuple[set[FileScope], set[FileKey]]:
    """Localiza escopos ativos sem montar o detalhe completo de cada arquivo."""
    if not file_keys:
        return set(), set()

    active_statuses = {"em_execucao", "agendada"}
    scopes = {key[:2] for key in file_keys}
    active_scopes = {
        scope for scope, (_, status) in latest_root_by_scope.items() if scope in scopes and status in active_statuses
    }
    active_file_keys: set[FileKey] = set()

    root_scope_by_id = {
        execution_id: scope
        for scope, (execution_id, _) in latest_root_by_scope.items()
        if scope in scopes
    }
    latest_roots = list(root_scope_by_id)
    for offset in range(0, len(latest_roots), 500):
        root_ids = latest_roots[offset : offset + 500]
        for parent_id, status in db.execute(
            select(ExecucaoSincronizacao.parent_execucao_id, ExecucaoSincronizacao.status).where(
                ExecucaoSincronizacao.parent_execucao_id.in_(root_ids)
            )
        ).all():
            if status in active_statuses and parent_id in root_scope_by_id:
                active_scopes.add(root_scope_by_id[parent_id])

    keys_without_root = [key for key in file_keys if key[:2] not in latest_root_by_scope]
    fallback_roots: dict[FileKey, tuple[uuid.UUID, str]] = {}
    for offset in range(0, len(keys_without_root), 100):
        batch = keys_without_root[offset : offset + 100]
        predicates = [
            and_(
                ExecucaoSincronizacao.tipo_fonte == tipo_fonte,
                ExecucaoSincronizacao.ano.is_(None)
                if ano is None
                else ExecucaoSincronizacao.ano == ano,
                ExecucaoSincronizacao.arquivo == arquivo,
            )
            for tipo_fonte, ano, arquivo in batch
        ]
        for execution_id, tipo_fonte, ano, arquivo, status in db.execute(
            select(
                ExecucaoSincronizacao.id,
                ExecucaoSincronizacao.tipo_fonte,
                ExecucaoSincronizacao.ano,
                ExecucaoSincronizacao.arquivo,
                ExecucaoSincronizacao.status,
            )
            .where(or_(*predicates))
            .order_by(ExecucaoSincronizacao.iniciada_em.desc())
        ).all():
            fallback_roots.setdefault((tipo_fonte, ano, arquivo), (execution_id, status))

    fallback_key_by_id = {execution_id: key for key, (execution_id, _) in fallback_roots.items()}
    fallback_root_ids = list(fallback_key_by_id)
    for key, (_, status) in fallback_roots.items():
        if status in active_statuses:
            active_file_keys.add(key)
    for offset in range(0, len(fallback_root_ids), 500):
        root_ids = fallback_root_ids[offset : offset + 500]
        for parent_id, status in db.execute(
            select(ExecucaoSincronizacao.parent_execucao_id, ExecucaoSincronizacao.status).where(
                ExecucaoSincronizacao.parent_execucao_id.in_(root_ids)
            )
        ).all():
            if status in active_statuses and parent_id in fallback_key_by_id:
                active_file_keys.add(fallback_key_by_id[parent_id])

    fallback_scopes = {
        key[:2]
        for key in keys_without_root
        if key not in fallback_roots and key[1] is not None
    }
    fallback_scope_list = list(fallback_scopes)
    for offset in range(0, len(fallback_scope_list), 100):
        scope_batch = fallback_scope_list[offset : offset + 100]
        predicates = [
            and_(
                ExecucaoSincronizacao.tipo_fonte == tipo_fonte,
                ExecucaoSincronizacao.ano == ano,
            )
            for tipo_fonte, ano in scope_batch
        ]
        for tipo_fonte, ano, status in db.execute(
            select(
                ExecucaoSincronizacao.tipo_fonte,
                ExecucaoSincronizacao.ano,
                ExecucaoSincronizacao.status,
            ).where(
                ExecucaoSincronizacao.tipo_execucao == "arquivo_membro",
                or_(*predicates),
            )
        ).all():
            if status in active_statuses:
                active_scopes.add((tipo_fonte, ano))

    return active_scopes, active_file_keys


def obter_arquivo_logico(db: Session, file_id: str) -> IngestionLogicalFileDetalhe | None:
    """Retorna o detalhe completo de um arquivo logico por seu ID estavel."""
    tipo_fonte, ano, arquivo_principal = parse_file_id(file_id)
    is_container = is_container_file(tipo_fonte, arquivo_principal)

    # 1. Carregar execucoes raiz e filhas
    exec_root_stmt = select(ExecucaoSincronizacao).where(
        ExecucaoSincronizacao.tipo_fonte == tipo_fonte,
        ExecucaoSincronizacao.ano == ano,
        ExecucaoSincronizacao.parent_execucao_id.is_(None),
    ).order_by(ExecucaoSincronizacao.iniciada_em.desc())
    root_executions = list(db.scalars(exec_root_stmt).all())

    # Se nao houver por parent_execucao_id IS NULL, busca pelo nome exato do arquivo principal
    if not root_executions:
        exec_root_stmt_alt = select(ExecucaoSincronizacao).where(
            ExecucaoSincronizacao.tipo_fonte == tipo_fonte,
            ExecucaoSincronizacao.ano == ano,
            ExecucaoSincronizacao.arquivo == arquivo_principal,
        ).order_by(ExecucaoSincronizacao.iniciada_em.desc())
        root_executions = list(db.scalars(exec_root_stmt_alt).all())

    latest_root_exec = root_executions[0] if root_executions else None

    # Filhos
    child_executions: list[ExecucaoSincronizacao] = []
    if latest_root_exec is not None:
        child_executions = list(
            db.scalars(
                select(ExecucaoSincronizacao)
                .where(ExecucaoSincronizacao.parent_execucao_id == latest_root_exec.id)
                .order_by(ExecucaoSincronizacao.iniciada_em.asc())
            ).all()
        )
    elif ano is not None:
        child_executions = list(
            db.scalars(
                select(ExecucaoSincronizacao)
                .where(
                    ExecucaoSincronizacao.tipo_fonte == tipo_fonte,
                    ExecucaoSincronizacao.ano == ano,
                    ExecucaoSincronizacao.tipo_execucao == "arquivo_membro",
                )
                .order_by(ExecucaoSincronizacao.iniciada_em.asc())
            ).all()
        )

    # 2. Runs tecnicas
    runs_stmt = select(IngestionRun).where(
        IngestionRun.tipo_fonte == tipo_fonte,
        IngestionRun.ano == ano,
    ).order_by(IngestionRun.created_at.desc())
    runs = list(db.scalars(runs_stmt).all())
    latest_run = runs[0] if runs else None

    # 3. Snapshots de artefatos
    snapshots_stmt = select(SourceArtifactSnapshot).where(
        SourceArtifactSnapshot.tipo_fonte == tipo_fonte,
        SourceArtifactSnapshot.ano == ano,
    ).order_by(SourceArtifactSnapshot.created_at.desc())
    snapshots = list(db.scalars(snapshots_stmt).all())

    # 4. Updates pendentes
    updates_stmt = select(PendingUpdate).where(
        PendingUpdate.fonte == tipo_fonte,
        PendingUpdate.ano == ano,
    ).order_by(PendingUpdate.detection_timestamp.desc())
    pending_updates = list(db.scalars(updates_stmt).all())

    if not root_executions and not runs and not snapshots and not pending_updates:
        # Verifica se ao menos existe no catalogo
        fonte_reg = obter_fonte(tipo_fonte)
        if fonte_reg is None:
            return None

    # 5. Auditorias de operacao
    scope_ids = [file_id]
    if latest_run is not None:
        scope_ids.append(str(latest_run.id))
    for r in runs:
        scope_ids.append(str(r.id))
    audits = list(
        db.scalars(
            select(IngestionOperationAudit)
            .where(IngestionOperationAudit.scope_id.in_(scope_ids))
            .order_by(IngestionOperationAudit.created_at.asc())
        ).all()
    )
    audit_ops = [a.operation for a in audits]

    # 6. Membros descobertos / snapshots de membros
    member_snapshots: list[SourceMemberSnapshot] = []
    if snapshots:
        snap_ids = [s.id for s in snapshots]
        member_snapshots = list(
            db.scalars(
                select(SourceMemberSnapshot)
                .where(SourceMemberSnapshot.artifact_snapshot_id.in_(snap_ids))
                .order_by(SourceMemberSnapshot.created_at.asc())
            ).all()
        )

    # IngestionFileMembers
    file_members: list[IngestionFileMember] = []
    if runs:
        run_ids = [r.id for r in runs]
        file_members = list(
            db.scalars(
                select(IngestionFileMember)
                .join(IngestionFile, IngestionFile.id == IngestionFileMember.ingestion_file_id)
                .where(IngestionFile.ingestion_run_id.in_(run_ids))
            ).all()
        )

    # Quarentena
    quar_total = int(
        db.scalar(
            select(func.count(QuarantineItem.id))
            .where(
                QuarantineItem.ano_origem == ano,
                QuarantineItem.arquivo_origem.like(f"{tipo_fonte}%") if ano is not None else QuarantineItem.arquivo_origem.like("cad%"),
            )
        ) or 0
    )
    quar_pendente = int(
        db.scalar(
            select(func.count(QuarantineItem.id))
            .where(
                QuarantineItem.ano_origem == ano,
                QuarantineItem.status == "pendente",
                QuarantineItem.arquivo_origem.like(f"{tipo_fonte}%") if ano is not None else QuarantineItem.arquivo_origem.like("cad%"),
            )
        ) or 0
    )

    # 7. Mapeamento de membros presentes
    members_present: dict[str, dict[str, Any]] = {}
    for c in child_executions:
        members_present[c.arquivo] = {
            "status": c.status,
            "canonical_write_confirmed": c.status == "sucesso" and (c.total_inseridos + c.total_atualizados + c.total_inalterados > 0),
            "total_linhas": c.total_linhas_lidas,
            "sha256": c.hash_arquivo,
            "execucao_id": str(c.id),
            "mensagem_erro": c.mensagem_erro,
        }
    for m in member_snapshots:
        if m.member_name not in members_present:
            members_present[m.member_name] = {
                "status": m.lifecycle_status or "processed",
                "canonical_write_confirmed": m.lifecycle_status == "processed",
                "total_linhas": m.row_count,
                "sha256": m.member_sha256,
                "execucao_id": None,
                "mensagem_erro": None,
            }
    for fm in file_members:
        if fm.member_name not in members_present:
            members_present[fm.member_name] = {
                "status": "sucesso" if fm.schema_status == "ok" else "falha",
                "canonical_write_confirmed": fm.schema_status == "ok",
                "total_linhas": fm.row_count,
                "sha256": fm.member_sha256,
                "execucao_id": None,
                "mensagem_erro": fm.schema_message,
            }

    # 8. Datasets obrigatorios
    datasets_obrig = datasets_obrigatorios_para_fonte(tipo_fonte, ano)

    # 9. Conclusoes e escritas canonicas comprovadas
    root_write_confirmed = (
        (latest_root_exec is not None and latest_root_exec.status == "sucesso")
        or (latest_run is not None and latest_run.status in ("sucesso", "sucesso_com_alerta"))
    )

    integridade_detalhe = calcular_integridade(
        tipo_fonte=tipo_fonte,
        ano=ano,
        is_container=is_container,
        datasets_obrigatorios=datasets_obrig,
        members_present=members_present,
        root_execution=latest_root_exec,
        root_run=latest_run,
        audit_operations=audit_ops,
        quarantine_total=quar_total,
        quarantine_pendente=quar_pendente,
        canonical_write_confirmed=root_write_confirmed,
    )

    # 10. Versoes observadas
    versoes_dict: dict[str, IngestionVersionSummary] = {}

    exec_by_sha: dict[str, ExecucaoSincronizacao] = {}
    for ex in root_executions:
        if ex.hash_arquivo:
            exec_by_sha[ex.hash_arquivo] = ex

    for snap in reversed(snapshots):
        if snap.content_sha256:
            corresponding_exec = exec_by_sha.get(snap.content_sha256)
            is_snap_success = (
                snap.status == "sucesso"
                or (corresponding_exec is not None and corresponding_exec.status == "sucesso")
            )
            v_integridade = "completo" if is_snap_success else "parcial"
            v_status = "sucesso" if is_snap_success else snap.status
            v_total = corresponding_exec.total_linhas_lidas if corresponding_exec else None
            versoes_dict[snap.content_sha256] = IngestionVersionSummary(
                sha256=snap.content_sha256,
                detected_at=_aware(snap.created_at),
                processed_at=_aware(snap.updated_at),
                status=v_status,
                integridade=v_integridade,
                role="historica",
                total_linhas=v_total,
                storage_uri=snap.storage_uri,
            )

    for ex in reversed(root_executions):
        if ex.hash_arquivo and ex.hash_arquivo not in versoes_dict:
            is_ex_success = ex.status == "sucesso"
            versoes_dict[ex.hash_arquivo] = IngestionVersionSummary(
                sha256=ex.hash_arquivo,
                detected_at=_aware(ex.iniciada_em),
                processed_at=_aware(ex.finalizada_em),
                status=ex.status,
                integridade="completo" if is_ex_success else "parcial",
                role="historica",
                total_linhas=ex.total_linhas_lidas,
                storage_uri=None,
            )

    for pu in reversed(pending_updates):
        sha = pu.artifact_url
        if sha not in versoes_dict:
            versoes_dict[sha] = IngestionVersionSummary(
                sha256=None,
                detected_at=_aware(pu.detection_timestamp),
                processed_at=None,
                status=pu.status,
                integridade="nao_aplicado" if pu.status != "applied" else "completo",
                role="apenas_detectada" if pu.status == "pending" else "alvo",
                total_linhas=None,
                storage_uri=None,
            )

    # Versao em uso e versao alvo
    versao_em_uso: IngestionVersionSummary | None = None
    versao_alvo: IngestionVersionSummary | None = None

    for v in reversed(list(versoes_dict.values())):
        if v.status == "sucesso" and v.integridade in ("completo", "completo_com_ressalvas"):
            v.role = "em_uso"
            versao_em_uso = v
            break

    if latest_run is not None or latest_root_exec is not None:
        sha_alvo = (
            latest_root_exec.hash_arquivo
            if latest_root_exec and latest_root_exec.hash_arquivo
            else (snapshots[0].content_sha256 if snapshots else None)
        )
        status_alvo = (
            latest_root_exec.status
            if latest_root_exec
            else (latest_run.status if latest_run else "desconhecido")
        )
        target_detected = (
            latest_root_exec.iniciada_em if latest_root_exec else latest_run.created_at if latest_run else None
        )
        target_processed = (
            latest_root_exec.finalizada_em if latest_root_exec else latest_run.finished_at if latest_run else None
        )
        if versao_em_uso is not None and versao_em_uso.sha256 == sha_alvo and status_alvo == "sucesso":
            versao_alvo = versao_em_uso
        else:
            versao_alvo = IngestionVersionSummary(
                sha256=sha_alvo,
                detected_at=_aware(target_detected),
                processed_at=_aware(target_processed),
                status=status_alvo,
                integridade=integridade_detalhe.status if status_alvo == "sucesso" else "parcial" if status_alvo == "falha" else "nao_aplicado",
                role="alvo",
                total_linhas=latest_root_exec.total_linhas_lidas if latest_root_exec else None,
                storage_uri=snapshots[0].storage_uri if snapshots else None,
            )
            if versao_em_uso is None and status_alvo == "sucesso" and integridade_detalhe.status in ("completo", "completo_com_ressalvas"):
                versao_em_uso = versao_alvo
                versao_alvo.role = "em_uso"

    # Se ainda nao tem versao em uso, mas root teve sucesso
    if versao_em_uso is None and latest_root_exec is not None and latest_root_exec.status == "sucesso":
        versao_em_uso = IngestionVersionSummary(
            sha256=latest_root_exec.hash_arquivo,
            detected_at=_aware(latest_root_exec.iniciada_em),
            processed_at=_aware(latest_root_exec.finalizada_em),
            status=latest_root_exec.status,
            integridade=integridade_detalhe.status,
            role="em_uso",
            total_linhas=latest_root_exec.total_linhas_lidas,
            storage_uri=None,
        )

    # 11. Atividade operacional
    child_statuses = [c.status for c in child_executions]
    atividade_atual = calcular_atividade_atual(
        root_status=latest_root_exec.status if latest_root_exec else None,
        children_statuses=child_statuses,
    )

    # 12. Falha relevante e resolucao
    falha_relevante: IngestionFailureDetail | None = None
    has_later_success = (
        len(root_executions) > 1
        and latest_root_exec is not None
        and latest_root_exec.status == "sucesso"
        and root_executions[-1].status == "falha"
    )
    has_superseding = (
        versao_em_uso is not None
        and versao_alvo is not None
        and versao_alvo.status == "falha"
        and versao_em_uso.sha256 != versao_alvo.sha256
    )

    if latest_root_exec is not None and latest_root_exec.status == "falha":
        resolucao = calcular_resolucao_falha(
            failed_target_type="file",
            failed_target_id=file_id,
            latest_status=latest_root_exec.status,
            audit_operations=audit_ops,
            has_later_successful_attempt=has_later_success,
            has_superseding_version=has_superseding,
        )
        falha_relevante = IngestionFailureDetail(
            target_type="file",
            target_id=file_id,
            target_name=arquivo_principal,
            etapa=latest_run.phase if latest_run else "pre_download",
            codigo_erro="EXECUTION_FAILED",
            mensagem_erro=latest_root_exec.mensagem_erro or "Falha registrada na execucao principal.",
            resolucao=resolucao,
            reparavel=True,
            attempt_number=1,
            acknowledged_at=audits[-1].created_at if "acknowledge-failure" in audit_ops else None,
            acknowledged_by=None,
        )
    elif integridade_detalhe.membros_com_falha:
        primeiro_falho = integridade_detalhe.membros_com_falha[0]
        member_id = build_member_id(file_id, primeiro_falho)
        falha_relevante = IngestionFailureDetail(
            target_type="member",
            target_id=member_id,
            target_name=primeiro_falho,
            etapa="stage",
            codigo_erro="MEMBER_FAILED",
            mensagem_erro=members_present.get(primeiro_falho, {}).get("mensagem_erro") or "Falha no processamento do membro.",
            resolucao=calcular_resolucao_falha(
                failed_target_type="member",
                failed_target_id=member_id,
                latest_status=members_present.get(primeiro_falho, {}).get("status", "falha"),
                audit_operations=audit_ops,
                has_later_successful_attempt=has_later_success,
                has_superseding_version=has_superseding,
            ),
            reparavel=True,
            attempt_number=1,
        )
    elif integridade_detalhe.membros_faltantes:
        primeiro_faltante = integridade_detalhe.membros_faltantes[0]
        member_id = build_member_id(file_id, primeiro_faltante)
        falha_relevante = IngestionFailureDetail(
            target_type="member",
            target_id=member_id,
            target_name=primeiro_faltante,
            etapa="extract",
            codigo_erro="REQUIRED_MEMBER_MISSING",
            mensagem_erro=f"Membro obrigatorio '{primeiro_faltante}' ausente no pacote.",
            resolucao="aberta",
            reparavel=False,
            attempt_number=1,
        )

    # 13. Acoes permitidas e proxima acao
    allowed_actions: list[IngestionAllowedAction] = []
    next_action: str | None = None
    requires_operator = False

    if atividade_atual == "aguardando_parent_window":
        next_action = "wait"
        requires_operator = False
    elif atividade_atual == "em_processamento":
        next_action = "wait"
        requires_operator = False
    elif latest_root_exec is not None and latest_root_exec.status == "aguardando_ingestao":
        next_action = "start_ingestion"
        requires_operator = True
        allowed_actions.append(
            IngestionAllowedAction(
                action="start_ingestion",
                target=IngestionActionTarget(target_type="file", target_id=file_id, target_name=arquivo_principal),
                endpoint=f"/ingestion/sincronizacoes/{latest_root_exec.id}/iniciar",
                method="POST",
                description="Iniciar ingestao pendente do pacote de sincronizacao.",
                requires_operator=True,
            )
        )
    elif falha_relevante is not None and falha_relevante.resolucao in ("aberta", "em_nova_tentativa"):
        next_action = "replay"
        requires_operator = True
        if latest_root_exec is not None:
            allowed_actions.append(
                IngestionAllowedAction(
                    action="replay",
                    target=IngestionActionTarget(target_type="file", target_id=file_id, target_name=arquivo_principal),
                    endpoint=f"/ingestion/sincronizacoes/{latest_root_exec.id}/replay",
                    method="POST",
                    description="Reexecutar sincronizacao do pacote e recuperar lacunas de membros.",
                    requires_operator=True,
                )
            )
        if latest_run is not None:
            allowed_actions.append(
                IngestionAllowedAction(
                    action="recover",
                    target=IngestionActionTarget(target_type="run", target_id=str(latest_run.id), target_name=arquivo_principal),
                    endpoint=f"/ingestion/runs/{latest_run.id}/recover",
                    method="POST",
                    description="Recuperar execucao da run interrompida deterministicamente.",
                    requires_operator=True,
                )
            )
            allowed_actions.append(
                IngestionAllowedAction(
                    action="acknowledge_failure",
                    target=IngestionActionTarget(target_type="run", target_id=str(latest_run.id), target_name=arquivo_principal),
                    endpoint=f"/ingestion/runs/{latest_run.id}/acknowledge-failure",
                    method="POST",
                    description="Reconhecer falha operacional e encerrar investigacao sem reparar integridade.",
                    requires_operator=True,
                )
            )
    else:
        next_action = "none"
        requires_operator = False

    # 14. Tentativas (Attempts)
    tentativas: list[IngestionAttemptSummary] = []

    # Phases by run id
    phases_by_run: dict[uuid.UUID, list[IngestionPhaseExecution]] = defaultdict(list)
    if runs:
        for ph in db.scalars(
            select(IngestionPhaseExecution)
            .where(IngestionPhaseExecution.ingestion_run_id.in_([r.id for r in runs]))
            .order_by(IngestionPhaseExecution.attempt.asc(), IngestionPhaseExecution.created_at.asc())
        ).all():
            phases_by_run[ph.ingestion_run_id].append(ph)

    attempt_counter = 1
    for r in reversed(runs):
        # Determina correlacao
        if "replay" in audit_ops:
            corr = "replay"
        elif "recover" in audit_ops:
            corr = "recovery"
        elif attempt_counter == 1:
            corr = "original"
        else:
            corr = "desconhecida"

        r_phases = [
            IngestionRunPhaseExecutionResumo(
                id=str(p.id),
                phase=p.phase,
                status=p.status,
                attempt=p.attempt,
                task_id=p.task_id,
                lease_owner=p.lease_owner,
                started_at=_aware(p.started_at),
                heartbeat_at=_aware(p.heartbeat_at),
                finished_at=_aware(p.finished_at),
                cancel_requested_at=_aware(p.cancel_requested_at),
            )
            for p in phases_by_run.get(r.id, [])
        ]

        tentativas.append(
            IngestionAttemptSummary(
                attempt_id=str(r.id),
                attempt_number=attempt_counter,
                correlacao=corr,
                origem_tentativa_id=str(runs[-1].id) if len(runs) > 1 and r.id != runs[-1].id else None,
                run_id=str(r.id),
                execucao_id=str(r.execucao_sincronizacao_id) if r.execucao_sincronizacao_id else None,
                status=r.status,
                phase=r.phase,
                iniciada_em=_aware(r.started_at or r.created_at) or datetime.now(UTC),
                finalizada_em=_aware(r.finished_at),
                mensagem_erro=r.quality_summary.get("error") if isinstance(r.quality_summary, dict) else None,
                etapas=r_phases,
            )
        )
        attempt_counter += 1

    if not tentativas and latest_root_exec is not None:
        tentativas.append(
            IngestionAttemptSummary(
                attempt_id=str(latest_root_exec.id),
                attempt_number=1,
                correlacao="original",
                origem_tentativa_id=None,
                run_id=None,
                execucao_id=str(latest_root_exec.id),
                status=latest_root_exec.status,
                phase=None,
                iniciada_em=_aware(latest_root_exec.iniciada_em) or datetime.now(UTC),
                finalizada_em=_aware(latest_root_exec.finalizada_em),
                mensagem_erro=latest_root_exec.mensagem_erro,
                etapas=[],
            )
        )

    # 15. Membros logicos estruturados
    membros_logicos: list[IngestionLogicalMemberSummary] = []
    has_discovered_members = bool(members_present or member_snapshots or file_members)
    if is_container and has_discovered_members:
        # Cruza datasets do catalogo com os membros presentes
        seen_names: set[str] = set()
        fonte_reg = obter_fonte(tipo_fonte)
        datasets_todos = fonte_reg.datasets if fonte_reg else ()

        for ds in datasets_todos:
            try:
                m_nome = ds.render_member_name(ano=ano)
            except Exception:
                m_nome = ds.member_name_template
            seen_names.add(m_nome)
            info = members_present.get(m_nome, {})
            m_status = info.get("status", "nao_iniciado")
            m_id = build_member_id(file_id, m_nome)
            m_falha: IngestionFailureDetail | None = None
            if m_status in ("falha", "quality_fail"):
                m_falha = IngestionFailureDetail(
                    target_type="member",
                    target_id=m_id,
                    target_name=m_nome,
                    etapa="stage",
                    codigo_erro="MEMBER_FAILED",
                    mensagem_erro=info.get("mensagem_erro") or "Falha no processamento do membro.",
                    resolucao=calcular_resolucao_falha(
                        failed_target_type="member",
                        failed_target_id=m_id,
                        latest_status=m_status,
                        audit_operations=audit_ops,
                        has_later_successful_attempt=has_later_success,
                        has_superseding_version=has_superseding,
                    ),
                    reparavel=True,
                )

            membros_logicos.append(
                IngestionLogicalMemberSummary(
                    member_id=m_id,
                    parent_file_id=file_id,
                    member_name=m_nome,
                    tipo_fonte=tipo_fonte,
                    ano=ano,
                    dataset_key=ds.dataset,
                    descricao=ds.descricao,
                    obrigatorio=ds.obrigatorio,
                    status=m_status,
                    integridade="completo" if m_status == "sucesso" else "parcial" if m_status == "falha" else "nao_aplicado",
                    sha256=info.get("sha256"),
                    total_linhas=info.get("total_linhas"),
                    quarentena_total=0,
                    next_action="wait" if m_status == "aguardando_parent_window" else "replay" if m_status == "falha" else None,
                    resolucao_falha=m_falha.resolucao if m_falha else None,
                    falha=m_falha,
                )
            )

        # Adiciona membros extras nao mapeados no catalogo
        for m_nome, info in members_present.items():
            if m_nome not in seen_names:
                m_id = build_member_id(file_id, m_nome)
                membros_logicos.append(
                    IngestionLogicalMemberSummary(
                        member_id=m_id,
                        parent_file_id=file_id,
                        member_name=m_nome,
                        tipo_fonte=tipo_fonte,
                        ano=ano,
                        dataset_key=None,
                        descricao=None,
                        obrigatorio=False,
                        status=info.get("status", "sucesso"),
                        integridade="completo" if info.get("status") == "sucesso" else "parcial",
                        sha256=info.get("sha256"),
                        total_linhas=info.get("total_linhas"),
                        quarentena_total=0,
                        next_action=None,
                        resolucao_falha=None,
                        falha=None,
                    )
                )

    # 16. Montagem do resumo e detalhe
    ultima_ativ = None
    if latest_root_exec is not None:
        ultima_ativ = latest_root_exec.finalizada_em or latest_root_exec.iniciada_em
    elif latest_run is not None:
        ultima_ativ = latest_run.finished_at or latest_run.updated_at or latest_run.started_at

    concluido_em = None
    if versao_em_uso is not None and versao_em_uso.processed_at:
        concluido_em = versao_em_uso.processed_at
    elif latest_root_exec is not None and latest_root_exec.finalizada_em:
        concluido_em = latest_root_exec.finalizada_em

    progresso = 100.0 if integridade_detalhe.status == "completo" else 0.0
    if integridade_detalhe.membros_obrigatorios_esperados > 0:
        progresso = round(
            (integridade_detalhe.membros_processados / integridade_detalhe.membros_obrigatorios_esperados) * 100.0,
            1,
        )

    return IngestionLogicalFileDetalhe(
        file_id=file_id,
        tipo_fonte=tipo_fonte,
        ano=ano,
        arquivo_principal=arquivo_principal,
        is_container=is_container,
        atividade_atual=atividade_atual,
        integridade_em_uso=versao_em_uso.integridade if versao_em_uso else "nao_aplicado",
        resultado_alvo=versao_alvo.status if versao_alvo else None,
        versao_em_uso=versao_em_uso,
        versao_alvo=versao_alvo,
        etapa_relevante=latest_run.phase if latest_run else None,
        progresso_porcentagem=progresso,
        falha_relevante=falha_relevante,
        next_action=next_action,
        requires_operator=requires_operator,
        total_membros=len(membros_logicos),
        membros_com_falha=len(integridade_detalhe.membros_com_falha),
        ultima_atividade_em=_aware(ultima_ativ),
        concluido_em=_aware(concluido_em),
        integridade_detalhe=integridade_detalhe,
        membros=membros_logicos,
        versoes=list(versoes_dict.values()),
        tentativas=tentativas,
        allowed_actions=allowed_actions,
    )


def listar_arquivos_logicos(
    db: Session,
    *,
    ano: int | None = None,
    fonte: str | None = None,
    arquivo: str | None = None,
    atividade: str | None = None,
    integridade: str | None = None,
    necessidade_intervencao: bool | None = None,
    resolucao_falha: str | None = None,
    concluido_apos: datetime | None = None,
    concluido_antes: datetime | None = None,
    pagina: int = 1,
    tamanho_pagina: int = 50,
) -> tuple[int, list[IngestionLogicalFileSummary]]:
    """Lista arquivos logicos de forma paginada com contagem nao truncada e filtros server-side."""
    concluido_apos_aware = _aware(concluido_apos)
    concluido_antes_aware = _aware(concluido_antes)

    # 1. Coleta chaves unicas de arquivos conhecidos
    file_keys: set[FileKey] = set()
    latest_root_by_scope: dict[FileScope, tuple[uuid.UUID, str]] = {}

    # De ExecucaoSincronizacao (raiz: parent_execucao_id IS NULL)
    exec_query = select(
        ExecucaoSincronizacao.id,
        ExecucaoSincronizacao.tipo_fonte,
        ExecucaoSincronizacao.ano,
        ExecucaoSincronizacao.arquivo,
        ExecucaoSincronizacao.status,
    ).where(ExecucaoSincronizacao.parent_execucao_id.is_(None))
    if fonte:
        exec_query = exec_query.where(ExecucaoSincronizacao.tipo_fonte == fonte)
    if ano is not None:
        exec_query = exec_query.where(ExecucaoSincronizacao.ano == ano)
    exec_query = exec_query.order_by(ExecucaoSincronizacao.iniciada_em.desc())
    for execution_id, f, a, arq, status in db.execute(exec_query).all():
        file_keys.add((f, a, arq))
        latest_root_by_scope.setdefault((f, a), (execution_id, status))

    # De IngestionRun
    run_query = select(IngestionRun.tipo_fonte, IngestionRun.ano).distinct()
    if fonte:
        run_query = run_query.where(IngestionRun.tipo_fonte == fonte)
    if ano is not None:
        run_query = run_query.where(IngestionRun.ano == ano)
    for f, a in db.execute(run_query).all():
        arq = resolver_nome_arquivo_principal(f, a)
        file_keys.add((f, a, arq))

    # De PendingUpdate
    update_query = select(PendingUpdate.fonte, PendingUpdate.ano).distinct()
    if fonte:
        update_query = update_query.where(PendingUpdate.fonte == fonte)
    if ano is not None:
        update_query = update_query.where(PendingUpdate.ano == ano)
    for f, a in db.execute(update_query).all():
        arq = resolver_nome_arquivo_principal(f, a)
        file_keys.add((f, a, arq))

    # Se nenhum registro encontrado no DB e filtros batem com o catalogo, adiciona do catalogo
    if not file_keys:
        for f_reg in listar_fontes():
            if fonte and f_reg.fonte != fonte:
                continue
            if f_reg.tipo_distribuicao == "zip_anual":
                if ano is not None:
                    file_keys.add((f_reg.fonte, ano, f_reg.render_arquivo_principal(ano=ano)))
            else:
                if ano is None:
                    file_keys.add((f_reg.fonte, None, f_reg.arquivo_principal_template))

    if atividade == "em_processamento":
        active_scopes, active_file_keys = _em_processamento_scopes(db, file_keys, latest_root_by_scope)
        file_keys = {key for key in file_keys if key[:2] in active_scopes or key in active_file_keys}

    # Filtragem preliminar de string de arquivo
    filtered_keys = []
    for f, a, arq in file_keys:
        if arquivo and arquivo.lower() not in arq.lower():
            continue
        filtered_keys.append((f, a, arq))

    # Ordenacao estavel: ano decrescente (nulos primeiro), fonte ascendente, arquivo ascendente
    filtered_keys.sort(key=lambda k: (k[1] is None, -(k[1] or 0), k[0], k[2]))

    # Constrói objetos completos para avaliar os filtros operacionais
    computed_files: list[IngestionLogicalFileSummary] = []
    for f, a, arq in filtered_keys:
        fid = build_file_id(f, a, arq)
        detalhe = obter_arquivo_logico(db, fid)
        if detalhe is None:
            continue

        # Filtros operacionais
        if atividade and detalhe.atividade_atual != atividade:
            continue
        if integridade and detalhe.integridade_em_uso != integridade:
            continue
        if necessidade_intervencao is not None and detalhe.requires_operator != necessidade_intervencao:
            continue
        if resolucao_falha:
            if not detalhe.falha_relevante or detalhe.falha_relevante.resolucao != resolucao_falha:
                continue
        if concluido_apos_aware and (detalhe.concluido_em is None or detalhe.concluido_em < concluido_apos_aware):
            continue
        if concluido_antes_aware and (detalhe.concluido_em is None or detalhe.concluido_em > concluido_antes_aware):
            continue

        # Converte para Summary
        computed_files.append(
            IngestionLogicalFileSummary(
                file_id=detalhe.file_id,
                tipo_fonte=detalhe.tipo_fonte,
                ano=detalhe.ano,
                arquivo_principal=detalhe.arquivo_principal,
                is_container=detalhe.is_container,
                atividade_atual=detalhe.atividade_atual,
                integridade_em_uso=detalhe.integridade_em_uso,
                resultado_alvo=detalhe.resultado_alvo,
                versao_em_uso=detalhe.versao_em_uso,
                versao_alvo=detalhe.versao_alvo,
                etapa_relevante=detalhe.etapa_relevante,
                progresso_porcentagem=detalhe.progresso_porcentagem,
                falha_relevante=detalhe.falha_relevante,
                next_action=detalhe.next_action,
                requires_operator=detalhe.requires_operator,
                total_membros=detalhe.total_membros,
                membros_com_falha=detalhe.membros_com_falha,
                ultima_atividade_em=detalhe.ultima_atividade_em,
                concluido_em=detalhe.concluido_em,
            )
        )

    total_arquivos = len(computed_files)
    offset = (pagina - 1) * tamanho_pagina
    paged_items = computed_files[offset : offset + tamanho_pagina]

    return total_arquivos, paged_items


def listar_arquivos_membros(
    db: Session,
    *,
    ano: int | None = None,
    fonte: str | None = None,
    busca: str | None = None,
    status: str | None = None,
    obrigatorio: bool | None = None,
    pagina: int = 1,
    tamanho_pagina: int = 50,
) -> tuple[int, list[IngestionLogicalMemberSummary]]:
    """Lista arquivos membros de forma paginada com contagem total e filtros server-side."""
    member_keys: dict[tuple[str, str, int | None], dict[str, Any]] = {}

    # 1. ExecucaoSincronizacao de membros
    exec_stmt = select(
        ExecucaoSincronizacao.arquivo,
        ExecucaoSincronizacao.tipo_fonte,
        ExecucaoSincronizacao.ano,
        ExecucaoSincronizacao.status,
        ExecucaoSincronizacao.hash_arquivo,
        ExecucaoSincronizacao.total_linhas_lidas,
        ExecucaoSincronizacao.mensagem_erro,
        ExecucaoSincronizacao.parent_execucao_id,
    ).where(
        (ExecucaoSincronizacao.tipo_execucao == "arquivo_membro") | (ExecucaoSincronizacao.parent_execucao_id.is_not(None))
    )
    if fonte:
        exec_stmt = exec_stmt.where(ExecucaoSincronizacao.tipo_fonte == fonte)
    if ano is not None:
        exec_stmt = exec_stmt.where(ExecucaoSincronizacao.ano == ano)

    for arq, f, a, st, h, tot, err, p_id in db.execute(exec_stmt.order_by(ExecucaoSincronizacao.iniciada_em.desc())).all():
        if not arq:
            continue
        key = (arq, f, a)
        if key not in member_keys:
            member_keys[key] = {
                "status": st,
                "sha256": h,
                "total_linhas": tot,
                "mensagem_erro": err,
                "parent_execucao_id": p_id,
            }

    # 2. SourceMemberSnapshot
    snap_stmt = select(
        SourceMemberSnapshot.member_name,
        SourceArtifactSnapshot.tipo_fonte,
        SourceArtifactSnapshot.ano,
        SourceMemberSnapshot.schema_status,
        SourceMemberSnapshot.member_sha256,
        SourceMemberSnapshot.row_count,
        SourceMemberSnapshot.schema_message,
    ).join(
        SourceArtifactSnapshot, SourceArtifactSnapshot.id == SourceMemberSnapshot.artifact_snapshot_id
    )
    if fonte:
        snap_stmt = snap_stmt.where(SourceArtifactSnapshot.tipo_fonte == fonte)
    if ano is not None:
        snap_stmt = snap_stmt.where(SourceArtifactSnapshot.ano == ano)

    for m_name, f, a, s_st, s_sha, s_rows, s_msg in db.execute(snap_stmt.order_by(SourceMemberSnapshot.created_at.desc())).all():
        key = (m_name, f, a)
        if key not in member_keys:
            member_keys[key] = {
                "status": "sucesso" if s_st == "ok" else "falha",
                "sha256": s_sha,
                "total_linhas": s_rows,
                "mensagem_erro": s_msg,
                "parent_execucao_id": None,
            }

    # 3. Catalogo de fontes
    for f_reg in listar_fontes():
        if fonte and f_reg.fonte != fonte:
            continue
        if f_reg.tipo_distribuicao == "zip_anual":
            anos_alvo = [ano] if ano is not None else [None]
            for target_year in anos_alvo:
                for ds in f_reg.datasets:
                    try:
                        m_name = ds.render_member_name(ano=target_year)
                    except Exception:
                        m_name = ds.member_name_template
                    key = (m_name, f_reg.fonte, target_year)
                    if key not in member_keys:
                        member_keys[key] = {
                            "status": "nao_iniciado",
                            "sha256": None,
                            "total_linhas": None,
                            "mensagem_erro": None,
                            "parent_execucao_id": None,
                        }

    # 4. Quarentena
    quarantine_counts: dict[str, int] = dict(
        db.execute(
            select(QuarantineItem.arquivo_origem, func.count(QuarantineItem.id))
            .group_by(QuarantineItem.arquivo_origem)
        ).all()
    )

    # 5. Filtragem e construcao de itens
    items: list[IngestionLogicalMemberSummary] = []
    busca_lower = busca.lower().strip() if busca else None

    for (m_name, f, a), info in member_keys.items():
        if busca_lower and busca_lower not in m_name.lower():
            continue

        parent_arq = resolver_nome_arquivo_principal(f, a)
        parent_fid = build_file_id(f, a, parent_arq)
        m_id = build_member_id(parent_fid, m_name)

        ds_info = dataset_por_member_name(f, m_name, a) if a is not None else None
        obr = ds_info.obrigatorio if ds_info else False
        if obrigatorio is not None and obr != obrigatorio:
            continue

        m_status = info["status"]
        if status and m_status != status:
            continue

        q_count = quarantine_counts.get(m_name, 0)
        m_integridade = "completo" if m_status == "sucesso" else "parcial" if m_status == "falha" else "nao_aplicado"

        m_falha = None
        if m_status in ("falha", "quality_fail"):
            m_falha = IngestionFailureDetail(
                target_type="member",
                target_id=m_id,
                target_name=m_name,
                etapa="stage",
                codigo_erro="MEMBER_FAILED",
                mensagem_erro=info["mensagem_erro"] or "Falha no processamento do membro.",
                resolucao="aberta",
                reparavel=True,
            )

        items.append(
            IngestionLogicalMemberSummary(
                member_id=m_id,
                parent_file_id=parent_fid,
                member_name=m_name,
                tipo_fonte=f,
                ano=a,
                dataset_key=ds_info.dataset if ds_info else None,
                descricao=ds_info.descricao if ds_info else None,
                obrigatorio=obr,
                status=m_status,
                integridade=m_integridade,
                sha256=info["sha256"],
                total_linhas=info["total_linhas"],
                quarentena_total=q_count,
                next_action="replay" if m_status == "falha" else None,
                resolucao_falha="aberta" if m_status == "falha" else None,
                falha=m_falha,
            )
        )

    items.sort(key=lambda x: (x.ano is None, -(x.ano or 0), x.tipo_fonte or "", x.member_name))

    total = len(items)
    offset = (pagina - 1) * tamanho_pagina
    paginated = items[offset : offset + tamanho_pagina]
    return total, paginated
