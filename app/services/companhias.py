import re
from datetime import datetime

from sqlalchemy import Select, case, func, or_, select
from sqlalchemy.orm import Session

from app.models.companhia import Companhia
from app.models.fca import FcaValorMobiliario
from app.schemas.companhia import CompanhiaResposta, ListaCompanhiasResposta
from app.schemas.comum import Paginacao
from app.services.normalizacao import normalizar_cnpj

_LOGO_BASE_URL = "https://pub-04fd7aefad4846c98bccc4719b2eaed1.r2.dev/png"
_PADRAO_TICKER_LOGO = re.compile(r"^[A-Z]{4}\d{1,2}$")


def _ticker_serve_para_logo(codigo_negociacao: str | None) -> bool:
    if not codigo_negociacao:
        return False
    return bool(_PADRAO_TICKER_LOGO.fullmatch(codigo_negociacao.strip().upper()))


def _montar_logo_url_por_ticker(codigo_negociacao: str | None) -> str | None:
    if not _ticker_serve_para_logo(codigo_negociacao):
        return None
    assert codigo_negociacao is not None
    ticker = codigo_negociacao.strip().upper()
    return f"{_LOGO_BASE_URL}/{ticker[0]}/{ticker}.png"


def obter_logo_urls_por_cnpj(db: Session, cnpjs: list[str]) -> dict[str, str | None]:
    if not cnpjs:
        return {}

    hoje = datetime.now().date()
    registros = (
        db.execute(
            select(FcaValorMobiliario)
            .where(FcaValorMobiliario.cnpj_companhia.in_(cnpjs))
            .where(FcaValorMobiliario.codigo_negociacao.is_not(None))
            .where(or_(FcaValorMobiliario.data_fim_listagem.is_(None), FcaValorMobiliario.data_fim_listagem >= hoje))
            .order_by(
                FcaValorMobiliario.cnpj_companhia.asc(),
                FcaValorMobiliario.data_referencia.desc(),
                FcaValorMobiliario.versao.desc(),
                FcaValorMobiliario.data_inicio_listagem.desc().nullslast(),
                FcaValorMobiliario.codigo_negociacao.asc(),
            )
        )
        .scalars()
        .all()
    )

    logo_por_cnpj: dict[str, str | None] = {cnpj: None for cnpj in cnpjs}

    for registro in registros:
        cnpj = registro.cnpj_companhia
        if logo_por_cnpj.get(cnpj) is not None:
            continue
        logo_url = _montar_logo_url_por_ticker(registro.codigo_negociacao)
        if logo_url is not None:
            logo_por_cnpj[cnpj] = logo_url

    return logo_por_cnpj


def serializar_companhia(companhia: Companhia, logo_url: str | None) -> CompanhiaResposta:
    return CompanhiaResposta.model_validate(companhia).model_copy(update={"logo_url": logo_url})


def listar_companhias(
    db: Session,
    *,
    pagina: int,
    tamanho_pagina: int,
    cnpj_companhia: str | None = None,
    codigo_cvm: int | None = None,
    nome: str | None = None,
    situacao_registro: str | None = None,
    ordenar: str | None = "ativa_nome",
) -> ListaCompanhiasResposta:
    query: Select[tuple[Companhia]] = select(Companhia)
    query_total = select(func.count()).select_from(Companhia)

    if cnpj_companhia:
        cnpj = normalizar_cnpj(cnpj_companhia)
        query = query.where(Companhia.cnpj_companhia == cnpj)
        query_total = query_total.where(Companhia.cnpj_companhia == cnpj)

    if codigo_cvm is not None:
        query = query.where(Companhia.codigo_cvm == codigo_cvm)
        query_total = query_total.where(Companhia.codigo_cvm == codigo_cvm)

    if nome:
        busca = f"%{nome}%"
        filtro_nome = (Companhia.denominacao_social.ilike(busca)) | (Companhia.denominacao_comercial.ilike(busca))
        query = query.where(filtro_nome)
        query_total = query_total.where(filtro_nome)

    if situacao_registro:
        query = query.where(Companhia.situacao_registro == situacao_registro)
        query_total = query_total.where(Companhia.situacao_registro == situacao_registro)

    if ordenar == "ativa_nome":
        query = query.order_by(
            case((Companhia.situacao_registro == "ATIVO", 0), else_=1),
            Companhia.denominacao_social,
        )
    elif ordenar == "nome":
        query = query.order_by(Companhia.denominacao_social)
    elif ordenar == "codigo_cvm":
        query = query.order_by(Companhia.codigo_cvm)
    else:
        query = query.order_by(Companhia.denominacao_social)

    total = db.scalar(query_total) or 0
    offset = (pagina - 1) * tamanho_pagina
    itens = db.execute(query.offset(offset).limit(tamanho_pagina)).scalars().all()

    logos_por_cnpj = obter_logo_urls_por_cnpj(db, [item.cnpj_companhia for item in itens if item.cnpj_companhia])

    return ListaCompanhiasResposta(
        dados=[serializar_companhia(item, logos_por_cnpj.get(item.cnpj_companhia)) for item in itens],
        paginacao=Paginacao(
            pagina=pagina,
            tamanho_pagina=tamanho_pagina,
            total=total,
        ),
    )


def obter_companhia_por_codigo_cvm(db: Session, codigo_cvm: int) -> CompanhiaResposta | None:
    companhia = db.scalar(select(Companhia).where(Companhia.codigo_cvm == codigo_cvm))
    if companhia is None:
        return None
    logo_url = obter_logo_urls_por_cnpj(db, [companhia.cnpj_companhia]).get(companhia.cnpj_companhia)
    return serializar_companhia(companhia, logo_url)


def obter_companhia_por_cnpj(db: Session, cnpj_companhia: str) -> CompanhiaResposta | None:
    cnpj = normalizar_cnpj(cnpj_companhia)
    companhia = db.scalar(select(Companhia).where(Companhia.cnpj_companhia == cnpj))
    if companhia is None:
        return None
    logo_url = obter_logo_urls_por_cnpj(db, [companhia.cnpj_companhia]).get(companhia.cnpj_companhia)
    return serializar_companhia(companhia, logo_url)


__all__: tuple[str, ...] = (
    "listar_companhias",
    "obter_companhia_por_cnpj",
    "obter_companhia_por_codigo_cvm",
    "obter_logo_urls_por_cnpj",
    "serializar_companhia",
)
