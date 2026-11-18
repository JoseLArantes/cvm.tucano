import uuid
import zipfile
from decimal import Decimal
from io import BytesIO
from pathlib import Path

import httpx
import pytest
from celery.schedules import crontab
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.fii import FiiInformeAtivoPassivo, FiiInformeComplemento, FiiInformeGeral
from app.models.ingestion_queue import IngestionQueueItem
from app.models.sincronizacao import ExecucaoSincronizacao, HistoricoAlteracaoCampo
from app.services.ingestion import fii as fii_service
from app.services.ingestion.fii import _parse_zip, _upsert_rows, normalizar_fii_row


def _zip(
    year: int,
    *,
    two_types: bool = False,
    financial_values: tuple[str, ...] = ("100.25", "100.25"),
    cnpj: str = "12.345.678/0001-90",
    reference: str | None = None,
) -> bytes:
    reference = reference or f"{year}-01-01"
    cnpj_header = "CNPJ_Fundo_Classe" if year >= 2021 else "CNPJ_Fundo"
    general_header = (
        "Tipo_Fundo_Classe;CNPJ_Fundo_Classe;Data_Referencia;Versao;Nome_Fundo_Classe;Quantidade_Cotas_Emitidas"
        if year >= 2021
        else "CNPJ_Fundo;Data_Referencia;Versao;Nome_Fundo;Quantidade_Cotas_Emitidas"
    )
    general_rows = [
        (
            f"Fundo;{cnpj};{reference};1;FII Exemplo;12.5"
            if year >= 2021
            else f"{cnpj};{reference};1;FII Exemplo;12.5"
        ),
    ]
    if two_types:
        general_rows.append(f"Classe;{cnpj};{reference};1;Classe Exemplo;12.5")
    sections = {
        "geral": (general_header, "\n".join(general_rows)),
        "complemento": (
            f"{cnpj_header};Data_Referencia;Versao;Patrimonio_Liquido;Percentual_Dividend_Yield_Mes",
            "\n".join(
                f"{cnpj};{reference};1;{value};-1E-20"
                for value in financial_values
            ),
        ),
        "ativo_passivo": (
            f"{cnpj_header};Data_Referencia;Versao;Total_Investido;Total_Passivo",
            "\n".join(
                f"{cnpj};{reference};1;200;75"
                for _ in range(2 if two_types else 1)
            ),
        ),
    }
    archive = BytesIO()
    with zipfile.ZipFile(archive, "w") as output:
        for section, (header, rows) in sections.items():
            output.writestr(f"inf_mensal_fii_{section}_{year}.csv", f"{header}\n{rows}\n")
    return archive.getvalue()


def _execution(db: Session, *, year: int = 2026) -> uuid.UUID:
    execution = ExecucaoSincronizacao(
        tipo_execucao="arquivo_zip", tipo_fonte="fii", ano=year, id_tarefa=str(uuid.uuid4()),
        arquivo=f"inf_mensal_fii_{year}.zip", url="https://example.test/fii.zip", status="em_execucao",
    )
    db.add(execution)
    db.flush()
    return execution.id


def test_fii_parser_normalizes_decimals_and_legacy_funds(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    row_kind, normalized_row = normalizar_fii_row(
        arquivo_origem="inf_mensal_fii_geral_2018.csv",
        ano_origem=2018,
        linha_origem=2,
        linha={"CNPJ_Fundo": "12.345.678/0001-90", "Data_Referencia": "2018-01-01", "Versao": "1"},
    )
    assert row_kind == "fii_geral"
    assert normalized_row["tipo"] == "fundo"
    members, _counts = _parse_zip(_zip(2018), 2018)
    general = members["geral"][1][0]
    complemento = members["complemento"][1][0]
    assert general["tipo"] == "fundo"
    assert general["values"]["Quantidade_Cotas_Emitidas"] == Decimal("12.5")
    assert complemento["values"]["Percentual_Dividend_Yield_Mes"] == Decimal("-1E-20")
    assert "Tipo_Fundo_Classe" not in complemento["data"]
    assert members["ativo_passivo"][1][0]["data"]["CRI_CRA"] is None
    members_cached, _counts_cached = _parse_zip(_zip(2018), 2018)
    assert members_cached["geral"][1] == members["geral"][1]


@pytest.mark.parametrize("year", range(2016, 2027))
def test_fii_parser_accepts_official_historical_layout_families(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    year: int,
) -> None:
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / str(year)))
    members, _counts = _parse_zip(_zip(year), year)
    assert set(members) == {"geral", "complemento", "ativo_passivo"}
    assert members["geral"][1][0]["tipo"] == "fundo"
    assert members["geral"][1][0]["cnpj"] == "12345678000190"
    assert members["complemento"][1][0]["values"]["Patrimonio_Liquido"] == Decimal("100.25")


def test_fii_financial_variants_resolve_identical_rows_and_keep_conflicts(db_session: Session) -> None:
    execution_id = _execution(db_session, year=2026)
    zip_members, _counts = _parse_zip(
        _zip(2026, two_types=True, cnpj="56.978.773/0001-00", reference="2026-10-01"), 2026
    )
    _upsert_rows(db_session, secao="geral", rows=zip_members["geral"][1], run_id=uuid.uuid4(), execution_id=execution_id, ano=2026)
    _upsert_rows(db_session, secao="complemento", rows=zip_members["complemento"][1], run_id=uuid.uuid4(), execution_id=execution_id, ano=2026)
    _upsert_rows(db_session, secao="ativo_passivo", rows=zip_members["ativo_passivo"][1], run_id=uuid.uuid4(), execution_id=execution_id, ano=2026)
    db_session.commit()

    complementos = db_session.scalars(select(FiiInformeComplemento).order_by(FiiInformeComplemento.tipo)).all()
    assert [item.tipo for item in complementos] == ["classe", "fundo"]
    assert all(item.status_atribuicao == "disponivel" for item in complementos)

    execution_2025 = _execution(db_session, year=2025)
    changed_members, _counts = _parse_zip(
        _zip(2025, two_types=True, financial_values=("100.25", "100.50"),
             cnpj="15.447.110/0001-73", reference="2025-10-01"), 2025
    )
    _upsert_rows(db_session, secao="geral", rows=changed_members["geral"][1], run_id=uuid.uuid4(), execution_id=execution_2025, ano=2025)
    _upsert_rows(db_session, secao="complemento", rows=changed_members["complemento"][1], run_id=uuid.uuid4(), execution_id=execution_2025, ano=2025)
    _upsert_rows(db_session, secao="ativo_passivo", rows=changed_members["ativo_passivo"][1], run_id=uuid.uuid4(), execution_id=execution_2025, ano=2025)
    db_session.commit()
    ambiguous = db_session.scalars(select(FiiInformeComplemento).where(FiiInformeComplemento.status_atribuicao == "ambiguo")).all()
    assert len(ambiguous) == 2
    assert {item.tipo for item in ambiguous} == {None}
    assert db_session.scalar(select(FiiInformeGeral).where(FiiInformeGeral.tipo == "fundo")) is not None
    assert db_session.scalar(select(FiiInformeAtivoPassivo).where(FiiInformeAtivoPassivo.status_atribuicao == "disponivel")) is not None


def test_fii_general_upsert_tracks_cell_changes_removals_and_reappearances(db_session: Session) -> None:
    first_execution = _execution(db_session)
    rows = _parse_zip(_zip(2026), 2026)[0]["geral"][1]
    first = _upsert_rows(db_session, secao="geral", rows=rows, run_id=uuid.uuid4(), execution_id=first_execution, ano=2026)
    db_session.commit()
    assert first["inseridos"] == 1

    second_execution = _execution(db_session)
    unchanged = _upsert_rows(db_session, secao="geral", rows=rows, run_id=uuid.uuid4(), execution_id=second_execution, ano=2026)
    assert unchanged["inalterados"] == 1
    assert db_session.scalar(select(func.count()).select_from(HistoricoAlteracaoCampo)) == 0

    changed_rows = _parse_zip(_zip(2026), 2026)[0]["geral"][1]
    changed_rows[0]["data"]["Nome_Fundo_Classe"] = "Nome corrigido"
    changed_rows[0]["values"]["Nome_Fundo_Classe"] = "Nome corrigido"
    third_execution = _execution(db_session)
    changed = _upsert_rows(db_session, secao="geral", rows=changed_rows, run_id=uuid.uuid4(), execution_id=third_execution, ano=2026)
    assert changed["atualizados"] == 1
    assert db_session.scalar(select(FiiInformeGeral).where(FiiInformeGeral.nome == "Nome corrigido")) is not None
    history = db_session.scalars(select(HistoricoAlteracaoCampo)).all()
    assert [(item.campo, item.valor_anterior, item.valor_novo) for item in history] == [
        ("Nome_Fundo_Classe", "FII Exemplo", "Nome corrigido")
    ]

    fourth_execution = _execution(db_session)
    withdrawn = _upsert_rows(db_session, secao="geral", rows=[], run_id=uuid.uuid4(), execution_id=fourth_execution, ano=2026)
    assert withdrawn["retirados"] == 1
    fifth_execution = _execution(db_session)
    returned = _upsert_rows(db_session, secao="geral", rows=changed_rows, run_id=uuid.uuid4(), execution_id=fifth_execution, ano=2026)
    assert returned["reaparecidos"] == 1


def test_fii_weekly_scheduler_discovers_years_prioritizes_recent_and_deduplicates(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
) -> None:
    class FakeResponse:
        text = " ".join(f'href="inf_mensal_fii_{year}.zip"' for year in range(2016, 2027))

        @staticmethod
        def raise_for_status() -> None:
            return None

    requested: list[str] = []

    def fake_get(url: str, *, timeout: int) -> FakeResponse:
        requested.append(url)
        return FakeResponse()

    monkeypatch.setattr(fii_service, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(httpx, "get", fake_get)

    first = fii_service.agendar_ingestao_semanal_fii()
    assert first["anos_enfileirados"] == list(range(2026, 2015, -1))
    assert requested[0].endswith("/FII/DOC/INF_MENSAL/DADOS/")
    queued = db_session.scalars(select(IngestionQueueItem).order_by(IngestionQueueItem.sequence)).all()
    assert [item.task_args for item in queued] == [[year] for year in range(2026, 2015, -1)]
    queued_count = db_session.scalar(select(func.count()).select_from(IngestionQueueItem))

    second = fii_service.agendar_ingestao_semanal_fii()
    assert second["status"] == "sem_pendencias"
    assert db_session.scalar(select(func.count()).select_from(IngestionQueueItem)) == queued_count


def test_fii_beat_schedule_uses_monday_0830_when_automatic_ingestion_is_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.worker import celery_app as celery_module

    monkeypatch.setattr(
        celery_module,
        "settings",
        celery_module.settings.model_copy(update={"auto_trigger_updates": True}),
    )
    schedule = celery_module.construir_beat_schedule()
    assert celery_module.celery_app.conf.timezone == "America/Sao_Paulo"
    assert schedule["sincronizar-fii-semanal"]["schedule"] == crontab(
        day_of_week="monday", hour=8, minute=30
    )
