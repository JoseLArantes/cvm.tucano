from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.ingestion.cadastro import sincronizar_cadastro_companhias_v2
from app.services.ingestion.financeiro import sincronizar_dfp_v2, sincronizar_itr_v2
from app.services.ingestion.fre import sincronizar_fre_v2
from app.services.ingestion.summary import render_parity_report_markdown
from app.services.sincronizacao_financeiro import sincronizar_dfp, sincronizar_itr
from app.services.sincronizacao_fre import sincronizar_fre


@contextmanager
def override_ingestion_v2_promote_enabled(valor: bool) -> Iterator[None]:
    settings = get_settings()
    anterior = settings.ingestion_v2_promote_enabled
    settings.ingestion_v2_promote_enabled = valor
    try:
        yield
    finally:
        settings.ingestion_v2_promote_enabled = anterior


def run_one_year_backfill(
    db: Session,
    *,
    ano: int,
    task_id: str | None = None,
) -> dict[str, Any]:
    cadastro = sincronizar_cadastro_companhias_v2(db, task_id=task_id)
    dfp = sincronizar_dfp_v2(db, ano, task_id=task_id)
    itr = sincronizar_itr_v2(db, ano, task_id=task_id)
    fre = sincronizar_fre_v2(db, ano, task_id=task_id)
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
    with override_ingestion_v2_promote_enabled(False):
        v2_dfp = sincronizar_dfp_v2(db, ano)
        v2_itr = sincronizar_itr_v2(db, ano)
        v2_fre = sincronizar_fre_v2(db, ano)
    v1_dfp = sincronizar_dfp(db, ano)
    v1_itr = sincronizar_itr(db, ano)
    v1_fre = sincronizar_fre(db, ano)
    linhas = [
        render_parity_report_markdown(v1=v1_dfp, v2=v2_dfp),
        render_parity_report_markdown(v1=v1_itr, v2=v2_itr),
        render_parity_report_markdown(v1=v1_fre, v2=v2_fre),
    ]
    return "\n".join(linhas)
