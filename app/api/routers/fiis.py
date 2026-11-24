from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal, cast

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import func, select
from sqlalchemy.sql import Select

from app.api.deps import DbSession, PaginacaoQuery
from app.models.fii import FiiInformeAtivoPassivo, FiiInformeComplemento, FiiInformeGeral
from app.schemas.comum import Paginacao
from app.schemas.fii import (
    FiiInformeCompletoResposta,
    FiiInformeResumoResposta,
    FiiPerfilResposta,
    FiiSecaoResposta,
    FiiVarianteProveniencia,
    FiiVarianteResposta,
    ListaFiisResposta,
    UnidadeFii,
)

router = APIRouter(prefix="/fiis")
TipoFii = Literal["fundo", "classe"]


def _cnpj(value: str, *, allow_mask: bool = False) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]", "", value).upper() if allow_mask else value.upper()
    if not re.fullmatch(r"[A-Z0-9]{12}[0-9]{2}", normalized):
        raise HTTPException(status_code=422, detail="CNPJ deve conter 14 caracteres alfanumericos.")
    return normalized


def _competencia(value: str) -> date:
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", value):
        raise HTTPException(status_code=422, detail="Competencia deve usar o formato AAAA-MM.")
    return date.fromisoformat(f"{value}-01")


def _proveniencia(row: FiiInformeGeral) -> dict[str, str | int | None]:
    return {
        "arquivo_zip": f"inf_mensal_fii_{row.ano_origem}.zip",
        "arquivo_csv": row.arquivo_origem,
        "linha": row.linha_origem,
        "hash_normalizado": row.hash_origem,
        "execucao_sincronizacao_id": str(row.execucao_sincronizacao_id),
    }


def _unidades(secao: str, dados: dict[str, str | int | bool | None]) -> dict[str, UnidadeFii]:
    units: dict[str, UnidadeFii] = {}
    for field in dados:
        if field.startswith("Data_"):
            unit: UnidadeFii = "data"
        elif field in {"Fundo_Exclusivo", "Cotistas_Vinculo_Familiar", "Mercado_Negociacao_Bolsa",
                       "Mercado_Negociacao_MBO", "Mercado_Negociacao_MB", "Entidade_Administradora_BVMF",
                       "Entidade_Administradora_CETIP"}:
            unit = "booleano"
        elif field.startswith("Numero_Cotistas_") or field == "Total_Numero_Cotistas":
            unit = "contagens"
        elif field.startswith("Percentual_"):
            unit = "percentual CVM"
        elif field == "Versao":
            unit = "versao"
        elif field in {"Quantidade_Cotas_Emitidas", "Cotas_Emitidas"}:
            unit = "cotas"
        elif field == "Valor_Patrimonial_Cotas":
            unit = "BRL/cota"
        elif secao == "ativo_passivo" or (secao == "complemento" and field in {"Valor_Ativo", "Patrimonio_Liquido"}):
            unit = "BRL"
        elif field.startswith("CNPJ_") or field == "Codigo_ISIN":
            unit = "identificador"
        else:
            unit = "texto"
        units[field] = unit
    return units


def _section_provenance(row: FiiInformeComplemento | FiiInformeAtivoPassivo) -> FiiVarianteProveniencia:
    return FiiVarianteProveniencia(
        arquivo_csv=row.arquivo_origem,
        arquivo_zip=f"inf_mensal_fii_{row.ano_origem}.zip",
        linha=row.linha_origem,
        hash_origem=row.hash_origem,
        execucao_sincronizacao_id=str(row.execucao_sincronizacao_id),
        ocorrencias=row.ocorrencias,
        consta_no_snapshot_atual=row.consta_no_snapshot_atual,
    )


def _section_response[SecaoFii: (FiiInformeComplemento, FiiInformeAtivoPassivo)](
    db: DbSession,
    model: type[SecaoFii],
    *,
    secao: str,
    cnpj: str,
    tipo: TipoFii,
    competencia: date,
    versao: int,
    consta_no_snapshot_atual: bool,
) -> FiiSecaoResposta:
    filters = [
        model.cnpj == cnpj,
        model.data_referencia == competencia,
        model.versao == versao,
        (model.tipo == tipo) | (model.tipo.is_(None)),
    ]
    if consta_no_snapshot_atual:
        filters.append(model.consta_no_snapshot_atual.is_(True))
    rows = db.scalars(select(model).where(*filters).order_by(model.hash_variante.asc())).all()
    if not rows:
        return FiiSecaoResposta(status="ausente", dados=None, unidades={}, variantes=[], proveniencia=None,
                                consta_no_snapshot_atual=None)
    assigned = [row for row in rows if row.tipo == tipo and row.status_atribuicao == "disponivel"]
    if len(assigned) == 1:
        row = assigned[0]
        return FiiSecaoResposta(status="disponivel", dados=row.dados, unidades=_unidades(secao, row.dados),
                                variantes=[], proveniencia=_section_provenance(row),
                                consta_no_snapshot_atual=row.consta_no_snapshot_atual)
    ambiguous = [row for row in rows if row.status_atribuicao == "ambiguo"]
    if ambiguous:
        variants = [FiiVarianteResposta(
            dados=row.dados,
            unidades=_unidades(secao, row.dados),
            proveniencia=_section_provenance(row),
        ) for row in ambiguous]
        current_values = {row.consta_no_snapshot_atual for row in ambiguous}
        return FiiSecaoResposta(status="ambiguo", dados=None, unidades={}, variantes=variants, proveniencia=None,
                                consta_no_snapshot_atual=current_values.pop() if len(current_values) == 1 else None)
    return FiiSecaoResposta(status="ausente", dados=None, unidades={}, variantes=[], proveniencia=None,
                            consta_no_snapshot_atual=None)


def _decimal_metric(data: dict[str, str | int | bool | None] | None, field: str) -> Decimal | None:
    if data is None:
        return None
    value = data.get(field)
    if value is None or isinstance(value, bool):
        return None
    return Decimal(str(value))


def _integer_metric(data: dict[str, str | int | bool | None] | None, field: str) -> int | None:
    if data is None:
        return None
    value = data.get(field)
    if value is None or isinstance(value, bool):
        return None
    return int(value)


def _build_summary(db: DbSession, general: FiiInformeGeral) -> FiiInformeResumoResposta:
    tipo = cast(TipoFii, general.tipo)
    complemento = _section_response(db, FiiInformeComplemento, cnpj=general.cnpj, tipo=tipo,
                                    competencia=general.data_referencia, versao=general.versao,
                                    secao="complemento", consta_no_snapshot_atual=general.consta_no_snapshot_atual)
    ativo = _section_response(db, FiiInformeAtivoPassivo, cnpj=general.cnpj, tipo=tipo,
                              competencia=general.data_referencia, versao=general.versao,
                              secao="ativo_passivo", consta_no_snapshot_atual=general.consta_no_snapshot_atual)
    normalized_data = general.dados
    return FiiInformeResumoResposta(
        cnpj=general.cnpj,
        tipo=tipo,
        competencia=general.data_referencia.strftime("%Y-%m"),
        versao=general.versao,
        data_entrega=normalized_data.get("Data_Entrega"),
        nome=general.nome,
        codigo_isin=general.codigo_isin,
        segmento_atuacao=general.segmento_atuacao,
        patrimonio_liquido_brl=_decimal_metric(complemento.dados, "Patrimonio_Liquido"),
        valor_ativo_brl=_decimal_metric(complemento.dados, "Valor_Ativo"),
        valor_patrimonial_cota_brl=_decimal_metric(complemento.dados, "Valor_Patrimonial_Cotas"),
        cotistas_total=_integer_metric(complemento.dados, "Total_Numero_Cotistas"),
        dividend_yield_mes_percentual_cvm=_decimal_metric(complemento.dados, "Percentual_Dividend_Yield_Mes"),
        disponibilidade_secoes={
            "geral": "disponivel",
            "complemento": complemento.status,
            "ativo_passivo": ativo.status,
        },
        consta_no_snapshot_atual=general.consta_no_snapshot_atual,
    )


def _build_report(db: DbSession, general: FiiInformeGeral) -> FiiInformeCompletoResposta:
    resumo = _build_summary(db, general)
    tipo = cast(TipoFii, general.tipo)
    complemento = _section_response(db, FiiInformeComplemento, cnpj=general.cnpj, tipo=tipo,
                                    competencia=general.data_referencia, versao=general.versao,
                                    secao="complemento", consta_no_snapshot_atual=general.consta_no_snapshot_atual)
    ativo = _section_response(db, FiiInformeAtivoPassivo, cnpj=general.cnpj, tipo=tipo,
                              competencia=general.data_referencia, versao=general.versao,
                              secao="ativo_passivo", consta_no_snapshot_atual=general.consta_no_snapshot_atual)
    return FiiInformeCompletoResposta(
        **resumo.model_dump(),
        geral=FiiSecaoResposta(status="disponivel", dados=general.dados, unidades=_unidades("geral", general.dados),
                              variantes=[], proveniencia=FiiVarianteProveniencia(
                                  arquivo_csv=general.arquivo_origem,
                                  arquivo_zip=f"inf_mensal_fii_{general.ano_origem}.zip",
                                  linha=general.linha_origem,
                                  hash_origem=general.hash_origem,
                                  execucao_sincronizacao_id=str(general.execucao_sincronizacao_id),
                                  ocorrencias=1,
                                  consta_no_snapshot_atual=general.consta_no_snapshot_atual,
                              ),
                              consta_no_snapshot_atual=general.consta_no_snapshot_atual),
        complemento=complemento,
        ativo_passivo=ativo,
        proveniencia=_proveniencia(general),
    )


def _latest_identity_query() -> Select[FiiInformeGeral]:
    ranked = (
        select(
            FiiInformeGeral.id.label("id"),
            func.row_number().over(
                partition_by=(FiiInformeGeral.cnpj, FiiInformeGeral.tipo),
                order_by=(FiiInformeGeral.data_referencia.desc(), FiiInformeGeral.versao.desc()),
            ).label("position"),
        )
        .where(FiiInformeGeral.consta_no_snapshot_atual.is_(True))
        .subquery()
    )
    return select(FiiInformeGeral).join(ranked, ranked.c.id == FiiInformeGeral.id).where(ranked.c.position == 1)


@router.get(
    "",
    response_model=ListaFiisResposta,
    summary="Listar fundos imobiliarios",
    description=(
        "Lista o perfil vigente informado pela CVM para cada identidade de fundo ou classe. "
        "O filtro e aplicado sobre o informe mais recente que consta no snapshot anual publicado. "
        "O patrimonio liquido, o ativo, o valor patrimonial por cota, o numero de cotistas e o dividend yield "
        "sao valores declarados no Informe Mensal. O dividend yield e devolvido na escala decimal apresentada "
        "pela CVM e usa como base o valor patrimonial da cota do mes anterior. Requer token de API."
    ),
    operation_id="listarFiis",
)
def listar_fiis(
    db: DbSession,
    paginacao: Annotated[PaginacaoQuery, Depends()],
    cnpj: Annotated[str | None, Query(description="CNPJ numerico ou alfanumerico, com ou sem pontuacao.")] = None,
    tipo: Annotated[TipoFii | None, Query(description="Tipo declarado na CVM.")] = None,
    nome: Annotated[str | None, Query(min_length=1, max_length=255, description="Busca parcial sem diferenciar maiusculas.")] = None,
    codigo_isin: Annotated[str | None, Query(max_length=32, description="Codigo ISIN do informe.")] = None,
    segmento_atuacao: Annotated[str | None, Query(max_length=255, description="Segmento de atuacao declarado.")] = None,
    negociado_em_bolsa: Annotated[bool | None, Query(description="Filtra o indicador de negociacao em bolsa declarado.")] = None,
) -> ListaFiisResposta:
    query = _latest_identity_query()
    if cnpj:
        query = query.where(FiiInformeGeral.cnpj == _cnpj(cnpj, allow_mask=True))
    if tipo is not None:
        query = query.where(FiiInformeGeral.tipo == tipo)
    if nome:
        query = query.where(FiiInformeGeral.nome.ilike(f"%{nome.strip()}%"))
    if codigo_isin:
        query = query.where(FiiInformeGeral.codigo_isin.ilike(codigo_isin.strip()))
    if segmento_atuacao:
        query = query.where(FiiInformeGeral.segmento_atuacao.ilike(f"%{segmento_atuacao.strip()}%"))
    if negociado_em_bolsa is not None:
        query = query.where(FiiInformeGeral.mercado_negociacao_bolsa.is_(negociado_em_bolsa))
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
    rows = db.scalars(query.order_by(FiiInformeGeral.nome.asc(), FiiInformeGeral.cnpj.asc(), FiiInformeGeral.tipo.asc())
                      .offset(paginacao.offset).limit(paginacao.tamanho_pagina)).all()
    return ListaFiisResposta(
        dados=[_build_summary(db, row) for row in rows],
        paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total),
    )


@router.get(
    "/{cnpj}/{tipo}",
    response_model=FiiPerfilResposta,
    summary="Consultar perfil do fundo ou classe",
    description="Retorna o perfil e os fundamentos do informe mais recente que consta no snapshot publicado. Requer token de API.",
    operation_id="obterPerfilFii",
)
def obter_perfil_fii(
    cnpj: Annotated[str, Path(description="CNPJ de 14 caracteres sem pontuacao.")],
    tipo: TipoFii,
    db: DbSession,
) -> FiiPerfilResposta:
    identifier = _cnpj(cnpj)
    general = db.scalar(_latest_identity_query().where(FiiInformeGeral.cnpj == identifier, FiiInformeGeral.tipo == tipo))
    if general is None:
        raise HTTPException(status_code=404, detail="Fundo ou classe nao encontrado.")
    return FiiPerfilResposta(identidade={"cnpj": general.cnpj, "tipo": general.tipo}, informe_atual=_build_report(db, general))


@router.get(
    "/{cnpj}/{tipo}/informes",
    response_model=ListaFiisResposta,
    summary="Listar historico mensal de informes",
    description=(
        "Lista o historico de informes publicados para o fundo ou classe. `todas_versoes=false` retorna a maior "
        "versao presente no snapshot atual por competencia. `todas_versoes=true` inclui todas as versoes observadas, "
        "inclusive as que deixaram de constar no snapshot atual; `consta_no_snapshot_atual` identifica cada entrega. "
        "Competencias usam AAAA-MM. Requer token de API."
    ),
    operation_id="listarInformesFii",
)
def listar_informes_fii(
    cnpj: Annotated[str, Path(description="CNPJ sem pontuacao.")],
    tipo: TipoFii,
    db: DbSession,
    paginacao: Annotated[PaginacaoQuery, Depends()],
    competencia_inicio: Annotated[str | None, Query(description="Competencia inicial inclusiva AAAA-MM.")] = None,
    competencia_fim: Annotated[str | None, Query(description="Competencia final inclusiva AAAA-MM.")] = None,
    todas_versoes: Annotated[bool, Query(description="Inclui versoes CVM presentes no snapshot anual atual.")] = False,
) -> ListaFiisResposta:
    identifier = _cnpj(cnpj)
    if db.scalar(select(FiiInformeGeral.id).where(
        FiiInformeGeral.cnpj == identifier, FiiInformeGeral.tipo == tipo
    ).limit(1)) is None:
        raise HTTPException(status_code=404, detail="Fundo ou classe nao encontrado.")
    query = select(FiiInformeGeral).where(FiiInformeGeral.cnpj == identifier, FiiInformeGeral.tipo == tipo)
    start = _competencia(competencia_inicio) if competencia_inicio else None
    end = _competencia(competencia_fim) if competencia_fim else None
    if start and end and start > end:
        raise HTTPException(status_code=422, detail="competencia_inicio deve ser anterior ou igual a competencia_fim.")
    if start:
        query = query.where(FiiInformeGeral.data_referencia >= start)
    if end:
        query = query.where(FiiInformeGeral.data_referencia <= end)
    if not todas_versoes:
        query = query.where(FiiInformeGeral.consta_no_snapshot_atual.is_(True))
        ranked = select(
            FiiInformeGeral.id.label("id"),
            func.row_number().over(
                partition_by=(FiiInformeGeral.cnpj, FiiInformeGeral.tipo, FiiInformeGeral.data_referencia),
                order_by=FiiInformeGeral.versao.desc(),
            ).label("position"),
        ).where(FiiInformeGeral.consta_no_snapshot_atual.is_(True)).subquery()
        query = query.join(ranked, ranked.c.id == FiiInformeGeral.id).where(ranked.c.position == 1)
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0
    rows = db.scalars(query.order_by(FiiInformeGeral.data_referencia.desc(), FiiInformeGeral.versao.desc())
                      .offset(paginacao.offset).limit(paginacao.tamanho_pagina)).all()
    return ListaFiisResposta(dados=[_build_summary(db, row) for row in rows],
                             paginacao=Paginacao(pagina=paginacao.pagina, tamanho_pagina=paginacao.tamanho_pagina, total=total))


@router.get(
    "/{cnpj}/{tipo}/informes/{competencia}",
    response_model=FiiInformeCompletoResposta,
    summary="Consultar informe mensal completo",
    description=(
        "Retorna perfil, indicadores, cotistas, composicao do ativo e passivo, proveniencia e variantes de cada secao. "
        "Quando `versao` nao e informada, seleciona a maior versao do snapshot atual. Uma versao explicita pode "
        "consultar uma entrega anteriormente observada. Secoes financeiras sem atribuicao segura retornam "
        "`status=ambiguo`, `dados=null` e as variantes observadas. Requer token de API."
    ),
    operation_id="obterInformeFii",
)
def obter_informe_fii(
    cnpj: Annotated[str, Path(description="CNPJ sem pontuacao.")],
    tipo: TipoFii,
    competencia: Annotated[str, Path(description="Competencia AAAA-MM.")],
    db: DbSession,
    versao: Annotated[int | None, Query(ge=1, description="Versao CVM observada na entrega.")] = None,
) -> FiiInformeCompletoResposta:
    identifier = _cnpj(cnpj)
    reference = _competencia(competencia)
    query = select(FiiInformeGeral).where(FiiInformeGeral.cnpj == identifier,
                                          FiiInformeGeral.tipo == tipo,
                                          FiiInformeGeral.data_referencia == reference)
    if versao is None:
        query = query.where(FiiInformeGeral.consta_no_snapshot_atual.is_(True)).order_by(FiiInformeGeral.versao.desc())
    else:
        query = query.where(FiiInformeGeral.versao == versao)
    row = db.scalar(query.limit(1))
    if row is None:
        raise HTTPException(status_code=404, detail="Informe nao encontrado.")
    return _build_report(db, row)
