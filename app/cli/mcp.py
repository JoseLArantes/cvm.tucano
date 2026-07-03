import argparse
import json
import sys
from typing import Any

from app.mcp.adapters import healthcheck_adapter
from app.mcp.registry import READ_ONLY_TOOL_NAMES
from app.mcp.serialization import error_response
from app.mcp.settings import get_mcp_settings


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli.mcp",
        description="Servidor MCP analitico read-only do Tucano CVM.",
    )
    subparsers = parser.add_subparsers(dest="command")
    serve = subparsers.add_parser("serve", help="Inicia o servidor MCP via stdio.")
    serve.add_argument("--transport", choices=["stdio"], default="stdio", help="Transporte MCP habilitado neste corte.")
    subparsers.add_parser("smoke-test", help="Valida configuracao basica e healthcheck sem iniciar o loop MCP.")
    return parser


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    settings = get_mcp_settings()

    if args.command in (None, "serve"):
        try:
            from app.mcp.server import run_stdio

            run_stdio(settings)
            return 0
        except Exception as exc:
            _print_json(error_response("serve", exc))
            return 1

    if args.command == "smoke-test":
        try:
            payload = healthcheck_adapter(settings=settings)
            payload["listed_tools_count"] = len(READ_ONLY_TOOL_NAMES)
            _print_json(payload)
            return 0
        except Exception as exc:
            _print_json(error_response("smoke-test", exc))
            return 1

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())

