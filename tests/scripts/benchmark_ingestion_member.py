from __future__ import annotations

import argparse
import csv
import io
import tracemalloc
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime
from time import perf_counter
from typing import Any

from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.models.companhia import Companhia
from app.models.financeiro import DemonstracaoFinanceira
from app.models.fre import FrePosicaoAcionaria
from app.models.identidade import CompanhiaIdentificador
from app.models.ingestion import QuarantineItem
from app.models.sincronizacao import ExecucaoSincronizacao
from app.services.ingestion.financeiro import _process_financeiro_member
from app.services.ingestion.fre import _process_fre_member
from app.services.ingestion.staging import create_run, register_file, stage_csv_payload_streaming


@dataclass(frozen=True)
class BenchmarkResult:
    case_name: str
    rows: int
    stage_chunk_size: int
    promote_chunk_size: int
    stage_seconds: float
    process_seconds: float
    total_seconds: float
    peak_memory_bytes: int
    statement_count: int
    promoted_rows: int
    quarantined_rows: int


def _companhia() -> Companhia:
    agora = datetime.now(UTC)
    return Companhia(
        cnpj_companhia="08773135000100",
        codigo_cvm=25224,
        denominacao_social="Empresa Benchmark",
        denominacao_comercial="Empresa Benchmark",
        situacao_registro="ATIVA",
        data_registro=date(2020, 1, 1),
        data_constituicao=date(2000, 1, 1),
        data_inicio_situacao=date(2020, 1, 1),
        setor_atividade="Energia",
        tipo_mercado="Categoria A",
        categoria_registro="Categoria A",
        data_inicio_categoria=date(2020, 1, 1),
        situacao_emissor="ATIVO",
        data_inicio_situacao_emissor=date(2020, 1, 1),
        controle_acionario="PRIVADO",
        endereco={"municipio": "Sao Paulo"},
        responsavel={"nome_responsavel": "Benchmark"},
        auditor="Auditoria X",
        cnpj_auditor="10830108000165",
        tipo_emissor="aberta",
        fonte_identidade_principal="cad_cia_aberta",
        qualidade_identidade="alta",
        arquivo_origem="cad_cia_aberta.csv",
        ano_origem=None,
        linha_origem=2,
        hash_origem="benchmark",
        criado_em=agora,
        sincronizado_em=agora,
        alterado_em=agora,
    )


def _add_identifiers(session: Session, companhia: Companhia) -> None:
    session.add_all(
        [
            CompanhiaIdentificador(
                companhia_id=companhia.id,
                tipo="cnpj",
                valor="08773135000100",
                valor_normalizado="08773135000100",
                fonte="cad_cia_aberta",
                confianca="alta",
                ativo=True,
            ),
            CompanhiaIdentificador(
                companhia_id=companhia.id,
                tipo="codigo_cvm",
                valor="25224",
                valor_normalizado="25224",
                fonte="cad_cia_aberta",
                confianca="alta",
                ativo=True,
            ),
        ]
    )
    session.flush()


def _build_dfp_payload(rows: int) -> bytes:
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
                "EMPRESA BENCHMARK",
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


def _build_fre_payload(rows: int) -> bytes:
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
                "EMPRESA BENCHMARK",
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


def _print_summary(results: list[BenchmarkResult]) -> None:
    print(
        "| caso | linhas | chunk_stage | chunk_promote | tempo_stage_s | tempo_process_s | tempo_total_s | "
        "memoria_pico | statements | promovidas | quarentena |"
    )
    print("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for result in results:
        print(
            f"| {result.case_name} | {result.rows} | {result.stage_chunk_size} | {result.promote_chunk_size} | "
            f"{result.stage_seconds:.4f} | {result.process_seconds:.4f} | {result.total_seconds:.4f} | "
            f"{_format_bytes(result.peak_memory_bytes)} | {result.statement_count} | {result.promoted_rows} | "
            f"{result.quarantined_rows} |"
        )


def _format_bytes(value: int) -> str:
    size = float(value)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} TB"


def _run_dfp_case(
    session: Session,
    *,
    rows: int,
    stage_chunk_size: int,
    promote_chunk_size: int,
) -> tuple[int, int, float, float]:
    execucao = ExecucaoSincronizacao(
        tipo_fonte="dfp",
        ano=2025,
        arquivo="benchmark_dfp.zip",
        url="https://benchmark.local/dfp",
        status="em_execucao",
    )
    session.add(execucao)
    session.flush()
    run = create_run(
        session,
        tipo_fonte="dfp",
        ano=2025,
        execucao_sincronizacao_id=execucao.id,
        phase="stage",
    )
    session.flush()
    ingestion_file = register_file(
        session,
        ingestion_run=run,
        source_url="https://benchmark.local/dfp/member",
        source_filename="benchmark_dfp.zip",
        payload=b"benchmark",
        is_zip=True,
    )
    payload = _build_dfp_payload(rows)
    stage_started = perf_counter()
    member = stage_csv_payload_streaming(
        session,
        ingestion_run=run,
        ingestion_file=ingestion_file,
        payload=payload,
        member_name="dfp_cia_aberta_DRE_con_2025.csv",
        arquivo_origem="dfp_cia_aberta_DRE_con_2025.csv",
        ano_origem=2025,
        row_kind="dfp_demonstracao",
        chunk_size=stage_chunk_size,
    )
    stage_elapsed = perf_counter() - stage_started

    contadores = {"lidas": 0, "inseridos": 0, "atualizados": 0, "inalterados": 0, "rejeitados": 0}
    quality_counters: dict[str, Counter[str] | int] = {
        "reason_counts": Counter(),
        "resolver_methods": Counter(),
        "top_quarantine_files": Counter(),
        "provisional_company_count": 0,
    }
    process_started = perf_counter()
    _process_financeiro_member(
        session,
        execucao=execucao,
        run=run,
        member=member,
        reconcile_required=False,
        prefixo="dfp",
        tipo_formulario="DFP",
        ano=2025,
        promote_enabled=True,
        contadores=contadores,
        quality_counters=quality_counters,
        seen_by_row_kind={},
        header_map={},
        chunk_size=promote_chunk_size,
    )
    process_elapsed = perf_counter() - process_started
    promoted_rows = session.scalar(select(func.count()).select_from(DemonstracaoFinanceira)) or 0
    quarantined_rows = session.scalar(select(func.count()).where(QuarantineItem.ingestion_run_id == run.id)) or 0
    return promoted_rows, quarantined_rows, stage_elapsed, process_elapsed


def _run_fre_case(
    session: Session,
    *,
    rows: int,
    stage_chunk_size: int,
    promote_chunk_size: int,
) -> tuple[int, int, float, float]:
    execucao = ExecucaoSincronizacao(
        tipo_fonte="fre",
        ano=2025,
        arquivo="benchmark_fre.zip",
        url="https://benchmark.local/fre",
        status="em_execucao",
    )
    session.add(execucao)
    session.flush()
    run = create_run(
        session,
        tipo_fonte="fre",
        ano=2025,
        execucao_sincronizacao_id=execucao.id,
        phase="stage",
    )
    session.flush()
    ingestion_file = register_file(
        session,
        ingestion_run=run,
        source_url="https://benchmark.local/fre/member",
        source_filename="benchmark_fre.zip",
        payload=b"benchmark",
        is_zip=True,
    )
    payload = _build_fre_payload(rows)
    stage_started = perf_counter()
    member = stage_csv_payload_streaming(
        session,
        ingestion_run=run,
        ingestion_file=ingestion_file,
        payload=payload,
        member_name="fre_cia_aberta_posicao_acionaria_2025.csv",
        arquivo_origem="fre_cia_aberta_posicao_acionaria_2025.csv",
        ano_origem=2025,
        row_kind="fre_posicao_acionaria",
        chunk_size=stage_chunk_size,
    )
    stage_elapsed = perf_counter() - stage_started

    contadores = {"lidas": 0, "inseridos": 0, "atualizados": 0, "inalterados": 0, "rejeitados": 0}
    process_started = perf_counter()
    _process_fre_member(
        session,
        execucao=execucao,
        run=run,
        ano=2025,
        member=member,
        reconcile_required=False,
        promote_enabled=True,
        contadores=contadores,
        seen_by_row_kind={},
        header_map={},
        chunk_size=promote_chunk_size,
    )
    process_elapsed = perf_counter() - process_started
    promoted_rows = session.scalar(select(func.count()).select_from(FrePosicaoAcionaria)) or 0
    quarantined_rows = session.scalar(select(func.count()).where(QuarantineItem.ingestion_run_id == run.id)) or 0
    return promoted_rows, quarantined_rows, stage_elapsed, process_elapsed


def _run_case(
    session_factory: sessionmaker[Session],
    *,
    case_name: str,
    rows: int,
    stage_chunk_size: int,
    promote_chunk_size: int,
) -> BenchmarkResult:
    statement_count = 0

    def before_cursor_execute(
        conn: Any, cursor: Any, statement: str, parameters: Any, context: Any, executemany: bool
    ) -> None:
        nonlocal statement_count
        statement_count += 1

    engine = session_factory.kw["bind"]
    assert engine is not None
    assert hasattr(engine, "connect")
    connection = engine.connect()
    outer_transaction = connection.begin()
    local_session = session_factory(bind=connection)
    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    try:
        compania = _companhia()
        local_session.add(compania)
        local_session.flush()
        _add_identifiers(local_session, compania)

        tracemalloc.start()
        started = perf_counter()
        if case_name == "dfp_demonstracao":
            promoted_rows, quarantined_rows, stage_seconds, process_seconds = _run_dfp_case(
                local_session,
                rows=rows,
                stage_chunk_size=stage_chunk_size,
                promote_chunk_size=promote_chunk_size,
            )
        else:
            promoted_rows, quarantined_rows, stage_seconds, process_seconds = _run_fre_case(
                local_session,
                rows=rows,
                stage_chunk_size=stage_chunk_size,
                promote_chunk_size=promote_chunk_size,
            )
        total_seconds = perf_counter() - started
        _, peak_memory = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        return BenchmarkResult(
            case_name=case_name,
            rows=rows,
            stage_chunk_size=stage_chunk_size,
            promote_chunk_size=promote_chunk_size,
            stage_seconds=stage_seconds,
            process_seconds=process_seconds,
            total_seconds=total_seconds,
            peak_memory_bytes=peak_memory,
            statement_count=statement_count,
            promoted_rows=int(promoted_rows),
            quarantined_rows=int(quarantined_rows),
        )
    finally:
        local_session.close()
        outer_transaction.rollback()
        connection.close()
        event.remove(engine, "before_cursor_execute", before_cursor_execute)


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark ponta a ponta por member da ingestao.")
    parser.add_argument("--rows-dfp", type=int, default=50_000)
    parser.add_argument("--rows-fre", type=int, default=50_000)
    parser.add_argument("--stage-chunk-size", type=int, default=5_000)
    parser.add_argument("--promote-chunk-size", type=int, default=5_000)
    args = parser.parse_args()

    settings = get_settings()
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    results = [
        _run_case(
            session_factory,
            case_name="dfp_demonstracao",
            rows=args.rows_dfp,
            stage_chunk_size=args.stage_chunk_size,
            promote_chunk_size=args.promote_chunk_size,
        ),
        _run_case(
            session_factory,
            case_name="fre_posicao_acionaria",
            rows=args.rows_fre,
            stage_chunk_size=args.stage_chunk_size,
            promote_chunk_size=args.promote_chunk_size,
        ),
    ]
    _print_summary(results)


if __name__ == "__main__":
    main()
