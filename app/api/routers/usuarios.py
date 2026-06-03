import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from sqlalchemy import func, select

from app.api.auth import exigir_admin_api, gerar_hash_senha
from app.api.deps import DbSession, PaginacaoQuery
from app.models.usuario import Usuario
from app.schemas.comum import Paginacao
from app.schemas.usuario import ListaUsuariosResposta, UsuarioAtualizacao, UsuarioCriacao, UsuarioResposta

router = APIRouter(prefix="/usuarios")

_RESPOSTAS_USUARIOS: dict[int | str, dict[str, Any]] = {
    401: {
        "description": "Token ausente ou invalido.",
        "content": {"application/json": {"example": {"detail": "Token de acesso invalido."}}},
    },
    403: {
        "description": "Permissao administrativa requerida.",
        "content": {"application/json": {"example": {"detail": "Permissao administrativa requerida."}}},
    },
    404: {
        "description": "Usuario nao encontrado.",
        "content": {"application/json": {"example": {"detail": "Usuario nao encontrado."}}},
    },
    409: {
        "description": "Conflito de dados.",
        "content": {"application/json": {"example": {"detail": "Username ja cadastrado."}}},
    },
}


def _buscar_usuario_ou_404(db: DbSession, usuario_id: uuid.UUID) -> Usuario:
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status_code=404, detail="Usuario nao encontrado.")
    return usuario


def _username_existe(db: DbSession, username: str, ignorar_usuario_id: uuid.UUID | None = None) -> bool:
    query = select(Usuario.id).where(Usuario.username == username)
    if ignorar_usuario_id is not None:
        query = query.where(Usuario.id != ignorar_usuario_id)
    return db.scalar(query) is not None


def _total_admins_ativos(db: DbSession) -> int:
    return (
        db.scalar(select(func.count()).select_from(Usuario).where(Usuario.is_admin.is_(True), Usuario.ativo.is_(True)))
        or 0
    )


def _garantir_admin_remanescente(db: DbSession, usuario: Usuario) -> None:
    if usuario.is_admin and usuario.ativo and _total_admins_ativos(db) <= 1:
        raise HTTPException(status_code=409, detail="Nao e permitido remover o ultimo admin ativo.")


@router.get(
    "",
    response_model=ListaUsuariosResposta,
    summary="Listar Usuarios",
    description="Lista usuarios cadastrados com paginacao.",
    responses=_RESPOSTAS_USUARIOS,
    operation_id="listarUsuarios",
)
def listar_usuarios(
    db: DbSession,
    paginacao: Annotated[PaginacaoQuery, Depends()],
    _: Annotated[None, Depends(exigir_admin_api)],
    ativo: Annotated[
        bool | None,
        Query(description="Filtra usuarios ativos ou inativos.", examples=[True, False]),
    ] = None,
) -> ListaUsuariosResposta:
    query = select(Usuario)
    query_total = select(func.count()).select_from(Usuario)

    if ativo is not None:
        query = query.where(Usuario.ativo.is_(ativo))
        query_total = query_total.where(Usuario.ativo.is_(ativo))

    total = db.scalar(query_total) or 0
    itens = (
        db.execute(query.order_by(Usuario.username).offset(paginacao.offset).limit(paginacao.tamanho_pagina))
        .scalars()
        .all()
    )

    return ListaUsuariosResposta(
        dados=[UsuarioResposta.model_validate(item) for item in itens],
        paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total),
    )


@router.post(
    "",
    response_model=UsuarioResposta,
    status_code=status.HTTP_201_CREATED,
    summary="Criar Usuario",
    description="Cria usuario para login na API.",
    responses=_RESPOSTAS_USUARIOS,
    operation_id="criarUsuario",
)
def criar_usuario(
    payload: UsuarioCriacao,
    db: DbSession,
    _: Annotated[None, Depends(exigir_admin_api)],
) -> UsuarioResposta:
    if _username_existe(db, payload.username):
        raise HTTPException(status_code=409, detail="Username ja cadastrado.")

    usuario = Usuario(
        username=payload.username,
        nome=payload.nome,
        senha_hash=gerar_hash_senha(payload.password),
        is_admin=payload.is_admin,
        ativo=payload.ativo,
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return UsuarioResposta.model_validate(usuario)


@router.get(
    "/{usuario_id}",
    response_model=UsuarioResposta,
    summary="Obter Usuario",
    description="Retorna usuario por ID.",
    responses=_RESPOSTAS_USUARIOS,
    operation_id="obterUsuario",
)
def obter_usuario(
    usuario_id: Annotated[uuid.UUID, Path(description="ID do usuario.")],
    db: DbSession,
    _: Annotated[None, Depends(exigir_admin_api)],
) -> UsuarioResposta:
    return UsuarioResposta.model_validate(_buscar_usuario_ou_404(db, usuario_id))


@router.patch(
    "/{usuario_id}",
    response_model=UsuarioResposta,
    summary="Atualizar Usuario",
    description="Atualiza dados, senha, status e perfil administrativo de usuario.",
    responses=_RESPOSTAS_USUARIOS,
    operation_id="atualizarUsuario",
)
def atualizar_usuario(
    usuario_id: Annotated[uuid.UUID, Path(description="ID do usuario.")],
    payload: UsuarioAtualizacao,
    db: DbSession,
    _: Annotated[None, Depends(exigir_admin_api)],
) -> UsuarioResposta:
    usuario = _buscar_usuario_ou_404(db, usuario_id)

    if payload.username is not None:
        if _username_existe(db, payload.username, ignorar_usuario_id=usuario.id):
            raise HTTPException(status_code=409, detail="Username ja cadastrado.")
        usuario.username = payload.username

    if payload.password is not None:
        usuario.senha_hash = gerar_hash_senha(payload.password)
    if payload.nome is not None:
        usuario.nome = payload.nome
    if payload.is_admin is not None and usuario.is_admin and not payload.is_admin:
        _garantir_admin_remanescente(db, usuario)
        usuario.is_admin = payload.is_admin
    elif payload.is_admin is not None:
        usuario.is_admin = payload.is_admin
    if payload.ativo is not None and usuario.ativo and not payload.ativo:
        _garantir_admin_remanescente(db, usuario)
        usuario.ativo = payload.ativo
    elif payload.ativo is not None:
        usuario.ativo = payload.ativo

    usuario.alterado_em = datetime.now(UTC)
    db.commit()
    db.refresh(usuario)
    return UsuarioResposta.model_validate(usuario)


@router.delete(
    "/{usuario_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Excluir Usuario",
    description="Remove usuario cadastrado.",
    responses=_RESPOSTAS_USUARIOS,
    operation_id="excluirUsuario",
)
def excluir_usuario(
    usuario_id: Annotated[uuid.UUID, Path(description="ID do usuario.")],
    db: DbSession,
    _: Annotated[None, Depends(exigir_admin_api)],
) -> Response:
    usuario = _buscar_usuario_ou_404(db, usuario_id)
    _garantir_admin_remanescente(db, usuario)
    db.delete(usuario)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
