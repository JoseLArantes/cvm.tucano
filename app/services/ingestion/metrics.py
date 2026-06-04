from __future__ import annotations

from time import perf_counter
from typing import Any

try:
    from prometheus_client import Counter, Gauge, Histogram, REGISTRY
except Exception:  # pragma: no cover
    Counter = None  # type: ignore[assignment]
    Gauge = None  # type: ignore[assignment]
    Histogram = None  # type: ignore[assignment]
    REGISTRY = None  # type: ignore[assignment]


_METRICS: dict[str, Any] | None = None


def _get_or_create_metric(factory: Any, name: str, doc: str, labels: list[str]) -> Any:
    if factory is None or REGISTRY is None:
        return None
    existing = getattr(REGISTRY, "_names_to_collectors", {}).get(name)
    if existing is not None:
        return existing
    return factory(name, doc, labels)


def get_ingestion_metrics() -> dict[str, Any]:
    global _METRICS
    if _METRICS is not None:
        return _METRICS
    _METRICS = {
        "rows": _get_or_create_metric(
            Counter,
            "cvm_ingestion_v2_rows_total",
            "Total de linhas por source, status e reason.",
            ["source", "status", "reason"],
        ),
        "run_duration": _get_or_create_metric(
            Histogram,
            "cvm_ingestion_v2_run_duration_seconds",
            "Duracao de runs por source e phase.",
            ["source", "phase"],
        ),
        "retries": _get_or_create_metric(
            Counter,
            "cvm_ingestion_v2_retries_total",
            "Tentativas de retry por operacao e erro.",
            ["operation", "error_type"],
        ),
        "quarantine": _get_or_create_metric(
            Gauge,
            "cvm_ingestion_v2_quarantine_total",
            "Total atual em quarentena por reason.",
            ["reason"],
        ),
        "resolution": _get_or_create_metric(
            Counter,
            "cvm_ingestion_v2_resolution_total",
            "Resolucao de identidade por metodo e confianca.",
            ["method", "confidence"],
        ),
    }
    return _METRICS


def observe_row(source: str, status: str, reason: str | None) -> None:
    metric = get_ingestion_metrics()["rows"]
    if metric is not None:
        metric.labels(source, status, reason or "none").inc()


def observe_retry(operation: str, error_type: str) -> None:
    metric = get_ingestion_metrics()["retries"]
    if metric is not None:
        metric.labels(operation, error_type).inc()


def observe_resolution(method: str | None, confidence: str | None) -> None:
    metric = get_ingestion_metrics()["resolution"]
    if metric is not None:
        metric.labels(method or "none", confidence or "none").inc()


def set_quarantine_total(reason: str, total: int) -> None:
    metric = get_ingestion_metrics()["quarantine"]
    if metric is not None:
        metric.labels(reason).set(total)


class RunTimer:
    def __init__(self, source: str, phase: str) -> None:
        self.source = source
        self.phase = phase
        self.started_at = perf_counter()

    def observe(self) -> None:
        metric = get_ingestion_metrics()["run_duration"]
        if metric is not None:
            metric.labels(self.source, self.phase).observe(perf_counter() - self.started_at)
