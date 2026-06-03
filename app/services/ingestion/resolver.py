from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.companhia import Companhia
from app.models.identidade import CompanhiaIdentificador, RepairRule
from app.models.ingestion import IngestionRow
from app.services.ingestion.normalizers import (
    normalizar_cnpj_opcional,
    normalizar_codigo_cvm,
    normalizar_nome_emissor_chave,
    normalizar_texto,
)
from app.services.ingestion.staging import register_row_event

STATUS_RESOLVED = "resolved"
STATUS_AMBIGUOUS = "ambiguous"
STATUS_NOT_FOUND = "not_found"
STATUS_PROVISIONAL_CREATED = "provisional_created"


@dataclass(frozen=True)
class ResolverInput:
    cnpj_companhia: str | None = None
    codigo_cvm: int | str | None = None
    denominacao_companhia: str | None = None
    tipo_formulario: str | None = None
    id_documento: int | None = None
    versao: int | None = None
    data_referencia: date | None = None
    raw_context: dict[str, Any] = field(default_factory=dict)

    @property
    def cnpj_normalizado(self) -> str | None:
        return normalizar_cnpj_opcional(self.cnpj_companhia)

    @property
    def codigo_cvm_normalizado(self) -> int | None:
        return normalizar_codigo_cvm(self.codigo_cvm)

    @property
    def document_header_key(self) -> tuple[str | None, int | None, int | None, date | None]:
        return (self.tipo_formulario, self.id_documento, self.versao, self.data_referencia)

    def to_rule_payload(self) -> dict[str, Any]:
        return {
            "cnpj_companhia": self.cnpj_normalizado,
            "codigo_cvm": self.codigo_cvm_normalizado,
            "denominacao_companhia": normalizar_texto(self.denominacao_companhia),
            "nome_emissor_chave": normalizar_nome_emissor_chave(self.denominacao_companhia),
            "tipo_formulario": normalizar_texto(self.tipo_formulario),
            "id_documento": self.id_documento,
            "versao": self.versao,
            "data_referencia": self.data_referencia.isoformat() if self.data_referencia is not None else None,
            **self.raw_context,
        }


@dataclass(frozen=True)
class ResolverResult:
    status: str
    companhia_id: UUID | None
    resolution_method: str | None
    resolution_confidence: str | None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DocumentHeaderResolution:
    companhia_id: UUID
    cnpj_companhia: str | None
    codigo_cvm: int | None
    confidence: str = "media"


DocumentHeaderMap = dict[tuple[str | None, int | None, int | None, date | None], DocumentHeaderResolution]


def build_document_header_key(
    *,
    tipo_formulario: str | None,
    id_documento: int | None,
    versao: int | None,
    data_referencia: date | None,
) -> tuple[str | None, int | None, int | None, date | None]:
    return (tipo_formulario, id_documento, versao, data_referencia)


def register_document_header(
    header_map: DocumentHeaderMap,
    *,
    tipo_formulario: str | None,
    id_documento: int | None,
    versao: int | None,
    data_referencia: date | None,
    companhia_id: UUID,
    cnpj_companhia: str | None,
    codigo_cvm: int | None,
    confidence: str = "media",
) -> None:
    header_map[
        build_document_header_key(
            tipo_formulario=tipo_formulario,
            id_documento=id_documento,
            versao=versao,
            data_referencia=data_referencia,
        )
    ] = DocumentHeaderResolution(
        companhia_id=companhia_id,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        confidence=confidence,
    )


def _query_identifier_company_ids(db: Session, *, tipo: str, valor_normalizado: str | None) -> set[UUID]:
    if valor_normalizado is None:
        return set()
    rows = db.execute(
        select(CompanhiaIdentificador.companhia_id).where(
            CompanhiaIdentificador.tipo == tipo,
            CompanhiaIdentificador.valor_normalizado == valor_normalizado,
            CompanhiaIdentificador.ativo.is_(True),
        )
    ).all()
    return {row[0] for row in rows}


def _resolve_exact_identifier_sets(
    db: Session,
    resolver_input: ResolverInput,
) -> tuple[set[UUID], set[UUID]]:
    cnpj_ids = _query_identifier_company_ids(
        db,
        tipo="cnpj",
        valor_normalizado=resolver_input.cnpj_normalizado,
    )
    codigo_normalizado = resolver_input.codigo_cvm_normalizado
    codigo_ids = _query_identifier_company_ids(
        db,
        tipo="codigo_cvm",
        valor_normalizado=None if codigo_normalizado is None else str(codigo_normalizado),
    )
    return cnpj_ids, codigo_ids


def _resolve_exact_identifier_result(
    resolver_input: ResolverInput,
    cnpj_ids: set[UUID],
    codigo_ids: set[UUID],
) -> ResolverResult | None:
    if cnpj_ids and codigo_ids:
        intersecao = cnpj_ids & codigo_ids
        if len(intersecao) == 1:
            return ResolverResult(
                status=STATUS_RESOLVED,
                companhia_id=next(iter(intersecao)),
                resolution_method="cnpj_e_codigo_cvm_identificador_alta",
                resolution_confidence="alta",
                details={"cnpj_match_count": len(cnpj_ids), "codigo_match_count": len(codigo_ids)},
            )
        return ResolverResult(
            status=STATUS_AMBIGUOUS,
            companhia_id=None,
            resolution_method="companhia_ambigua",
            resolution_confidence=None,
            details={"cnpj_ids": sorted(str(valor) for valor in cnpj_ids), "codigo_ids": sorted(str(valor) for valor in codigo_ids)},
        )

    if len(cnpj_ids) == 1:
        return ResolverResult(
            status=STATUS_RESOLVED,
            companhia_id=next(iter(cnpj_ids)),
            resolution_method="cnpj_identificador_alta",
            resolution_confidence="alta",
            details={"cnpj_match_count": 1},
        )
    if len(cnpj_ids) > 1:
        return ResolverResult(
            status=STATUS_AMBIGUOUS,
            companhia_id=None,
            resolution_method="companhia_ambigua",
            resolution_confidence=None,
            details={"cnpj_ids": sorted(str(valor) for valor in cnpj_ids)},
        )

    if len(codigo_ids) == 1:
        return ResolverResult(
            status=STATUS_RESOLVED,
            companhia_id=next(iter(codigo_ids)),
            resolution_method="codigo_cvm_identificador_alta",
            resolution_confidence="alta",
            details={"codigo_match_count": 1},
        )
    if len(codigo_ids) > 1:
        return ResolverResult(
            status=STATUS_AMBIGUOUS,
            companhia_id=None,
            resolution_method="companhia_ambigua",
            resolution_confidence=None,
            details={"codigo_ids": sorted(str(valor) for valor in codigo_ids)},
        )
    return None


def _resolve_document_header(header_map: DocumentHeaderMap | None, resolver_input: ResolverInput) -> ResolverResult | None:
    if not header_map:
        return None
    resolution = header_map.get(resolver_input.document_header_key)
    if resolution is None:
        return None
    return ResolverResult(
        status=STATUS_RESOLVED,
        companhia_id=resolution.companhia_id,
        resolution_method="header_documento_media",
        resolution_confidence=resolution.confidence,
        details={
            "header_key": {
                "tipo_formulario": resolver_input.tipo_formulario,
                "id_documento": resolver_input.id_documento,
                "versao": resolver_input.versao,
                "data_referencia": resolver_input.data_referencia.isoformat()
                if resolver_input.data_referencia is not None
                else None,
            }
        },
    )


def _resolve_repair_rule(db: Session, resolver_input: ResolverInput) -> ResolverResult | None:
    payload = resolver_input.to_rule_payload()
    rules = db.execute(
        select(RepairRule).where(
            RepairRule.rule_type == "identity_exact",
            RepairRule.enabled.is_(True),
        )
    ).scalars()
    for rule in rules:
        if all(payload.get(key) == value for key, value in rule.match_payload.items()):
            companhia_id = rule.action_payload.get("companhia_id")
            if companhia_id is None:
                continue
            return ResolverResult(
                status=STATUS_RESOLVED,
                companhia_id=UUID(str(companhia_id)),
                resolution_method="manual_identity_rule_media",
                resolution_confidence="media",
                details={"repair_rule_id": str(rule.id)},
            )
    return None


def _resolve_legacy_company(db: Session, resolver_input: ResolverInput) -> ResolverResult | None:
    companhia_por_cnpj = None
    companhia_por_codigo = None

    if resolver_input.cnpj_normalizado is not None:
        companhia_por_cnpj = db.scalar(
            select(Companhia).where(Companhia.cnpj_companhia == resolver_input.cnpj_normalizado)
        )
    if resolver_input.codigo_cvm_normalizado is not None:
        companhia_por_codigo = db.scalar(
            select(Companhia).where(Companhia.codigo_cvm == resolver_input.codigo_cvm_normalizado)
        )

    if companhia_por_cnpj is not None and companhia_por_codigo is not None:
        if companhia_por_cnpj.id == companhia_por_codigo.id:
            return ResolverResult(
                status=STATUS_RESOLVED,
                companhia_id=companhia_por_cnpj.id,
                resolution_method="companhia_legado_alta",
                resolution_confidence="alta",
                details={"fonte": "companhias"},
            )
        return ResolverResult(
            status=STATUS_AMBIGUOUS,
            companhia_id=None,
            resolution_method="companhia_ambigua",
            resolution_confidence=None,
            details={
                "legacy_cnpj_companhia_id": str(companhia_por_cnpj.id),
                "legacy_codigo_companhia_id": str(companhia_por_codigo.id),
            },
        )
    if companhia_por_cnpj is not None:
        return ResolverResult(
            status=STATUS_RESOLVED,
            companhia_id=companhia_por_cnpj.id,
            resolution_method="companhia_legado_alta",
            resolution_confidence="alta",
            details={"fonte": "companhias"},
        )
    if companhia_por_codigo is not None:
        return ResolverResult(
            status=STATUS_RESOLVED,
            companhia_id=companhia_por_codigo.id,
            resolution_method="companhia_legado_alta",
            resolution_confidence="alta",
            details={"fonte": "companhias"},
        )
    return None


def _provisional_cnpj(resolver_input: ResolverInput) -> str | None:
    if resolver_input.cnpj_normalizado:
        return resolver_input.cnpj_normalizado
    if resolver_input.codigo_cvm_normalizado is None:
        return None
    return f"PROV{resolver_input.codigo_cvm_normalizado:010d}"


def _create_provisional_company(db: Session, resolver_input: ResolverInput) -> ResolverResult:
    cnpj = _provisional_cnpj(resolver_input)
    if cnpj is None:
        return ResolverResult(
            status=STATUS_NOT_FOUND,
            companhia_id=None,
            resolution_method="companhia_nao_encontrada",
            resolution_confidence=None,
            details={"motivo": "identidade_insuficiente_para_provisorio"},
        )

    companhia = Companhia(
        cnpj_companhia=cnpj,
        codigo_cvm=resolver_input.codigo_cvm_normalizado,
        denominacao_social=normalizar_texto(resolver_input.denominacao_companhia),
        denominacao_comercial=normalizar_texto(resolver_input.denominacao_companhia),
        tipo_emissor="provisorio",
        fonte_identidade_principal="resolver_v2_provisional",
        qualidade_identidade="baixa",
        arquivo_origem="resolver_v2_provisional",
        ano_origem=resolver_input.data_referencia.year if resolver_input.data_referencia is not None else None,
        linha_origem=None,
        hash_origem="resolver_v2_provisional",
    )
    db.add(companhia)
    db.flush()

    if resolver_input.cnpj_normalizado:
        db.add(
            CompanhiaIdentificador(
                companhia_id=companhia.id,
                tipo="cnpj",
                valor=resolver_input.cnpj_normalizado,
                valor_normalizado=resolver_input.cnpj_normalizado,
                fonte="resolver_v2_provisional",
                confianca="baixa",
                ativo=True,
            )
        )
    if resolver_input.codigo_cvm_normalizado is not None:
        codigo_texto = str(resolver_input.codigo_cvm_normalizado)
        db.add(
            CompanhiaIdentificador(
                companhia_id=companhia.id,
                tipo="codigo_cvm",
                valor=codigo_texto,
                valor_normalizado=codigo_texto,
                fonte="resolver_v2_provisional",
                confianca="baixa",
                ativo=True,
            )
        )
    db.flush()
    return ResolverResult(
        status=STATUS_PROVISIONAL_CREATED,
        companhia_id=companhia.id,
        resolution_method="provisional_company_baixa",
        resolution_confidence="baixa",
        details={"tipo_emissor": "provisorio"},
    )


def resolve_companhia_v2(
    db: Session,
    resolver_input: ResolverInput,
    *,
    header_map: DocumentHeaderMap | None = None,
    provisional_enabled: bool | None = None,
) -> ResolverResult:
    cnpj_ids, codigo_ids = _resolve_exact_identifier_sets(db, resolver_input)
    exact_result = _resolve_exact_identifier_result(resolver_input, cnpj_ids, codigo_ids)
    if exact_result is not None:
        return exact_result

    header_result = _resolve_document_header(header_map, resolver_input)
    if header_result is not None:
        return header_result

    repair_result = _resolve_repair_rule(db, resolver_input)
    if repair_result is not None:
        return repair_result

    legacy_result = _resolve_legacy_company(db, resolver_input)
    if legacy_result is not None:
        return legacy_result

    if provisional_enabled is None:
        provisional_enabled = get_settings().ingestion_v2_provisional_company_enabled
    if provisional_enabled:
        return _create_provisional_company(db, resolver_input)

    return ResolverResult(
        status=STATUS_NOT_FOUND,
        companhia_id=None,
        resolution_method="companhia_nao_encontrada",
        resolution_confidence=None,
        details={},
    )


def persist_resolution_result(
    db: Session,
    *,
    ingestion_row: IngestionRow,
    result: ResolverResult,
    created_by: str = "resolver_v2",
) -> IngestionRow:
    ingestion_row.resolved_companhia_id = result.companhia_id
    ingestion_row.resolution_method = result.resolution_method
    ingestion_row.resolution_confidence = result.resolution_confidence
    register_row_event(
        db,
        ingestion_row=ingestion_row,
        event_type="resolved" if result.status in {STATUS_RESOLVED, STATUS_PROVISIONAL_CREATED} else result.status,
        event_payload={
            "status": result.status,
            "companhia_id": None if result.companhia_id is None else str(result.companhia_id),
            "resolution_method": result.resolution_method,
            "resolution_confidence": result.resolution_confidence,
            "details": result.details,
        },
        created_by=created_by,
    )
    return ingestion_row
