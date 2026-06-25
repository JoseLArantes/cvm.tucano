from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.api.deps import DbSession, PaginacaoQuery
from app.models.companhia import Companhia
from app.models.fre import (
    FreAcaoEntregue,
    FreAdministradorDeclaracaoGenero,
    FreAdministradorDeclaracaoRaca,
    FreAdministradorPcd,
    FreAuditor,
    FreCapitalSocial,
    FreCapitalSocialClasseAcao,
    FreCapitalSocialTituloConversivel,
    FreDistribuicaoCapital,
    FreDistribuicaoCapitalClasseAcao,
    FreDocumento,
    FreEmpregadoLocalDeclaracaoGenero,
    FreEmpregadoLocalDeclaracaoRaca,
    FreEmpregadoLocalFaixaEtaria,
    FreEmpregadoPcd,
    FreEmpregadoPosicaoDeclaracaoRaca,
    FreEmpregadoPosicaoFaixaEtaria,
    FreEmpregadoPosicaoGenero,
    FreEmpregadoPosicaoLocal,
    FreMercadoEstrangeiro,
    FreOutroValorMobiliario,
    FreParticipacaoSociedade,
    FrePlanoRecompra,
    FrePlanoRecompraClasseAcao,
    FrePosicaoAcionaria,
    FrePosicaoAcionariaClasseAcao,
    FreRelacaoFamiliar,
    FreRemuneracaoAcao,
    FreRemuneracaoMaximaMinimaMedia,
    FreRemuneracaoTotalOrgao,
    FreRemuneracaoVariavel,
    FreResponsavel,
    FreTitularValorMobiliario,
    FreTituloExterior,
    FreValorMobiliarioTesourariaMovimentacao,
    FreValorMobiliarioTesourariaUltimoExercicio,
    FreVolumeValorMobiliario,
)
from app.schemas.comum import BrazilianDate, Paginacao
from app.schemas.fre import (
    FreAcaoEntregueResposta,
    FreAdministradorDeclaracaoGeneroResposta,
    FreAdministradorDeclaracaoRacaResposta,
    FreAdministradorPcdResposta,
    FreAuditorResposta,
    FreCapitalSocialClasseAcaoResposta,
    FreCapitalSocialResposta,
    FreCapitalSocialTituloConversivelResposta,
    FreDistribuicaoCapitalClasseAcaoResposta,
    FreDistribuicaoCapitalResposta,
    FreDocumentoResposta,
    FreEmpregadoLocalDeclaracaoGeneroResposta,
    FreEmpregadoLocalDeclaracaoRacaResposta,
    FreEmpregadoLocalFaixaEtariaResposta,
    FreEmpregadoPcdResposta,
    FreEmpregadoPosicaoDeclaracaoRacaResposta,
    FreEmpregadoPosicaoFaixaEtariaResposta,
    FreEmpregadoPosicaoGeneroResposta,
    FreEmpregadoPosicaoLocalResposta,
    FreMercadoEstrangeiroResposta,
    FreOutroValorMobiliarioResposta,
    FreParticipacaoSociedadeResposta,
    FrePlanoRecompraClasseAcaoResposta,
    FrePlanoRecompraResposta,
    FrePosicaoAcionariaClasseAcaoResposta,
    FrePosicaoAcionariaResposta,
    FreRelacaoFamiliarResposta,
    FreRemuneracaoAcaoResposta,
    FreRemuneracaoMaximaMinimaMediaResposta,
    FreRemuneracaoTotalOrgaoResposta,
    FreRemuneracaoVariavelResposta,
    FreResponsavelResposta,
    FreTitularValorMobiliarioResposta,
    FreTituloExteriorResposta,
    FreValorMobiliarioTesourariaMovimentacaoResposta,
    FreValorMobiliarioTesourariaUltimoExercicioResposta,
    FreVolumeValorMobiliarioResposta,
    ListaFreAcoesEntreguesResposta,
    ListaFreAdministradoresDeclaracaoGeneroResposta,
    ListaFreAdministradoresDeclaracaoRacaResposta,
    ListaFreAdministradoresPcdResposta,
    ListaFreAuditoresResposta,
    ListaFreCapitalSocialClassesAcoesResposta,
    ListaFreCapitalSocialResposta,
    ListaFreCapitalSocialTitulosConversiveisResposta,
    ListaFreDistribuicaoCapitalClassesAcoesResposta,
    ListaFreDistribuicaoCapitalResposta,
    ListaFreDocumentosResposta,
    ListaFreEmpregadoLocalDeclaracaoGeneroResposta,
    ListaFreEmpregadoLocalDeclaracaoRacaResposta,
    ListaFreEmpregadoLocalFaixaEtariaResposta,
    ListaFreEmpregadoPcdResposta,
    ListaFreEmpregadoPosicaoDeclaracaoRacaResposta,
    ListaFreEmpregadoPosicaoFaixaEtariaResposta,
    ListaFreEmpregadoPosicaoGeneroResposta,
    ListaFreEmpregadoPosicaoLocalResposta,
    ListaFreMercadosEstrangeirosResposta,
    ListaFreOutrosValoresMobiliariosResposta,
    ListaFreParticipacoesSociedadesResposta,
    ListaFrePlanoRecompraClassesAcoesResposta,
    ListaFrePlanosRecompraResposta,
    ListaFrePosicaoAcionariaResposta,
    ListaFrePosicoesAcionariasClassesAcoesResposta,
    ListaFreRelacoesFamiliaresResposta,
    ListaFreRemuneracaoTotalOrgaoResposta,
    ListaFreRemuneracoesAcoesResposta,
    ListaFreRemuneracoesMaximasMinimasMediasResposta,
    ListaFreRemuneracoesVariaveisResposta,
    ListaFreResponsaveisResposta,
    ListaFreTitularesValoresMobiliariosResposta,
    ListaFreTitulosExteriorResposta,
    ListaFreValoresMobiliariosTesourariaMovimentacoesResposta,
    ListaFreValoresMobiliariosTesourariaUltimosExerciciosResposta,
    ListaFreVolumeValoresMobiliariosResposta,
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
    Query(description="CNPJ da companhia (com ou sem pontuação).", examples=["08.773.135/0001-00"]),
]
ParametroCodigoCvm = Annotated[int | None, Query(description="Código CVM da companhia.", examples=[25224])]
ParametroDataInicio = Annotated[
    BrazilianDate | None,
    Query(description="Data inicial de referência no formato brasileiro (DD/MM/AAAA).", examples=["01/01/2025"]),
]
ParametroDataFim = Annotated[
    BrazilianDate | None,
    Query(description="Data final de referência no formato brasileiro (DD/MM/AAAA).", examples=["31/12/2025"]),
]
ParametroAnoOrigem = Annotated[int | None, Query(description="Ano do ZIP de origem.", examples=[2025])]
ParametroAnoInicio = Annotated[int | None, Query(description="Ano inicial do ZIP/dados de origem.", examples=[2010])]
ParametroAnoFim = Annotated[int | None, Query(description="Ano final do ZIP/dados de origem.", examples=[2020])]
ParametroVersao = Annotated[int | None, Query(description="Versão do documento FRE.", examples=[1])]
ParametroIdDocumento = Annotated[int | None, Query(description="ID do documento FRE.", examples=[12345])]
ParametroIdCapitalSocial = Annotated[int | None, Query(description="Filtrar por ID do Capital Social.", examples=[1])]
ParametroIdAcionista = Annotated[int | None, Query(description="Filtrar por ID do Acionista.", examples=[1])]
ParametroIdSociedade = Annotated[int | None, Query(description="Filtrar por ID da sociedade.", examples=[1])]
ParametroOrgaoAdministracao = Annotated[
    str | None, Query(description="Filtrar por Órgão da Administração.", examples=["Conselho"])
]
ParametroPosicao = Annotated[str | None, Query(description="Filtrar pela posição declarada no FRE.", examples=["Diretoria"])]
ParametroLocal = Annotated[str | None, Query(description="Filtrar pelo local declarado no FRE.", examples=["Brasil"])]
ParametroTipoParentesco = Annotated[
    str | None, Query(description="Filtrar pelo tipo de parentesco declarado no FRE.", examples=["Conjuge"])
]


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
    id_documento: int | None,
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
    if id_documento is not None:
        query = query.where(_col(modelo, "id_documento") == id_documento)
        query_total = query_total.where(_col(modelo, "id_documento") == id_documento)
    return query, query_total


def _aplicar_ordenacao(
    query: Select[Any],
    *,
    modelo: type[Any],
    ordenar_por: str | None,
    campos_permitidos: set[str],
) -> Select[Any]:
    if not ordenar_por:
        return query
    desc = ordenar_por.startswith("-")
    campo = ordenar_por[1:] if desc else ordenar_por
    if campo not in campos_permitidos:
        raise HTTPException(status_code=422, detail=f"Campo invalido para ordenacao: {campo}")
    coluna = _col(modelo, campo)
    return query.order_by(coluna.desc() if desc else coluna.asc())


@router.get(
    "/fre/documentos",
    response_model=ListaFreDocumentosResposta,
    summary="Listar Documentos FRE",
    description="Retorna documentos principais FRE (`fre_cia_aberta_{ano}.csv`).",
    responses=_RESPOSTAS_PADRAO,
    operation_id="listarDocumentosFre",
)
def listar_documentos_fre(
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
    id_documento: ParametroIdDocumento = None,
    ordenar_por: Annotated[
        str | None,
        Query(description="Campos: data_referencia, versao, cnpj_companhia, codigo_cvm, id_documento."),
    ] = "-data_referencia",
) -> ListaFreDocumentosResposta:
    query: Select[Any] = select(FreDocumento)
    query_total = select(func.count()).select_from(FreDocumento)
    query, query_total = _aplicar_filtros_base(
        query,
        query_total,
        modelo=FreDocumento,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        ano_inicio=ano_inicio,
        ano_fim=ano_fim,
        versao=versao,
        id_documento=id_documento,
    )
    if codigo_cvm is not None:
        query = query.where(FreDocumento.codigo_cvm == codigo_cvm)
        query_total = query_total.where(FreDocumento.codigo_cvm == codigo_cvm)
    query = _aplicar_ordenacao(
        query,
        modelo=FreDocumento,
        ordenar_por=ordenar_por,
        campos_permitidos={"data_referencia", "versao", "cnpj_companhia", "codigo_cvm", "id_documento"},
    )
    total = db.scalar(query_total) or 0
    itens = db.execute(query.offset(paginacao.offset).limit(paginacao.tamanho_pagina)).scalars().all()
    return ListaFreDocumentosResposta(
        dados=[FreDocumentoResposta.model_validate(item) for item in itens],
        paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total),
    )


def _lista_fre_generica(
    db: Session,
    *,
    modelo: type[Any],
    schema: type[Any],
    paginacao: PaginacaoQuery,
    cnpj_companhia: str | None,
    codigo_cvm: int | None,
    data_referencia_inicio: date | None,
    data_referencia_fim: date | None,
    ano_origem: int | None,
    versao: int | None,
    id_documento: int | None,
    ordenar_por: str | None,
    campos_permitidos: set[str],
    filtros_adicionais: dict[str, Any] | None = None,
    ano_inicio: int | None = None,
    ano_fim: int | None = None,
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
        versao=versao,
        id_documento=id_documento,
        ano_inicio=ano_inicio,
        ano_fim=ano_fim,
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
    "/fre/auditores",
    response_model=ListaFreAuditoresResposta,
    summary="Listar Auditores FRE",
    description="Retorna registros de auditores (`fre_cia_aberta_auditor_{ano}.csv`).",
    responses=_RESPOSTAS_PADRAO,
    operation_id="listarAuditoresFre",
)
def listar_auditores_fre(
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
    id_documento: ParametroIdDocumento = None,
    ordenar_por: Annotated[
        str | None,
        Query(description="Campos: data_referencia, versao, cnpj_companhia, id_auditor."),
    ] = "-data_referencia",
) -> ListaFreAuditoresResposta:
    dados, total = _lista_fre_generica(
        db,
        modelo=FreAuditor,
        schema=FreAuditorResposta,
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        ano_inicio=ano_inicio,
        ano_fim=ano_fim,
        versao=versao,
        id_documento=id_documento,
        ordenar_por=ordenar_por,
        campos_permitidos={"data_referencia", "versao", "cnpj_companhia", "id_auditor"},
    )
    return ListaFreAuditoresResposta(
        dados=dados,
        paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total),
    )


@router.get(
    "/fre/capital-social",
    response_model=ListaFreCapitalSocialResposta,
    summary="Listar Capital Social FRE",
    description=(
        "Retorna registros de capital social (`fre_cia_aberta_capital_social_{ano}.csv`). "
        "Para exercícios de 2024 em diante, este é um dos quadros públicos ativos que substituem "
        "os detalhamentos descontinuados pela CVM sobre aumentos, reduções e desdobramentos do capital."
    ),
    responses=_RESPOSTAS_PADRAO,
    operation_id="listarCapitalSocialFre",
)
def listar_capital_social_fre(
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
    id_documento: ParametroIdDocumento = None,
    id_capital_social: ParametroIdCapitalSocial = None,
    ordenar_por: Annotated[
        str | None, Query(description="Campos: data_referencia, versao, cnpj_companhia, id_capital_social.")
    ] = "-data_referencia",
) -> ListaFreCapitalSocialResposta:
    dados, total = _lista_fre_generica(
        db,
        modelo=FreCapitalSocial,
        schema=FreCapitalSocialResposta,
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        ano_inicio=ano_inicio,
        ano_fim=ano_fim,
        versao=versao,
        id_documento=id_documento,
        ordenar_por=ordenar_por,
        campos_permitidos={"data_referencia", "versao", "cnpj_companhia", "id_capital_social"},
        filtros_adicionais={"id_capital_social": id_capital_social},
    )
    return ListaFreCapitalSocialResposta(
        dados=dados,
        paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total),
    )


@router.get(
    "/fre/posicao-acionaria",
    response_model=ListaFrePosicaoAcionariaResposta,
    summary="Listar Posição Acionária FRE",
    description="Retorna posição acionária (`fre_cia_aberta_posicao_acionaria_{ano}.csv`).",
    responses=_RESPOSTAS_PADRAO,
    operation_id="listarPosicaoAcionariaFre",
)
def listar_posicao_acionaria_fre(
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
    id_documento: ParametroIdDocumento = None,
    id_acionista: ParametroIdAcionista = None,
    ordenar_por: Annotated[
        str | None,
        Query(description="Campos: data_referencia, versao, cnpj_companhia, id_acionista."),
    ] = "-data_referencia",
) -> ListaFrePosicaoAcionariaResposta:
    dados, total = _lista_fre_generica(
        db,
        modelo=FrePosicaoAcionaria,
        schema=FrePosicaoAcionariaResposta,
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        ano_inicio=ano_inicio,
        ano_fim=ano_fim,
        versao=versao,
        id_documento=id_documento,
        ordenar_por=ordenar_por,
        campos_permitidos={"data_referencia", "versao", "cnpj_companhia", "id_acionista"},
        filtros_adicionais={"id_acionista": id_acionista},
    )
    return ListaFrePosicaoAcionariaResposta(
        dados=dados,
        paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total),
    )


@router.get(
    "/fre/remuneracao/total-por-orgao",
    response_model=ListaFreRemuneracaoTotalOrgaoResposta,
    summary="Listar Remuneração Total por Órgão FRE",
    description=(
        "Retorna remuneração total por órgão de administração (`fre_cia_aberta_remuneracao_total_orgao_{ano}.csv`)."
    ),
    responses=_RESPOSTAS_PADRAO,
    operation_id="listarRemuneracaoTotalOrgaoFre",
)
def listar_remuneracao_total_orgao_fre(
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
    id_documento: ParametroIdDocumento = None,
    orgao_administracao: ParametroOrgaoAdministracao = None,
    ordenar_por: Annotated[
        str | None, Query(description="Campos: data_referencia, versao, cnpj_companhia, orgao_administracao.")
    ] = "-data_referencia",
) -> ListaFreRemuneracaoTotalOrgaoResposta:
    dados, total = _lista_fre_generica(
        db,
        modelo=FreRemuneracaoTotalOrgao,
        schema=FreRemuneracaoTotalOrgaoResposta,
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        ano_inicio=ano_inicio,
        ano_fim=ano_fim,
        versao=versao,
        id_documento=id_documento,
        ordenar_por=ordenar_por,
        campos_permitidos={"data_referencia", "versao", "cnpj_companhia", "orgao_administracao"},
        filtros_adicionais={"orgao_administracao": orgao_administracao},
    )
    return ListaFreRemuneracaoTotalOrgaoResposta(
        dados=dados,
        paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total),
    )


@router.get(
    "/fre/empregados/posicao-genero",
    response_model=ListaFreEmpregadoPosicaoGeneroResposta,
    summary="Listar Empregados por Posição e Gênero FRE",
    description=(
        "Retorna distribuição de empregados por posição e gênero "
        "(`fre_cia_aberta_empregado_posicao_declaracao_genero_{ano}.csv`)."
    ),
    responses=_RESPOSTAS_PADRAO,
    operation_id="listarEmpregadosPosicaoGeneroFre",
)
def listar_empregados_posicao_genero_fre(
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
    id_documento: ParametroIdDocumento = None,
    ordenar_por: Annotated[
        str | None, Query(description="Campos: data_referencia, versao, cnpj_companhia, posicao.")
    ] = "-data_referencia",
) -> ListaFreEmpregadoPosicaoGeneroResposta:
    dados, total = _lista_fre_generica(
        db,
        modelo=FreEmpregadoPosicaoGenero,
        schema=FreEmpregadoPosicaoGeneroResposta,
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        ano_inicio=ano_inicio,
        ano_fim=ano_fim,
        versao=versao,
        id_documento=id_documento,
        ordenar_por=ordenar_por,
        campos_permitidos={"data_referencia", "versao", "cnpj_companhia", "posicao"},
    )
    return ListaFreEmpregadoPosicaoGeneroResposta(
        dados=dados,
        paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total),
    )


@router.get(
    "/fre/participacoes-sociedades",
    response_model=ListaFreParticipacoesSociedadesResposta,
    summary="Listar Participações em Sociedades FRE",
    description="Retorna participações em sociedades do FRE (`fre_cia_aberta_participacao_sociedade_{ano}.csv`).",
    responses=_RESPOSTAS_PADRAO,
    operation_id="listarParticipacoesSociedadesFre",
)
def listar_participacoes_sociedades_fre(
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
    id_documento: ParametroIdDocumento = None,
    id_sociedade: ParametroIdSociedade = None,
    ordenar_por: Annotated[
        str | None, Query(description="Campos: data_referencia, versao, cnpj_companhia, id_sociedade, codigo_cvm.")
    ] = "-data_referencia",
) -> ListaFreParticipacoesSociedadesResposta:
    dados, total = _lista_fre_generica(
        db,
        modelo=FreParticipacaoSociedade,
        schema=FreParticipacaoSociedadeResposta,
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        ano_inicio=ano_inicio,
        ano_fim=ano_fim,
        versao=versao,
        id_documento=id_documento,
        ordenar_por=ordenar_por,
        campos_permitidos={"data_referencia", "versao", "cnpj_companhia", "id_sociedade", "codigo_cvm"},
        filtros_adicionais={"id_sociedade": id_sociedade},
    )
    return ListaFreParticipacoesSociedadesResposta(
        dados=dados,
        paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total),
    )


@router.get(
    "/fre/relacoes-familiares",
    response_model=ListaFreRelacoesFamiliaresResposta,
    summary="Listar Relações Familiares FRE",
    description="Retorna relações familiares declaradas no FRE (`fre_cia_aberta_relacao_familiar_{ano}.csv`).",
    responses=_RESPOSTAS_PADRAO,
    operation_id="listarRelacoesFamiliaresFre",
)
def listar_relacoes_familiares_fre(
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
    id_documento: ParametroIdDocumento = None,
    tipo_parentesco: ParametroTipoParentesco = None,
    ordenar_por: Annotated[
        str | None, Query(description="Campos: data_referencia, versao, cnpj_companhia, nome_administrador, nome_pessoa_relacionada, tipo_parentesco.")
    ] = "-data_referencia",
) -> ListaFreRelacoesFamiliaresResposta:
    dados, total = _lista_fre_generica(
        db,
        modelo=FreRelacaoFamiliar,
        schema=FreRelacaoFamiliarResposta,
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        ano_inicio=ano_inicio,
        ano_fim=ano_fim,
        versao=versao,
        id_documento=id_documento,
        ordenar_por=ordenar_por,
        campos_permitidos={"data_referencia", "versao", "cnpj_companhia", "nome_administrador", "nome_pessoa_relacionada", "tipo_parentesco"},
        filtros_adicionais={"tipo_parentesco": tipo_parentesco},
    )
    return ListaFreRelacoesFamiliaresResposta(
        dados=dados,
        paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total),
    )


@router.get(
    "/fre/empregados/posicao-local",
    response_model=ListaFreEmpregadoPosicaoLocalResposta,
    summary="Listar Empregados por Posição e Local FRE",
    description="Retorna distribuição de empregados por posição e local (`fre_cia_aberta_empregado_posicao_local_{ano}.csv`).",
    responses=_RESPOSTAS_PADRAO,
    operation_id="listarEmpregadosPosicaoLocalFre",
)
def listar_empregados_posicao_local_fre(
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
    id_documento: ParametroIdDocumento = None,
    posicao: ParametroPosicao = None,
    ordenar_por: Annotated[
        str | None, Query(description="Campos: data_referencia, versao, cnpj_companhia, posicao.")
    ] = "-data_referencia",
) -> ListaFreEmpregadoPosicaoLocalResposta:
    dados, total = _lista_fre_generica(
        db,
        modelo=FreEmpregadoPosicaoLocal,
        schema=FreEmpregadoPosicaoLocalResposta,
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        ano_inicio=ano_inicio,
        ano_fim=ano_fim,
        versao=versao,
        id_documento=id_documento,
        ordenar_por=ordenar_por,
        campos_permitidos={"data_referencia", "versao", "cnpj_companhia", "posicao"},
        filtros_adicionais={"posicao": posicao},
    )
    return ListaFreEmpregadoPosicaoLocalResposta(
        dados=dados,
        paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total),
    )


@router.get(
    "/fre/empregados/posicao-faixa-etaria",
    response_model=ListaFreEmpregadoPosicaoFaixaEtariaResposta,
    summary="Listar Empregados por Posição e Faixa Etária FRE",
    description="Retorna distribuição de empregados por posição e faixa etária (`fre_cia_aberta_empregado_posicao_faixa_etaria_{ano}.csv`).",
    responses=_RESPOSTAS_PADRAO,
    operation_id="listarEmpregadosPosicaoFaixaEtariaFre",
)
def listar_empregados_posicao_faixa_etaria_fre(
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
    id_documento: ParametroIdDocumento = None,
    posicao: ParametroPosicao = None,
    ordenar_por: Annotated[
        str | None, Query(description="Campos: data_referencia, versao, cnpj_companhia, posicao.")
    ] = "-data_referencia",
) -> ListaFreEmpregadoPosicaoFaixaEtariaResposta:
    dados, total = _lista_fre_generica(
        db,
        modelo=FreEmpregadoPosicaoFaixaEtaria,
        schema=FreEmpregadoPosicaoFaixaEtariaResposta,
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        ano_inicio=ano_inicio,
        ano_fim=ano_fim,
        versao=versao,
        id_documento=id_documento,
        ordenar_por=ordenar_por,
        campos_permitidos={"data_referencia", "versao", "cnpj_companhia", "posicao"},
        filtros_adicionais={"posicao": posicao},
    )
    return ListaFreEmpregadoPosicaoFaixaEtariaResposta(
        dados=dados,
        paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total),
    )


@router.get(
    "/fre/empregados/posicao-declaracao-raca",
    response_model=ListaFreEmpregadoPosicaoDeclaracaoRacaResposta,
    summary="Listar Empregados por Posição e Declaração de Raça FRE",
    description="Retorna distribuição de empregados por posição e declaração de raça (`fre_cia_aberta_empregado_posicao_declaracao_raca_{ano}.csv`).",
    responses=_RESPOSTAS_PADRAO,
    operation_id="listarEmpregadosPosicaoDeclaracaoRacaFre",
)
def listar_empregados_posicao_declaracao_raca_fre(
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
    id_documento: ParametroIdDocumento = None,
    posicao: ParametroPosicao = None,
    ordenar_por: Annotated[
        str | None, Query(description="Campos: data_referencia, versao, cnpj_companhia, posicao.")
    ] = "-data_referencia",
) -> ListaFreEmpregadoPosicaoDeclaracaoRacaResposta:
    dados, total = _lista_fre_generica(
        db,
        modelo=FreEmpregadoPosicaoDeclaracaoRaca,
        schema=FreEmpregadoPosicaoDeclaracaoRacaResposta,
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        ano_inicio=ano_inicio,
        ano_fim=ano_fim,
        versao=versao,
        id_documento=id_documento,
        ordenar_por=ordenar_por,
        campos_permitidos={"data_referencia", "versao", "cnpj_companhia", "posicao"},
        filtros_adicionais={"posicao": posicao},
    )
    return ListaFreEmpregadoPosicaoDeclaracaoRacaResposta(
        dados=dados,
        paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total),
    )


@router.get(
    "/fre/empregados/pcd",
    response_model=ListaFreEmpregadoPcdResposta,
    summary="Listar Empregados PCD FRE",
    description="Retorna distribuição de empregados PCD (`fre_cia_aberta_empregado_PCD_{ano}.csv`).",
    responses=_RESPOSTAS_PADRAO,
    operation_id="listarEmpregadosPcdFre",
)
def listar_empregados_pcd_fre(
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
    id_documento: ParametroIdDocumento = None,
    posicao: ParametroPosicao = None,
    ordenar_por: Annotated[
        str | None, Query(description="Campos: data_referencia, versao, cnpj_companhia, codigo_posicao, posicao.")
    ] = "-data_referencia",
) -> ListaFreEmpregadoPcdResposta:
    dados, total = _lista_fre_generica(
        db,
        modelo=FreEmpregadoPcd,
        schema=FreEmpregadoPcdResposta,
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        ano_inicio=ano_inicio,
        ano_fim=ano_fim,
        versao=versao,
        id_documento=id_documento,
        ordenar_por=ordenar_por,
        campos_permitidos={"data_referencia", "versao", "cnpj_companhia", "codigo_posicao", "posicao"},
        filtros_adicionais={"posicao": posicao},
    )
    return ListaFreEmpregadoPcdResposta(
        dados=dados,
        paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total),
    )


@router.get(
    "/fre/empregados/local-faixa-etaria",
    response_model=ListaFreEmpregadoLocalFaixaEtariaResposta,
    summary="Listar Empregados por Local e Faixa Etária FRE",
    description="Retorna distribuição de empregados por local e faixa etária (`fre_cia_aberta_empregado_local_faixa_etaria_{ano}.csv`).",
    responses=_RESPOSTAS_PADRAO,
    operation_id="listarEmpregadosLocalFaixaEtariaFre",
)
def listar_empregados_local_faixa_etaria_fre(
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
    id_documento: ParametroIdDocumento = None,
    local: ParametroLocal = None,
    ordenar_por: Annotated[
        str | None, Query(description="Campos: data_referencia, versao, cnpj_companhia, local.")
    ] = "-data_referencia",
) -> ListaFreEmpregadoLocalFaixaEtariaResposta:
    dados, total = _lista_fre_generica(
        db,
        modelo=FreEmpregadoLocalFaixaEtaria,
        schema=FreEmpregadoLocalFaixaEtariaResposta,
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        ano_inicio=ano_inicio,
        ano_fim=ano_fim,
        versao=versao,
        id_documento=id_documento,
        ordenar_por=ordenar_por,
        campos_permitidos={"data_referencia", "versao", "cnpj_companhia", "local"},
        filtros_adicionais={"local": local},
    )
    return ListaFreEmpregadoLocalFaixaEtariaResposta(
        dados=dados,
        paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total),
    )


@router.get(
    "/fre/empregados/local-declaracao-raca",
    response_model=ListaFreEmpregadoLocalDeclaracaoRacaResposta,
    summary="Listar Empregados por Local e Declaração de Raça FRE",
    description="Retorna distribuição de empregados por local e declaração de raça (`fre_cia_aberta_empregado_local_declaracao_raca_{ano}.csv`).",
    responses=_RESPOSTAS_PADRAO,
    operation_id="listarEmpregadosLocalDeclaracaoRacaFre",
)
def listar_empregados_local_declaracao_raca_fre(
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
    id_documento: ParametroIdDocumento = None,
    local: ParametroLocal = None,
    ordenar_por: Annotated[
        str | None, Query(description="Campos: data_referencia, versao, cnpj_companhia, local.")
    ] = "-data_referencia",
) -> ListaFreEmpregadoLocalDeclaracaoRacaResposta:
    dados, total = _lista_fre_generica(
        db,
        modelo=FreEmpregadoLocalDeclaracaoRaca,
        schema=FreEmpregadoLocalDeclaracaoRacaResposta,
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        ano_inicio=ano_inicio,
        ano_fim=ano_fim,
        versao=versao,
        id_documento=id_documento,
        ordenar_por=ordenar_por,
        campos_permitidos={"data_referencia", "versao", "cnpj_companhia", "local"},
        filtros_adicionais={"local": local},
    )
    return ListaFreEmpregadoLocalDeclaracaoRacaResposta(
        dados=dados,
        paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total),
    )


@router.get(
    "/fre/empregados/local-declaracao-genero",
    response_model=ListaFreEmpregadoLocalDeclaracaoGeneroResposta,
    summary="Listar Empregados por Local e Declaração de Gênero FRE",
    description="Retorna distribuição de empregados por local e declaração de gênero (`fre_cia_aberta_empregado_local_declaracao_genero_{ano}.csv`).",
    responses=_RESPOSTAS_PADRAO,
    operation_id="listarEmpregadosLocalDeclaracaoGeneroFre",
)
def listar_empregados_local_declaracao_genero_fre(
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
    id_documento: ParametroIdDocumento = None,
    local: ParametroLocal = None,
    ordenar_por: Annotated[
        str | None, Query(description="Campos: data_referencia, versao, cnpj_companhia, local.")
    ] = "-data_referencia",
) -> ListaFreEmpregadoLocalDeclaracaoGeneroResposta:
    dados, total = _lista_fre_generica(
        db,
        modelo=FreEmpregadoLocalDeclaracaoGenero,
        schema=FreEmpregadoLocalDeclaracaoGeneroResposta,
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        ano_inicio=ano_inicio,
        ano_fim=ano_fim,
        versao=versao,
        id_documento=id_documento,
        ordenar_por=ordenar_por,
        campos_permitidos={"data_referencia", "versao", "cnpj_companhia", "local"},
        filtros_adicionais={"local": local},
    )
    return ListaFreEmpregadoLocalDeclaracaoGeneroResposta(
        dados=dados,
        paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total),
    )


@router.get(
    "/fre/responsaveis",
    response_model=ListaFreResponsaveisResposta,
    summary="Listar Responsáveis FRE",
    description="Retorna responsáveis pelo documento FRE (`fre_cia_aberta_responsavel_{ano}.csv`).",
    responses=_RESPOSTAS_PADRAO,
    operation_id="listarResponsaveisFre",
)
def listar_responsaveis_fre(
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
    id_documento: ParametroIdDocumento = None,
    ordenar_por: Annotated[
        str | None, Query(description="Campos: data_referencia, versao, cnpj_companhia, nome_responsavel.")
    ] = "-data_referencia",
) -> ListaFreResponsaveisResposta:
    dados, total = _lista_fre_generica(
        db,
        modelo=FreResponsavel,
        schema=FreResponsavelResposta,
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        ano_inicio=ano_inicio,
        ano_fim=ano_fim,
        versao=versao,
        id_documento=id_documento,
        ordenar_por=ordenar_por,
        campos_permitidos={"data_referencia", "versao", "cnpj_companhia", "nome_responsavel"},
    )
    return ListaFreResponsaveisResposta(
        dados=dados,
        paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total),
    )


@router.get(
    "/fre/capital-social-classes-acoes",
    response_model=ListaFreCapitalSocialClassesAcoesResposta,
    summary="Listar Classes de Ações do Capital Social FRE",
    description=(
        "Retorna classes de ações do capital social FRE (`fre_cia_aberta_capital_social_classe_acao_{ano}.csv`). "
        "Para exercícios de 2024 em diante, este quadro deve ser usado em conjunto com `/fre/capital-social` "
        "e `/fre/distribuicao-capital` para analisar a composição atualizada do capital."
    ),
    responses=_RESPOSTAS_PADRAO,
    operation_id="listarCapitalSocialClassesAcoesFre",
)
def listar_capital_social_classes_acoes_fre(
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
    id_documento: ParametroIdDocumento = None,
    id_capital_social: ParametroIdCapitalSocial = None,
    ordenar_por: Annotated[
        str | None, Query(description="Campos: data_referencia, versao, cnpj_companhia, id_capital_social.")
    ] = "-data_referencia",
) -> ListaFreCapitalSocialClassesAcoesResposta:
    dados, total = _lista_fre_generica(
        db,
        modelo=FreCapitalSocialClasseAcao,
        schema=FreCapitalSocialClasseAcaoResposta,
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        ano_inicio=ano_inicio,
        ano_fim=ano_fim,
        versao=versao,
        id_documento=id_documento,
        ordenar_por=ordenar_por,
        campos_permitidos={"data_referencia", "versao", "cnpj_companhia", "id_capital_social"},
        filtros_adicionais={"id_capital_social": id_capital_social},
    )
    return ListaFreCapitalSocialClassesAcoesResposta(
        dados=dados,
        paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total),
    )


@router.get(
    "/fre/capital-social-titulos-conversiveis",
    response_model=ListaFreCapitalSocialTitulosConversiveisResposta,
    summary="Listar Títulos Conversíveis do Capital Social FRE",
    description=(
        "Retorna títulos conversíveis em ações do capital social "
        "(`fre_cia_aberta_capital_social_titulo_conversivel_{ano}.csv`)."
    ),
    responses=_RESPOSTAS_PADRAO,
    operation_id="listarCapitalSocialTitulosConversiveisFre",
)
def listar_capital_social_titulos_conversiveis_fre(
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
    id_documento: ParametroIdDocumento = None,
    id_capital_social: ParametroIdCapitalSocial = None,
    ordenar_por: Annotated[
        str | None, Query(description="Campos: data_referencia, versao, cnpj_companhia, id_capital_social.")
    ] = "-data_referencia",
) -> ListaFreCapitalSocialTitulosConversiveisResposta:
    dados, total = _lista_fre_generica(
        db,
        modelo=FreCapitalSocialTituloConversivel,
        schema=FreCapitalSocialTituloConversivelResposta,
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        ano_inicio=ano_inicio,
        ano_fim=ano_fim,
        versao=versao,
        id_documento=id_documento,
        ordenar_por=ordenar_por,
        campos_permitidos={"data_referencia", "versao", "cnpj_companhia", "id_capital_social"},
        filtros_adicionais={"id_capital_social": id_capital_social},
    )
    return ListaFreCapitalSocialTitulosConversiveisResposta(
        dados=dados,
        paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total),
    )


@router.get(
    "/fre/distribuicao-capital",
    response_model=ListaFreDistribuicaoCapitalResposta,
    summary="Listar Distribuição de Capital FRE",
    description=(
        "Retorna distribuição de capital FRE (`fre_cia_aberta_distribuicao_capital_{ano}.csv`). "
        "Para exercícios de 2024 em diante, este é um dos quadros ativos recomendados para consultar a "
        "posição atualizada do capital após a descontinuação, pela CVM, dos membros específicos de "
        "aumentos, reduções e desdobramentos."
    ),
    responses=_RESPOSTAS_PADRAO,
    operation_id="listarDistribuicaoCapitalFre",
)
def listar_distribuicao_capital_fre(
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
    id_documento: ParametroIdDocumento = None,
    ordenar_por: Annotated[
        str | None, Query(description="Campos: data_referencia, versao, cnpj_companhia.")
    ] = "-data_referencia",
) -> ListaFreDistribuicaoCapitalResposta:
    dados, total = _lista_fre_generica(
        db,
        modelo=FreDistribuicaoCapital,
        schema=FreDistribuicaoCapitalResposta,
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        ano_inicio=ano_inicio,
        ano_fim=ano_fim,
        versao=versao,
        id_documento=id_documento,
        ordenar_por=ordenar_por,
        campos_permitidos={"data_referencia", "versao", "cnpj_companhia"},
    )
    return ListaFreDistribuicaoCapitalResposta(
        dados=dados,
        paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total),
    )


@router.get(
    "/fre/distribuicao-capital-classes-acoes",
    response_model=ListaFreDistribuicaoCapitalClassesAcoesResposta,
    summary="Listar Classes de Ações da Distribuição de Capital FRE",
    description=(
        "Retorna classes de ações preferenciais da distribuição de capital FRE "
        "(`fre_cia_aberta_distribuicao_capital_classe_acao_{ano}.csv`)."
    ),
    responses=_RESPOSTAS_PADRAO,
    operation_id="listarDistribuicaoCapitalClassesAcoesFre",
)
def listar_distribuicao_capital_classes_acoes_fre(
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
    id_documento: ParametroIdDocumento = None,
    ordenar_por: Annotated[
        str | None,
        Query(description="Campos: data_referencia, versao, cnpj_companhia, sigla_classe_acoes_preferenciais."),
    ] = "-data_referencia",
) -> ListaFreDistribuicaoCapitalClassesAcoesResposta:
    dados, total = _lista_fre_generica(
        db,
        modelo=FreDistribuicaoCapitalClasseAcao,
        schema=FreDistribuicaoCapitalClasseAcaoResposta,
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        ano_inicio=ano_inicio,
        ano_fim=ano_fim,
        versao=versao,
        id_documento=id_documento,
        ordenar_por=ordenar_por,
        campos_permitidos={"data_referencia", "versao", "cnpj_companhia", "sigla_classe_acoes_preferenciais"},
    )
    return ListaFreDistribuicaoCapitalClassesAcoesResposta(
        dados=dados,
        paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total),
    )


@router.get(
    "/fre/posicoes-acionarias-classes-acoes",
    response_model=ListaFrePosicoesAcionariasClassesAcoesResposta,
    summary="Listar Classes de Ações da Posição Acionária FRE",
    description=(
        "Retorna classes de ações preferenciais da posição acionária FRE "
        "(`fre_cia_aberta_posicao_acionaria_classe_acao_{ano}.csv`)."
    ),
    responses=_RESPOSTAS_PADRAO,
    operation_id="listarPosicoesAcionariasClassesAcoesFre",
)
def listar_posicoes_acionarias_classes_acoes_fre(
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
    id_documento: ParametroIdDocumento = None,
    id_acionista: ParametroIdAcionista = None,
    ordenar_por: Annotated[
        str | None, Query(description="Campos: data_referencia, versao, cnpj_companhia, id_acionista.")
    ] = "-data_referencia",
) -> ListaFrePosicoesAcionariasClassesAcoesResposta:
    dados, total = _lista_fre_generica(
        db,
        modelo=FrePosicaoAcionariaClasseAcao,
        schema=FrePosicaoAcionariaClasseAcaoResposta,
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        ano_inicio=ano_inicio,
        ano_fim=ano_fim,
        versao=versao,
        id_documento=id_documento,
        ordenar_por=ordenar_por,
        campos_permitidos={"data_referencia", "versao", "cnpj_companhia", "id_acionista"},
        filtros_adicionais={"id_acionista": id_acionista},
    )
    return ListaFrePosicoesAcionariasClassesAcoesResposta(
        dados=dados,
        paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total),
    )


@router.get(
    "/fre/remuneracoes-maximas-minimas-medias",
    response_model=ListaFreRemuneracoesMaximasMinimasMediasResposta,
    summary="Listar Remunerações Máximas, Mínimas e Médias FRE",
    description=(
        "Retorna remunerações máximas, mínimas e médias por órgão de administração "
        "(`fre_cia_aberta_remuneracao_maxima_minima_media_{ano}.csv`)."
    ),
    responses=_RESPOSTAS_PADRAO,
    operation_id="listarRemuneracoesMaximasMinimasMediasFre",
)
def listar_remuneracoes_maximas_minimas_medias_fre(
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
    id_documento: ParametroIdDocumento = None,
    orgao_administracao: ParametroOrgaoAdministracao = None,
    ordenar_por: Annotated[
        str | None, Query(description="Campos: data_referencia, versao, cnpj_companhia, orgao_administracao.")
    ] = "-data_referencia",
) -> ListaFreRemuneracoesMaximasMinimasMediasResposta:
    dados, total = _lista_fre_generica(
        db,
        modelo=FreRemuneracaoMaximaMinimaMedia,
        schema=FreRemuneracaoMaximaMinimaMediaResposta,
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        ano_inicio=ano_inicio,
        ano_fim=ano_fim,
        versao=versao,
        id_documento=id_documento,
        ordenar_por=ordenar_por,
        campos_permitidos={"data_referencia", "versao", "cnpj_companhia", "orgao_administracao"},
        filtros_adicionais={"orgao_administracao": orgao_administracao},
    )
    return ListaFreRemuneracoesMaximasMinimasMediasResposta(
        dados=dados,
        paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total),
    )


@router.get(
    "/fre/remuneracoes-variaveis",
    response_model=ListaFreRemuneracoesVariaveisResposta,
    summary="Listar Remunerações Variáveis FRE",
    description="Retorna remunerações variáveis do FRE (`fre_cia_aberta_remuneracao_variavel_{ano}.csv`).",
    responses=_RESPOSTAS_PADRAO,
    operation_id="listarRemuneracoesVariaveisFre",
)
def listar_remuneracoes_variaveis_fre(
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
    id_documento: ParametroIdDocumento = None,
    orgao_administracao: ParametroOrgaoAdministracao = None,
    ordenar_por: Annotated[
        str | None, Query(description="Campos: data_referencia, versao, cnpj_companhia, orgao_administracao.")
    ] = "-data_referencia",
) -> ListaFreRemuneracoesVariaveisResposta:
    dados, total = _lista_fre_generica(
        db,
        modelo=FreRemuneracaoVariavel,
        schema=FreRemuneracaoVariavelResposta,
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        ano_inicio=ano_inicio,
        ano_fim=ano_fim,
        versao=versao,
        id_documento=id_documento,
        ordenar_por=ordenar_por,
        campos_permitidos={"data_referencia", "versao", "cnpj_companhia", "orgao_administracao"},
        filtros_adicionais={"orgao_administracao": orgao_administracao},
    )
    return ListaFreRemuneracoesVariaveisResposta(
        dados=dados,
        paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total),
    )


@router.get(
    "/fre/remuneracoes-acoes",
    response_model=ListaFreRemuneracoesAcoesResposta,
    summary="Listar Remunerações Baseadas em Ações FRE",
    description="Retorna remunerações baseadas em ações do FRE (`fre_cia_aberta_remuneracao_acao_{ano}.csv`).",
    responses=_RESPOSTAS_PADRAO,
    operation_id="listarRemuneracoesAcoesFre",
)
def listar_remuneracoes_acoes_fre(
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
    id_documento: ParametroIdDocumento = None,
    orgao_administracao: ParametroOrgaoAdministracao = None,
    ordenar_por: Annotated[
        str | None, Query(description="Campos: data_referencia, versao, cnpj_companhia, orgao_administracao.")
    ] = "-data_referencia",
) -> ListaFreRemuneracoesAcoesResposta:
    dados, total = _lista_fre_generica(
        db,
        modelo=FreRemuneracaoAcao,
        schema=FreRemuneracaoAcaoResposta,
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        ano_inicio=ano_inicio,
        ano_fim=ano_fim,
        versao=versao,
        id_documento=id_documento,
        ordenar_por=ordenar_por,
        campos_permitidos={"data_referencia", "versao", "cnpj_companhia", "orgao_administracao"},
        filtros_adicionais={"orgao_administracao": orgao_administracao},
    )
    return ListaFreRemuneracoesAcoesResposta(
        dados=dados,
        paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total),
    )


@router.get(
    "/fre/acoes-entregues",
    response_model=ListaFreAcoesEntreguesResposta,
    summary="Listar Ações Entregues FRE",
    description=(
        "Retorna ações entregues aos órgãos de administração do FRE (`fre_cia_aberta_acao_entregue_{ano}.csv`)."
    ),
    responses=_RESPOSTAS_PADRAO,
    operation_id="listarAcoesEntreguesFre",
)
def listar_acoes_entregues_fre(
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
    id_documento: ParametroIdDocumento = None,
    orgao_administracao: ParametroOrgaoAdministracao = None,
    ordenar_por: Annotated[
        str | None, Query(description="Campos: data_referencia, versao, cnpj_companhia, orgao_administracao.")
    ] = "-data_referencia",
) -> ListaFreAcoesEntreguesResposta:
    dados, total = _lista_fre_generica(
        db,
        modelo=FreAcaoEntregue,
        schema=FreAcaoEntregueResposta,
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        ano_inicio=ano_inicio,
        ano_fim=ano_fim,
        versao=versao,
        id_documento=id_documento,
        ordenar_por=ordenar_por,
        campos_permitidos={"data_referencia", "versao", "cnpj_companhia", "orgao_administracao"},
        filtros_adicionais={"orgao_administracao": orgao_administracao},
    )
    return ListaFreAcoesEntreguesResposta(
        dados=dados,
        paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total),
    )


@router.get(
    "/fre/volume-valor-mobiliario",
    response_model=ListaFreVolumeValoresMobiliariosResposta,
    summary="Listar Volume de Negociação de Valores Mobiliários FRE",
    description="Retorna dados de volume de negociação de valores mobiliários (`fre_cia_aberta_volume_valor_mobiliario_{ano}.csv`).",
    responses=_RESPOSTAS_PADRAO,
    operation_id="listarVolumeValorMobiliarioFre",
)
def listar_volume_valor_mobiliario_fre(
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
    id_documento: ParametroIdDocumento = None,
    ordenar_por: Annotated[
        str | None, Query(description="Campos: data_referencia, versao, cnpj_companhia, classe_valor_mobiliario.")
    ] = "-data_referencia",
) -> ListaFreVolumeValoresMobiliariosResposta:
    dados, total = _lista_fre_generica(
        db,
        modelo=FreVolumeValorMobiliario,
        schema=FreVolumeValorMobiliarioResposta,
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        ano_inicio=ano_inicio,
        ano_fim=ano_fim,
        versao=versao,
        id_documento=id_documento,
        ordenar_por=ordenar_por,
        campos_permitidos={"data_referencia", "versao", "cnpj_companhia", "classe_valor_mobiliario"},
    )
    return ListaFreVolumeValoresMobiliariosResposta(
        dados=dados,
        paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total),
    )


@router.get(
    "/fre/outro-valor-mobiliario",
    response_model=ListaFreOutrosValoresMobiliariosResposta,
    summary="Listar Outros Valores Mobiliários FRE",
    description="Retorna outros valores mobiliários emitidos (`fre_cia_aberta_outro_valor_mobiliario_{ano}.csv`).",
    responses=_RESPOSTAS_PADRAO,
    operation_id="listarOutroValorMobiliarioFre",
)
def listar_outro_valor_mobiliario_fre(
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
    id_documento: ParametroIdDocumento = None,
    ordenar_por: Annotated[
        str | None, Query(description="Campos: data_referencia, versao, cnpj_companhia, nome_valor_mobiliario.")
    ] = "-data_referencia",
) -> ListaFreOutrosValoresMobiliariosResposta:
    dados, total = _lista_fre_generica(
        db,
        modelo=FreOutroValorMobiliario,
        schema=FreOutroValorMobiliarioResposta,
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        ano_inicio=ano_inicio,
        ano_fim=ano_fim,
        versao=versao,
        id_documento=id_documento,
        ordenar_por=ordenar_por,
        campos_permitidos={"data_referencia", "versao", "cnpj_companhia", "nome_valor_mobiliario"},
    )
    return ListaFreOutrosValoresMobiliariosResposta(
        dados=dados,
        paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total),
    )


@router.get(
    "/fre/titular-valor-mobiliario",
    response_model=ListaFreTitularesValoresMobiliariosResposta,
    summary="Listar Titulares de Valores Mobiliários FRE",
    description="Retorna titulares de valores mobiliários (`fre_cia_aberta_titular_valor_mobiliario_{ano}.csv`).",
    responses=_RESPOSTAS_PADRAO,
    operation_id="listarTitularValorMobiliarioFre",
)
def listar_titular_valor_mobiliario_fre(
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
    id_documento: ParametroIdDocumento = None,
    ordenar_por: Annotated[
        str | None, Query(description="Campos: data_referencia, versao, cnpj_companhia, nome_titular, classe_valor_mobiliario.")
    ] = "-data_referencia",
) -> ListaFreTitularesValoresMobiliariosResposta:
    dados, total = _lista_fre_generica(
        db,
        modelo=FreTitularValorMobiliario,
        schema=FreTitularValorMobiliarioResposta,
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        ano_inicio=ano_inicio,
        ano_fim=ano_fim,
        versao=versao,
        id_documento=id_documento,
        ordenar_por=ordenar_por,
        campos_permitidos={"data_referencia", "versao", "cnpj_companhia", "nome_titular", "classe_valor_mobiliario"},
    )
    return ListaFreTitularesValoresMobiliariosResposta(
        dados=dados,
        paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total),
    )


@router.get(
    "/fre/mercado-estrangeiro",
    response_model=ListaFreMercadosEstrangeirosResposta,
    summary="Listar Mercados Estrangeiros FRE",
    description="Retorna admissão de negociação em mercados estrangeiros (`fre_cia_aberta_mercado_estrangeiro_{ano}.csv`).",
    responses=_RESPOSTAS_PADRAO,
    operation_id="listarMercadoEstrangeiroFre",
)
def listar_mercado_estrangeiro_fre(
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
    id_documento: ParametroIdDocumento = None,
    ordenar_por: Annotated[
        str | None, Query(description="Campos: data_referencia, versao, cnpj_companhia, nome_mercado.")
    ] = "-data_referencia",
) -> ListaFreMercadosEstrangeirosResposta:
    dados, total = _lista_fre_generica(
        db,
        modelo=FreMercadoEstrangeiro,
        schema=FreMercadoEstrangeiroResposta,
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        ano_inicio=ano_inicio,
        ano_fim=ano_fim,
        versao=versao,
        id_documento=id_documento,
        ordenar_por=ordenar_por,
        campos_permitidos={"data_referencia", "versao", "cnpj_companhia", "nome_mercado"},
    )
    return ListaFreMercadosEstrangeirosResposta(
        dados=dados,
        paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total),
    )


@router.get(
    "/fre/titulo-exterior",
    response_model=ListaFreTitulosExteriorResposta,
    summary="Listar Títulos no Exterior FRE",
    description="Retorna títulos emitidos no exterior (`fre_cia_aberta_titulo_exterior_{ano}.csv`).",
    responses=_RESPOSTAS_PADRAO,
    operation_id="listarTituloExteriorFre",
)
def listar_titulo_exterior_fre(
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
    id_documento: ParametroIdDocumento = None,
    ordenar_por: Annotated[
        str | None, Query(description="Campos: data_referencia, versao, cnpj_companhia, nome_titulo.")
    ] = "-data_referencia",
) -> ListaFreTitulosExteriorResposta:
    dados, total = _lista_fre_generica(
        db,
        modelo=FreTituloExterior,
        schema=FreTituloExteriorResposta,
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        ano_inicio=ano_inicio,
        ano_fim=ano_fim,
        versao=versao,
        id_documento=id_documento,
        ordenar_por=ordenar_por,
        campos_permitidos={"data_referencia", "versao", "cnpj_companhia", "nome_titulo"},
    )
    return ListaFreTitulosExteriorResposta(
        dados=dados,
        paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total),
    )


@router.get(
    "/fre/plano-recompra",
    response_model=ListaFrePlanosRecompraResposta,
    summary="Listar Planos de Recompra FRE",
    description="Retorna planos de recompra de ações do FRE (`fre_cia_aberta_plano_recompra_{ano}.csv`).",
    responses=_RESPOSTAS_PADRAO,
    operation_id="listarPlanoRecompraFre",
)
def listar_plano_recompra_fre(
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
    id_documento: ParametroIdDocumento = None,
    ordenar_por: Annotated[
        str | None, Query(description="Campos: data_referencia, versao, cnpj_companhia, id_plano_recompra.")
    ] = "-data_referencia",
) -> ListaFrePlanosRecompraResposta:
    dados, total = _lista_fre_generica(
        db,
        modelo=FrePlanoRecompra,
        schema=FrePlanoRecompraResposta,
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        ano_inicio=ano_inicio,
        ano_fim=ano_fim,
        versao=versao,
        id_documento=id_documento,
        ordenar_por=ordenar_por,
        campos_permitidos={"data_referencia", "versao", "cnpj_companhia", "id_plano_recompra"},
    )
    return ListaFrePlanosRecompraResposta(
        dados=dados,
        paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total),
    )


@router.get(
    "/fre/plano-recompra-classes-acoes",
    response_model=ListaFrePlanoRecompraClassesAcoesResposta,
    summary="Listar Classes de Ações nos Planos de Recompra FRE",
    description="Retorna classes de ações nos planos de recompra do FRE (`fre_cia_aberta_plano_recompra_classe_acao_{ano}.csv`).",
    responses=_RESPOSTAS_PADRAO,
    operation_id="listarPlanoRecompraClassesAcoesFre",
)
def listar_plano_recompra_classes_acoes_fre(
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
    id_documento: ParametroIdDocumento = None,
    id_plano_recompra: Annotated[int | None, Query(description="Filtrar por ID do Plano de Recompra.", examples=[1])] = None,
    ordenar_por: Annotated[
        str | None, Query(description="Campos: data_referencia, versao, cnpj_companhia, id_plano_recompra, tipo_classe_acao_preferencial.")
    ] = "-data_referencia",
) -> ListaFrePlanoRecompraClassesAcoesResposta:
    dados, total = _lista_fre_generica(
        db,
        modelo=FrePlanoRecompraClasseAcao,
        schema=FrePlanoRecompraClasseAcaoResposta,
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        ano_inicio=ano_inicio,
        ano_fim=ano_fim,
        versao=versao,
        id_documento=id_documento,
        ordenar_por=ordenar_por,
        campos_permitidos={"data_referencia", "versao", "cnpj_companhia", "id_plano_recompra", "tipo_classe_acao_preferencial"},
        filtros_adicionais={"id_plano_recompra": id_plano_recompra},
    )
    return ListaFrePlanoRecompraClassesAcoesResposta(
        dados=dados,
        paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total),
    )


@router.get(
    "/fre/valor-mobiliario-tesouraria-movimentacao",
    response_model=ListaFreValoresMobiliariosTesourariaMovimentacoesResposta,
    summary="Listar Movimentações de Valores Mobiliários em Tesouraria FRE",
    description="Retorna movimentações de valores mobiliários em tesouraria (`fre_cia_aberta_valor_mobiliario_tesouraria_movimentacao_{ano}.csv`).",
    responses=_RESPOSTAS_PADRAO,
    operation_id="listarValorMobiliarioTesourariaMovimentacaoFre",
)
def listar_valor_mobiliario_tesouraria_movimentacao_fre(
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
    id_documento: ParametroIdDocumento = None,
    ordenar_por: Annotated[
        str | None, Query(description="Campos: data_referencia, versao, cnpj_companhia, classe_valor_mobiliario, data_movimentacao.")
    ] = "-data_referencia",
) -> ListaFreValoresMobiliariosTesourariaMovimentacoesResposta:
    dados, total = _lista_fre_generica(
        db,
        modelo=FreValorMobiliarioTesourariaMovimentacao,
        schema=FreValorMobiliarioTesourariaMovimentacaoResposta,
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        ano_inicio=ano_inicio,
        ano_fim=ano_fim,
        versao=versao,
        id_documento=id_documento,
        ordenar_por=ordenar_por,
        campos_permitidos={"data_referencia", "versao", "cnpj_companhia", "classe_valor_mobiliario", "data_movimentacao"},
    )
    return ListaFreValoresMobiliariosTesourariaMovimentacoesResposta(
        dados=dados,
        paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total),
    )


@router.get(
    "/fre/valor-mobiliario-tesouraria-ultimo-exercicio",
    response_model=ListaFreValoresMobiliariosTesourariaUltimosExerciciosResposta,
    summary="Listar Saldos do Último Exercício de Valores Mobiliários em Tesouraria FRE",
    description="Retorna saldos no último exercício social de valores mobiliários em tesouraria (`fre_cia_aberta_valor_mobiliario_tesouraria_ultimo_exercicio_{ano}.csv`).",
    responses=_RESPOSTAS_PADRAO,
    operation_id="listarValorMobiliarioTesourariaUltimoExercicioFre",
)
def listar_valor_mobiliario_tesouraria_ultimo_exercicio_fre(
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
    id_documento: ParametroIdDocumento = None,
    ordenar_por: Annotated[
        str | None, Query(description="Campos: data_referencia, versao, cnpj_companhia, classe_valor_mobiliario, historico_exercicio.")
    ] = "-data_referencia",
) -> ListaFreValoresMobiliariosTesourariaUltimosExerciciosResposta:
    dados, total = _lista_fre_generica(
        db,
        modelo=FreValorMobiliarioTesourariaUltimoExercicio,
        schema=FreValorMobiliarioTesourariaUltimoExercicioResposta,
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        ano_inicio=ano_inicio,
        ano_fim=ano_fim,
        versao=versao,
        id_documento=id_documento,
        ordenar_por=ordenar_por,
        campos_permitidos={"data_referencia", "versao", "cnpj_companhia", "classe_valor_mobiliario", "historico_exercicio"},
    )
    return ListaFreValoresMobiliariosTesourariaUltimosExerciciosResposta(
        dados=dados,
        paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total),
    )


@router.get(
    "/fre/administradores/declaracao-genero",
    response_model=ListaFreAdministradoresDeclaracaoGeneroResposta,
    summary="Listar Declarações de Gênero de Administradores FRE",
    description="Retorna declarações de gênero de administradores do FRE (`fre_cia_aberta_administrador_declaracao_genero_{ano}.csv`).",
    responses=_RESPOSTAS_PADRAO,
    operation_id="listarAdministradoresDeclaracaoGeneroFre",
)
def listar_administradores_declaracao_genero_fre(
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
    id_documento: ParametroIdDocumento = None,
    orgao_administracao: ParametroOrgaoAdministracao = None,
    ordenar_por: Annotated[
        str | None, Query(description="Campos: data_referencia, versao, cnpj_companhia, orgao_administracao.")
    ] = "-data_referencia",
) -> ListaFreAdministradoresDeclaracaoGeneroResposta:
    dados, total = _lista_fre_generica(
        db,
        modelo=FreAdministradorDeclaracaoGenero,
        schema=FreAdministradorDeclaracaoGeneroResposta,
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        ano_inicio=ano_inicio,
        ano_fim=ano_fim,
        versao=versao,
        id_documento=id_documento,
        ordenar_por=ordenar_por,
        campos_permitidos={"data_referencia", "versao", "cnpj_companhia", "orgao_administracao"},
        filtros_adicionais={"orgao_administracao": orgao_administracao},
    )
    return ListaFreAdministradoresDeclaracaoGeneroResposta(
        dados=dados,
        paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total),
    )


@router.get(
    "/fre/administradores/declaracao-raca",
    response_model=ListaFreAdministradoresDeclaracaoRacaResposta,
    summary="Listar Declarações de Raça de Administradores FRE",
    description="Retorna declarações de raça de administradores do FRE (`fre_cia_aberta_administrador_declaracao_raca_{ano}.csv`).",
    responses=_RESPOSTAS_PADRAO,
    operation_id="listarAdministradoresDeclaracaoRacaFre",
)
def listar_administradores_declaracao_raca_fre(
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
    id_documento: ParametroIdDocumento = None,
    orgao_administracao: ParametroOrgaoAdministracao = None,
    ordenar_por: Annotated[
        str | None, Query(description="Campos: data_referencia, versao, cnpj_companhia, orgao_administracao.")
    ] = "-data_referencia",
) -> ListaFreAdministradoresDeclaracaoRacaResposta:
    dados, total = _lista_fre_generica(
        db,
        modelo=FreAdministradorDeclaracaoRaca,
        schema=FreAdministradorDeclaracaoRacaResposta,
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        ano_inicio=ano_inicio,
        ano_fim=ano_fim,
        versao=versao,
        id_documento=id_documento,
        ordenar_por=ordenar_por,
        campos_permitidos={"data_referencia", "versao", "cnpj_companhia", "orgao_administracao"},
        filtros_adicionais={"orgao_administracao": orgao_administracao},
    )
    return ListaFreAdministradoresDeclaracaoRacaResposta(
        dados=dados,
        paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total),
    )


@router.get(
    "/fre/administradores/pcd",
    response_model=ListaFreAdministradoresPcdResposta,
    summary="Listar Declarações PCD de Administradores FRE",
    description="Retorna declarações PCD de administradores do FRE (`fre_cia_aberta_administrador_PCD_{ano}.csv`).",
    responses=_RESPOSTAS_PADRAO,
    operation_id="listarAdministradoresPcdFre",
)
def listar_administradores_pcd_fre(
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
    id_documento: ParametroIdDocumento = None,
    orgao_administracao: ParametroOrgaoAdministracao = None,
    ordenar_por: Annotated[
        str | None, Query(description="Campos: data_referencia, versao, cnpj_companhia, orgao_administracao.")
    ] = "-data_referencia",
) -> ListaFreAdministradoresPcdResposta:
    dados, total = _lista_fre_generica(
        db,
        modelo=FreAdministradorPcd,
        schema=FreAdministradorPcdResposta,
        paginacao=paginacao,
        cnpj_companhia=cnpj_companhia,
        codigo_cvm=codigo_cvm,
        data_referencia_inicio=data_referencia_inicio,
        data_referencia_fim=data_referencia_fim,
        ano_origem=ano_origem,
        ano_inicio=ano_inicio,
        ano_fim=ano_fim,
        versao=versao,
        id_documento=id_documento,
        ordenar_por=ordenar_por,
        campos_permitidos={"data_referencia", "versao", "cnpj_companhia", "orgao_administracao"},
        filtros_adicionais={"orgao_administracao": orgao_administracao},
    )
    return ListaFreAdministradoresPcdResposta(
        dados=dados,
        paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total),
    )
