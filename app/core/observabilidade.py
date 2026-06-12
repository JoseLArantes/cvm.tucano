import json
import logging
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from time import perf_counter
from typing import Any, cast
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

counter_factory: Any = None
histogram_factory: Any = None
make_asgi_app: Any = None

try:
    from prometheus_client import Counter as _counter_factory
    from prometheus_client import Histogram as _histogram_factory
    from prometheus_client import make_asgi_app as _make_asgi_app
except Exception:  # pragma: no cover - ambiente sem dependencia opcional
    pass
else:
    counter_factory = _counter_factory
    histogram_factory = _histogram_factory
    make_asgi_app = _make_asgi_app


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "nivel": record.levelname,
            "logger": record.name,
            "mensagem": record.getMessage(),
        }
        for campo in ("evento", "request_id", "metodo", "path", "status_code", "duracao_ms"):
            valor = getattr(record, campo, None)
            if valor is not None:
                payload[campo] = valor
        return json.dumps(payload, ensure_ascii=True, default=str)


def configurar_logging(log_level: str) -> None:
    logger = logging.getLogger("app.api")
    if logger.handlers:
        logger.setLevel(log_level.upper())
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger.setLevel(log_level.upper())
    logger.addHandler(handler)
    logger.propagate = False


_CONTADOR_REQUISICOES = (
    counter_factory(
        "cvm_api_requisicoes_total",
        "Total de requisicoes HTTP por metodo, rota e status.",
        ["metodo", "rota", "status_code"],
    )
    if counter_factory is not None
    else None
)
_LATENCIA_REQUISICOES = (
    histogram_factory(
        "cvm_api_requisicao_duracao_segundos",
        "Duracao das requisicoes HTTP em segundos.",
        ["metodo", "rota"],
    )
    if histogram_factory is not None
    else None
)


class ObservabilidadeMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: Callable[..., Any], *, habilitar_metricas: bool) -> None:
        super().__init__(app)
        self.logger = logging.getLogger("app.api")
        self.habilitar_metricas = habilitar_metricas

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("x-request-id", str(uuid4()))
        inicio = perf_counter()
        status_code = 500
        response = None
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            duracao = perf_counter() - inicio
            rota = request.scope.get("route")
            rota_normalizada = request.url.path if rota is None else getattr(rota, "path", request.url.path)
            self.logger.info(
                "request.finalizada",
                extra={
                    "evento": "http_request",
                    "request_id": request_id,
                    "metodo": request.method,
                    "path": rota_normalizada,
                    "status_code": status_code,
                    "duracao_ms": round(duracao * 1000, 3),
                },
            )
            if self.habilitar_metricas and _CONTADOR_REQUISICOES is not None and _LATENCIA_REQUISICOES is not None:
                _CONTADOR_REQUISICOES.labels(request.method, rota_normalizada, str(status_code)).inc()
                _LATENCIA_REQUISICOES.labels(request.method, rota_normalizada).observe(duracao)
            if response is not None:
                response.headers["x-request-id"] = request_id


def criar_app_metricas() -> object | None:
    if make_asgi_app is None:
        return None
    return cast(object, make_asgi_app())
