from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any

MAX_STATEMENT_PARAMETERS = 60000
MAX_LOOKUP_STATEMENT_PARAMETERS = 6000


def max_rows_for_parameter_budget(*, parameter_width: int, budget: int = MAX_STATEMENT_PARAMETERS) -> int:
    width = max(1, parameter_width)
    return max(1, budget // width)


def iter_parameter_batches(
    rows: Sequence[Any],
    *,
    parameter_width: int,
    budget: int = MAX_STATEMENT_PARAMETERS,
) -> Iterator[Sequence[Any]]:
    batch_size = max_rows_for_parameter_budget(parameter_width=parameter_width, budget=budget)
    for index in range(0, len(rows), batch_size):
        yield rows[index : index + batch_size]


def iter_lookup_batches(
    rows: Sequence[Any],
    *,
    parameter_width: int,
    budget: int = MAX_LOOKUP_STATEMENT_PARAMETERS,
) -> Iterator[Sequence[Any]]:
    yield from iter_parameter_batches(rows, parameter_width=parameter_width, budget=budget)


def mapping_parameter_width(rows: Sequence[dict[str, Any]]) -> int:
    if not rows:
        return 1
    return max(len(row) for row in rows)
