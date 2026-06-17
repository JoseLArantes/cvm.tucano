import uuid
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.ingestion import IngestionRow, QuarantineItem
from app.models.sincronizacao import ExecucaoSincronizacao, RegistroQuarentena
from app.services.ingestion.staging import create_run, register_file, safe_promote_chunk, stage_csv_payload


def _session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    local_session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return local_session()


def test_safe_promote_chunk_fallback_behavior() -> None:
    session = _session()
    try:
        # 1. Setup execution run, ingestion file and rows
        execucao = ExecucaoSincronizacao(
            tipo_fonte="fre",
            ano=2026,
            arquivo="fre_2026.zip",
            url="https://example.test",
            status="em_execucao",
        )
        session.add(execucao)
        session.flush()

        run = create_run(session, tipo_fonte="fre", ano=2026, execucao_sincronizacao_id=execucao.id)
        ingestion_file = register_file(
            session,
            ingestion_run=run,
            source_url="https://example.test/fre_2026.zip",
            source_filename="fre_2026.zip",
            payload=b"fake",
            is_zip=True,
        )

        member, rows = stage_csv_payload(
            session,
            ingestion_run=run,
            ingestion_file=ingestion_file,
            payload=b"col1;col2\nrow1;data1\nrow2;data2\n",
            member_name="fre_test_member.csv",
            arquivo_origem="fre_test_member.csv",
            ano_origem=2026,
            row_kind="fre_test_kind",
        )
        session.commit()

        # We have 2 rows.
        assert len(rows) == 2

        # 2. Define a promote function that fails on chunk, but on row-by-row:
        # - row 1 (index 0) succeeds.
        # - row 2 (index 1) fails with NumericValueOutOfRange/Numeric field overflow.
        calls: list[int] = []

        def dummy_promote_func(
            db: Session,
            *,
            linhas_promovidas: list[tuple[IngestionRow, dict[str, Any]]],
            execucao_id: Any,
            contadores: dict[str, int],
            **kwargs: Any,
        ) -> None:
            calls.append(len(linhas_promovidas))
            if len(linhas_promovidas) > 1:
                # Bulk insert fails
                raise ValueError("psycopg.errors.NumericValueOutOfRange: numeric field overflow")
            else:
                # Single row insert
                row, data = linhas_promovidas[0]
                if data["col1"] == "row2":
                    raise ValueError("NumericValueOutOfRange: numeric field overflow on row2")
                else:
                    contadores["inseridos"] += 1

        # 3. Call safe_promote_chunk
        contadores = {"inseridos": 0, "atualizados": 0, "inalterados": 0, "rejeitados": 0}
        linhas_promovidas = [
            (rows[0], {"col1": "row1", "col2": "data1"}),
            (rows[1], {"col1": "row2", "col2": "data2"}),
        ]

        def dummy_registrar_quarentena(
            db: Session,
            execucao_id: uuid.UUID,
            arquivo_origem: str,
            ano_origem: int | None,
            linha_origem: int | None,
            motivo: str,
            dados_originais: dict[str, Any] | None,
        ) -> None:
            reg = RegistroQuarentena(
                execucao_sincronizacao_id=execucao_id,
                arquivo_origem=arquivo_origem,
                ano_origem=ano_origem,
                linha_origem=linha_origem,
                motivo=motivo,
                dados_originais=dados_originais,
            )
            db.add(reg)

        safe_promote_chunk(
            session,
            promote_func=dummy_promote_func,
            linhas_promovidas=linhas_promovidas,
            execucao_id=execucao.id,
            contadores=contadores,
            registrar_quarentena_fn=dummy_registrar_quarentena,
        )
        session.commit()

        # 4. Assertions
        # - calls should be: 1 chunk call of size 2, then 2 single-row calls of size 1.
        assert calls == [2, 1, 1]

        # - contadores should show 1 inserido, 1 rejeitado
        assert contadores["inseridos"] == 1
        assert contadores["rejeitados"] == 1

        # - row 2 (index 1) should have validation_status as 'invalid'
        session.refresh(rows[0])
        session.refresh(rows[1])
        assert rows[0].validation_status in {None, "pending", "valid"}
        assert rows[1].validation_status == "invalid"
        assert rows[1].validation_reason_code == "normalizacao_invalida"

        # - quarantine item should have been created for row 2
        quarantines = session.query(QuarantineItem).all()
        assert len(quarantines) == 1
        assert quarantines[0].ingestion_row_id == rows[1].id
        assert quarantines[0].diagnostico is not None
        assert "NumericValueOutOfRange" in quarantines[0].diagnostico["details"]["erro"]

        # - legacy RegistroQuarentena should have been created (both by create_quarantine_item and by registrar_quarentena_fn)
        legacy_quarantines = session.query(RegistroQuarentena).all()
        assert len(legacy_quarantines) == 2
        assert legacy_quarantines[0].linha_origem == rows[1].linha_origem
        assert "NumericValueOutOfRange" in legacy_quarantines[0].motivo or "NumericValueOutOfRange" in legacy_quarantines[1].motivo

    finally:
        session.close()
