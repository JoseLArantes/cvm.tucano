from pydantic import BaseModel, ConfigDict, Field


class LoginRequisicao(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "username": "admin",
                "password": "senha-admin-segura",
            }
        }
    )

    username: str = Field(
        min_length=3,
        max_length=150,
        description=(
            "Identificador do usuario cadastrado em `/usuarios`. "
            "A API remove espacos nas extremidades e compara em minusculas."
        ),
        examples=["admin", "frontend"],
    )
    password: str = Field(
        min_length=8,
        max_length=256,
        description=(
            "Senha atual do usuario. Este valor e usado apenas para comparacao com o hash armazenado "
            "e nunca aparece em respostas da API."
        ),
        examples=["senha-admin-segura"],
    )


class LoginResposta(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {"access_token": "tucano.v1.payload.assinatura", "token_type": "bearer", "expires_in": 28800}
        }
    )

    access_token: str = Field(
        description=(
            "Token assinado emitido para o usuario autenticado. Envie no header "
            "`Authorization: Bearer <access_token>` para acessar rotas protegidas."
        ),
        examples=["tucano.v1.eyJleHAiOjE3ODA1MjIzNTksInN1YiI6Ii4uLiJ9.assinatura"],
    )
    token_type: str = Field(
        description='Tipo do token retornado. Valor esperado: "bearer".',
        examples=["bearer"],
    )
    expires_in: int = Field(
        description=(
            "Tempo de validade do token em segundos. Derivado de `ACCESS_TOKEN_TTL_MINUTES` "
            "no momento do login."
        ),
        examples=[28800],
    )
