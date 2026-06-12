from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.ingestion.cadastro import sincronizar_cadastro_companhias
from app.services.ingestion.financeiro import sincronizar_dfp, sincronizar_itr
from app.services.ingestion.fre import sincronizar_fre


@contextmanager
def override_ingestion_promote_enabled(valor: bool) -> Iterator[None]:
    settings = get_settings()
    anterior = settings.ingestion_promote_enabled
    settings.ingestion_promote_enabled = valor
    try:
        yield
    finally:
        settings.ingestion_promote_enabled = anterior


def run_one_year_backfill(
    db: Session,
    *,
    ano: int,
    task_id: str | None = None,
) -> dict[str, Any]:
    cadastro = sincronizar_cadastro_companhias(db, task_id=task_id)
    dfp = sincronizar_dfp(db, ano, task_id=task_id)
    itr = sincronizar_itr(db, ano, task_id=task_id)
    fre = sincronizar_fre(db, ano, task_id=task_id)
    return {"cadastro": cadastro, "dfp": dfp, "itr": itr, "fre": fre}


def run_backfill_years(
    db: Session,
    *,
    anos: list[int],
    task_id: str | None = None,
) -> dict[str, Any]:
    resultados: dict[int, dict[str, Any]] = {}
    for ano in sorted(anos):
        resultados[ano] = run_one_year_backfill(db, ano=ano, task_id=task_id)
    return {"anos": resultados}


def build_dark_launch_parity_report(
    db: Session,
    *,
    ano: int,
) -> str:
    raise RuntimeError("relatorio_paridade_legado_removido")
