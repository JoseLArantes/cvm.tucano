from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.models.ingestion import IngestionFileMember, IngestionRow
from app.services.ingestion.normalizers import gerar_hash_canonico, normalizar_chave_natural
from app.services.ingestion.staging import register_row_event, update_row_validation


@dataclass(frozen=True)
class ValidationResult:
    status: str
    reason_code: str | None
    severity: str
    details: dict[str, Any] = field(default_factory=dict)
    repairable: bool = False

    def to_json_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
        return payload


_REQUIRED_COLUMNS_BY_ROW_KIND: dict[str, set[str]] = {
    "cadastro_aberta": {"CNPJ_CIA", "CD_CVM", "DENOM_SOCIAL"},
    "cadastro_estrangeira": {"CNPJ", "CD_CVM", "DENOM_SOCIAL"},
    "dfp_documento": {"CNPJ_CIA", "DT_REFER", "VERSAO", "ID_DOC"},
    "itr_documento": {"CNPJ_CIA", "DT_REFER", "VERSAO", "ID_DOC"},
    "dfp_demonstracao": {"CNPJ_CIA", "DT_REFER", "VERSAO", "CD_CONTA"},
    "itr_demonstracao": {"CNPJ_CIA", "DT_REFER", "VERSAO", "CD_CONTA"},
    "dfp_composicao_capital": {"CNPJ_CIA", "DT_REFER", "VERSAO"},
    "itr_composicao_capital": {"CNPJ_CIA", "DT_REFER", "VERSAO"},
    "dfp_parecer": {"CNPJ_CIA", "DT_REFER", "VERSAO"},
    "itr_parecer": {"CNPJ_CIA", "DT_REFER", "VERSAO"},
    "fre_documento": {"CNPJ_CIA", "DT_REFER", "VERSAO", "ID_DOC"},
    "fre_auditor": {"CNPJ_Companhia", "Data_Referencia", "Versao", "ID_Documento", "ID_Auditor"},
    "fre_capital_social": {"CNPJ_Companhia", "Data_Referencia", "Versao", "ID_Documento", "ID_Capital_Social"},
    "fre_posicao_acionaria": {"CNPJ_Companhia", "Data_Referencia", "Versao", "ID_Documento", "ID_Acionista"},
    "fre_remuneracao_total_orgao": {
        "CNPJ_Companhia",
        "Data_Referencia",
        "Versao",
        "ID_Documento",
        "Orgao_Administracao",
    },
    "fre_empregado_posicao_genero": {"CNPJ_Companhia", "Data_Referencia", "Versao", "ID_Documento"},
}


def ok_result(*, details: dict[str, Any] | None = None) -> ValidationResult:
    return ValidationResult(status="valid", reason_code=None, severity="info", details=details or {}, repairable=False)


def invalid_result(
    reason_code: str,
    *,
    severity: str = "error",
    details: dict[str, Any] | None = None,
    repairable: bool = False,
) -> ValidationResult:
    return ValidationResult(
        status="invalid",
        reason_code=reason_code,
        severity=severity,
        details=details or {},
        repairable=repairable,
    )


def validate_member_header(row_kind: str, header: list[str] | None) -> ValidationResult:
    header_list = header or []
    header_set = set(header_list)
    required = _REQUIRED_COLUMNS_BY_ROW_KIND.get(row_kind, set())
    if not required:
        return ok_result(details={"row_kind": row_kind, "unknown_columns": sorted(header_set)})

    missing = sorted(required - header_set)
    unknown = sorted(header_set - required)
    if missing:
        return invalid_result(
            "schema_inesperado",
            details={
                "row_kind": row_kind,
                "missing_required_columns": missing,
                "unknown_columns": unknown,
            },
            repairable=True,
        )
    return ok_result(details={"row_kind": row_kind, "unknown_columns": unknown})


NaturalKeyBuilder = dict[str, Any]


def _natural_key_documento(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "tipo_formulario": dados.get("tipo_formulario"),
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
    }


def _natural_key_demonstracao(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "tipo_formulario": dados.get("tipo_formulario"),
        "tipo_demonstracao": dados.get("tipo_demonstracao"),
        "escopo_demonstracao": dados.get("escopo_demonstracao"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "data_referencia": dados.get("data_referencia"),
        "versao": dados.get("versao"),
        "grupo_demonstracao": dados.get("grupo_demonstracao"),
        "ordem_exercicio": dados.get("ordem_exercicio"),
        "data_fim_exercicio": dados.get("data_fim_exercicio"),
        "codigo_conta": dados.get("codigo_conta"),
    }


def _natural_key_composicao(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "tipo_formulario": dados.get("tipo_formulario"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "data_referencia": dados.get("data_referencia"),
        "versao": dados.get("versao"),
    }


def _natural_key_parecer(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "tipo_formulario": dados.get("tipo_formulario"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "data_referencia": dados.get("data_referencia"),
        "versao": dados.get("versao"),
        "tipo_relatorio_auditor": dados.get("tipo_relatorio_auditor"),
        "tipo_parecer_declaracao": dados.get("tipo_parecer_declaracao"),
        "numero_item_parecer_declaracao": dados.get("numero_item_parecer_declaracao"),
    }


def _natural_key_cadastro_registro(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "fonte_cadastro": dados.get("fonte_cadastro"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "codigo_cvm": dados.get("codigo_cvm"),
        "hash_sem_mercado": dados.get("hash_sem_mercado"),
    }


def _natural_key_fre_auditor(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "id_auditor": dados.get("id_auditor"),
    }


def _natural_key_fre_capital_social(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "id_capital_social": dados.get("id_capital_social"),
    }


def _natural_key_fre_posicao_acionaria(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "id_acionista": dados.get("id_acionista"),
    }


def _natural_key_fre_remuneracao(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "orgao_administracao": dados.get("orgao_administracao"),
        "data_inicio_exercicio_social": dados.get("data_inicio_exercicio_social"),
        "data_fim_exercicio_social": dados.get("data_fim_exercicio_social"),
    }


def _natural_key_fre_empregado_posicao_genero(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "id_documento": dados.get("id_documento"),
        "versao": dados.get("versao"),
        "data_referencia": dados.get("data_referencia"),
        "cnpj_companhia": dados.get("cnpj_companhia"),
        "tipo_genero": dados.get("tipo_genero"),
        "numero_empregados": dados.get("numero_empregados"),
    }


_NATURAL_KEY_BUILDERS: dict[str, Any] = {
    "cadastro_registro_cvm": _natural_key_cadastro_registro,
    "dfp_documento": _natural_key_documento,
    "itr_documento": _natural_key_documento,
    "dfp_demonstracao": _natural_key_demonstracao,
    "itr_demonstracao": _natural_key_demonstracao,
    "dfp_composicao_capital": _natural_key_composicao,
    "itr_composicao_capital": _natural_key_composicao,
    "dfp_parecer": _natural_key_parecer,
    "itr_parecer": _natural_key_parecer,
    "fre_documento": _natural_key_documento,
    "fre_auditor": _natural_key_fre_auditor,
    "fre_capital_social": _natural_key_fre_capital_social,
    "fre_posicao_acionaria": _natural_key_fre_posicao_acionaria,
    "fre_remuneracao_total_orgao": _natural_key_fre_remuneracao,
    "fre_empregado_posicao_genero": _natural_key_fre_empregado_posicao_genero,
}


def build_natural_key(row_kind: str, normalized_data: dict[str, Any]) -> dict[str, Any]:
    builder = _NATURAL_KEY_BUILDERS.get(row_kind)
    if builder is None:
        raise KeyError(f"natural_key_builder_nao_encontrado: {row_kind}")
    return normalizar_chave_natural(builder(normalized_data))


def _normalized_diff(previous_data: dict[str, Any], current_data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    diff: dict[str, dict[str, Any]] = {}
    for key in sorted(set(previous_data) | set(current_data)):
        before = previous_data.get(key)
        after = current_data.get(key)
        if before != after:
            diff[key] = {"before": before, "after": after}
    return diff


def classify_duplicate(
    *,
    natural_key: dict[str, Any],
    normalized_hash: str,
    normalized_data: dict[str, Any],
    seen_by_key: dict[str, dict[str, Any]],
) -> ValidationResult:
    natural_key_payload = normalizar_chave_natural(natural_key)
    natural_key_json = json.dumps(natural_key_payload, ensure_ascii=False, sort_keys=True, default=str)
    seen = seen_by_key.get(natural_key_json)
    if seen is None:
        seen_by_key[natural_key_json] = {
            "normalized_hash": normalized_hash,
            "normalized_data": normalized_data,
        }
        return ok_result(details={"duplicate_status": "new"})

    if seen["normalized_hash"] == normalized_hash:
        return ValidationResult(
            status="ignored_duplicate",
            reason_code="ignored_duplicate",
            severity="info",
            details={"natural_key": natural_key_payload},
            repairable=False,
        )

    return invalid_result(
        "chave_natural_duplicada_conflitante",
        details={
            "natural_key": natural_key_payload,
            "field_diff": _normalized_diff(seen["normalized_data"], normalized_data),
        },
        repairable=True,
    )


def write_validation_result(
    db: Session,
    *,
    ingestion_row: IngestionRow,
    result: ValidationResult,
    normalized_data: dict[str, Any] | None = None,
    natural_key: dict[str, Any] | None = None,
    created_by: str = "validation_v2",
) -> IngestionRow:
    normalized_hash = None
    normalized_data_payload = None
    natural_key_payload = None
    if normalized_data is not None:
        normalized_hash = gerar_hash_canonico(normalized_data)
        normalized_data_payload = normalizar_chave_natural(normalized_data)
    if natural_key is not None:
        natural_key_payload = normalizar_chave_natural(natural_key)
    update_row_validation(
        ingestion_row,
        validation_status=result.status,
        validation_reason_code=result.reason_code,
        validation_details=result.to_json_payload(),
        normalized_data=normalized_data_payload,
        normalized_hash=normalized_hash,
        natural_key=natural_key_payload,
    )
    register_row_event(
        db,
        ingestion_row=ingestion_row,
        event_type="validated" if result.status in {"valid", "ignored_duplicate"} else "quarantined",
        event_payload=result.to_json_payload(),
        created_by=created_by,
    )
    return ingestion_row


def update_member_schema_validation(
    member: IngestionFileMember,
    *,
    result: ValidationResult,
) -> IngestionFileMember:
    member.schema_status = result.status
    member.schema_message = json.dumps(result.to_json_payload(), ensure_ascii=False, sort_keys=True, default=str)
    return member
