from __future__ import annotations

from time import perf_counter
from typing import Any

counter_factory: Any = None
gauge_factory: Any = None
histogram_factory: Any = None
prom_registry: Any = None

try:
    from prometheus_client import REGISTRY as _prom_registry
    from prometheus_client import Counter as _counter_factory
    from prometheus_client import Gauge as _gauge_factory
    from prometheus_client import Histogram as _histogram_factory
except Exception:  # pragma: no cover
    pass
else:
    counter_factory = _counter_factory
    gauge_factory = _gauge_factory
    histogram_factory = _histogram_factory
    prom_registry = _prom_registry


_METRICS: dict[str, Any] | None = None


def _get_or_create_metric(factory: Any, name: str, doc: str, labels: list[str]) -> Any:
    if factory is None or prom_registry is None:
        return None
    existing = getattr(prom_registry, "_names_to_collectors", {}).get(name)
    if existing is not None:
        return existing
    return factory(name, doc, labels)


def get_ingestion_metrics() -> dict[str, Any]:
    global _METRICS
    if _METRICS is not None:
        return _METRICS
    _METRICS = {
        "rows": _get_or_create_metric(
            counter_factory,
            "cvm_ingestion_rows_total",
            "Total de linhas por source, status e reason.",
            ["source", "status", "reason"],
        ),
        "run_duration": _get_or_create_metric(
            histogram_factory,
            "cvm_ingestion_run_duration_seconds",
            "Duracao de runs por source e phase.",
            ["source", "phase"],
        ),
        "retries": _get_or_create_metric(
            counter_factory,
            "cvm_ingestion_retries_total",
            "Tentativas de retry por operacao e erro.",
            ["operation", "error_type"],
        ),
        "quarantine": _get_or_create_metric(
            gauge_factory,
            "cvm_ingestion_quarantine_total",
            "Total atual em quarentena por reason.",
            ["reason"],
        ),
        "resolution": _get_or_create_metric(
            counter_factory,
            "cvm_ingestion_resolution_total",
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
