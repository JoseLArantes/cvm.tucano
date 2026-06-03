from fastapi import APIRouter

router = APIRouter()


@router.get(
    "/health",
    summary="Healthcheck",
    description="Verifica disponibilidade básica do serviço.",
    operation_id="healthcheckApi",
)
def healthcheck() -> dict[str, str]:
    """Retorna estado básico de disponibilidade da aplicação."""
    return {"status": "ok"}
