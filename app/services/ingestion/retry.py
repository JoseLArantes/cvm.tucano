from __future__ import annotations

from dataclasses import dataclass


class RetryableIngestionError(Exception):
    pass


@dataclass(slots=True)
class RetryableHttpStatus(RetryableIngestionError):
    status_code: int
    url: str

    def __str__(self) -> str:
        return f"retryable_http_status:{self.status_code}:{self.url}"


class DependencyNotReady(RetryableIngestionError):
    pass


class TerminalIngestionError(Exception):
    pass


def is_retryable_http_status(status_code: int) -> bool:
    return status_code in {408, 429} or 500 <= status_code <= 599


def classify_terminal_http_status(status_code: int) -> bool:
    return status_code == 404 or 400 <= status_code <= 499 and status_code not in {408, 429}
