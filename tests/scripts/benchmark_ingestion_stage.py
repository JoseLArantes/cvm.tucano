from __future__ import annotations

import argparse
import csv
import io
import tracemalloc
from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.services.ingestion.staging import create_run, register_file, stage_csv_payload_streaming


@dataclass(frozen=True)
class BenchmarkCase:
    name: str
    member_name: str
    row_kind: str
    payload_builder: Callable[[int], bytes]


@dataclass(frozen=True)
class BenchmarkResult:
    case_name: str
    mode: str
    rows: int
    chunk_size: int
    elapsed_seconds: float
    peak_memory_bytes: int
    statement_count: int


def _build_dfp_demonstracao_payload(rows: int) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(
        [
            "CNPJ_CIA",
            "DT_REFER",
            "VERSAO",
            "DENOM_CIA",
            "CD_CVM",
            "GRUPO_DFP",
            "MOEDA",
            "ESCALA_MOEDA",
            "ORDEM_EXERC",
            "DT_INI_EXERC",
            "DT_FIM_EXERC",
            "CD_CONTA",
            "DS_CONTA",
            "VL_CONTA",
            "ST_CONTA_FIXA",
        ]
    )
    for index in range(rows):
        writer.writerow(
            [
                "08.773.135/0001-00",
                "2025-12-31",
                "1",
                "EMPRESA A",
                "25224",
                "GRUPO",
                "REAL",
                "UNIDADE",
                "ULTIMO",
                "2025-01-01",
                "2025-12-31",
                f"1.{index:05d}",
                f"Conta {index}",
                "1000,00",
                "S",
            ]
        )
    return buffer.getvalue().encode("latin1")


def _build_fre_posicao_payload(rows: int) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(
        [
            "CNPJ_Companhia",
            "Data_Referencia",
            "Versao",
            "ID_Documento",
            "Nome_Companhia",
            "ID_Acionista",
            "Acionista",
            "Tipo_Pessoa_Acionista",
            "CPF_CNPJ_Acionista",
            "ID_Acionista_Relacionado",
            "Acionista_Relacionado",
            "Tipo_Pessoa_Acionista_Relacionado",
            "CPF_CNPJ_Acionista_Relacionado",
            "Quantidade_Acao_Ordinaria_Circulacao",
            "Percentual_Acao_Ordinaria_Circulacao",
            "Quantidade_Acao_Preferencial_Circulacao",
            "Percentual_Acao_Preferencial_Circulacao",
            "Quantidade_Total_Acoes_Circulacao",
            "Percentual_Total_Acoes_Circulacao",
            "Nacionalidade",
            "Sigla_UF",
            "Residente_Exterior",
            "Representante_Legal",
            "Tipo_Pessoa_Representante_Legal",
            "CPF_CNPJ_Representante_legal",
            "Data_Composicao_Capital_Social",
            "Data_Ultima_Alteracao",
            "Acionista_Controlador",
            "Participante_Acordo_Acionistas",
        ]
    )
    for index in range(rows):
        writer.writerow(
            [
                "08.773.135/0001-00",
                "2025-12-31",
                "1",
                "123",
                "EMPRESA A",
                str(index + 1),
                f"ACIONISTA {index}",
                "PF",
                f"{index:011d}",
                "",
                "",
                "",
                "",
                "10",
                "1,5",
                "20",
                "2,5",
                "30",
                "4,0",
                "BRASIL",
                "SP",
                "N",
                "REPRESENTANTE X",
                "PF",
                "12345678901",
                "2025-01-01",
                "2025-12-31",
                "S",
                "N",
            ]
        )
    return buffer.getvalue().encode("latin1")


def _run_case(
    session_factory: sessionmaker[Session],
    case: BenchmarkCase,
    *,
    rows: int,
    chunk_size: int,
    use_copy: bool,
) -> BenchmarkResult:
    statement_count = 0

    def before_cursor_execute(
        conn: Any, cursor: Any, statement: str, parameters: Any, context: Any, executemany: bool
    ) -> None:
        nonlocal statement_count
        statement_count += 1

    payload = case.payload_builder(rows)
    with session_factory() as db:
        engine = db.get_bind()
        assert engine is not None
        event.listen(engine, "before_cursor_execute", before_cursor_execute)
        transaction = db.begin()
        try:
            run = create_run(db, tipo_fonte=f"benchmark_{case.name}", ano=2025)
            ingestion_file = register_file(
                db,
                ingestion_run=run,
                source_url=f"https://benchmark.local/{case.member_name}",
                source_filename=f"{case.name}.zip",
                payload=b"benchmark",
                is_zip=True,
            )
            tracemalloc.start()
            started = perf_counter()
            member = stage_csv_payload_streaming(
                db,
                ingestion_run=run,
                ingestion_file=ingestion_file,
                payload=payload,
                member_name=case.member_name,
                arquivo_origem=case.member_name,
                ano_origem=2025,
                row_kind=case.row_kind,
                chunk_size=chunk_size,
                use_copy=use_copy,
            )
            db.flush()
            elapsed = perf_counter() - started
            _, peak_memory = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            assert member.row_count == rows
            return BenchmarkResult(
                case_name=case.name,
                mode="copy" if use_copy else "insert",
                rows=rows,
                chunk_size=chunk_size,
                elapsed_seconds=elapsed,
                peak_memory_bytes=peak_memory,
                statement_count=statement_count,
            )
        finally:
            transaction.rollback()
            event.remove(engine, "before_cursor_execute", before_cursor_execute)


def _format_bytes(value: int) -> str:
    size = float(value)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} TB"


def _print_summary(results: list[BenchmarkResult]) -> None:
    print("| caso | modo | linhas | chunk | tempo_s | memoria_pico | statements |")
    print("| --- | --- | ---: | ---: | ---: | ---: | ---: |")
    for result in results:
        print(
            f"| {result.case_name} | {result.mode} | {result.rows} | {result.chunk_size} | "
            f"{result.elapsed_seconds:.4f} | {_format_bytes(result.peak_memory_bytes)} | {result.statement_count} |"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark de staging da ingestion com insert vs COPY.")
    parser.add_argument("--rows-dfp", type=int, default=50_000)
    parser.add_argument("--rows-fre", type=int, default=50_000)
    parser.add_argument("--chunk-size", type=int, default=5_000)
    args = parser.parse_args()

    settings = get_settings()
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    cases = [
        BenchmarkCase(
            name="dfp_demonstracao",
            member_name="dfp_cia_aberta_DRE_con_2025.csv",
            row_kind="dfp_demonstracao",
            payload_builder=_build_dfp_demonstracao_payload,
        ),
        BenchmarkCase(
            name="fre_posicao_acionaria",
            member_name="fre_cia_aberta_posicao_acionaria_2025.csv",
            row_kind="fre_posicao_acionaria",
            payload_builder=_build_fre_posicao_payload,
        ),
    ]
    rows_by_case = {
        "dfp_demonstracao": args.rows_dfp,
        "fre_posicao_acionaria": args.rows_fre,
    }

    results: list[BenchmarkResult] = []
    for case in cases:
        for use_copy in (False, True):
            results.append(
                _run_case(
                    session_factory,
                    case,
                    rows=rows_by_case[case.name],
                    chunk_size=args.chunk_size,
                    use_copy=use_copy,
                )
            )

    _print_summary(results)


if __name__ == "__main__":
    main()
