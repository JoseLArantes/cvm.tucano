#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.ingestion.audit import build_audit_report, render_console_summary  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit current CVM ingestion consistency assumptions.")
    parser.add_argument("--year", type=int, default=2021, help="Document package year. Default: 2021.")
    parser.add_argument(
        "--sources",
        nargs="+",
        choices=("dfp", "itr", "fre", "all"),
        default=("all",),
        help="Document sources to audit. Default: all.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=None,
        help="Optional JSON output path. Example: tmp/ingestion_audit_20260603.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    document_sources = ("dfp", "itr", "fre") if "all" in args.sources else tuple(args.sources)
    report = build_audit_report(year=args.year, document_sources=document_sources)
    report["generated_at"] = datetime.now(UTC).isoformat()
    print(render_console_summary(report))

    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
