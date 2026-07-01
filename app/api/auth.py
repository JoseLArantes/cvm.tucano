import base64
import hashlib
import hmac
import json
import time
import uuid
from dataclasses import dataclass
from secrets import compare_digest, token_urlsafe
from typing import Annotated, Any

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.usuario import Usuario

_bearer_scheme = HTTPBearer(auto_error=False)
_HASH_ALGORITMO = "pbkdf2_sha256"
_HASH_ITERACOES = 600_000
_TOKEN_PREFIXO = "tucano.v1"


@dataclass(frozen=True)
class AutenticacaoApi:
    usuario: Usuario | None
    token_sistema: bool


def _codificar_base64url(valor: bytes) -> str:
    return base64.urlsafe_b64encode(valor).decode("ascii").rstrip("=")


def _decodificar_base64url(valor: str) -> bytes:
    padding = "=" * (-len(valor) % 4)
    return base64.urlsafe_b64decode(f"{valor}{padding}".encode("ascii"))


def obter_token_api() -> str:
    return get_settings().api_token


def gerar_hash_senha(senha: str) -> str:
    salt = token_urlsafe(24)
    digest = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), salt.encode("utf-8"), _HASH_ITERACOES)
    return f"{_HASH_ALGORITMO}${_HASH_ITERACOES}${salt}${base64.b64encode(digest).decode('ascii')}"


def verificar_senha(senha: str, senha_hash: str) -> bool:
    try:
        algoritmo, iteracoes_texto, salt, digest_esperado = senha_hash.split("$", 3)
        iteracoes = int(iteracoes_texto)
    except ValueError:
        return False

    if algoritmo != _HASH_ALGORITMO:
        return False

    digest = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), salt.encode("utf-8"), iteracoes)
    return compare_digest(base64.b64encode(digest).decode("ascii"), digest_esperado)


def autenticar_usuario(db: Session, username: str, password: str) -> Usuario | None:
    usuario = db.scalar(select(Usuario).where(Usuario.username == username.strip().lower()))
    if usuario is None or not usuario.ativo:
        return None
    if not verificar_senha(password, usuario.senha_hash):
        return None
    return usuario


def gerar_token_usuario(usuario: Usuario) -> tuple[str, int]:
    settings = get_settings()
    expires_in = settings.access_token_ttl_minutes * 60
    payload = {
        "sub": str(usuario.id),
        "username": usuario.username,
        "exp": int(time.time()) + expires_in,
    }
    payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_token = _codificar_base64url(payload_json)
    assinatura = hmac.new(settings.api_token.encode("utf-8"), payload_token.encode("ascii"), hashlib.sha256).digest()
    return f"{_TOKEN_PREFIXO}.{payload_token}.{_codificar_base64url(assinatura)}", expires_in


def _decodificar_token_usuario(token: str) -> uuid.UUID | None:
    partes = token.split(".")
    if len(partes) != 4 or ".".join(partes[:2]) != _TOKEN_PREFIXO:
        return None

    payload_token = partes[2]
    assinatura_recebida = partes[3]
    assinatura_esperada = hmac.new(
        get_settings().api_token.encode("utf-8"), payload_token.encode("ascii"), hashlib.sha256
    ).digest()
    if not compare_digest(_codificar_base64url(assinatura_esperada), assinatura_recebida):
        return None

    try:
        payload: dict[str, Any] = json.loads(_decodificar_base64url(payload_token))
        exp = int(payload["exp"])
        usuario_id = uuid.UUID(str(payload["sub"]))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None

    if exp < int(time.time()):
        return None
    return usuario_id


def autenticar_requisicao(
    db: Annotated[Session, Depends(get_db)],
    credenciais: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)] = None,
) -> AutenticacaoApi:
    if credenciais is None or credenciais.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Token de acesso invalido.")

    token = credenciais.credentials
    if compare_digest(token, obter_token_api()):
        return AutenticacaoApi(usuario=None, token_sistema=True)

    usuario_id = _decodificar_token_usuario(token)
    if usuario_id is None:
        raise HTTPException(status_code=401, detail="Token de acesso invalido.")

    usuario = db.get(Usuario, usuario_id)
    if usuario is None or not usuario.ativo:
        raise HTTPException(status_code=401, detail="Token de acesso invalido.")
    return AutenticacaoApi(usuario=usuario, token_sistema=False)


def validar_token_api(
    autenticacao: Annotated[AutenticacaoApi, Depends(autenticar_requisicao)],
) -> None:
    _ = autenticacao


def obter_usuario_atual(
    autenticacao: Annotated[AutenticacaoApi, Depends(autenticar_requisicao)],
) -> Usuario:
    if autenticacao.usuario is None:
        raise HTTPException(status_code=401, detail="Token de usuario requerido.")
    return autenticacao.usuario


def exigir_admin_api(
    autenticacao: Annotated[AutenticacaoApi, Depends(autenticar_requisicao)],
) -> None:
    if autenticacao.token_sistema:
        return
    if autenticacao.usuario is None or not autenticacao.usuario.is_admin:
        raise HTTPException(status_code=403, detail="Permissao administrativa requerida.")


def exigir_operador_materializacao_api(
    autenticacao: Annotated[AutenticacaoApi, Depends(autenticar_requisicao)],
) -> None:
    if autenticacao.token_sistema:
        return
    if autenticacao.usuario is not None and (
        autenticacao.usuario.is_admin or autenticacao.usuario.pode_operar_materializacao
    ):
        return
    if autenticacao.usuario is None:
        raise HTTPException(status_code=401, detail="Token de acesso invalido.")
    raise HTTPException(status_code=403, detail="Permissao de operacao de materializacao requerida.")
