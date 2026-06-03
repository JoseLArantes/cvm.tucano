from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.auth import autenticar_usuario, gerar_token_usuario, obter_usuario_atual
from app.api.deps import DbSession
from app.models.usuario import Usuario
from app.schemas.auth import LoginRequisicao, LoginResposta
from app.schemas.usuario import UsuarioResposta

router = APIRouter(prefix="/auth")

_DESCRICAO_LOGIN = """
Autentica um usuario cadastrado na tabela `usuarios` e emite um token bearer temporario.

Fluxo esperado:

1. Um administrador cria o usuario em `POST /usuarios` usando o token de sistema
   ou um usuario com `is_admin=true`.
2. A API valida usuario ativo, hash da senha e credenciais informadas.
3. A API retorna `access_token`, `token_type` e `expires_in`.

Regras de autenticacao:

- `username` e normalizado para minusculas antes da busca.
- Usuario precisa existir e estar com `ativo=true`.
- Token expira conforme `ACCESS_TOKEN_TTL_MINUTES`; valor padrao: 480 minutos.
- Se o usuario for desativado depois do login, tokens ja emitidos deixam de ser aceitos.

Falhas comuns:

- Usuario inexistente, inativo ou senha incorreta retornam `401`.
- Payload sem `username` ou `password`, ou com tipos invalidos, retorna `422`.
"""

_RESPOSTAS_LOGIN: dict[int | str, dict[str, Any]] = {
    200: {
        "description": "Login realizado com sucesso. Use `access_token` como bearer token.",
        "content": {
            "application/json": {
                "example": {
                    "access_token": "tucano.v1.eyJleHAiOjE3ODA1MjIzNTksInN1YiI6Ii4uLiJ9.assinatura",
                    "token_type": "bearer",
                    "expires_in": 28800,
                }
            }
        },
    },
    401: {
        "description": "Credenciais invalidas, usuario inexistente ou usuario inativo.",
        "content": {"application/json": {"example": {"detail": "Usuario ou senha invalidos."}}},
    },
    422: {
        "description": "Payload invalido ou campos obrigatorios ausentes.",
        "content": {
            "application/json": {
                "example": {
                    "detail": [
                        {
                            "type": "missing",
                            "loc": ["body", "password"],
                            "msg": "Field required",
                            "input": {"username": "admin"},
                        }
                    ]
                }
            }
        },
    },
}


@router.post(
    "/login",
    response_model=LoginResposta,
    summary="Realizar Login",
    description=_DESCRICAO_LOGIN,
    responses=_RESPOSTAS_LOGIN,
    operation_id="realizarLoginAuth",
)
def realizar_login(payload: LoginRequisicao, db: DbSession) -> LoginResposta:
    usuario = autenticar_usuario(db, payload.username, payload.password)
    if usuario is None:
        raise HTTPException(status_code=401, detail="Usuario ou senha invalidos.")
    token, expires_in = gerar_token_usuario(usuario)
    return LoginResposta(access_token=token, token_type="bearer", expires_in=expires_in)


@router.get(
    "/me",
    response_model=UsuarioResposta,
    summary="Obter Usuario Atual",
    description="Retorna dados do usuario autenticado pelo token bearer.",
    operation_id="obterUsuarioAtualAuth",
)
def obter_me(usuario: Annotated[Usuario, Depends(obter_usuario_atual)]) -> UsuarioResposta:
    return UsuarioResposta.model_validate(usuario)
