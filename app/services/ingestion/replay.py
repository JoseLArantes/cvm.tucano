from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.companhia import Companhia
from app.models.ingestion import IngestionRow, IngestionRun, QuarantineItem
from app.services.ingestion.fca import _promote_fca_row, normalizar_fca_row
from app.services.ingestion.financeiro import _promote_financeiro_row, normalizar_financeiro_row
from app.services.ingestion.fre import _promote_fre_row, normalizar_fre_row
from app.services.ingestion.ipe import _promote_ipe_row, normalizar_ipe_row
from app.services.ingestion.quarantine import (
    create_quarantine_item,
    mark_quarantine_resolved,
    register_quarantine_replay_attempt,
)
from app.services.ingestion.repair_rules import find_matching_repair_rule
from app.services.ingestion.resolver import (
    STATUS_PROVISIONAL_CREATED,
    STATUS_RESOLVED,
    ResolverInput,
    persist_resolution_result,
    register_document_header,
    resolve_companhia,
)
from app.services.ingestion.staging import register_attempt, register_row_event
from app.services.ingestion.summary import persist_quality_summary
from app.services.ingestion.validation import (
    build_natural_key,
    classify_duplicate,
    invalid_result,
    write_validation_result,
)


def _build_header_map_for_run(db: Session, *, run_id: Any) -> dict[Any, Any]:
    header_map: dict[Any, Any] = {}
    rows = list(
        db.execute(
            select(IngestionRow).where(
                IngestionRow.ingestion_run_id == run_id,
                IngestionRow.row_kind.in_(("dfp_documento", "itr_documento", "fre_documento", "fca_documento")),
                IngestionRow.resolved_companhia_id.is_not(None),
            )
        ).scalars()
    )
    for row in rows:
        dados = row.normalized_data or {}
        if row.resolved_companhia_id is not None:
            register_document_header(
                header_map,
                tipo_formulario=dados.get(
                    "tipo_formulario",
                    "FRE" if row.row_kind == "fre_documento" else "FCA" if row.row_kind == "fca_documento" else None,
                ),
                id_documento=dados.get("id_documento"),
                versao=dados.get("versao"),
                data_referencia=dados.get("data_referencia"),
                companhia_id=row.resolved_companhia_id,
                cnpj_companhia=dados.get("cnpj_companhia"),
                codigo_cvm=dados.get("codigo_cvm"),
            )
    return header_map


def _renormalize_row(db: Session, row: IngestionRow) -> tuple[str, dict[str, Any]]:
    if row.row_kind.startswith(("dfp_", "itr_")):
        prefixo = row.row_kind.split("_", 1)[0]
        tipo_formulario = prefixo.upper()
        return normalizar_financeiro_row(
            prefixo=prefixo,
            tipo_formulario=tipo_formulario,
            arquivo_origem=row.arquivo_origem,
            ano_origem=row.ano_origem or 0,
            linha_origem=row.linha_origem,
            linha=row.raw_data,
        )
    if row.row_kind.startswith("fre_"):
        tipo_por_row_kind = {
            "fre_documento": "documentos",
            "fre_auditor": "auditores",
            "fre_capital_social": "capital_social",
            "fre_posicao_acionaria": "posicao_acionaria",
            "fre_remuneracao_total_orgao": "remuneracao_total_orgao",
            "fre_empregado_posicao_genero": "empregado_posicao_genero",
            "fre_participacao_sociedade": "participacao_sociedade",
            "fre_empregado_posicao_local": "empregado_posicao_local",
            "fre_empregado_posicao_faixa_etaria": "empregado_posicao_faixa_etaria",
            "fre_empregado_posicao_declaracao_raca": "empregado_posicao_declaracao_raca",
            "fre_empregado_pcd": "empregado_pcd",
            "fre_empregado_local_faixa_etaria": "empregado_local_faixa_etaria",
            "fre_empregado_local_declaracao_raca": "empregado_local_declaracao_raca",
            "fre_empregado_local_declaracao_genero": "empregado_local_declaracao_genero",
            "fre_administrador_pcd": "administrador_pcd",
            "fre_responsavel": "responsavel",
            "fre_capital_social_classe_acao": "capital_social_classe_acao",
            "fre_capital_social_titulo_conversivel": "capital_social_titulo_conversivel",
            "fre_distribuicao_capital": "distribuicao_capital",
            "fre_distribuicao_capital_classe_acao": "distribuicao_capital_classe_acao",
            "fre_posicao_acionaria_classe_acao": "posicao_acionaria_classe_acao",
            "fre_remuneracao_maxima_minima_media": "remuneracao_maxima_minima_media",
            "fre_remuneracao_variavel": "remuneracao_variavel",
            "fre_remuneracao_acao": "remuneracao_acao",
            "fre_acao_entregue": "acao_entregue",
            "fre_administrador_membro_conselho_fiscal": "administrador_membro_conselho_fiscal",
            "fre_membro_comite": "membro_comite",
            "fre_relacao_familiar": "relacao_familiar",
            "fre_relacao_subordinacao": "relacao_subordinacao",
            "fre_transacao_parte_relacionada": "transacao_parte_relacionada",
            "fre_capital_social_aumento": "capital_social_aumento",
            "fre_capital_social_aumento_classe_acao": "capital_social_aumento_classe_acao",
            "fre_capital_social_desdobramento": "capital_social_desdobramento",
            "fre_capital_social_desdobramento_classe_acao": "capital_social_desdobramento_classe_acao",
            "fre_capital_social_reducao": "capital_social_reducao",
            "fre_capital_social_reducao_classe_acao": "capital_social_reducao_classe_acao",
            "fre_direito_acao": "direito_acao",
            "fre_volume_valor_mobiliario": "volume_valor_mobiliario",
            "fre_outro_valor_mobiliario": "outro_valor_mobiliario",
            "fre_titular_valor_mobiliario": "titular_valor_mobiliario",
            "fre_mercado_estrangeiro": "mercado_estrangeiro",
            "fre_titulo_exterior": "titulo_exterior",
            "fre_plano_recompra": "plano_recompra",
            "fre_plano_recompra_classe_acao": "plano_recompra_classe_acao",
            "fre_valor_mobiliario_tesouraria_movimentacao": "valor_mobiliario_tesouraria_movimentacao",
            "fre_valor_mobiliario_tesouraria_ultimo_exercicio": "valor_mobiliario_tesouraria_ultimo_exercicio",
            "fre_administrador_declaracao_genero": "administrador_declaracao_genero",
            "fre_administrador_declaracao_raca": "administrador_declaracao_raca",
        }
        return normalizar_fre_row(
            tipo=tipo_por_row_kind[row.row_kind],
            arquivo_origem=row.arquivo_origem,
            ano_origem=row.ano_origem or 0,
            linha_origem=row.linha_origem,
            linha=row.raw_data,
        )
    if row.row_kind.startswith("fca_"):
        tipo_por_row_kind = {
            "fca_documento": "original",
            "fca_geral": "geral",
            "fca_endereco": "endereco",
            "fca_dri": "dri",
            "fca_auditor": "auditor",
            "fca_valor_mobiliario": "valor_mobiliario",
            "fca_escriturador": "escriturador",
            "fca_canal_divulgacao": "canal_divulgacao",
            "fca_departamento_acionistas": "departamento_acionistas",
            "fca_pais_estrangeiro_negociacao": "pais_estrangeiro_negociacao",
        }
        return normalizar_fca_row(
            tipo=tipo_por_row_kind[row.row_kind],
            arquivo_origem=row.arquivo_origem,
            ano_origem=row.ano_origem or 0,
            linha_origem=row.linha_origem,
            linha=row.raw_data,
        )
    if row.row_kind.startswith("ipe_"):
        return normalizar_ipe_row(
            arquivo_origem=row.arquivo_origem,
            ano_origem=row.ano_origem or 0,
            linha_origem=row.linha_origem,
            linha=row.raw_data,
        )
    raise ValueError(f"row_kind_nao_suportado_para_replay: {row.row_kind}")


def _resolver_input_for_row(row_kind: str, dados: dict[str, Any]) -> ResolverInput:
    return ResolverInput(
        cnpj_companhia=dados.get("cnpj_companhia"),
        codigo_cvm=dados.get("codigo_cvm"),
        denominacao_companhia=dados.get("denominacao_companhia") or dados.get("nome_companhia"),
        tipo_formulario=dados.get(
            "tipo_formulario",
            "FRE" if row_kind.startswith("fre_") else "FCA" if row_kind.startswith("fca_") else row_kind[:3].upper(),
        ),
        id_documento=dados.get("id_documento"),
        versao=dados.get("versao"),
        data_referencia=dados.get("data_referencia"),
    )


def replay_ingestion_row(
    db: Session,
    *,
    row_id: Any,
    resolved_by: str = "replay",
) -> dict[str, Any]:
    row = db.get(IngestionRow, row_id)
    if row is None:
        raise ValueError("ingestion_row_nao_encontrada")
    if row.row_kind == "desconhecido":
        return {"status": "sucesso", "row_id": str(row.id), "skipped": True}
    run = db.get(IngestionRun, row.ingestion_run_id)
    if run is None:
        raise ValueError("ingestion_run_nao_encontrado")
    quarantine = db.scalar(select(QuarantineItem).where(QuarantineItem.ingestion_row_id == row.id))

    attempt_number = 1 if quarantine is None else quarantine.tentativas_reprocessamento + 1
    attempt = register_attempt(
        db,
        ingestion_run=run,
        operation="replay",
        attempt_number=attempt_number,
        status="success",
    )
    header_map = _build_header_map_for_run(db, run_id=run.id)

    try:
        row_kind, dados = _renormalize_row(db, row)
        natural_key = build_natural_key(row_kind, dados)
        duplicate_result = classify_duplicate(
            natural_key=natural_key,
            normalized_hash=row.normalized_hash or "",
            normalized_data=dados,
            seen_by_key={},
        )
        resolver_result = resolve_companhia(
            db,
            _resolver_input_for_row(row_kind, dados),
            header_map=header_map,
        )
        if resolver_result.status not in {STATUS_RESOLVED, STATUS_PROVISIONAL_CREATED}:
            payload = _resolver_input_for_row(row_kind, dados).to_rule_payload()
            rule = find_matching_repair_rule(db, rule_type="identity_exact", payload=payload)
            if rule is not None:
                resolver_result = resolve_companhia(
                    db,
                    _resolver_input_for_row(row_kind, dados),
                    header_map=header_map,
                )
        if resolver_result.status not in {STATUS_RESOLVED, STATUS_PROVISIONAL_CREATED}:
            result = invalid_result(
                resolver_result.resolution_method or "companhia_nao_encontrada",
                details=resolver_result.details,
                repairable=True,
            )
            write_validation_result(
                db, ingestion_row=row, result=result, normalized_data=dados, natural_key=natural_key
            )
            if quarantine is None:
                quarantine = create_quarantine_item(
                    db,
                    ingestion_row=row,
                    result=result,
                    execucao_sincronizacao_id=run.execucao_sincronizacao_id,
                )
            register_quarantine_replay_attempt(
                quarantine,
                success=False,
                error_message=resolver_result.resolution_method,
            )
            attempt.status = "terminal_failure"
            attempt.error_type = "ReplayValidationFailure"
            attempt.error_message = resolver_result.resolution_method
            register_row_event(
                db,
                ingestion_row=row,
                event_type="replayed",
                event_payload={"status": "falha", "reason": resolver_result.resolution_method},
                created_by=resolved_by,
            )
            persist_quality_summary(db, run=run)
            db.commit()
            return {"status": "falha", "row_id": str(row.id), "reason": resolver_result.resolution_method}

        persist_resolution_result(db, ingestion_row=row, result=resolver_result, created_by=resolved_by)
        companhia = db.get(Companhia, resolver_result.companhia_id) if resolver_result.companhia_id else None
        dados["companhia_id"] = resolver_result.companhia_id
        if dados.get("cnpj_companhia") is None and companhia is not None:
            dados["cnpj_companhia"] = companhia.cnpj_companhia
        if (
            row_kind in {"dfp_documento", "itr_documento", "fre_documento", "fca_documento"}
            and dados.get("codigo_cvm") is None
            and companhia is not None
        ):
            dados["codigo_cvm"] = companhia.codigo_cvm
        write_validation_result(
            db, ingestion_row=row, result=duplicate_result, normalized_data=dados, natural_key=natural_key
        )
        contadores = {"lidas": 1, "inseridos": 0, "atualizados": 0, "inalterados": 0, "rejeitados": 0}
        if row_kind.startswith(("dfp_", "itr_")):
            _promote_financeiro_row(
                db,
                row_kind=row_kind,
                row=row,
                dados=dados,
                execucao_id=run.execucao_sincronizacao_id,
                contadores=contadores,
            )
        elif row_kind.startswith("fca_"):
            _promote_fca_row(
                db,
                row_kind=row_kind,
                row=row,
                dados=dados,
                execucao_id=run.execucao_sincronizacao_id,
                contadores=contadores,
            )
        elif row_kind.startswith("ipe_"):
            _promote_ipe_row(
                db,
                row=row,
                dados=dados,
                execucao_id=run.execucao_sincronizacao_id,
                contadores=contadores,
            )
        else:
            _promote_fre_row(
                db,
                row_kind=row_kind,
                row=row,
                dados=dados,
                execucao_id=run.execucao_sincronizacao_id,
                contadores=contadores,
            )
        if quarantine is not None:
            register_quarantine_replay_attempt(quarantine, success=True)
            mark_quarantine_resolved(db, item=quarantine, status="resolvido_auto", resolved_by=resolved_by)
        register_row_event(
            db,
            ingestion_row=row,
            event_type="replayed",
            event_payload={"status": "sucesso"},
            created_by=resolved_by,
        )
        persist_quality_summary(db, run=run)
        db.commit()
        return {"status": "sucesso", "row_id": str(row.id)}
    except Exception as exc:
        if quarantine is None:
            quarantine = db.scalar(select(QuarantineItem).where(QuarantineItem.ingestion_row_id == row.id))
        if quarantine is not None:
            register_quarantine_replay_attempt(quarantine, success=False, error_message=str(exc))
        attempt.status = "terminal_failure"
        attempt.error_type = type(exc).__name__
        attempt.error_message = str(exc)
        db.commit()
        raise


def replay_file_member(db: Session, *, member_id: Any) -> dict[str, Any]:
    rows = list(db.execute(select(IngestionRow.id).where(IngestionRow.ingestion_file_member_id == member_id)).all())
    processed = [replay_ingestion_row(db, row_id=row_id) for (row_id,) in rows]
    return {"status": "sucesso", "rows": processed}


def replay_ingestion_run(db: Session, *, run_id: Any) -> dict[str, Any]:
    rows = list(db.execute(select(IngestionRow.id).where(IngestionRow.ingestion_run_id == run_id)).all())
    processed = [replay_ingestion_row(db, row_id=row_id) for (row_id,) in rows]
    return {"status": "sucesso", "rows": processed}


def replay_quarantine(
    db: Session,
    *,
    reason_code: str | None = None,
    arquivo_origem: str | None = None,
    ano: int | None = None,
) -> dict[str, Any]:
    query = select(QuarantineItem).where(QuarantineItem.status == "pendente")
    if reason_code is not None:
        query = query.where(QuarantineItem.motivo_codigo == reason_code)
    if arquivo_origem is not None:
        query = query.where(QuarantineItem.arquivo_origem == arquivo_origem)
    if ano is not None:
        query = query.where(QuarantineItem.ano_origem == ano)
    items = list(db.execute(query.order_by(QuarantineItem.created_at.asc())).scalars())
    processed = [replay_ingestion_row(db, row_id=item.ingestion_row_id) for item in items]
    return {"status": "sucesso", "total": len(processed), "items": processed}
