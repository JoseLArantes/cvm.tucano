import uuid
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.companhia import Companhia
from app.services.ingestion.duckdb_financeiro import (
    can_use_duckdb_for_member,
    process_demonstracao_member_duckdb,
)


def test_can_use_duckdb_for_member() -> None:
    assert can_use_duckdb_for_member("dfp_cia_aberta_BPA_con_2025.csv", "dfp_demonstracao") is True
    assert can_use_duckdb_for_member("itr_cia_aberta_DRE_ind_2025.csv", "itr_demonstracao") is True
    assert can_use_duckdb_for_member("dfp_cia_aberta_2025.csv", "dfp_documento") is False
    assert can_use_duckdb_for_member("dfp_cia_aberta_parecer_2025.csv", "dfp_parecer") is False


def test_process_demonstracao_member_duckdb_normalizes_and_deduplicates(
    db_session: Session,
    tmp_path: Path,
) -> None:
    company = Companhia(
        id=uuid.uuid4(),
        cnpj_companhia="08773135000100",
        codigo_cvm=25224,
        denominacao_social="Empresa Teste",
        denominacao_comercial="Empresa Teste",
        situacao_registro="ATIVA",
        criado_em=datetime.now(UTC),
        sincronizado_em=datetime.now(UTC),
        alterado_em=datetime.now(UTC),
        hash_origem="hash1",
        arquivo_origem="cad.csv",
        linha_origem=1,
    )
    db_session.add(company)
    db_session.flush()

    csv_path = tmp_path / "dfp_cia_aberta_BPA_con_2025.csv"
    csv_path.write_text(
        "\n".join(
            [
                "CNPJ_CIA;DT_REFER;VERSAO;DENOM_CIA;CD_CVM;GRUPO_DFP;MOEDA;ESCALA_MOEDA;ORDEM_EXERC;DT_INI_EXERC;DT_FIM_EXERC;CD_CONTA;DS_CONTA;VL_CONTA;ST_CONTA_FIXA",
                "08.773.135/0001-00;2025-12-31;1;EMPRESA TESTE;25224;DF Consolidado;REAL;MIL;ULTIMO;2025-01-01;2025-12-31;1;Ativo Total;1000,50;S",
                # Duplicate with identical natural key but second occurrence:
                "08.773.135/0001-00;2025-12-31;1;EMPRESA TESTE;25224;DF Consolidado;REAL;MIL;ULTIMO;2025-01-01;2025-12-31;1;Ativo Total;1000,50;S",
                # Different account:
                "08.773.135/0001-00;2025-12-31;1;EMPRESA TESTE;25224;DF Consolidado;REAL;MIL;ULTIMO;2025-01-01;2025-12-31;1.01;Ativo Circulante;500,25;S",
            ]
        ),
        encoding="latin1",
    )

    contadores = {"lidas": 0, "inseridos": 0, "atualizados": 0, "inalterados": 0, "rejeitados": 0}
    quality_counters: dict[str, Counter[str] | int] = {"resolver_methods": Counter()}

    result = process_demonstracao_member_duckdb(
        db_session,
        file_path=str(csv_path),
        member_name=csv_path.name,
        tipo_formulario="DFP",
        prefixo="dfp",
        ano=2025,
        encoding="latin1",
        delimiter=";",
        run_id=uuid.uuid4(),
        member_id=uuid.uuid4(),
        header_map={},
        contadores=contadores,
        quality_counters=quality_counters,
    )

    assert result is not None
    total_raw_rows, artifacts = result
    assert total_raw_rows == 3
    assert contadores["lidas"] == 3
    assert contadores["inalterados"] == 1  # 1 duplicate filtered out
    assert "dfp_demonstracao" in artifacts
    artifact = artifacts["dfp_demonstracao"]
    assert Path(artifact["uri"]).exists()
