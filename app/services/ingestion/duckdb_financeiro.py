from __future__ import annotations

import logging
import shutil
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

import duckdb
from sqlalchemy import insert
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.ingestion import IngestionFinanceiroStageRow
from app.services.financeiro_mapas import arquivos_demonstracao
from app.services.ingestion.file_manager import compute_file_sha256
from app.services.ingestion.resolver import (
    STATUS_PROVISIONAL_CREATED,
    STATUS_RESOLVED,
    ResolverInput,
    resolve_companhia,
)
from app.services.ingestion.typed_staging import (
    _STAGE_COLUMNS,
    _should_use_postgres_copy,
    clear_financeiro_stage_rows,
)

logger = logging.getLogger(__name__)


def can_use_duckdb_for_member(member_name: str, row_kind: str) -> bool:
    """Check if member can be processed via DuckDB vectorized pipeline."""
    return row_kind.endswith("_demonstracao") and (
        member_name.startswith("dfp_cia_aberta_") or member_name.startswith("itr_cia_aberta_")
    )


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
    load_stage: bool = True,
) -> tuple[int, dict[str, Any], bool] | None:
    """Vectorized normalization, deduplication & direct staging via DuckDB.

    Returns (total_rows, normalized_artifacts_dict, stage_loaded) or None on failure.
    """
    mapa_demonstracoes = {
        nome_arquivo: (tipo_dem, escopo)
        for nome_arquivo, tipo_dem, escopo in arquivos_demonstracao(prefixo, ano)
    }
    if member_name not in mapa_demonstracoes:
        return None

    tipo_demonstracao, escopo_demonstracao = mapa_demonstracoes[member_name]
    resolved_row_kind = f"{prefixo}_demonstracao"

    temp_spill = Path(tempfile.mkdtemp(prefix="duckdb_spill_"))
    con = duckdb.connect(database=":memory:")
    try:
        con.execute("PRAGMA memory_limit='1500MB'")
        con.execute("PRAGMA threads=1")
        con.execute("SET preserve_insertion_order=false")
        con.execute(f"PRAGMA temp_directory='{temp_spill}'")

        # Read raw CSV
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
            msg = str(exc).lower()
            if "no space left" in msg or "database or disk is full" in msg:
                raise
            logger.warning("DuckDB failed to load CSV %s: %s. Falling back to Python.", member_name, exc)
            return None

        # Verify expected columns
        cols = [desc[0].upper() for desc in con.execute("DESCRIBE raw_csv").fetchall()]
        if "CNPJ_CIA" not in cols or "DT_REFER" not in cols or "VERSAO" not in cols:
            return None

        grupo_expr = f"r.{'GRUPO_DFP' if 'GRUPO_DFP' in cols else 'GRUPO_ITR'}" if ("GRUPO_DFP" in cols or "GRUPO_ITR" in cols) else "NULL"
        coluna_df_expr = "r.COLUNA_DF" if "COLUNA_DF" in cols else "''"
        cd_cvm_expr = "r.CD_CVM" if "CD_CVM" in cols else "NULL"
        moeda_expr = "r.MOEDA" if "MOEDA" in cols else "NULL"
        escala_expr = "r.ESCALA_MOEDA" if "ESCALA_MOEDA" in cols else "NULL"
        ordem_expr = "r.ORDEM_EXERC" if "ORDEM_EXERC" in cols else "NULL"
        dt_ini_expr = "r.DT_INI_EXERC" if "DT_INI_EXERC" in cols else "NULL"
        dt_fim_expr = "r.DT_FIM_EXERC" if "DT_FIM_EXERC" in cols else "NULL"
        cd_conta_expr = "r.CD_CONTA" if "CD_CONTA" in cols else "NULL"
        ds_conta_expr = "r.DS_CONTA" if "DS_CONTA" in cols else "NULL"
        vl_conta_expr = "r.VL_CONTA" if "VL_CONTA" in cols else "NULL"
        st_fixa_expr = "r.ST_CONTA_FIXA" if "ST_CONTA_FIXA" in cols else "NULL"
        denom_expr = "r.DENOM_CIA" if "DENOM_CIA" in cols else "NULL"
    
        # Step 1: Resolve companies in Python for the distinct set (< 500 distinct companies)
        distinct_companies_rows = con.execute(f"""
            SELECT
                lpad(regexp_replace(CNPJ_CIA, '[^0-9]', '', 'g'), 14, '0') as cnpj_companhia,
                try_cast({cd_cvm_expr.replace('r.', '')} as INTEGER) as codigo_cvm,
                trim(nullif({denom_expr.replace('r.', '')}, '')) as denominacao_companhia,
                count(*) as row_count
            FROM raw_csv
            WHERE CNPJ_CIA IS NOT NULL AND trim(CNPJ_CIA) != ''
            GROUP BY 1, 2, 3
        """).fetchall()
    
        resolver_methods = quality_counters.setdefault("resolver_methods", Counter())
        resolved_tuples: list[tuple[str, str | None, int | None]] = []
    
        for cnpj, cd_cvm, denom, row_count in distinct_companies_rows:
            res = resolve_companhia(
                db,
                ResolverInput(
                    cnpj_companhia=cnpj,
                    codigo_cvm=cd_cvm,
                    denominacao_companhia=denom,
                    tipo_formulario=tipo_formulario,
                ),
                header_map=header_map,
                provisional_enabled=True,
            )
            comp_id_str: str | None = None
            resolved_cvm: int | None = cd_cvm
            if res.status in {STATUS_RESOLVED, STATUS_PROVISIONAL_CREATED}:
                comp_id_str = str(res.companhia_id) if res.companhia_id else None
                if isinstance(resolver_methods, Counter):
                    resolver_methods[res.resolution_method or "none"] += int(row_count)
                if res.status == STATUS_PROVISIONAL_CREATED:
                    provisional_raw = quality_counters.get("provisional_company_count", 0)
                    quality_counters["provisional_company_count"] = (
                        (provisional_raw if isinstance(provisional_raw, int) else 0) + 1
                    )
            resolved_tuples.append((cnpj, comp_id_str, resolved_cvm))
    
        con.execute("""
            CREATE TEMPORARY TABLE resolved_companies (
                cnpj_companhia VARCHAR,
                companhia_id UUID,
                codigo_cvm_resolvido INTEGER
            )
        """)
        if resolved_tuples:
            con.executemany("INSERT INTO resolved_companies VALUES (?, ?, ?)", resolved_tuples)
    
        # Step 2: Vectorized parsing, joining companies, and deterministic deduplication in DuckDB
        con.execute(f"""
            CREATE TEMPORARY TABLE parsed AS
            SELECT
                r.linha_origem,
                '{tipo_formulario}' as tipo_formulario,
                '{tipo_demonstracao}' as tipo_demonstracao,
                '{escopo_demonstracao}' as escopo_demonstracao,
                lpad(regexp_replace(r.CNPJ_CIA, '[^0-9]', '', 'g'), 14, '0') as cnpj_companhia,
                coalesce(try_cast({cd_cvm_expr} as INTEGER), rc.codigo_cvm_resolvido) as codigo_cvm,
                rc.companhia_id,
                try_cast(r.DT_REFER as DATE) as data_referencia,
                try_cast(r.VERSAO as INTEGER) as versao,
                trim(nullif({denom_expr}, '')) as denominacao_companhia,
                trim(nullif({grupo_expr}, '')) as grupo_demonstracao,
                trim(nullif({moeda_expr}, '')) as moeda,
                upper(trim(nullif({escala_expr}, ''))) as escala_moeda,
                trim(nullif({ordem_expr}, '')) as ordem_exercicio,
                try_cast({dt_ini_expr} as DATE) as data_inicio_exercicio,
                try_cast({dt_fim_expr} as DATE) as data_fim_exercicio,
                trim(nullif({cd_conta_expr}, '')) as codigo_conta,
                coalesce(trim({coluna_df_expr}), '') as coluna_df,
                trim(nullif({ds_conta_expr}, '')) as descricao_conta,
                try_cast(replace({vl_conta_expr}, ',', '.') as DECIMAL(38,10)) as valor_conta,
                case when upper(trim({st_fixa_expr})) in ('S', 'SIM', 'TRUE', '1') then true else false end as conta_fixa,
                '{member_name}' as arquivo_origem,
                {ano} as ano_origem
            FROM raw_csv r
            LEFT JOIN resolved_companies rc ON lpad(regexp_replace(r.CNPJ_CIA, '[^0-9]', '', 'g'), 14, '0') = rc.cnpj_companhia
            WHERE r.DT_REFER IS NOT NULL AND r.VERSAO IS NOT NULL
        """)
    
        # Vectorized deterministic deduplication:
        # 1. Prefer non-zero value over zero shadow
        # 2. Prefer conta_fixa
        # 3. Prefer latest linha_origem
        con.execute("""
            CREATE TEMPORARY TABLE normalized_dedup AS
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
                ORDER BY
                    case when abs(coalesce(valor_conta, 0)) > 0 then 1 else 0 end desc,
                    case when conta_fixa then 1 else 0 end desc,
                    linha_origem desc
            ) = 1
        """)
    
        raw_res = con.execute("SELECT count(*) FROM raw_csv").fetchone()
        total_raw_count = int(raw_res[0]) if raw_res is not None else 0
        dedup_res = con.execute("SELECT count(*) FROM normalized_dedup").fetchone()
        total_dedup_count = int(dedup_res[0]) if dedup_res is not None else 0
        duplicates_ignored = total_raw_count - total_dedup_count
        contadores["lidas"] = contadores.get("lidas", 0) + total_raw_count
        if "inalterados" in contadores:
            contadores["inalterados"] += duplicates_ignored
        elif "inalteradas" in contadores:
            contadores["inalteradas"] += duplicates_ignored
        else:
            contadores["inalterados"] = duplicates_ignored
    
        # Step 3: Exact bit-for-bit SQL macros matching Python JSON / SHA256 canonical hashing
        con.execute("""
            CREATE MACRO py_natural_key_json(cnpj, cd_conta, col_df, dt_fim, dt_ini, dt_ref, escopo, grupo, ordem, tp_dem, tp_form, versao) AS (
                '{"cnpj_companhia": "' || coalesce(cnpj, '') ||
                '", "codigo_conta": "' || coalesce(cd_conta, '') ||
                '", "coluna_df": ' || case when col_df is null or col_df = '' then 'null' else '"' || col_df || '"' end ||
                ', "data_fim_exercicio": ' || case when dt_fim is null then 'null' else '"' || strftime(dt_fim, '%Y-%m-%d') || '"' end ||
                ', "data_inicio_exercicio": ' || case when dt_ini is null then 'null' else '"' || strftime(dt_ini, '%Y-%m-%d') || '"' end ||
                ', "data_referencia": "' || strftime(dt_ref, '%Y-%m-%d') ||
                '", "escopo_demonstracao": "' || coalesce(escopo, '') ||
                '", "grupo_demonstracao": "' || replace(replace(coalesce(grupo, ''), '\\', '\\\\'), '"', '\\"') ||
                '", "ordem_exercicio": ' || case when ordem is null then 'null' else '"' || ordem || '"' end ||
                ', "tipo_demonstracao": "' || coalesce(tp_dem, '') ||
                '", "tipo_formulario": "' || coalesce(tp_form, '') ||
                '", "versao": ' || versao || '}'
            );
    
            CREATE MACRO py_hash_origem(
                cnpj, cd_conta, cd_cvm, col_df, comp_id, c_fixa, dt_fim, dt_ini, dt_ref,
                denom, desc_c, esc_moeda, escopo, grupo, moeda, ordem, tp_dem, tp_form, vl, versao
            ) AS sha256(
                '{"cnpj_companhia": "' || coalesce(cnpj, '') ||
                '", "codigo_conta": "' || coalesce(cd_conta, '') ||
                '", "codigo_cvm": ' || case when cd_cvm is null then 'null' else cast(cd_cvm as varchar) end ||
                ', "coluna_df": ' || case when col_df is null or col_df = '' then 'null' else '"' || col_df || '"' end ||
                ', "companhia_id": ' || case when comp_id is null then 'null' else '"' || cast(comp_id as varchar) || '"' end ||
                ', "conta_fixa": ' || case when c_fixa then 'true' else 'false' end ||
                ', "data_fim_exercicio": ' || case when dt_fim is null then 'null' else '"' || strftime(dt_fim, '%Y-%m-%d') || '"' end ||
                ', "data_inicio_exercicio": ' || case when dt_ini is null then 'null' else '"' || strftime(dt_ini, '%Y-%m-%d') || '"' end ||
                ', "data_referencia": "' || strftime(dt_ref, '%Y-%m-%d') ||
                '", "denominacao_companhia": ' || case when denom is null then 'null' else '"' || replace(replace(denom, '\\', '\\\\'), '"', '\\"') || '"' end ||
                ', "descricao_conta": ' || case when desc_c is null then 'null' else '"' || replace(replace(desc_c, '\\', '\\\\'), '"', '\\"') || '"' end ||
                ', "escala_moeda": ' || case when esc_moeda is null then 'null' else '"' || esc_moeda || '"' end ||
                ', "escopo_demonstracao": "' || coalesce(escopo, '') ||
                '", "grupo_demonstracao": "' || replace(replace(coalesce(grupo, ''), '\\', '\\\\'), '"', '\\"') ||
                '", "moeda": ' || case when moeda is null then 'null' else '"' || moeda || '"' end ||
                ', "ordem_exercicio": ' || case when ordem is null then 'null' else '"' || ordem || '"' end ||
                ', "tipo_demonstracao": "' || coalesce(tp_dem, '') ||
                '", "tipo_formulario": "' || coalesce(tp_form, '') ||
                '", "valor_conta": ' || case when vl is null then 'null' else '"' || cast(vl as varchar) || '"' end ||
                ', "versao": ' || versao || '}'
            );
        """)
    
        # Target artifact path
        settings = get_settings()
        root = Path(settings.storage_dir) / "artifacts" / "normalized" / str(run_id) / str(member_id)
        stem = Path(member_name).stem
        artifact_path = root / f"{stem}__{resolved_row_kind}.typed.csv"
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
    
        # Step 4: Build stage_rows temporary table with exact columns matching _STAGE_COLUMNS
        con.execute(f"""
            CREATE TEMPORARY TABLE stage_rows AS
            SELECT
                gen_random_uuid() as id,
                CAST('{str(run_id)}' AS UUID) as ingestion_run_id,
                CAST('{str(member_id)}' AS UUID) as ingestion_file_member_id,
                '{str(artifact_path)}' as artifact_uri,
                '{resolved_row_kind}' as row_kind,
                arquivo_origem,
                ano_origem,
                linha_origem,
                py_hash_origem(cnpj_companhia, codigo_conta, codigo_cvm, coluna_df, companhia_id, conta_fixa, data_fim_exercicio, data_inicio_exercicio, data_referencia, denominacao_companhia, descricao_conta, escala_moeda, escopo_demonstracao, grupo_demonstracao, moeda, ordem_exercicio, tipo_demonstracao, tipo_formulario, valor_conta, versao) as normalized_hash,
                py_hash_origem(cnpj_companhia, codigo_conta, codigo_cvm, coluna_df, companhia_id, conta_fixa, data_fim_exercicio, data_inicio_exercicio, data_referencia, denominacao_companhia, descricao_conta, escala_moeda, escopo_demonstracao, grupo_demonstracao, moeda, ordem_exercicio, tipo_demonstracao, tipo_formulario, valor_conta, versao) as hash_origem,
                sha256(py_natural_key_json(cnpj_companhia, codigo_conta, coluna_df, data_fim_exercicio, data_inicio_exercicio, data_referencia, escopo_demonstracao, grupo_demonstracao, ordem_exercicio, tipo_demonstracao, tipo_formulario, versao)) as chave_negocio,
                companhia_id,
                py_natural_key_json(cnpj_companhia, codigo_conta, coluna_df, data_fim_exercicio, data_inicio_exercicio, data_referencia, escopo_demonstracao, grupo_demonstracao, ordem_exercicio, tipo_demonstracao, tipo_formulario, versao) as natural_key,
                tipo_formulario,
                cnpj_companhia,
                codigo_cvm,
                data_referencia,
                versao,
                denominacao_companhia,
                CAST(NULL AS VARCHAR) as categoria_documento,
                CAST(NULL AS INTEGER) as id_documento,
                CAST(NULL AS DATE) as data_recebimento,
                CAST(NULL AS VARCHAR) as link_documento,
                tipo_demonstracao,
                escopo_demonstracao,
                grupo_demonstracao,
                moeda,
                escala_moeda,
                ordem_exercicio,
                data_inicio_exercicio,
                data_fim_exercicio,
                codigo_conta,
                coluna_df,
                descricao_conta,
                valor_conta,
                conta_fixa,
                CAST(NULL AS DECIMAL(38,10)) as quantidade_acoes_ordinarias_capital_integralizado,
                CAST(NULL AS DECIMAL(38,10)) as quantidade_acoes_preferenciais_capital_integralizado,
                CAST(NULL AS DECIMAL(38,10)) as quantidade_total_acoes_capital_integralizado,
                CAST(NULL AS DECIMAL(38,10)) as quantidade_acoes_ordinarias_tesouraria,
                CAST(NULL AS DECIMAL(38,10)) as quantidade_acoes_preferenciais_tesouraria,
                CAST(NULL AS DECIMAL(38,10)) as quantidade_total_acoes_tesouraria,
                CAST(NULL AS VARCHAR) as tipo_relatorio_auditor,
                CAST(NULL AS VARCHAR) as tipo_parecer_declaracao,
                CAST(NULL AS VARCHAR) as numero_item_parecer_declaracao,
                CAST(NULL AS VARCHAR) as texto_parecer_declaracao
            FROM normalized_dedup
        """)
    
        # Step 5: Export normalized artifact directly to disk in C++ (< 0.3s)
        con.execute(f"""
            COPY (
                SELECT
                    row_kind,
                    linha_origem,
                    arquivo_origem,
                    ano_origem,
                    companhia_id,
                    normalized_hash,
                    hash_origem,
                    natural_key,
                    chave_negocio,
                    tipo_formulario,
                    tipo_demonstracao,
                    escopo_demonstracao,
                    cnpj_companhia,
                    codigo_cvm,
                    strftime(data_referencia, '%Y-%m-%d') as data_referencia,
                    versao,
                    denominacao_companhia,
                    grupo_demonstracao,
                    moeda,
                    escala_moeda,
                    ordem_exercicio,
                    strftime(data_inicio_exercicio, '%Y-%m-%d') as data_inicio_exercicio,
                    strftime(data_fim_exercicio, '%Y-%m-%d') as data_fim_exercicio,
                    codigo_conta,
                    coluna_df,
                    descricao_conta,
                    cast(valor_conta as varchar) as valor_conta,
                    case when conta_fixa then 'S' else 'N' end as conta_fixa
                FROM stage_rows
                ORDER BY linha_origem ASC
            ) TO '{str(artifact_path)}' (FORMAT CSV, DELIMITER ';', HEADER true, NULL '')
        """)
    
        # Step 6: Direct staging stream into PostgreSQL ingestion_financeiro_stage_rows
        stage_loaded = False
        if load_stage:
            rows_replaced = clear_financeiro_stage_rows(db, ingestion_file_member_id=member_id)
            rows_loaded = 0
            use_copy = _should_use_postgres_copy(db)
    
            if use_copy:
                sa_connection = db.connection()
                proxied = sa_connection.connection
                raw_connection = getattr(proxied, "driver_connection", proxied)
                copy_sql = f"""
                    COPY ingestion_financeiro_stage_rows (
                        {", ".join(_STAGE_COLUMNS)}
                    )
                    FROM STDIN
                """
                cursor = raw_connection.cursor()
                select_res = con.execute(f"SELECT {', '.join(_STAGE_COLUMNS)} FROM stage_rows ORDER BY linha_origem ASC")
                try:
                    with cursor.copy(copy_sql) as copy:
                        while batch := select_res.fetchmany(20000):
                            for row in batch:
                                copy.write_row(row)
                                rows_loaded += 1
                finally:
                    cursor.close()
            else:
                select_res = con.execute(f"SELECT {', '.join(_STAGE_COLUMNS)} FROM stage_rows ORDER BY linha_origem ASC")
                while batch := select_res.fetchmany(5000):
                    batch_dicts = [dict(zip(_STAGE_COLUMNS, row, strict=False)) for row in batch]
                    db.execute(insert(IngestionFinanceiroStageRow), batch_dicts)
                    rows_loaded += len(batch)
                db.flush()
    
            quality_counters["typed_stage_rows_loaded"] = rows_loaded
            quality_counters["typed_stage_bytes_loaded"] = artifact_path.stat().st_size
            quality_counters["typed_stage_rows_replaced"] = rows_replaced
            if use_copy:
                quality_counters["typed_stage_copy_loads"] = 1
            stage_loaded = True
    
    finally:
        try:
            con.close()
        except Exception:
            pass
        shutil.rmtree(temp_spill, ignore_errors=True)

    # Step 7: Build artifact metadata
    artifact_size = artifact_path.stat().st_size if artifact_path.exists() else 0
    artifact_sha = compute_file_sha256(str(artifact_path)) if artifact_path.exists() else ""
    artifact = {
        "uri": str(artifact_path),
        "role": "normalized_typed_csv",
        "content_type": "text/csv; charset=utf-8",
        "logical_name": artifact_path.name,
        "size_bytes": artifact_size,
        "content_sha256": artifact_sha,
        "row_count": total_dedup_count,
        "fieldnames": _STAGE_COLUMNS,
    }

    return total_raw_count, {resolved_row_kind: artifact}, stage_loaded
