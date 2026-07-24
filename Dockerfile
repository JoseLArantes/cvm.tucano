FROM python:3.12-slim AS wheel-builder

WORKDIR /build

COPY pyproject.toml .
COPY app ./app

RUN python -m pip install --no-cache-dir --upgrade pip && \
    python -m pip wheel --no-cache-dir --wheel-dir /wheels .


FROM wheel-builder AS development-wheel-builder

RUN python -m pip wheel --no-cache-dir --wheel-dir /development-wheels ".[dev]"


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN --mount=type=bind,from=wheel-builder,source=/wheels,target=/wheels \
    python -m pip install --no-cache-dir --no-compile --no-index --find-links=/wheels tucano-cvm

COPY alembic ./alembic
COPY alembic.ini .

EXPOSE 8007

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8007"]


FROM runtime AS development

RUN --mount=type=bind,from=development-wheel-builder,source=/development-wheels,target=/wheels \
    python -m pip install --no-cache-dir --no-index --find-links=/wheels "tucano-cvm[dev]"
