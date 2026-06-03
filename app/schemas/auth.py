from pydantic import BaseModel, ConfigDict, Field


class LoginRequisicao(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {"username": "frontend", "password": "trocar-senha"}})

    username: str = Field(description="Usuario configurado para autenticacao da aplicacao cliente.")
    password: str = Field(description="Senha configurada para autenticacao da aplicacao cliente.")


class LoginResposta(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"access_token": "token-teste", "token_type": "bearer"}}
    )

    access_token: str = Field(description="Token bearer a ser enviado no header Authorization.")
    token_type: str = Field(description='Tipo do token retornado. Valor esperado: "bearer".')
