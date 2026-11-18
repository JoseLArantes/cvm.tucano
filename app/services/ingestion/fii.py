from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import zipfile
from collections import Counter, defaultdict
from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.fii import FiiInformeAtivoPassivo, FiiInformeComplemento, FiiInformeGeral
from app.models.ingestion import IngestionFile, IngestionFileMember, IngestionRun
from app.models.sincronizacao import ExecucaoSincronizacao, HistoricoAlteracaoCampo
from app.services.ingestion.artifact_store import build_artifact_metadata
from app.services.ingestion.operational import record_phase_artifact
from app.services.ingestion.scheduling import adotar_ou_criar_execucao_sincronizacao
from app.services.ingestion.source_registry import dataset_por_member_name, obter_fonte
from app.services.ingestion.staging import create_run, update_run_state
from app.services.normalizacao import decimal_para_canonical_string

_NORMALIZER_VERSION = "fii-informe-v2"
_CNPJ_PATTERN = re.compile(r"^[A-Z0-9]{12}[0-9]{2}$")
_SECTIONS: dict[str, tuple[type[Any], str]] = {
    "geral": (FiiInformeGeral, "fii_informes_gerais"),
    "complemento": (FiiInformeComplemento, "fii_informes_complementos"),
    "ativo_passivo": (FiiInformeAtivoPassivo, "fii_informes_ativos_passivos"),
}
_ALIASES = {
    "CNPJ_Fundo": "CNPJ_Fundo_Classe",
    "Nome_Fundo": "Nome_Fundo_Classe",
}
_BOOL_FIELDS = {
    "Fundo_Exclusivo",
    "Cotistas_Vinculo_Familiar",
    "Mercado_Negociacao_Bolsa",
    "Mercado_Negociacao_MBO",
    "Mercado_Negociacao_MB",
    "Entidade_Administradora_BVMF",
    "Entidade_Administradora_CETIP",
}
_DATE_FIELDS = {"Data_Referencia", "Data_Entrega", "Data_Funcionamento", "Data_Prazo_Duracao", "Data_Informacao_Numero_Cotistas"}
_INT_FIELDS = {"Versao", "Total_Numero_Cotistas"} | {
    f"Numero_Cotistas_{suffix}"
    for suffix in (
        "Pessoa_Fisica", "Pessoa_Juridica_Nao_Financeira", "Banco_Comercial", "Corretora_Distribuidora",
        "Outras_Pessoas_Juridicas_Financeira", "Investidores_Nao_Residentes",
        "Entidade_Aberta_Previdencia_Complementar", "Entidade_Fechada_Previdência_Complementar",
        "Regime_Proprio_Previdencia_Servidores_Publicos", "Sociedade_Seguradora_Resseguradora",
        "Sociedade_Capitalizacao_Arrendamento_Mercantil", "FII", "Outros_Fundos", "Distribuidores_Fundo", "Outros_Tipos",
    )
}
_GENERAL_DECIMALS = {"Quantidade_Cotas_Emitidas"}
_COMPLEMENT_DECIMALS = {
    "Valor_Ativo", "Patrimonio_Liquido", "Cotas_Emitidas", "Valor_Patrimonial_Cotas",
    "Percentual_Despesas_Taxa_Administracao", "Percentual_Despesas_Agente_Custodiante",
    "Percentual_Rentabilidade_Efetiva_Mes", "Percentual_Rentabilidade_Patrimonial_Mes",
    "Percentual_Dividend_Yield_Mes", "Percentual_Amortizacao_Cotas_Mes",
}
_HISTORICAL_NULL_FIELDS: dict[str, tuple[str, ...]] = {
    "ativo_passivo": ("CRI_CRA", "LCI_LCA"),
}
_CORE_MAPPING: dict[str, dict[str, str]] = {
    "geral": {
        "Tipo_Fundo_Classe": "tipo", "Nome_Fundo_Classe": "nome", "Codigo_ISIN": "codigo_isin",
        "Segmento_Atuacao": "segmento_atuacao", "Publico_Alvo": "publico_alvo", "Mandato": "mandato",
        "Tipo_Gestao": "tipo_gestao", "Prazo_Duracao": "prazo_duracao", "Data_Funcionamento": "data_funcionamento",
        "Data_Prazo_Duracao": "data_prazo_duracao", "Quantidade_Cotas_Emitidas": "quantidade_cotas_emitidas",
        "Fundo_Exclusivo": "fundo_exclusivo", "Cotistas_Vinculo_Familiar": "cotistas_vinculo_familiar",
        "Mercado_Negociacao_Bolsa": "mercado_negociacao_bolsa", "Nome_Administrador": "nome_administrador",
        "CNPJ_Administrador": "cnpj_administrador",
    },
    "complemento": {
        "Valor_Ativo": "valor_ativo", "Patrimonio_Liquido": "patrimonio_liquido", "Cotas_Emitidas": "cotas_emitidas",
        "Valor_Patrimonial_Cotas": "valor_patrimonial_cotas", "Total_Numero_Cotistas": "total_numero_cotistas",
        "Percentual_Rentabilidade_Efetiva_Mes": "percentual_rentabilidade_efetiva_mes",
        "Percentual_Rentabilidade_Patrimonial_Mes": "percentual_rentabilidade_patrimonial_mes",
        "Percentual_Dividend_Yield_Mes": "percentual_dividend_yield_mes",
        "Percentual_Amortizacao_Cotas_Mes": "percentual_amortizacao_cotas_mes",
    },
    "ativo_passivo": {
        "Total_Necessidades_Liquidez": "total_necessidades_liquidez", "Disponibilidades": "disponibilidades",
        "Total_Investido": "total_investido", "Direitos_Bens_Imoveis": "direitos_bens_imoveis",
        "Valores_Receber": "valores_receber", "Total_Passivo": "total_passivo",
    },
}


def _canonical_cnpj(value: str | None) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]", "", value or "").upper()
    if not _CNPJ_PATTERN.fullmatch(normalized):
        raise ValueError("cnpj_fundo_classe_invalido")
    return normalized


def _normalizar_valor(campo: str, value: str | None, secao: str) -> Any:
    text = (value or "").strip()
    if not text:
        return None
    if campo in _BOOL_FIELDS:
        if text.upper() not in {"S", "N"}:
            raise ValueError(f"valor_booleano_invalido:{campo}")
        return text.upper() == "S"
    if campo in _DATE_FIELDS:
        try:
            return date.fromisoformat(text)
        except ValueError as exc:
            raise ValueError(f"data_invalida:{campo}") from exc
    if campo in _INT_FIELDS:
        try:
            parsed = Decimal(text)
            if parsed != parsed.to_integral_value():
                raise ValueError(f"inteiro_invalido:{campo}")
            return int(parsed)
        except InvalidOperation as exc:
            raise ValueError(f"inteiro_invalido:{campo}") from exc
    if campo in _GENERAL_DECIMALS or (secao == "complemento" and campo in _COMPLEMENT_DECIMALS) or secao == "ativo_passivo":
        try:
            return Decimal(text)
        except InvalidOperation as exc:
            raise ValueError(f"decimal_invalido:{campo}") from exc
    return text


def _valor_json(value: Any) -> str | int | bool | None:
    if isinstance(value, Decimal):
        return decimal_para_canonical_string(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, (str, int, bool)):
        return value
    return None


def _normalizar_linha(secao: str, row: dict[str, str], line: int, arquivo: str) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for source_name, raw_value in row.items():
        if source_name is None:
            continue
        canonical_name = _ALIASES.get(source_name, source_name)
        if canonical_name == "CNPJ_Fundo_Classe":
            values[canonical_name] = _canonical_cnpj(raw_value)
        elif canonical_name == "Tipo_Fundo_Classe":
            kind = (raw_value or "").strip().lower()
            if kind not in {"fundo", "classe"}:
                raise ValueError("tipo_fundo_classe_invalido")
            values[canonical_name] = kind
        else:
            values[canonical_name] = _normalizar_valor(canonical_name, raw_value, secao)
    for required in ("CNPJ_Fundo_Classe", "Data_Referencia", "Versao"):
        if values.get(required) is None:
            raise ValueError(f"campo_chave_ausente:{required}")
    if secao == "geral":
        values.setdefault("Tipo_Fundo_Classe", "fundo")
    for field in _HISTORICAL_NULL_FIELDS.get(secao, ()):
        values.setdefault(field, None)
    data_json = {key: _valor_json(value) for key, value in values.items()}
    normalized = json.dumps(data_json, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return {
        "cnpj": values["CNPJ_Fundo_Classe"],
        "tipo": values.get("Tipo_Fundo_Classe"),
        "data_referencia": values["Data_Referencia"],
        "versao": values["Versao"],
        "values": values,
        "data": data_json,
        "hash": hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        "arquivo": arquivo,
        "linha": line,
    }


def normalizar_fii_row(
    *,
    arquivo_origem: str,
    ano_origem: int,
    linha_origem: int,
    linha: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    dataset = dataset_por_member_name("fii", Path(arquivo_origem).name, ano_origem)
    if dataset is None:
        raise ValueError(f"membro_fii_nao_registrado:{arquivo_origem}")
    return dataset.row_kind or f"fii_{dataset.dataset}", _normalizar_linha(
        dataset.dataset, linha, linha_origem, Path(arquivo_origem).name
    )


def _cache_path(*, secao: str, content_sha256: str) -> Path:
    return Path(get_settings().storage_dir) / "artifacts" / "fii_normalized" / _NORMALIZER_VERSION / secao / f"{content_sha256}.json"


def _restore_cached_row(secao: str, row: dict[str, Any], *, arquivo: str) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for field, value in row["values"].items():
        if value is None:
            values[field] = None
        elif field in {"CNPJ_Fundo_Classe", "Tipo_Fundo_Classe"}:
            values[field] = str(value)
        elif field in _DATE_FIELDS:
            values[field] = date.fromisoformat(value)
        elif field in _BOOL_FIELDS:
            values[field] = bool(value)
        elif field in _INT_FIELDS:
            values[field] = int(value)
        elif field in _GENERAL_DECIMALS or (secao == "complemento" and field in _COMPLEMENT_DECIMALS) or secao == "ativo_passivo":
            values[field] = Decimal(value)
        else:
            values[field] = value
    return {
        "cnpj": row["cnpj"], "tipo": row["tipo"], "data_referencia": date.fromisoformat(row["data_referencia"]),
        "versao": int(row["versao"]), "values": values, "data": row["data"], "hash": row["hash"],
        "arquivo": arquivo, "linha": int(row["linha"]),
    }


def _read_member(payload: bytes, *, secao: str, ano: int) -> tuple[list[str], list[dict[str, Any]]]:
    expected_name = f"inf_mensal_fii_{secao}_{ano}.csv"
    content_sha256 = hashlib.sha256(payload).hexdigest()
    cache_path = _cache_path(secao=secao, content_sha256=content_sha256)
    if cache_path.exists():
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
            cache_rows = cache["rows"]
            canonical_cache_rows = json.dumps(cache_rows, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
            cache_valid = (
                cache.get("normalizer_version") == _NORMALIZER_VERSION
                and cache.get("member_sha256") == content_sha256
                and cache.get("rows_sha256") == hashlib.sha256(canonical_cache_rows.encode("utf-8")).hexdigest()
            )
            if cache_valid:
                return cache["header"], [_restore_cached_row(secao, row, arquivo=expected_name) for row in cache_rows]
        except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
            pass
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = payload.decode("latin1")
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    headers = list(reader.fieldnames or [])
    cnpj_field = "CNPJ_Fundo_Classe" if "CNPJ_Fundo_Classe" in headers else "CNPJ_Fundo"
    required_headers = {cnpj_field, "Data_Referencia", "Versao"}
    if not required_headers.issubset(headers):
        raise ValueError(f"cabecalho_incompativel:{expected_name}")
    if secao == "geral" and ano >= 2021 and "Tipo_Fundo_Classe" not in headers:
        raise ValueError("cabecalho_geral_sem_tipo_fundo_classe")
    rows: list[dict[str, Any]] = []
    for line_number, row in enumerate(reader, start=2):
        if None in row:
            raise ValueError(f"colunas_adicionais:{expected_name}:{line_number}")
        row_kind, normalized_row = normalizar_fii_row(
            arquivo_origem=expected_name,
            ano_origem=ano,
            linha_origem=line_number,
            linha=row,
        )
        if row_kind != f"fii_{secao}":
            raise ValueError(f"membro_fii_leiaute_incompativel:{expected_name}")
        rows.append(normalized_row)
    if not rows:
        raise ValueError(f"csv_sem_linhas:{expected_name}")
    if secao == "geral":
        keys = [(row["cnpj"], row["tipo"], row["data_referencia"], row["versao"]) for row in rows]
        if len(keys) != len(set(keys)):
            raise ValueError("chave_geral_duplicada")
    cache_rows = [
        {"cnpj": row["cnpj"], "tipo": row["tipo"], "data_referencia": row["data_referencia"].isoformat(),
         "versao": row["versao"], "values": {field: _valor_json(value) for field, value in row["values"].items()},
         "data": row["data"], "hash": row["hash"], "arquivo": row["arquivo"], "linha": row["linha"]}
        for row in rows
    ]
    canonical_cache_rows = json.dumps(cache_rows, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = cache_path.with_suffix(f".{content_sha256[:10]}.tmp")
    temp_path.write_text(json.dumps({
        "normalizer_version": _NORMALIZER_VERSION,
        "member_sha256": content_sha256,
        "rows_sha256": hashlib.sha256(canonical_cache_rows.encode("utf-8")).hexdigest(),
        "header": headers,
        "rows": cache_rows,
    }, ensure_ascii=True, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    temp_path.replace(cache_path)
    return headers, rows


def _prepare_row(secao: str, row: dict[str, Any], *, execution_id: Any, ano: int) -> dict[str, Any]:
    base = {
        "cnpj": row["cnpj"], "data_referencia": row["data_referencia"], "versao": row["versao"],
        "dados": row["data"], "linha_origem": row["linha"], "hash_origem": row["hash"],
        "arquivo_origem": row["arquivo"], "ano_origem": ano, "execucao_sincronizacao_id": execution_id,
    }
    if secao == "geral":
        base["tipo"] = row["tipo"]
        return base | {dest: row["values"].get(source) for source, dest in _CORE_MAPPING[secao].items()}
    return base | {dest: row["values"].get(source) for source, dest in _CORE_MAPPING[secao].items()}


def _value_string(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, Decimal):
        return decimal_para_canonical_string(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def _record_history(db: Session, *, table_name: str, row_id: Any, execution_id: Any, ano: int, field: str, before: Any, after: Any) -> None:
    db.add(HistoricoAlteracaoCampo(
        entidade=table_name,
        entidade_id=row_id,
        campo=field,
        valor_anterior=_value_string(before),
        valor_novo=_value_string(after),
        execucao_sincronizacao_id=execution_id,
        arquivo_origem=f"inf_mensal_fii_{ano}.zip",
        ano_origem=ano,
    ))


def _upsert_rows(
    db: Session,
    *,
    secao: str,
    rows: list[dict[str, Any]],
    run_id: Any,
    execution_id: Any,
    ano: int,
) -> dict[str, int]:
    model, table_name = _SECTIONS[secao]
    if secao != "geral":
        return _upsert_candidates(db, secao=secao, rows=rows, run_id=run_id, execution_id=execution_id, ano=ano)
    counters = {"inseridos": 0, "atualizados": 0, "inalterados": 0, "retirados": 0, "reaparecidos": 0}
    existing_rows: Sequence[Any] = db.scalars(select(model).where(model.ano_origem == ano)).all()
    existing = {(item.cnpj, item.tipo, item.data_referencia, item.versao): item for item in existing_rows}
    present: set[tuple[str, str, date, int]] = set()
    business_fields = set(_CORE_MAPPING[secao].values()) | {"dados"}
    for raw in rows:
        values = _prepare_row(secao, raw, execution_id=execution_id, ano=ano)
        key = (values["cnpj"], values["tipo"], values["data_referencia"], values["versao"])
        present.add(key)
        previous = existing.get(key)
        if previous is None:
            db.add(model(**values))
            counters["inseridos"] += 1
            continue
        changed = False
        for field in business_fields:
            before, after = getattr(previous, field), values[field]
            before_compare = _value_string(before) if field != "dados" else json.dumps(before, sort_keys=True, ensure_ascii=True)
            after_compare = _value_string(after) if field != "dados" else json.dumps(after, sort_keys=True, ensure_ascii=True)
            if before_compare != after_compare:
                if field == "dados":
                    old_data = previous.dados
                    new_data = values["dados"]
                    for source_field in sorted(set(old_data) | set(new_data)):
                        old_value = old_data.get(source_field)
                        new_value = new_data.get(source_field)
                        if old_value != new_value:
                            _record_history(
                                db, table_name=table_name, row_id=previous.id, execution_id=execution_id,
                                ano=ano, field=source_field, before=old_value, after=new_value,
                            )
                changed = True
                setattr(previous, field, after)
        if not previous.consta_no_snapshot_atual:
            counters["reaparecidos"] += 1
            _record_history(db, table_name=table_name, row_id=previous.id, execution_id=execution_id,
                            ano=ano, field="consta_no_snapshot_atual", before="false", after="true")
            changed = True
        previous.consta_no_snapshot_atual = True
        previous.linha_origem = values["linha_origem"]
        previous.hash_origem = values["hash_origem"]
        previous.arquivo_origem = values["arquivo_origem"]
        previous.execucao_sincronizacao_id = execution_id
        previous.sincronizado_em = datetime.now(UTC)
        if changed:
            previous.alterado_em = datetime.now(UTC)
            counters["atualizados"] += 1
        else:
            counters["inalterados"] += 1
    for key, previous in existing.items():
        if key not in present and previous.consta_no_snapshot_atual:
            previous.consta_no_snapshot_atual = False
            _record_history(db, table_name=table_name, row_id=previous.id, execution_id=execution_id,
                            ano=ano, field="consta_no_snapshot_atual", before="true", after="false")
            counters["retirados"] += 1
    db.flush()
    return counters


def _upsert_candidates(
    db: Session,
    *,
    secao: str,
    rows: list[dict[str, Any]],
    run_id: Any,
    execution_id: Any,
    ano: int,
) -> dict[str, int]:
    model, table_name = _SECTIONS[secao]
    keys_to_types: dict[tuple[str, date, int], set[str]] = defaultdict(set)
    for general_row in db.scalars(select(FiiInformeGeral).where(FiiInformeGeral.ano_origem == ano)).all():
        keys_to_types[(general_row.cnpj, general_row.data_referencia, general_row.versao)].add(general_row.tipo)
    groups: dict[tuple[str, date, int], Counter[str]] = defaultdict(Counter)
    representatives: dict[tuple[str, date, int, str], dict[str, Any]] = {}
    for candidate_row in rows:
        group_key = (candidate_row["cnpj"], candidate_row["data_referencia"], candidate_row["versao"])
        groups[group_key][candidate_row["hash"]] += 1
        representatives[( *group_key, candidate_row["hash"])] = candidate_row
    present: set[tuple[str, str | None, date, int, str]] = set()
    counters = {"inseridos": 0, "atualizados": 0, "inalterados": 0, "retirados": 0, "reaparecidos": 0}
    existing_rows: Sequence[Any] = db.scalars(select(model).where(model.ano_origem == ano)).all()
    existing = {(item.cnpj, item.tipo, item.data_referencia, item.versao, item.hash_variante): item for item in existing_rows}
    assigned_current = {
        (item.cnpj, item.tipo, item.data_referencia, item.versao): item
        for item in existing_rows
        if item.consta_no_snapshot_atual and item.tipo is not None and item.status_atribuicao == "disponivel"
    }
    old_variants: dict[tuple[str, date, int], set[tuple[str | None, str, str]]] = defaultdict(set)
    for item in existing_rows:
        if item.consta_no_snapshot_atual:
            old_variants[(item.cnpj, item.data_referencia, item.versao)].add(
                (item.tipo, item.hash_variante, item.status_atribuicao)
            )
    attributions: dict[tuple[str, date, int], list[tuple[str | None, str, dict[str, Any], int]]] = {}
    for group_key, variants in groups.items():
        general_types = keys_to_types.get(group_key, set())
        if not general_types:
            raise ValueError(f"chave_orfa:{secao}:{group_key[0]}:{group_key[1].isoformat()}")
        identical_duplicate_per_type = len(general_types) > 1 and len(variants) == 1 and next(iter(variants.values())) == len(general_types)
        attributed: list[tuple[str | None, str, dict[str, Any], int]] = []
        if len(general_types) == 1:
            assigned_type = next(iter(general_types))
            attributed.extend((assigned_type, digest, representatives[(*group_key, digest)], count) for digest, count in variants.items())
        elif identical_duplicate_per_type:
            digest, count = next(iter(variants.items()))
            attributed.extend((tipo, digest, representatives[(*group_key, digest)], 1) for tipo in sorted(general_types))
        else:
            attributed.extend((None, digest, representatives[(*group_key, digest)], count) for digest, count in variants.items())
        attributions[group_key] = attributed
    for group_key in set(old_variants) | set(groups):
        old_signature = sorted(old_variants.get(group_key, set()))
        new_signature = sorted(
            (tipo, digest, "disponivel" if tipo is not None else "ambiguo")
            for tipo, digest, _raw, _occurrences in attributions.get(group_key, [])
        )
        if old_signature == new_signature:
            continue
        parent_reports = db.scalars(select(FiiInformeGeral).where(
            FiiInformeGeral.cnpj == group_key[0], FiiInformeGeral.data_referencia == group_key[1],
            FiiInformeGeral.versao == group_key[2], FiiInformeGeral.ano_origem == ano,
        )).all()
        for parent in parent_reports:
            _record_history(
                db, table_name="fii_informes_gerais", row_id=parent.id, execution_id=execution_id,
                ano=ano, field=f"{secao}.variantes", before=json.dumps(old_signature), after=json.dumps(new_signature),
            )
    for group_key, attributed in attributions.items():
        for tipo, digest, raw, occurrences in attributed:
            identity = (*group_key[:1], tipo, *group_key[1:], digest)
            present.add(identity)
            previous = existing.get(identity)
            values = {
                "cnpj": raw["cnpj"], "tipo": tipo, "data_referencia": raw["data_referencia"], "versao": raw["versao"],
                "status_atribuicao": "disponivel" if tipo is not None else "ambiguo", "ocorrencias": occurrences,
                "dados": raw["data"], "linha_origem": raw["linha"], "hash_variante": digest,
                "hash_origem": raw["hash"],
                "arquivo_origem": raw["arquivo"], "ano_origem": ano, "execucao_sincronizacao_id": execution_id,
                "consta_no_snapshot_atual": True,
            }
            values.update({dest: raw["values"].get(source) for source, dest in _CORE_MAPPING[secao].items()})
            current_assigned = assigned_current.get((raw["cnpj"], tipo, raw["data_referencia"], raw["versao"])) if tipo else None
            if current_assigned is not None and current_assigned.hash_variante != digest:
                for source_field in sorted(set(current_assigned.dados) | set(raw["data"])):
                    old_value = current_assigned.dados.get(source_field)
                    new_value = raw["data"].get(source_field)
                    if old_value != new_value:
                        _record_history(db, table_name=table_name, row_id=current_assigned.id,
                                        execution_id=execution_id, ano=ano, field=source_field,
                                        before=old_value, after=new_value)
                current_assigned.consta_no_snapshot_atual = False
                _record_history(db, table_name=table_name, row_id=current_assigned.id,
                                execution_id=execution_id, ano=ano, field="consta_no_snapshot_atual",
                                before="true", after="false")
                counters["atualizados"] += 1
            if previous is None:
                db.add(model(**values))
                counters["inseridos"] += 1
                continue
            if not previous.consta_no_snapshot_atual:
                counters["reaparecidos"] += 1
            changed = previous.dados != values["dados"] or previous.ocorrencias != occurrences or not previous.consta_no_snapshot_atual
            for field in ("dados", "ocorrencias", "status_atribuicao", "consta_no_snapshot_atual"):
                old = getattr(previous, field)
                new = values[field]
                if old != new:
                    if field == "dados":
                        for source_field in sorted(set(old) | set(new)):
                            if old.get(source_field) != new.get(source_field):
                                _record_history(db, table_name=table_name, row_id=previous.id,
                                                execution_id=execution_id, ano=ano, field=source_field,
                                                before=old.get(source_field), after=new.get(source_field))
                    else:
                        _record_history(db, table_name=table_name, row_id=previous.id, execution_id=execution_id,
                                        ano=ano, field=field, before=old, after=new)
                    setattr(previous, field, new)
            previous.linha_origem = values["linha_origem"]
            previous.hash_origem = values["hash_origem"]
            previous.arquivo_origem = values["arquivo_origem"]
            previous.execucao_sincronizacao_id = execution_id
            if changed:
                counters["atualizados"] += 1
            else:
                counters["inalterados"] += 1
    for key, previous in existing.items():
        if key not in present and previous.consta_no_snapshot_atual:
            previous.consta_no_snapshot_atual = False
            _record_history(db, table_name=table_name, row_id=previous.id, execution_id=execution_id,
                            ano=ano, field="consta_no_snapshot_atual", before="true", after="false")
            counters["retirados"] += 1
    return counters


def _parse_zip(payload: bytes, ano: int) -> tuple[dict[str, tuple[list[str], list[dict[str, Any]], bytes]], dict[str, int]]:
    source = obter_fonte("fii")
    if source is None:
        raise ValueError("fonte_fii_nao_registrada")
    expected = {
        dataset.render_member_name(ano=ano): dataset.dataset
        for dataset in source.datasets
        if dataset.obrigatorio
    }
    if set(expected.values()) != set(_SECTIONS):
        raise ValueError("catalogo_fii_deve_ter_tres_membros_obrigatorios")
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        names = {Path(name).name: name for name in archive.namelist() if not name.endswith("/")}
        missing = set(expected) - set(names)
        if missing:
            raise ValueError(f"membros_obrigatorios_ausentes:{','.join(sorted(missing))}")
        members: dict[str, tuple[list[str], list[dict[str, Any]], bytes]] = {}
        for expected_name, section in expected.items():
            member_payload = archive.read(names[expected_name])
            header, rows = _read_member(member_payload, secao=section, ano=ano)
            members[section] = (header, rows, member_payload)
    general_keys = {(row["cnpj"], row["data_referencia"], row["versao"]) for row in members["geral"][1]}
    for section in ("complemento", "ativo_passivo"):
        for row in members[section][1]:
            if (row["cnpj"], row["data_referencia"], row["versao"]) not in general_keys:
                raise ValueError(f"chave_orfa:{section}:{row['cnpj']}:{row['data_referencia'].isoformat()}")
    if not all(members[section][1] for section in _SECTIONS):
        raise ValueError("zip_fii_sem_linhas")
    return members, {section: len(item[1]) for section, item in members.items()}


def processar_informe_fii(*, ano: int, task_id: str, force_reimport: bool = False) -> dict[str, Any]:
    db = SessionLocal()
    started = datetime.now(UTC)
    try:
        execution = adotar_ou_criar_execucao_sincronizacao(db, tipo_fonte="fii", ano=ano, task_id=task_id)
        execution.status = "em_execucao"
        execution.iniciada_em = started
        run = db.scalar(select(IngestionRun).where(IngestionRun.execucao_sincronizacao_id == execution.id).order_by(IngestionRun.created_at.desc()).limit(1))
        if run is None:
            run = create_run(db, tipo_fonte="fii", ano=ano, execucao_sincronizacao_id=execution.id, requested_by_task_id=task_id)
        else:
            update_run_state(run, status="em_execucao", phase="acquire", message=None)
        db.commit()

        settings = get_settings()
        source = obter_fonte("fii")
        if source is None:
            raise ValueError("fonte_fii_nao_registrada")
        url = f"{settings.cvm_base_url.rstrip('/')}/{source.dataset_path_template.format(ano=ano)}"
        response = httpx.get(url, timeout=300)
        response.raise_for_status()
        archive_payload = response.content
        archive_hash = hashlib.sha256(archive_payload).hexdigest()
        execution.url = url
        execution.hash_arquivo = archive_hash
        latest_valid = db.scalar(
            select(ExecucaoSincronizacao)
            .where(ExecucaoSincronizacao.tipo_fonte == "fii", ExecucaoSincronizacao.ano == ano,
                   ExecucaoSincronizacao.status.in_(("sucesso", "sem_alteracao", "skipped")),
                   ExecucaoSincronizacao.id != execution.id)
            .order_by(ExecucaoSincronizacao.iniciada_em.desc()).limit(1)
        )
        if latest_valid is not None and latest_valid.hash_arquivo == archive_hash and not force_reimport:
            execution.status = "sem_alteracao"
            execution.finalizada_em = datetime.now(UTC)
            update_run_state(run, status="sem_alteracao", phase="complete", message="zip_sha256_inalterado", finished_at=execution.finalizada_em)
            db.commit()
            return {"status": execution.status, "execucao_id": str(execution.id), "mensagem": "ZIP sem alteracoes"}

        _ = _NORMALIZER_VERSION
        members, row_counts = _parse_zip(archive_payload, ano)
        storage_dir = Path(settings.storage_dir) / str(execution.id)
        storage_dir.mkdir(parents=True, exist_ok=True)
        archive_path = storage_dir / f"inf_mensal_fii_{ano}.zip"
        archive_path.write_bytes(archive_payload)
        existing_file = db.scalar(select(IngestionFile).where(IngestionFile.ingestion_run_id == run.id).limit(1))
        if existing_file is None:
            existing_file = IngestionFile(ingestion_run_id=run.id, source_url=url, source_filename=archive_path.name,
                                          content_sha256=archive_hash, content_length_bytes=len(archive_payload), is_zip=True)
            db.add(existing_file)
            db.flush()
        else:
            existing_file.content_sha256 = archive_hash
            existing_file.content_length_bytes = len(archive_payload)
        record_phase_artifact(db, run_id=run.id, direction="output", artifact=build_artifact_metadata(
            artifact_path=archive_path, role="raw_zip", content_type="application/zip", logical_name=archive_path.name, content_sha256=archive_hash))
        for section, (header, rows, member_payload) in members.items():
            name = f"inf_mensal_fii_{section}_{ano}.csv"
            digest = hashlib.sha256(member_payload).hexdigest()
            member = db.scalar(select(IngestionFileMember).where(IngestionFileMember.ingestion_file_id == existing_file.id,
                                                                 IngestionFileMember.member_name == name).limit(1))
            if member is None:
                member = IngestionFileMember(ingestion_file_id=existing_file.id, member_name=name, member_sha256=digest,
                                             member_size_bytes=len(member_payload), header=header, row_count=len(rows),
                                             encoding="utf-8-sig", delimiter=";", schema_status="ok")
                db.add(member)
            else:
                member.member_sha256 = digest
                member.member_size_bytes = len(member_payload)
                member.header = header
                member.row_count = len(rows)
                member.schema_status = "ok"
        db.commit()

        previous_headers: dict[str, list[str]] = {}
        if latest_valid is not None:
            latest_file = db.scalar(select(IngestionFile).join(IngestionRun, IngestionRun.id == IngestionFile.ingestion_run_id)
                                    .where(IngestionRun.execucao_sincronizacao_id == latest_valid.id).limit(1))
            if latest_file is not None:
                for previous_member in db.scalars(select(IngestionFileMember).where(IngestionFileMember.ingestion_file_id == latest_file.id)).all():
                    for section in _SECTIONS:
                        if previous_member.member_name == f"inf_mensal_fii_{section}_{ano}.csv":
                            previous_headers[section] = previous_member.header or []
        changes: dict[str, Any] = {
            "linhas": {},
            "header_changed": [],
            "schema_changed": [],
            "normalizer_version": _NORMALIZER_VERSION,
        }
        counters: dict[str, dict[str, int]] = {}
        for section, (header, rows, _payload) in members.items():
            if previous_headers.get(section) != header and section in previous_headers:
                change = {
                    "member_name": f"inf_mensal_fii_{section}_{ano}.csv",
                    "before": previous_headers[section],
                    "after": header,
                }
                changes["header_changed"].append(change)
                changes["schema_changed"].append(change)
            counters[section] = _upsert_rows(db, secao=section, rows=rows, run_id=run.id,
                                             execution_id=execution.id, ano=ano)
            changes["linhas"][section] = counters[section]
        db.flush()
        execution.status = "sucesso"
        execution.finalizada_em = datetime.now(UTC)
        execution.total_linhas_lidas = sum(row_counts.values())
        execution.total_inseridos = sum(item["inseridos"] for item in counters.values())
        execution.total_atualizados = sum(item["atualizados"] for item in counters.values())
        execution.total_inalterados = sum(item["inalterados"] for item in counters.values())
        execution.total_rejeitados = 0
        update_run_state(run, status="sucesso", phase="complete", quality_summary={"source_rows": row_counts, "inserted": execution.total_inseridos,
                          "updated": execution.total_atualizados, "unchanged": execution.total_inalterados},
                         change_summary=changes, finished_at=execution.finalizada_em)
        db.commit()
        return {"status": execution.status, "execucao_id": str(execution.id), "total_linhas_lidas": execution.total_linhas_lidas,
                "total_inseridos": execution.total_inseridos, "total_atualizados": execution.total_atualizados,
                "total_inalterados": execution.total_inalterados, "mudancas": changes}
    except Exception as exc:
        db.rollback()
        failed_execution = db.scalar(select(ExecucaoSincronizacao).where(ExecucaoSincronizacao.id_tarefa == task_id).limit(1))
        if failed_execution is not None:
            failed_execution.status = "falha"
            failed_execution.finalizada_em = datetime.now(UTC)
            failed_execution.mensagem_erro = str(exc)[:4000]
            run = db.scalar(select(IngestionRun).where(IngestionRun.execucao_sincronizacao_id == failed_execution.id).order_by(IngestionRun.created_at.desc()).limit(1))
            if run is not None:
                update_run_state(run, status="falha", phase="complete", message=str(exc)[:4000], finished_at=failed_execution.finalizada_em)
            db.commit()
        raise
    finally:
        db.close()


def agendar_ingestao_semanal_fii() -> dict[str, Any]:
    """Discover published yearly packages and persist missing/recent work in the admission queue."""
    import re

    from app.services.ingestion.queue import adicionar_execucao_a_fila, criar_lote
    from app.services.ingestion.scheduling import criar_execucao_sincronizacao_agendada, novo_task_id

    settings = get_settings()
    source = obter_fonte("fii")
    if source is None:
        raise ValueError("fonte_fii_nao_registrada")
    index_url = f"{settings.cvm_base_url.rstrip('/')}/{source.dataset_path_template.rsplit('/', 1)[0]}/"
    response = httpx.get(index_url, timeout=60)
    response.raise_for_status()
    available_years = sorted(
        {int(year) for year in re.findall(r"inf_mensal_fii_(\d{4})\.zip", response.text) if int(year) >= 2016},
        reverse=True,
    )
    db: Session = SessionLocal()
    try:
        # Hold the persisted queue admission lock while checking active years and creating work.
        batch = criar_lote(db, source="celery_automatic", metadata={"fonte": "fii", "cadencia": "semanal"})
        valid_years = set(db.scalars(select(ExecucaoSincronizacao.ano).where(
            ExecucaoSincronizacao.tipo_fonte == "fii", ExecucaoSincronizacao.ano.is_not(None),
            ExecucaoSincronizacao.status.in_(("sucesso", "sem_alteracao", "skipped")),
        )).all())
        active_years = set(db.scalars(select(ExecucaoSincronizacao.ano).where(
            ExecucaoSincronizacao.tipo_fonte == "fii", ExecucaoSincronizacao.status.in_(("agendada", "aguardando_ingestao", "em_execucao")),
        )).all())
        newest = set(available_years[:5])
        queue_years = [year for year in available_years if year not in valid_years or year in newest]
        queue_years = [year for year in queue_years if year not in active_years]
        if not queue_years:
            db.rollback()
            return {"status": "sem_pendencias", "anos_disponiveis": available_years, "anos_enfileirados": []}
        queued: list[int] = []
        for sequence, year in enumerate(queue_years):
            task_id = novo_task_id()
            execution = criar_execucao_sincronizacao_agendada(db, tipo_fonte="fii", ano=year, task_id=task_id)
            adicionar_execucao_a_fila(db, batch=batch, execucao=execution,
                                      task_name="app.worker.tasks.sincronizar_fii_task", args=[year],
                                      kwargs={}, kind="zip_prepare", sequence=sequence)
            queued.append(year)
        db.commit()
        return {"status": "enfileirado", "anos_disponiveis": available_years, "anos_enfileirados": queued}
    finally:
        db.close()
