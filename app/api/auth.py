from secrets import compare_digest
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings

_bearer_scheme = HTTPBearer(auto_error=False)


def obter_token_api() -> str:
    return get_settings().api_token


def autenticar_login(username: str, password: str) -> bool:
    settings = get_settings()
    return compare_digest(username, settings.api_username) and compare_digest(password, settings.api_password)


def validar_token_api(
    credenciais: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)] = None,
) -> None:
    esperado = f"Bearer {obter_token_api()}"
    recebido = None if credenciais is None else f"{credenciais.scheme} {credenciais.credentials}"
    if recebido != esperado:
        raise HTTPException(status_code=401, detail="Token de acesso invalido.")
