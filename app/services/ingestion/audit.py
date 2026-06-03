from __future__ import annotations

import csv
import hashlib
import io
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import httpx

from app.services.normalizacao import normalizar_inteiro, normalizar_linha_cadastro

CVM_BASE_URL = "https://dados.cvm.gov.br/dados"
CADASTRO_ABERTA_PATH = "CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv"
CADASTRO_ESTRANGEIRA_PATH = "CIA_ESTRANG/CAD/DADOS/cad_cia_estrang.csv"
DOCUMENT_SOURCE_PATHS = {
    "dfp": "CIA_ABERTA/DOC/DFP/DADOS/dfp_cia_aberta_{ano}.zip",
    "itr": "CIA_ABERTA/DOC/ITR/DADOS/itr_cia_aberta_{ano}.zip",
    "fre": "CIA_ABERTA/DOC/FRE/DADOS/fre_cia_aberta_{ano}.zip",
}


@dataclass(frozen=True)
class DownloadedSource:
    name: str
    url: str
    filename: str
    payload: bytes


def sha256_hex(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def decode_csv_payload(payload: bytes) -> str:
    for encoding in ("utf-8-sig", "latin1"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("csv", payload, 0, 1, "Falha ao decodificar CSV")


def read_csv_rows(payload: bytes) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(decode_csv_payload(payload)), delimiter=";"))


def read_zip_csv_members(payload: bytes) -> dict[str, list[dict[str, str]]]:
    members: dict[str, list[dict[str, str]]] = {}
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        for member_name in archive.namelist():
            if not member_name.endswith(".csv"):
                continue
            members[member_name] = read_csv_rows(archive.read(member_name))
    return members


def normalize_optional_cnpj(raw_value: Any) -> str | None:
    text = "".join(char for char in str(raw_value or "") if char.isdigit())
    return text or None


def normalize_optional_int(raw_value: Any) -> int | None:
    try:
        return normalizar_inteiro(raw_value)
    except (TypeError, ValueError):
        return None


def download_source(url: str, *, timeout: float = 120.0) -> bytes:
    response = httpx.get(url, timeout=timeout)
    response.raise_for_status()
    return response.content


def build_source_url(path: str, *, year: int | None = None) -> str:
    return f"{CVM_BASE_URL}/{path.format(ano=year)}"


def fetch_sources(
    *,
    year: int,
    document_sources: tuple[str, ...],
    downloader: Callable[[str], bytes] = download_source,
) -> dict[str, DownloadedSource]:
    sources = {
        "cadastro_aberta": DownloadedSource(
            name="cadastro_aberta",
            url=build_source_url(CADASTRO_ABERTA_PATH),
            filename=Path(CADASTRO_ABERTA_PATH).name,
            payload=downloader(build_source_url(CADASTRO_ABERTA_PATH)),
        ),
        "cadastro_estrangeira": DownloadedSource(
            name="cadastro_estrangeira",
            url=build_source_url(CADASTRO_ESTRANGEIRA_PATH),
            filename=Path(CADASTRO_ESTRANGEIRA_PATH).name,
            payload=downloader(build_source_url(CADASTRO_ESTRANGEIRA_PATH)),
        ),
    }
    for document_source in document_sources:
        path = DOCUMENT_SOURCE_PATHS[document_source]
        url = build_source_url(path, year=year)
        sources[document_source] = DownloadedSource(
            name=document_source,
            url=url,
            filename=Path(path.format(ano=year)).name,
            payload=downloader(url),
        )
    return sources


def analyze_cadastro_duplicates(rows: list[dict[str, str]]) -> dict[str, Any]:
    grouped: dict[str, list[tuple[int, dict[str, str]]]] = defaultdict(list)
    for line_number, row in enumerate(rows, start=2):
        cnpj = normalize_optional_cnpj(row.get("CNPJ_CIA"))
        if cnpj is None:
            continue
        grouped[cnpj].append((line_number, row))

    categories = Counter()
    samples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    duplicate_bucket_count = 0
    duplicate_extra_rows = 0

    for cnpj, items in grouped.items():
        if len(items) < 2:
            continue

        duplicate_bucket_count += 1
        duplicate_extra_rows += len(items) - 1

        category = classify_cadastro_duplicate(items)
        categories[category] += len(items) - 1

        if len(samples[category]) < 5:
            samples[category].append(
                {
                    "cnpj_companhia": cnpj,
                    "linhas": [
                        {
                            "linha_origem": line_number,
                            "codigo_cvm": row.get("CD_CVM"),
                            "situacao": row.get("SIT"),
                            "tipo_mercado": row.get("TP_MERC"),
                            "categoria_registro": row.get("CATEG_REG"),
                            "data_registro": row.get("DT_REG"),
                            "data_cancelamento": row.get("DT_CANCEL"),
                            "denominacao_social": row.get("DENOM_SOCIAL"),
                        }
                        for line_number, row in items
                    ],
                }
            )

    return {
        "row_count": len(rows),
        "duplicate_bucket_count": duplicate_bucket_count,
        "duplicate_extra_rows": duplicate_extra_rows,
        "duplicate_extra_ratio": 0.0 if not rows else duplicate_extra_rows / len(rows),
        "categories": dict(categories),
        "samples": dict(samples),
    }


def classify_cadastro_duplicate(items: list[tuple[int, dict[str, str]]]) -> str:
    codigo_cvm_values = {normalize_optional_int(row.get("CD_CVM")) for _, row in items}
    normalized_rows: list[dict[str, Any]] = []
    for line_number, row in items:
        normalized = normalizar_linha_cadastro(
            row,
            arquivo_origem="cad_cia_aberta.csv",
            ano_origem=None,
            linha_origem=line_number,
        )
        normalized_rows.append(
            {
                key: value
                for key, value in normalized.items()
                if key not in {"tipo_mercado", "linha_origem", "hash_origem"}
            }
        )

    if len(codigo_cvm_values) == 1:
        first = normalized_rows[0]
        if all(candidate == first for candidate in normalized_rows[1:]):
            return "same_cd_only_tipo_mercado"
        return "same_cd_other_diff"
    return "different_cd"


def build_identity_sets(
    open_company_rows: list[dict[str, str]],
    foreign_company_rows: list[dict[str, str]] | None = None,
) -> dict[str, set[Any]]:
    cnpjs = {normalize_optional_cnpj(row.get("CNPJ_CIA")) for row in open_company_rows}
    codes = {normalize_optional_int(row.get("CD_CVM")) for row in open_company_rows}

    if foreign_company_rows is not None:
        cnpjs |= {normalize_optional_cnpj(row.get("CNPJ")) for row in foreign_company_rows}
        codes |= {normalize_optional_int(row.get("CD_CVM")) for row in foreign_company_rows}

    cnpjs.discard(None)
    codes.discard(None)
    return {"cnpjs": cnpjs, "codes": codes}


def analyze_missing_companies(
    document_source: str,
    zip_payload: bytes,
    *,
    open_company_rows: list[dict[str, str]],
    foreign_company_rows: list[dict[str, str]],
) -> dict[str, Any]:
    members = read_zip_csv_members(zip_payload)
    open_only = build_identity_sets(open_company_rows)
    open_plus_foreign = build_identity_sets(open_company_rows, foreign_company_rows)

    total_rows = 0
    missing_open_only = 0
    missing_open_plus_foreign = 0
    missing_by_file_open_only: Counter[str] = Counter()
    missing_by_file_open_plus_foreign: Counter[str] = Counter()
    missing_names_open_only: Counter[str] = Counter()
    missing_names_open_plus_foreign: Counter[str] = Counter()
    missing_examples_open_only: list[dict[str, Any]] = []
    missing_examples_open_plus_foreign: list[dict[str, Any]] = []

    for member_name, rows in members.items():
        for line_number, row in enumerate(rows, start=2):
            total_rows += 1
            cnpj = first_present_cnpj(row)
            code = normalize_optional_int(row.get("CD_CVM"))
            company_name = first_present_name(row)

            if not identity_hit(cnpj, code, open_only):
                missing_open_only += 1
                missing_by_file_open_only[member_name] += 1
                missing_names_open_only[company_name] += 1
                if len(missing_examples_open_only) < 10:
                    missing_examples_open_only.append(
                        build_missing_example(member_name, line_number, cnpj, code, company_name)
                    )

            if not identity_hit(cnpj, code, open_plus_foreign):
                missing_open_plus_foreign += 1
                missing_by_file_open_plus_foreign[member_name] += 1
                missing_names_open_plus_foreign[company_name] += 1
                if len(missing_examples_open_plus_foreign) < 10:
                    missing_examples_open_plus_foreign.append(
                        build_missing_example(member_name, line_number, cnpj, code, company_name)
                    )

    return {
        "source": document_source,
        "row_count": total_rows,
        "missing_open_only": missing_open_only,
        "missing_open_only_ratio": 0.0 if total_rows == 0 else missing_open_only / total_rows,
        "missing_open_plus_foreign": missing_open_plus_foreign,
        "missing_open_plus_foreign_ratio": 0.0 if total_rows == 0 else missing_open_plus_foreign / total_rows,
        "missing_by_file_open_only": dict(missing_by_file_open_only.most_common()),
        "missing_by_file_open_plus_foreign": dict(missing_by_file_open_plus_foreign.most_common()),
        "top_missing_names_open_only": missing_names_open_only.most_common(10),
        "top_missing_names_open_plus_foreign": missing_names_open_plus_foreign.most_common(10),
        "missing_examples_open_only": missing_examples_open_only,
        "missing_examples_open_plus_foreign": missing_examples_open_plus_foreign,
    }


def identity_hit(cnpj: str | None, code: int | None, identity_sets: dict[str, set[Any]]) -> bool:
    return (cnpj is not None and cnpj in identity_sets["cnpjs"]) or (
        code is not None and code in identity_sets["codes"]
    )


def first_present_cnpj(row: dict[str, str]) -> str | None:
    for field_name in ("CNPJ_CIA", "CNPJ_Companhia", "CNPJ"):
        if field_name in row:
            return normalize_optional_cnpj(row.get(field_name))
    return None


def first_present_name(row: dict[str, str]) -> str:
    for field_name in ("DENOM_CIA", "Nome_Companhia", "Nome_Cia"):
        value = row.get(field_name)
        if value:
            return value
    return "?"


def build_missing_example(
    member_name: str,
    line_number: int,
    cnpj: str | None,
    code: int | None,
    company_name: str,
) -> dict[str, Any]:
    return {
        "arquivo_origem": member_name,
        "linha_origem": line_number,
        "cnpj_companhia": cnpj,
        "codigo_cvm": code,
        "denominacao_companhia": company_name,
    }


def build_audit_report(
    *,
    year: int,
    document_sources: tuple[str, ...] = ("dfp", "itr", "fre"),
    downloader: Callable[[str], bytes] = download_source,
) -> dict[str, Any]:
    sources = fetch_sources(year=year, document_sources=document_sources, downloader=downloader)
    open_company_rows = read_csv_rows(sources["cadastro_aberta"].payload)
    foreign_company_rows = read_csv_rows(sources["cadastro_estrangeira"].payload)

    report = {
        "year": year,
        "sources": {
            source.name: {
                "url": source.url,
                "filename": source.filename,
                "size_bytes": len(source.payload),
                "sha256": sha256_hex(source.payload),
            }
            for source in sources.values()
        },
        "cadastro_duplicates": analyze_cadastro_duplicates(open_company_rows),
        "missing_parent": {},
    }

    for document_source in document_sources:
        report["missing_parent"][document_source] = analyze_missing_companies(
            document_source,
            sources[document_source].payload,
            open_company_rows=open_company_rows,
            foreign_company_rows=foreign_company_rows,
        )
    return report


def render_console_summary(report: dict[str, Any]) -> str:
    lines = [
        f"year: {report['year']}",
        "sources:",
    ]
    for source_name, source in sorted(report["sources"].items()):
        lines.append(
            f"  - {source_name}: file={source['filename']} size={source['size_bytes']} sha256={source['sha256']}"
        )

    duplicates = report["cadastro_duplicates"]
    lines.extend(
        [
            "cadastro_duplicates:",
            f"  - rows={duplicates['row_count']}",
            f"  - duplicate_buckets={duplicates['duplicate_bucket_count']}",
            f"  - duplicate_extra_rows={duplicates['duplicate_extra_rows']}",
            f"  - duplicate_extra_ratio={duplicates['duplicate_extra_ratio']:.6f}",
        ]
    )
    for category_name, count in sorted(duplicates["categories"].items()):
        lines.append(f"  - {category_name}={count}")

    lines.append("missing_parent:")
    for source_name, source_report in sorted(report["missing_parent"].items()):
        lines.extend(
            [
                f"  - {source_name}: rows={source_report['row_count']}",
                f"    open_only={source_report['missing_open_only']} ({source_report['missing_open_only_ratio']:.6f})",
                (
                    "    open_plus_foreign="
                    f"{source_report['missing_open_plus_foreign']}"
                    f" ({source_report['missing_open_plus_foreign_ratio']:.6f})"
                ),
            ]
        )
    return "\n".join(lines)
