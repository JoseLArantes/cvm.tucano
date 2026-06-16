from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Select, func, select

from app.api.deps import DbSession, PaginacaoQuery
from app.models.companhia import Companhia
from app.models.fca import (
    FcaAuditor,
    FcaDepartamentoAcionistas,
    FcaDocumento,
    FcaDri,
    FcaEndereco,
    FcaGeral,
    FcaValorMobiliario,
)
from app.schemas.comum import Paginacao
from app.schemas.fca import (
    FcaAuditorResposta,
    FcaDepartamentoAcionistasResposta,
    FcaDocumentoResposta,
    FcaDriResposta,
    FcaEnderecoResposta,
    FcaGeralResposta,
    FcaValorMobiliarioResposta,
    ListaFcaAuditoresResposta,
    ListaFcaDepartamentoAcionistasResposta,
    ListaFcaDocumentosResposta,
    ListaFcaDriResposta,
    ListaFcaEnderecosResposta,
    ListaFcaGeralResposta,
    ListaFcaValoresMobiliariosResposta,
)
from app.services.normalizacao import normalizar_cnpj

router = APIRouter()

_RESPOSTAS_PADRAO: dict[int | str, dict[str, Any]] = {
    422: {
        "description": "Parâmetros inválidos (filtro, formato ou ordenação).",
        "content": {"application/json": {"example": {"detail": "Campo invalido para ordenacao: campo"}}},
    }
}

ParametroCnpj = Annotated[
    str | None,
    Query(description="CNPJ da companhia (com ou sem pontuação).", examples=["00.000.000/0001-91"]),
]
ParametroCodigoCvm = Annotated[int | None, Query(description="Código CVM da companhia.", examples=[1023])]
ParametroDataInicio = Annotated[
    date | None,
    Query(description="Data inicial de referência no formato ISO (YYYY-MM-DD).", examples=["2025-01-01"]),
]
ParametroDataFim = Annotated[
    date | None,
    Query(description="Data final de referência no formato ISO (YYYY-MM-DD).", examples=["2025-12-31"]),
]
ParametroAnoOrigem = Annotated[int | None, Query(description="Ano do ZIP de origem.", examples=[2025])]
ParametroAnoInicio = Annotated[int | None, Query(description="Ano inicial do ZIP/dados de origem.", examples=[2010])]
ParametroAnoFim = Annotated[int | None, Query(description="Ano final do ZIP/dados de origem.", examples=[2020])]
ParametroVersao = Annotated[int | None, Query(description="Versão do documento FCA.", examples=[1])]


def _col(modelo: type[Any], campo: str) -> Any:
    return getattr(modelo, campo)


def _aplicar_filtros_base(
    query: Select[Any],
    query_total: Select[Any],
    *,
    modelo: type[Any],
    cnpj_companhia: str | None,
    codigo_cvm: int | None,
    data_referencia_inicio: date | None,
    data_referencia_fim: date | None,
    ano_origem: int | None,
    versao: int | None,
    ano_inicio: int | None = None,
    ano_fim: int | None = None,
) -> tuple[Select[Any], Select[Any]]:
    if cnpj_companhia:
        cnpj = normalizar_cnpj(cnpj_companhia)
        query = query.where(_col(modelo, "cnpj_companhia") == cnpj)
        query_total = query_total.where(_col(modelo, "cnpj_companhia") == cnpj)
    if codigo_cvm is not None and hasattr(modelo, "codigo_cvm"):
        query = query.where(_col(modelo, "codigo_cvm") == codigo_cvm)
        query_total = query_total.where(_col(modelo, "codigo_cvm") == codigo_cvm)
    if data_referencia_inicio is not None:
        query = query.where(_col(modelo, "data_referencia") >= data_referencia_inicio)
        query_total = query_total.where(_col(modelo, "data_referencia") >= data_referencia_inicio)
    if data_referencia_fim is not None:
        query = query.where(_col(modelo, "data_referencia") <= data_referencia_fim)
        query_total = query_total.where(_col(modelo, "data_referencia") <= data_referencia_fim)
    if ano_origem is not None:
        query = query.where(_col(modelo, "ano_origem") == ano_origem)
        query_total = query_total.where(_col(modelo, "ano_origem") == ano_origem)
    if ano_inicio is not None:
        query = query.where(_col(modelo, "ano_origem") >= ano_inicio)
        query_total = query_total.where(_col(modelo, "ano_origem") >= ano_inicio)
    if ano_fim is not None:
        query = query.where(_col(modelo, "ano_origem") <= ano_fim)
        query_total = query_total.where(_col(modelo, "ano_origem") <= ano_fim)
    if versao is not None:
        query = query.where(_col(modelo, "versao") == versao)
        query_total = query_total.where(_col(modelo, "versao") == versao)
    return query, query_total


def _aplicar_ordenacao(
    query: Select[Any],
    *,
    modelo: type[Any],
    ordenar_por: str | None,
    campos_permitidos: set[str],
) -> Select[Any]:
    campo = ordenar_por or "-data_referencia"
    direcao_desc = campo.startswith("-")
    campo_limpo = campo[1:] if direcao_desc else campo
    if campo_limpo not in campos_permitidos:
        raise HTTPException(status_code=422, detail=f"Campo invalido para ordenacao: {campo_limpo}")
    coluna = _col(modelo, campo_limpo)
    return query.order_by(coluna.desc() if direcao_desc else coluna.asc())


def _lista_fca_generica(
    db: DbSession,
    *,
    modelo: type[Any],
    schema: type[Any],
    paginacao: PaginacaoQuery,
    cnpj_companhia: str | None,
    codigo_cvm: int | None,
    data_referencia_inicio: date | None,
    data_referencia_fim: date | None,
    ano_origem: int | None,
    ano_inicio: int | None = None,
    ano_fim: int | None = None,
    versao: int | None,
    ordenar_por: str | None,
    campos_permitidos: set[str],
    filtros_adicionais: dict[str, Any] | None = None,
) -> tuple[list[Any], int]:
    if codigo_cvm is not None and not cnpj_companhia:
        cnpj_resolvido = db.scalar(select(Companhia.cnpj_companhia).where(Companhia.codigo_cvm == codigo_cvm))
        if cnpj_resolvido:
            cnpj_companhia = cnpj_resolvido
        elif not hasattr(modelo, "codigo_cvm"):
            return [], 0
    query: Select[Any] = select(modelo)
    query_total = select(func.count()).select_from(modelo)
    query, query_total = _aplicar_filtros_base(
        query,
        query_total,
        modelo=modelo,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        ano_inicio=ano_inicio,
        ano_fim=ano_fim,
        versao=versao,
    )
    if filtros_adicionais:
        for campo, valor in filtros_adicionais.items():
            if valor is not None:
                query = query.where(_col(modelo, campo) == valor)
                query_total = query_total.where(_col(modelo, campo) == valor)
    query = _aplicar_ordenacao(query, modelo=modelo, ordenar_por=ordenar_por, campos_permitidos=campos_permitidos)
    total = db.scalar(query_total) or 0
    itens = db.execute(query.offset(paginacao.offset).limit(paginacao.tamanho_pagina)).scalars().all()
    return [schema.model_validate(item) for item in itens], total


@router.get(
    "/fca/documentos",
    response_model=ListaFcaDocumentosResposta,
    responses=_RESPOSTAS_PADRAO,
    summary="Listar documentos FCA",
    description=(
        "Retorna uma lista paginada de cabeçalhos de documentos do Formulário "
        "Cadastral do Emissor (FCA) com base nos filtros informados."
    ),
)
def listar_documentos_fca(
    db: DbSession,
    paginacao: Annotated[PaginacaoQuery, Depends()],
    cnpj_companhia: ParametroCnpj = None,
    codigo_cvm: ParametroCodigoCvm = None,
    data_referencia_inicio: ParametroDataInicio = None,
    data_referencia_fim: ParametroDataFim = None,
    ano_origem: ParametroAnoOrigem = None,
    ano_inicio: ParametroAnoInicio = None,
    ano_fim: ParametroAnoFim = None,
    versao: ParametroVersao = None,
    ordenar_por: Annotated[
        str | None, Query(description="Campos: data_referencia, versao, cnpj_companhia, codigo_cvm.")
    ] = "-data_referencia",
) -> ListaFcaDocumentosResposta:
    dados, total = _lista_fca_generica(
        db,
        modelo=FcaDocumento,
        schema=FcaDocumentoResposta,
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        ano_inicio=ano_inicio,
        ano_fim=ano_fim,
        versao=versao,
        ordenar_por=ordenar_por,
        campos_permitidos={"data_referencia", "versao", "cnpj_companhia", "codigo_cvm"},
    )
    return ListaFcaDocumentosResposta(
        dados=dados, paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total)
    )


@router.get(
    "/fca/geral",
    response_model=ListaFcaGeralResposta,
    responses=_RESPOSTAS_PADRAO,
    summary="Listar dados gerais FCA",
    description=(
        "Retorna informações cadastrais gerais das companhias a partir do Formulário Cadastral do Emissor (FCA)."
    ),
)
def listar_geral_fca(
    db: DbSession,
    paginacao: Annotated[PaginacaoQuery, Depends()],
    cnpj_companhia: ParametroCnpj = None,
    codigo_cvm: ParametroCodigoCvm = None,
    data_referencia_inicio: ParametroDataInicio = None,
    data_referencia_fim: ParametroDataFim = None,
    ano_origem: ParametroAnoOrigem = None,
    ano_inicio: ParametroAnoInicio = None,
    ano_fim: ParametroAnoFim = None,
    versao: ParametroVersao = None,
    ordenar_por: Annotated[
        str | None, Query(description="Campos: data_referencia, versao, cnpj_companhia, codigo_cvm, nome_empresarial.")
    ] = "-data_referencia",
) -> ListaFcaGeralResposta:
    dados, total = _lista_fca_generica(
        db,
        modelo=FcaGeral,
        schema=FcaGeralResposta,
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        ano_inicio=ano_inicio,
        ano_fim=ano_fim,
        versao=versao,
        ordenar_por=ordenar_por,
        campos_permitidos={"data_referencia", "versao", "cnpj_companhia", "codigo_cvm", "nome_empresarial"},
    )
    return ListaFcaGeralResposta(
        dados=dados, paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total)
    )


@router.get(
    "/fca/enderecos",
    response_model=ListaFcaEnderecosResposta,
    responses=_RESPOSTAS_PADRAO,
    summary="Listar endereços FCA",
    description="Retorna a lista de endereços das companhias registradas no Formulário Cadastral do Emissor (FCA).",
)
def listar_enderecos_fca(
    db: DbSession,
    paginacao: Annotated[PaginacaoQuery, Depends()],
    cnpj_companhia: ParametroCnpj = None,
    codigo_cvm: ParametroCodigoCvm = None,
    data_referencia_inicio: ParametroDataInicio = None,
    data_referencia_fim: ParametroDataFim = None,
    ano_origem: ParametroAnoOrigem = None,
    ano_inicio: ParametroAnoInicio = None,
    ano_fim: ParametroAnoFim = None,
    versao: ParametroVersao = None,
    tipo_endereco: Annotated[str | None, Query(description="Filtrar por tipo de endereco.")] = None,
    pais: Annotated[str | None, Query(description="Filtrar por pais do endereco.")] = None,
    ordenar_por: Annotated[
        str | None, Query(description="Campos: data_referencia, versao, cnpj_companhia, tipo_endereco, pais.")
    ] = "-data_referencia",
) -> ListaFcaEnderecosResposta:
    dados, total = _lista_fca_generica(
        db,
        modelo=FcaEndereco,
        schema=FcaEnderecoResposta,
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        ano_inicio=ano_inicio,
        ano_fim=ano_fim,
        versao=versao,
        ordenar_por=ordenar_por,
        campos_permitidos={"data_referencia", "versao", "cnpj_companhia", "tipo_endereco", "pais"},
        filtros_adicionais={"tipo_endereco": tipo_endereco, "pais": pais},
    )
    return ListaFcaEnderecosResposta(
        dados=dados, paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total)
    )


@router.get(
    "/fca/dri",
    response_model=ListaFcaDriResposta,
    responses=_RESPOSTAS_PADRAO,
    summary="Listar diretores de relações com investidores (DRI) FCA",
    description=(
        "Retorna a lista de Diretores de Relações com Investidores (DRI) "
        "informados no Formulário Cadastral do Emissor (FCA)."
    ),
)
def listar_dri_fca(
    db: DbSession,
    paginacao: Annotated[PaginacaoQuery, Depends()],
    cnpj_companhia: ParametroCnpj = None,
    codigo_cvm: ParametroCodigoCvm = None,
    data_referencia_inicio: ParametroDataInicio = None,
    data_referencia_fim: ParametroDataFim = None,
    ano_origem: ParametroAnoOrigem = None,
    ano_inicio: ParametroAnoInicio = None,
    ano_fim: ParametroAnoFim = None,
    versao: ParametroVersao = None,
    nome_dri: Annotated[str | None, Query(description="Filtrar por nome do DRI.")] = None,
    email_dri: Annotated[str | None, Query(description="Filtrar por email do DRI.")] = None,
    ordenar_por: Annotated[
        str | None, Query(description="Campos: data_referencia, versao, cnpj_companhia, nome_dri, email_dri.")
    ] = "-data_referencia",
) -> ListaFcaDriResposta:
    dados, total = _lista_fca_generica(
        db,
        modelo=FcaDri,
        schema=FcaDriResposta,
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        ano_inicio=ano_inicio,
        ano_fim=ano_fim,
        versao=versao,
        ordenar_por=ordenar_por,
        campos_permitidos={"data_referencia", "versao", "cnpj_companhia", "nome_dri", "email_dri"},
        filtros_adicionais={"nome_dri": nome_dri, "email_dri": email_dri},
    )
    return ListaFcaDriResposta(
        dados=dados, paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total)
    )


@router.get(
    "/fca/auditores",
    response_model=ListaFcaAuditoresResposta,
    responses=_RESPOSTAS_PADRAO,
    summary="Listar auditores independentes FCA",
    description=(
        "Retorna a lista de auditores independentes das companhias, conforme registrado "
        "no Formulário Cadastral do Emissor (FCA)."
    ),
)
def listar_auditores_fca(
    db: DbSession,
    paginacao: Annotated[PaginacaoQuery, Depends()],
    cnpj_companhia: ParametroCnpj = None,
    codigo_cvm: ParametroCodigoCvm = None,
    data_referencia_inicio: ParametroDataInicio = None,
    data_referencia_fim: ParametroDataFim = None,
    ano_origem: ParametroAnoOrigem = None,
    ano_inicio: ParametroAnoInicio = None,
    ano_fim: ParametroAnoFim = None,
    versao: ParametroVersao = None,
    nome_auditor: Annotated[str | None, Query(description="Filtrar por nome do auditor.")] = None,
    codigo_cvm_auditor: Annotated[str | None, Query(description="Filtrar por codigo CVM do auditor.")] = None,
    ordenar_por: Annotated[
        str | None,
        Query(description="Campos: data_referencia, versao, cnpj_companhia, nome_auditor, codigo_cvm_auditor."),
    ] = "-data_referencia",
) -> ListaFcaAuditoresResposta:
    dados, total = _lista_fca_generica(
        db,
        modelo=FcaAuditor,
        schema=FcaAuditorResposta,
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        ano_inicio=ano_inicio,
        ano_fim=ano_fim,
        versao=versao,
        ordenar_por=ordenar_por,
        campos_permitidos={"data_referencia", "versao", "cnpj_companhia", "nome_auditor", "codigo_cvm_auditor"},
        filtros_adicionais={"nome_auditor": nome_auditor, "codigo_cvm_auditor": codigo_cvm_auditor},
    )
    return ListaFcaAuditoresResposta(
        dados=dados, paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total)
    )


@router.get(
    "/fca/valores-mobiliarios",
    response_model=ListaFcaValoresMobiliariosResposta,
    responses=_RESPOSTAS_PADRAO,
    summary="Listar valores mobiliários FCA",
    description=(
        "Retorna a lista de valores mobiliários emitidos pelas companhias e "
        "cadastrados no Formulário Cadastral do Emissor (FCA)."
    ),
)
def listar_valores_mobiliarios_fca(
    db: DbSession,
    paginacao: Annotated[PaginacaoQuery, Depends()],
    cnpj_companhia: ParametroCnpj = None,
    codigo_cvm: ParametroCodigoCvm = None,
    data_referencia_inicio: ParametroDataInicio = None,
    data_referencia_fim: ParametroDataFim = None,
    ano_origem: ParametroAnoOrigem = None,
    ano_inicio: ParametroAnoInicio = None,
    ano_fim: ParametroAnoFim = None,
    versao: ParametroVersao = None,
    tipo_valor_mobiliario: Annotated[str | None, Query(description="Filtrar por tipo de valor mobiliario.")] = None,
    ordenar_por: Annotated[
        str | None,
        Query(description="Campos: data_referencia, versao, cnpj_companhia, tipo_valor_mobiliario, codigo_negociacao."),
    ] = "-data_referencia",
) -> ListaFcaValoresMobiliariosResposta:
    dados, total = _lista_fca_generica(
        db,
        modelo=FcaValorMobiliario,
        schema=FcaValorMobiliarioResposta,
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        ano_inicio=ano_inicio,
        ano_fim=ano_fim,
        versao=versao,
        ordenar_por=ordenar_por,
        campos_permitidos={"data_referencia", "versao", "cnpj_companhia", "tipo_valor_mobiliario", "codigo_negociacao"},
        filtros_adicionais={"tipo_valor_mobiliario": tipo_valor_mobiliario},
    )
    return ListaFcaValoresMobiliariosResposta(
        dados=dados, paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total)
    )


@router.get(
    "/fca/departamento-acionistas",
    response_model=ListaFcaDepartamentoAcionistasResposta,
    responses=_RESPOSTAS_PADRAO,
    summary="Listar departamentos de atendimento a acionistas FCA",
    description=(
        "Retorna os contatos e endereços do departamento de atendimento a acionistas "
        "informados no Formulário Cadastral do Emissor (FCA)."
    ),
)
def listar_departamento_acionistas_fca(
    db: DbSession,
    paginacao: Annotated[PaginacaoQuery, Depends()],
    cnpj_companhia: ParametroCnpj = None,
    codigo_cvm: ParametroCodigoCvm = None,
    data_referencia_inicio: ParametroDataInicio = None,
    data_referencia_fim: ParametroDataFim = None,
    ano_origem: ParametroAnoOrigem = None,
    ano_inicio: ParametroAnoInicio = None,
    ano_fim: ParametroAnoFim = None,
    versao: ParametroVersao = None,
    contato: Annotated[str | None, Query(description="Filtrar por nome do contato.")] = None,
    email: Annotated[str | None, Query(description="Filtrar por email do departamento.")] = None,
    tipo_endereco: Annotated[str | None, Query(description="Filtrar por tipo de endereco.")] = None,
    sigla_uf: Annotated[str | None, Query(description="Filtrar por UF do departamento.")] = None,
    ordenar_por: Annotated[
        str | None,
        Query(description="Campos: data_referencia, versao, cnpj_companhia, contato, email, tipo_endereco, sigla_uf."),
    ] = "-data_referencia",
) -> ListaFcaDepartamentoAcionistasResposta:
    dados, total = _lista_fca_generica(
        db,
        modelo=FcaDepartamentoAcionistas,
        schema=FcaDepartamentoAcionistasResposta,
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        ano_inicio=ano_inicio,
        ano_fim=ano_fim,
        versao=versao,
        ordenar_por=ordenar_por,
        campos_permitidos={"data_referencia", "versao", "cnpj_companhia", "contato", "email", "tipo_endereco", "sigla_uf"},
        filtros_adicionais={
            "contato": contato,
            "email": email,
            "tipo_endereco": tipo_endereco,
            "sigla_uf": sigla_uf,
        },
    )
    return ListaFcaDepartamentoAcionistasResposta(
        dados=dados, paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total)
    )
