from __future__ import annotations

import logging
import uuid
from collections import Counter
from typing import Any

import duckdb
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.companhia import Companhia
from app.services.financeiro_mapas import arquivos_demonstracao
from app.services.ingestion.normalized_artifacts import NormalizedArtifactWriter
from app.services.ingestion.normalizers import gerar_hash_canonico
from app.services.ingestion.resolver import (
    STATUS_PROVISIONAL_CREATED,
    STATUS_RESOLVED,
    ResolverInput,
    _ensure_companhias_loaded,
    _session_cache,
    resolve_companhia,
)
from app.services.sincronizacao_financeiro import (
    gerar_chave_negocio_demonstracao,
)

logger = logging.getLogger(__name__)


def can_use_duckdb_for_member(member_name: str, row_kind: str) -> bool:
    """Check if member can be processed via DuckDB vectorized pipeline."""
    return row_kind.endswith("_demonstracao") and (
        member_name.startswith("dfp_cia_aberta_") or member_name.startswith("itr_cia_aberta_")
    )


def _get_companhias_mapping(db: Session) -> dict[str, uuid.UUID]:
    """Get mapping of CNPJ (14 digits) to companhia_id."""
    _ensure_companhias_loaded(db)
    cache = _session_cache(db)
    cnpj_map: dict[str, uuid.UUID] = {}
    if hasattr(cache, "_companhia_by_cnpj_cache") and cache._companhia_by_cnpj_cache:
        for cnpj, comp in cache._companhia_by_cnpj_cache.items():
            if comp and comp.id:
                clean_cnpj = "".join(filter(str.isdigit, cnpj)).zfill(14)
                cnpj_map[clean_cnpj] = comp.id
    else:
        for comp in db.execute(select(Companhia)).scalars():
            if comp.cnpj_companhia and comp.id:
                clean_cnpj = "".join(filter(str.isdigit, comp.cnpj_companhia)).zfill(14)
                cnpj_map[clean_cnpj] = comp.id
    return cnpj_map


def process_demonstracao_member_duckdb(
    db: Session,
    *,
    file_path: str,
    member_name: str,
    tipo_formulario: str,
    prefixo: str,
    ano: int,
    encoding: str,
    delimiter: str,
    run_id: Any,
    member_id: Any,
    header_map: dict[tuple[str | None, int | None, int | None, Any], Any],
    contadores: dict[str, int],
    quality_counters: dict[str, Counter[str] | int],
) -> tuple[int, dict[str, Any]] | None:
    """Vectorized normalization & deduplication of financial demonstration CSV via DuckDB.

    Returns (total_rows, normalized_artifacts_dict) or None if fallback to Python is required.
    """
    mapa_demonstracoes = {
        nome_arquivo: (tipo_dem, escopo)
        for nome_arquivo, tipo_dem, escopo in arquivos_demonstracao(prefixo, ano)
    }
    if member_name not in mapa_demonstracoes:
        return None

    tipo_demonstracao, escopo_demonstracao = mapa_demonstracoes[member_name]
    resolved_row_kind = f"{prefixo}_demonstracao"

    con = duckdb.connect(database=":memory:")
    con.execute("PRAGMA threads=4")

    # Read CSV
    duckdb_encoding = "latin-1" if "latin" in encoding.lower() or "8859" in encoding.lower() else "utf-8"
    csv_table_query = f"""
        CREATE TEMPORARY TABLE raw_csv AS
        SELECT
            row_number() over () as linha_origem,
            *
        FROM read_csv(
            '{file_path}',
            delim='{delimiter}',
            header=true,
            encoding='{duckdb_encoding}',
            all_varchar=true,
            ignore_errors=true
        )
    """
    try:
        con.execute(csv_table_query)
    except Exception as exc:
        logger.warning(f"DuckDB failed to load CSV {member_name}: {exc}. Falling back to Python.")
        con.close()
        return None

    # Verify expected columns
    cols = [desc[0].upper() for desc in con.execute("DESCRIBE raw_csv").fetchall()]
    if "CNPJ_CIA" not in cols or "DT_REFER" not in cols or "VERSAO" not in cols:
        con.close()
        return None

    grupo_col = "GRUPO_DFP" if "GRUPO_DFP" in cols else ("GRUPO_ITR" if "GRUPO_ITR" in cols else "NULL")
    coluna_df_col = "COLUNA_DF" if "COLUNA_DF" in cols else "''"
    cd_cvm_col = "CD_CVM" if "CD_CVM" in cols else "NULL"
    moeda_col = "MOEDA" if "MOEDA" in cols else "NULL"
    escala_col = "ESCALA_MOEDA" if "ESCALA_MOEDA" in cols else "NULL"
    ordem_col = "ORDEM_EXERC" if "ORDEM_EXERC" in cols else "NULL"
    dt_ini_col = "DT_INI_EXERC" if "DT_INI_EXERC" in cols else "NULL"
    dt_fim_col = "DT_FIM_EXERC" if "DT_FIM_EXERC" in cols else "NULL"
    cd_conta_col = "CD_CONTA" if "CD_CONTA" in cols else "NULL"
    ds_conta_col = "DS_CONTA" if "DS_CONTA" in cols else "NULL"
    vl_conta_col = "VL_CONTA" if "VL_CONTA" in cols else "NULL"
    st_fixa_col = "ST_CONTA_FIXA" if "ST_CONTA_FIXA" in cols else "NULL"
    denom_col = "DENOM_CIA" if "DENOM_CIA" in cols else "NULL"

    # Vectorized normalization and deduplication via window function
    normalized_sql = f"""
        CREATE TEMPORARY TABLE normalized_dedup AS
        WITH parsed AS (
            SELECT
                linha_origem,
                '{tipo_formulario}' as tipo_formulario,
                '{tipo_demonstracao}' as tipo_demonstracao,
                '{escopo_demonstracao}' as escopo_demonstracao,
                lpad(regexp_replace(CNPJ_CIA, '[^0-9]', '', 'g'), 14, '0') as cnpj_companhia,
                try_cast({cd_cvm_col} as INTEGER) as codigo_cvm,
                try_cast(DT_REFER as DATE) as data_referencia,
                try_cast(VERSAO as INTEGER) as versao,
                trim(nullif({denom_col}, '')) as denominacao_companhia,
                trim(nullif({grupo_col}, '')) as grupo_demonstracao,
                trim(nullif({moeda_col}, '')) as moeda,
                upper(trim(nullif({escala_col}, ''))) as escala_moeda,
                trim(nullif({ordem_col}, '')) as ordem_exercicio,
                try_cast({dt_ini_col} as DATE) as data_inicio_exercicio,
                try_cast({dt_fim_col} as DATE) as data_fim_exercicio,
                trim(nullif({cd_conta_col}, '')) as codigo_conta,
                coalesce(trim({coluna_df_col}), '') as coluna_df,
                trim(nullif({ds_conta_col}, '')) as descricao_conta,
                try_cast(replace({vl_conta_col}, ',', '.') as DECIMAL(38,10)) as valor_conta,
                case when upper(trim({st_fixa_col})) in ('S', 'SIM', 'TRUE', '1') then true else false end as conta_fixa,
                '{member_name}' as arquivo_origem,
                {ano} as ano_origem
            FROM raw_csv
            WHERE DT_REFER IS NOT NULL AND VERSAO IS NOT NULL
        )
        SELECT *
        FROM parsed
        QUALIFY ROW_NUMBER() OVER (
            PARTITION BY
                tipo_formulario,
                tipo_demonstracao,
                escopo_demonstracao,
                cnpj_companhia,
                data_referencia,
                versao,
                grupo_demonstracao,
                ordem_exercicio,
                data_inicio_exercicio,
                data_fim_exercicio,
                codigo_conta,
                coluna_df
            ORDER BY linha_origem DESC
        ) = 1
    """
    con.execute(normalized_sql)

    raw_res = con.execute("SELECT count(*) FROM raw_csv").fetchone()
    total_raw_count = int(raw_res[0]) if raw_res is not None else 0
    dedup_res = con.execute("SELECT count(*) FROM normalized_dedup").fetchone()
    total_dedup_count = int(dedup_res[0]) if dedup_res is not None else 0
    duplicates_ignored = total_raw_count - total_dedup_count
    contadores["lidas"] += total_raw_count
    contadores["inalterados"] += duplicates_ignored

    # Map companhias
    companhias_map = _get_companhias_mapping(db)
    resolver_methods = quality_counters.setdefault("resolver_methods", Counter())

    writer = NormalizedArtifactWriter(
        run_id=str(run_id),
        member_id=str(member_id),
        member_name=member_name,
        row_kind=resolved_row_kind,
    )

    # Fetch rows to stream into artifact writer
    cursor = con.execute("SELECT * FROM normalized_dedup ORDER BY linha_origem ASC")
    col_names = [desc[0] for desc in cursor.description]

    for row_tuple in cursor.fetchall():
        row_dict = dict(zip(col_names, row_tuple, strict=False))
        cnpj = row_dict.get("cnpj_companhia")
        comp_id = companhias_map.get(cnpj) if cnpj else None

        if comp_id is None:
            # Fallback to resolver
            res = resolve_companhia(
                db,
                ResolverInput(
                    cnpj_companhia=cnpj,
                    codigo_cvm=row_dict.get("codigo_cvm"),
                    denominacao_companhia=row_dict.get("denominacao_companhia"),
                    tipo_formulario=tipo_formulario,
                ),
                header_map=header_map,
                provisional_enabled=True,
            )
            if res.status in {STATUS_RESOLVED, STATUS_PROVISIONAL_CREATED}:
                comp_id = res.companhia_id
                if cnpj and comp_id:
                    companhias_map[cnpj] = comp_id
                if isinstance(resolver_methods, Counter):
                    resolver_methods[res.resolution_method or "none"] += 1

        row_dict["companhia_id"] = comp_id
        chave_negocio = gerar_chave_negocio_demonstracao(row_dict)
        row_dict["chave_negocio"] = chave_negocio

        dados_para_hash = {k: v for k, v in row_dict.items() if k not in {"linha_origem", "chave_negocio"}}
        hash_origem = gerar_hash_canonico(dados_para_hash, campos_ignorados={"hash_origem"})
        row_dict["hash_origem"] = hash_origem
        row_dict["normalized_hash"] = hash_origem

        from app.services.ingestion.validation import build_natural_key
        row_dict["natural_key"] = build_natural_key(resolved_row_kind, row_dict)
        row_dict["row_kind"] = resolved_row_kind

        writer.write_row(row_dict)

    con.close()
    artifact = writer.close()
    return total_raw_count, {resolved_row_kind: artifact}
