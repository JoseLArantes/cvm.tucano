import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.comum import BrazilianDateTime, Paginacao


def normalizar_username(valor: str) -> str:
    return valor.strip().lower()


class UsuarioCriacao(BaseModel):
    username: str = Field(
        min_length=3,
        max_length=150,
        pattern=r"^[a-zA-Z0-9_.@-]+$",
        description="Identificador unico usado no login.",
        examples=["frontend"],
    )
    password: str = Field(min_length=8, max_length=256, description="Senha inicial do usuario.")
    nome: str | None = Field(default=None, max_length=255, description="Nome de exibicao do usuario.")
    is_admin: bool = Field(default=False, description="Permite administrar usuarios.")
    ativo: bool = Field(default=True, description="Permite login e uso do token.")

    @field_validator("username", mode="before")
    @classmethod
    def _normalizar_username(cls, valor: Any) -> Any:
        if isinstance(valor, str):
            return normalizar_username(valor)
        return valor


class UsuarioAtualizacao(BaseModel):
    username: str | None = Field(
        default=None,
        min_length=3,
        max_length=150,
        pattern=r"^[a-zA-Z0-9_.@-]+$",
        description="Novo identificador de login.",
    )
    password: str | None = Field(default=None, min_length=8, max_length=256, description="Nova senha.")
    nome: str | None = Field(default=None, max_length=255, description="Novo nome de exibicao.")
    is_admin: bool | None = Field(default=None, description="Novo status administrativo.")
    ativo: bool | None = Field(default=None, description="Novo status de ativacao.")

    @field_validator("username", mode="before")
    @classmethod
    def _normalizar_username(cls, valor: Any) -> Any:
        if isinstance(valor, str):
            return normalizar_username(valor)
        return valor


class UsuarioResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="Identificador interno do usuario.")
    username: str = Field(description="Identificador usado no login.")
    nome: str | None = Field(description="Nome de exibicao.")
    is_admin: bool = Field(description="Indica se o usuario pode administrar usuarios.")
    ativo: bool = Field(description="Indica se login e tokens do usuario sao aceitos.")
    criado_em: BrazilianDateTime = Field(description="Data e hora de criacao, em `DD/MM/AAAA HH:MM:SS`.")
    alterado_em: BrazilianDateTime = Field(description="Data e hora da ultima alteracao, em `DD/MM/AAAA HH:MM:SS`.")


class ListaUsuariosResposta(BaseModel):
    dados: list[UsuarioResposta] = Field(description="Lista paginada de usuarios.")
    paginacao: Paginacao = Field(description="Metadados de paginacao.")
