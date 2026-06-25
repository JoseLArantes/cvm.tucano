from __future__ import annotations

import argparse
import sys
from typing import Literal, cast

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.companhia import Companhia
from app.services.analise import CALCULATION_VERSION, materializar_analise_companhia


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Canonical analytical facts backfill CLI")
    parser.add_argument("--codigo-cvm", type=int, action="append", dest="codigos_cvm", help="Filter by one or more CVM codes.")
    parser.add_argument(
        "--escopo",
        choices=("consolidated", "individual", "all"),
        default="all",
        help="Analytical scope to materialize.",
    )
    parser.add_argument(
        "--calculation-version",
        default=CALCULATION_VERSION,
        help="Expected analytical calculation version. Mismatches abort the run.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Limit number of companies processed.")
    parser.add_argument(
        "--incluir-canceladas",
        action="store_true",
        help="Permite materializar companhias com situacao_registro=CANCELADA em execucoes pontuais.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.calculation_version != CALCULATION_VERSION:
        print(
            f"Unsupported calculation version: {args.calculation_version}. Current version is {CALCULATION_VERSION}.",
            file=sys.stderr,
        )
        return 2

    db = SessionLocal()
    try:
        stmt = select(Companhia).order_by(Companhia.codigo_cvm)
        if args.codigos_cvm:
            stmt = stmt.where(Companhia.codigo_cvm.in_(args.codigos_cvm))
        elif not args.incluir_canceladas:
            stmt = stmt.where((Companhia.situacao_registro.is_(None)) | (Companhia.situacao_registro != "CANCELADA"))
        if args.limit is not None:
            stmt = stmt.limit(args.limit)
        companhias = db.scalars(stmt).all()
        scopes: tuple[Literal["consolidated", "individual"], ...]
        if args.escopo == "all":
            scopes = ("consolidated", "individual")
        else:
            scopes = (cast(Literal["consolidated", "individual"], args.escopo),)

        processadas = 0
        falhas = 0
        revisoes = 0

        for companhia in companhias:
            for scope in scopes:
                try:
                    execucao = materializar_analise_companhia(
                        db,
                        companhia,
                        scope=scope,
                        source="backfill",
                        incluir_canceladas=args.incluir_canceladas,
                    )
                    processadas += 1
                    revisoes += int((execucao.summary or {}).get("fact_revisions", 0))
                    print(
                        f"{companhia.codigo_cvm} {scope} status={execucao.status} "
                        f"coverage_complete={execucao.coverage_complete} summary={execucao.summary}"
                    )
                except Exception as exc:
                    falhas += 1
                    db.rollback()
                    print(f"{companhia.codigo_cvm} {scope} status=failed error={exc}", file=sys.stderr)

        print(
            f"processed={processadas} failed={falhas} fact_revisions={revisoes} "
            f"calculation_version={CALCULATION_VERSION}"
        )
        return 1 if falhas else 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
