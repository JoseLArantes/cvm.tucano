import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from app.api.deps import DbSession, PaginacaoQuery
from app.models.setores import Setor, SetorTaxonomia
from app.schemas.companhia import CompanhiaResposta, ListaCompanhiasResposta
from app.services.companhias import (
    listar_companhias as listar_companhias_service,
)
from app.services.companhias import (
    obter_companhia_por_cnpj as obter_companhia_por_cnpj_service,
)
from app.services.companhias import (
    obter_companhia_por_codigo_cvm as obter_companhia_por_codigo_cvm_service,
)

router = APIRouter(prefix="/companhias")

_RESPOSTAS_PADRAO: dict[int | str, dict[str, Any]] = {
    404: {
        "description": "Recurso não encontrado para os critérios informados.",
        "content": {"application/json": {"example": {"detail": "Companhia nao encontrada."}}},
    },
    422: {
        "description": "Parâmetro inválido.",
        "content": {"application/json": {"example": {"detail": "Campo invalido."}}},
    },
}


def _validar_taxonomia_selecionada(db: DbSession, taxonomia: str | None, setor_id: uuid.UUID | None = None) -> str:
    codigo = taxonomia or "cvm_cadastro"
    if taxonomia is not None or setor_id is not None:
        catalogo = db.get(SetorTaxonomia, codigo)
        if catalogo is None:
            raise HTTPException(status_code=404, detail="Taxonomia nao encontrada.")
        if catalogo.versao_atual is None:
            raise HTTPException(status_code=409, detail={"codigo": "TAXONOMIA_SEM_PUBLICACAO", "taxonomia": codigo})
        if setor_id is not None:
            setor = db.get(Setor, setor_id)
            if setor is None or setor.taxonomia != codigo:
                raise HTTPException(status_code=404, detail="Setor nao encontrado na taxonomia informada.")
    return codigo


@router.get(
    "",
    response_model=ListaCompanhiasResposta,
    summary="Listar Companhias",
    description="Retorna lista paginada de companhias abertas normalizadas. Permite filtragem por CNPJ, código CVM, nome e situação cadastral.",
    responses=_RESPOSTAS_PADRAO,
    operation_id="listarCompanhias",
)
def listar_companhias(
    db: DbSession,
    paginacao: Annotated[PaginacaoQuery, Depends()],
    cnpj_companhia: Annotated[
        str | None,
        Query(
            description="CNPJ da companhia (com ou sem pontuação).",
            examples=["08.773.135/0001-00", "08773135000100"],
        ),
    ] = None,
    codigo_cvm: Annotated[
        int | None,
        Query(
            description="Código CVM da companhia.",
            examples=[25224],
        ),
    ] = None,
    nome: Annotated[
        str | None,
        Query(
            description="Nome (razão social ou nome comercial) da companhia.",
            examples=["Petrobras"],
        ),
    ] = None,
    situacao_registro: Annotated[
        str | None,
        Query(
            description="Filtrar por situação do registro na CVM.",
            examples=["ATIVO", "SUSPENSO(A) - DECISAO ADM"],
        ),
    ] = None,
    categoria_registro: Annotated[
        str | None,
        Query(description="Categoria de registro da companhia (ex.: Categoria A)."),
    ] = None,
    tipo_emissor: Annotated[
        str | None,
        Query(description="Tipo de emissor informado no cadastro CVM."),
    ] = None,
    setor_id: Annotated[
        uuid.UUID | None,
        Query(description="UUID estável do setor para restringir a lista."),
    ] = None,
    taxonomia: Annotated[
        str | None,
        Query(description="Taxonomia usada para resolver `setor_id` e preencher a classificação setorial."),
    ] = None,
    ordenar: Annotated[
        str | None,
        Query(
            description="Ordenação dos resultados: ativa_nome, nome ou codigo_cvm.",
            examples=["ativa_nome", "nome", "codigo_cvm"],
        ),
    ] = "ativa_nome",
) -> ListaCompanhiasResposta:
    taxonomia_resolvida = _validar_taxonomia_selecionada(db, taxonomia, setor_id)
    return listar_companhias_service(
        db,
        pagina=paginacao.pagina,
        tamanho_pagina=paginacao.tamanho_pagina,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        nome=nome,
        situacao_registro=situacao_registro,
        categoria_registro=categoria_registro,
        tipo_emissor=tipo_emissor,
        setor_id=setor_id,
        taxonomia=taxonomia_resolvida,
        ordenar=ordenar,
    )


@router.get(
    "/codigo-cvm/{codigo_cvm}",
    response_model=CompanhiaResposta,
    summary="Obter Companhia por Código CVM",
    description="Retorna uma companhia específica a partir do código CVM.",
    responses=_RESPOSTAS_PADRAO,
    operation_id="obterCompanhiaPorCodigoCvm",
)
def obter_companhia_por_codigo_cvm(
    codigo_cvm: Annotated[
        int,
        Path(
            description="Código CVM da companhia.",
            examples=[25224],
        ),
    ],
    db: DbSession,
    taxonomia: Annotated[str | None, Query(description="Taxonomia usada para resolver o setor da companhia.")] = None,
) -> CompanhiaResposta:
    taxonomia_resolvida = _validar_taxonomia_selecionada(db, taxonomia)
    companhia = obter_companhia_por_codigo_cvm_service(db, codigo_cvm, taxonomia=taxonomia_resolvida)
    if companhia is None:
        raise HTTPException(status_code=404, detail="Companhia nao encontrada.")
    return companhia


# --- EXISTING GET BY CNPJ ENDPOINT (CATCH-ALL) REGISTERED LAST ---

@router.get(
    "/{cnpj_companhia:path}",
    response_model=CompanhiaResposta,
    summary="Obter Companhia por CNPJ",
    description="Retorna uma companhia específica a partir do CNPJ (formatado ou não).",
    responses=_RESPOSTAS_PADRAO,
    operation_id="obterCompanhiaPorCnpj",
)
def obter_companhia_por_cnpj(
    cnpj_companhia: Annotated[
        str,
        Path(
            description="CNPJ da companhia (aceita com ou sem pontuação).",
            examples=["08.773.135/0001-00", "08773135000100"],
        ),
    ],
    db: DbSession,
    taxonomia: Annotated[str | None, Query(description="Taxonomia usada para resolver o setor da companhia.")] = None,
) -> CompanhiaResposta:
    try:
        taxonomia_resolvida = _validar_taxonomia_selecionada(db, taxonomia)
        companhia = obter_companhia_por_cnpj_service(db, cnpj_companhia, taxonomia=taxonomia_resolvida)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Companhia nao encontrada.") from exc
    if companhia is None:
        raise HTTPException(status_code=404, detail="Companhia nao encontrada.")
    return companhia
