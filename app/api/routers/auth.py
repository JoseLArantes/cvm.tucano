from typing import Any

from fastapi import APIRouter, HTTPException

from app.api.auth import autenticar_login, obter_token_api
from app.schemas.auth import LoginRequisicao, LoginResposta

router = APIRouter(prefix="/auth")

_RESPOSTAS_LOGIN: dict[int | str, dict[str, Any]] = {
    401: {
        "description": "Credenciais invalidas.",
        "content": {"application/json": {"example": {"detail": "Usuario ou senha invalidos."}}},
    }
}


@router.post(
    "/login",
    response_model=LoginResposta,
    summary="Realizar Login",
    description="Valida usuario e senha configurados e retorna o token bearer da API.",
    responses=_RESPOSTAS_LOGIN,
    operation_id="realizarLoginAuth",
)
def realizar_login(payload: LoginRequisicao) -> LoginResposta:
    if not autenticar_login(payload.username, payload.password):
        raise HTTPException(status_code=401, detail="Usuario ou senha invalidos.")
    return LoginResposta(access_token=obter_token_api(), token_type="bearer")
