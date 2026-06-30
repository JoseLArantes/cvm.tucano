from __future__ import annotations

import csv
import io
import json
import uuid
from collections.abc import Iterable
from typing import Any

from sqlalchemy import delete, insert
from sqlalchemy.orm import Session

from app.models.ingestion import IngestionFinanceiroStageRow
from app.services.financeiro_valores import normalizar_decimal_financeiro, validar_escala_moeda
from app.services.ingestion.normalized_artifacts import iter_normalized_artifact_rows
from app.services.normalizacao import (
    normalizar_conta_fixa,
    normalizar_data,
    normalizar_inteiro,
    normalizar_texto,
)

_STAGE_COLUMNS = [
    "id",
    "ingestion_run_id",
    "ingestion_file_member_id",
    "artifact_uri",
    "row_kind",
    "arquivo_origem",
    "ano_origem",
    "linha_origem",
    "normalized_hash",
    "companhia_id",
    "natural_key",
    "tipo_formulario",
    "cnpj_companhia",
    "codigo_cvm",
    "data_referencia",
    "versao",
    "denominacao_companhia",
    "categoria_documento",
    "id_documento",
    "data_recebimento",
    "link_documento",
    "tipo_demonstracao",
    "escopo_demonstracao",
    "grupo_demonstracao",
    "moeda",
    "escala_moeda",
    "ordem_exercicio",
    "data_inicio_exercicio",
    "data_fim_exercicio",
    "codigo_conta",
    "coluna_df",
    "descricao_conta",
    "valor_conta",
    "conta_fixa",
    "quantidade_acoes_ordinarias_capital_integralizado",
    "quantidade_acoes_preferenciais_capital_integralizado",
    "quantidade_total_acoes_capital_integralizado",
    "quantidade_acoes_ordinarias_tesouraria",
    "quantidade_acoes_preferenciais_tesouraria",
    "quantidade_total_acoes_tesouraria",
    "tipo_relatorio_auditor",
    "tipo_parecer_declaracao",
    "numero_item_parecer_declaracao",
    "texto_parecer_declaracao",
]


def _should_use_postgres_copy(db: Session) -> bool:
    bind = db.get_bind()
    return bind is not None and bind.dialect.name == "postgresql"


def _parse_json(value: str | None) -> dict[str, Any] | None:
    if not value:
        return None
    parsed = json.loads(value)
    return parsed if isinstance(parsed, dict) else None


def _parse_uuid(value: str | None) -> uuid.UUID | None:
    if not value:
        return None
    return uuid.UUID(value)


def _parse_escala_moeda(value: str | None) -> str | None:
    texto = normalizar_texto(value)
    if texto is None:
        return None
    return validar_escala_moeda(texto)


def _normalize_stage_row(
    *,
    ingestion_run_id: Any,
    ingestion_file_member_id: Any,
    artifact_uri: str,
    row: dict[str, str],
) -> dict[str, Any]:
    return {
        "id": uuid.uuid4(),
        "ingestion_run_id": ingestion_run_id,
        "ingestion_file_member_id": ingestion_file_member_id,
        "artifact_uri": artifact_uri,
        "row_kind": row["row_kind"],
        "arquivo_origem": row["arquivo_origem"],
        "ano_origem": normalizar_inteiro(row.get("ano_origem")),
        "linha_origem": normalizar_inteiro(row.get("linha_origem")) or 0,
        "normalized_hash": row["normalized_hash"],
        "companhia_id": _parse_uuid(row.get("companhia_id")),
        "natural_key": _parse_json(row.get("natural_key")),
        "tipo_formulario": normalizar_texto(row.get("tipo_formulario")),
        "cnpj_companhia": normalizar_texto(row.get("cnpj_companhia")),
        "codigo_cvm": normalizar_inteiro(row.get("codigo_cvm")),
        "data_referencia": normalizar_data(row.get("data_referencia")),
        "versao": normalizar_inteiro(row.get("versao")),
        "denominacao_companhia": normalizar_texto(row.get("denominacao_companhia")),
        "categoria_documento": normalizar_texto(row.get("categoria_documento")),
        "id_documento": normalizar_inteiro(row.get("id_documento")),
        "data_recebimento": normalizar_data(row.get("data_recebimento")),
        "link_documento": normalizar_texto(row.get("link_documento")),
        "tipo_demonstracao": normalizar_texto(row.get("tipo_demonstracao")),
        "escopo_demonstracao": normalizar_texto(row.get("escopo_demonstracao")),
        "grupo_demonstracao": normalizar_texto(row.get("grupo_demonstracao")),
        "moeda": normalizar_texto(row.get("moeda")),
        "escala_moeda": _parse_escala_moeda(row.get("escala_moeda")),
        "ordem_exercicio": normalizar_texto(row.get("ordem_exercicio")),
        "data_inicio_exercicio": normalizar_data(row.get("data_inicio_exercicio")),
        "data_fim_exercicio": normalizar_data(row.get("data_fim_exercicio")),
        "codigo_conta": normalizar_texto(row.get("codigo_conta")),
        "coluna_df": normalizar_texto(row.get("coluna_df")),
        "descricao_conta": normalizar_texto(row.get("descricao_conta")),
        "valor_conta": normalizar_decimal_financeiro(row.get("valor_conta")),
        "conta_fixa": normalizar_conta_fixa(row.get("conta_fixa")),
        "quantidade_acoes_ordinarias_capital_integralizado": normalizar_decimal_financeiro(
            row.get("quantidade_acoes_ordinarias_capital_integralizado")
        ),
        "quantidade_acoes_preferenciais_capital_integralizado": normalizar_decimal_financeiro(
            row.get("quantidade_acoes_preferenciais_capital_integralizado")
        ),
        "quantidade_total_acoes_capital_integralizado": normalizar_decimal_financeiro(
            row.get("quantidade_total_acoes_capital_integralizado")
        ),
        "quantidade_acoes_ordinarias_tesouraria": normalizar_decimal_financeiro(
            row.get("quantidade_acoes_ordinarias_tesouraria")
        ),
        "quantidade_acoes_preferenciais_tesouraria": normalizar_decimal_financeiro(
            row.get("quantidade_acoes_preferenciais_tesouraria")
        ),
        "quantidade_total_acoes_tesouraria": normalizar_decimal_financeiro(
            row.get("quantidade_total_acoes_tesouraria")
        ),
        "tipo_relatorio_auditor": normalizar_texto(row.get("tipo_relatorio_auditor")),
        "tipo_parecer_declaracao": normalizar_texto(row.get("tipo_parecer_declaracao")),
        "numero_item_parecer_declaracao": normalizar_texto(row.get("numero_item_parecer_declaracao")),
        "texto_parecer_declaracao": normalizar_texto(row.get("texto_parecer_declaracao")),
    }


def clear_financeiro_stage_rows(db: Session, *, ingestion_file_member_id: Any) -> None:
    db.execute(
        delete(IngestionFinanceiroStageRow).where(
            IngestionFinanceiroStageRow.ingestion_file_member_id == ingestion_file_member_id
        )
    )
    db.flush()


def _serialize_copy_value(value: Any) -> str:
    if value is None:
        return "\\N"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=True, sort_keys=True)
    return str(value)


def _copy_financeiro_stage_rows_postgres(db: Session, *, payload: Iterable[dict[str, Any]]) -> None:
    rows = list(payload)
    if not rows:
        return
    sa_connection = db.connection()
    proxied = sa_connection.connection
    raw_connection = getattr(proxied, "driver_connection", proxied)
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter="\t", quotechar='"', lineterminator="\n")
    for item in rows:
        writer.writerow([_serialize_copy_value(item.get(column)) for column in _STAGE_COLUMNS])
    buffer.seek(0)
    copy_sql = f"""
        COPY ingestion_financeiro_stage_rows (
            {", ".join(_STAGE_COLUMNS)}
        )
        FROM STDIN WITH (FORMAT CSV, DELIMITER E'\\t', NULL '\\N')
    """
    cursor = raw_connection.cursor()
    try:
        with cursor.copy(copy_sql) as copy:
            copy.write(buffer.getvalue())
    finally:
        cursor.close()


def load_financeiro_artifact_to_stage(
    db: Session,
    *,
    ingestion_run_id: Any,
    ingestion_file_member_id: Any,
    artifact_uri: str,
    use_copy: bool | None = None,
) -> int:
    clear_financeiro_stage_rows(db, ingestion_file_member_id=ingestion_file_member_id)
    payload = [
        _normalize_stage_row(
            ingestion_run_id=ingestion_run_id,
            ingestion_file_member_id=ingestion_file_member_id,
            artifact_uri=artifact_uri,
            row=row,
        )
        for row in iter_normalized_artifact_rows(artifact_uri=artifact_uri)
    ]
    should_use_copy = (
        _should_use_postgres_copy(db)
        if use_copy is None
        else (use_copy and _should_use_postgres_copy(db))
    )
    if should_use_copy:
        _copy_financeiro_stage_rows_postgres(db, payload=payload)
    elif payload:
        db.execute(insert(IngestionFinanceiroStageRow), payload)
    db.flush()
    return len(payload)
