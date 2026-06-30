from __future__ import annotations

import argparse
import tempfile
import tracemalloc
import uuid
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from app.core.config import get_settings
from app.services.ingestion.normalized_artifacts import (
    NormalizedArtifactFormat,
    NormalizedArtifactWriter,
    iter_normalized_artifact_rows,
)


@dataclass(frozen=True)
class BenchmarkResult:
    artifact_format: str
    rows: int
    elapsed_write_seconds: float
    elapsed_read_seconds: float
    peak_memory_bytes: int
    size_bytes: int | None
    status: str
    detail: str | None = None


def _sample_row(index: int) -> dict[str, Any]:
    return {
        "row_kind": "dfp_demonstracao",
        "linha_origem": index + 2,
        "arquivo_origem": "dfp_cia_aberta_DRE_con_2025.csv",
        "ano_origem": 2025,
        "normalized_hash": f"hash-{index}",
        "companhia_id": 1000 + (index % 7),
        "natural_key": {"codigo_conta": f"1.{index:05d}"},
        "tipo_formulario": "DFP",
        "cnpj_companhia": "08773135000100",
        "codigo_cvm": 25224,
        "data_referencia": "2025-12-31",
        "versao": 1,
        "denominacao_companhia": "EMPRESA A",
        "tipo_demonstracao": "DRE",
        "escopo_demonstracao": "consolidado",
        "grupo_demonstracao": "DF Consolidado",
        "moeda": "BRL",
        "escala_moeda": "UNIDADE",
        "ordem_exercicio": "ULT",
        "data_inicio_exercicio": "2025-01-01",
        "data_fim_exercicio": "2025-12-31",
        "codigo_conta": f"1.{index:05d}",
        "coluna_df": "valor",
        "descricao_conta": f"Conta {index}",
        "valor_conta": f"{1000 + index}.00",
        "conta_fixa": True,
    }


def _format_bytes(value: int | None) -> str:
    if value is None:
        return "-"
    size = float(value)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} TB"


def _run_case(*, artifact_format: NormalizedArtifactFormat, rows: int, base_dir: str) -> BenchmarkResult:
    tracemalloc.start()
    started = perf_counter()
    try:
        writer = NormalizedArtifactWriter(
            run_id="benchmark-run",
            member_id=str(uuid.uuid4()),
            member_name="dfp_cia_aberta_DRE_con_2025.csv",
            row_kind="dfp_demonstracao",
            base_dir=base_dir,
            artifact_format=artifact_format,
        )
        for index in range(rows):
            writer.write_row(_sample_row(index))
        metadata = writer.close()
        write_elapsed = perf_counter() - started
        read_started = perf_counter()
        loaded_rows = sum(1 for _ in iter_normalized_artifact_rows(artifact_uri=metadata["uri"]))
        read_elapsed = perf_counter() - read_started
        _, peak_memory = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        if loaded_rows != rows:
            raise RuntimeError(f"Expected {rows} rows, got {loaded_rows}.")
        return BenchmarkResult(
            artifact_format=artifact_format,
            rows=rows,
            elapsed_write_seconds=write_elapsed,
            elapsed_read_seconds=read_elapsed,
            peak_memory_bytes=peak_memory,
            size_bytes=int(metadata["size_bytes"]),
            status="ok",
        )
    except Exception as exc:
        _, peak_memory = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        return BenchmarkResult(
            artifact_format=artifact_format,
            rows=rows,
            elapsed_write_seconds=0.0,
            elapsed_read_seconds=0.0,
            peak_memory_bytes=peak_memory,
            size_bytes=None,
            status="unavailable",
            detail=str(exc),
        )


def _print_summary(results: list[BenchmarkResult]) -> None:
    print("| formato | status | linhas | escrita_s | leitura_s | memoria_pico | tamanho | detalhe |")
    print("| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |")
    for result in results:
        print(
            f"| {result.artifact_format} | {result.status} | {result.rows} | "
            f"{result.elapsed_write_seconds:.4f} | {result.elapsed_read_seconds:.4f} | "
            f"{_format_bytes(result.peak_memory_bytes)} | {_format_bytes(result.size_bytes)} | "
            f"{result.detail or '-'} |"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark de artifact normalizado typed_csv vs parquet.")
    parser.add_argument("--rows", type=int, default=100_000)
    parser.add_argument(
        "--formats",
        nargs="+",
        choices=["typed_csv", "parquet"],
        default=["typed_csv", "parquet"],
    )
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(dir=get_settings().storage_dir) as tmp_dir:
        results = [
            _run_case(
                artifact_format=artifact_format,
                rows=args.rows,
                base_dir=tmp_dir,
            )
            for artifact_format in args.formats
        ]
    _print_summary(results)


if __name__ == "__main__":
    main()
