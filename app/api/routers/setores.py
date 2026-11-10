import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import func, or_, select

from app.api.auth import exigir_admin_api
from app.api.deps import DbSession
from app.models.companhia import Companhia
from app.models.setores import (
    Setor,
    SetorAlias,
    SetorClassificacaoCompanhia,
    SetorCorrespondencia,
    SetorTaxonomia,
    SetorTaxonomiaMudanca,
    SetorTaxonomiaVersao,
)
from app.schemas.setores import (
    AgregacaoSetorialRequest,
    AgregacaoSetorialResposta,
    SetorAliasRequest,
    SetorAliasResposta,
    SetorCompanhiaResposta,
    SetorCompanhiasResposta,
    SetorCorrespondenciaRequest,
    SetorCorrespondenciaResposta,
    SetorDetalheResposta,
    SetorListaResposta,
    SetorPaginacao,
    SetorResposta,
    SetorTaxonomiaResposta,
    SetorVersaoResposta,
)
from app.services.setores import (
    FatoCanonicoInconsistente,
    SeletorNaoEncontrado,
    TaxonomiaSemPublicacao,
    agregar_margens_com_cache,
    listar_correspondencias,
    normalizar_chave_setor,
    versao_publicada,
)

router = APIRouter()


def _taxonomia_ou_409(db: DbSession, codigo: str) -> SetorTaxonomia:
    try:
        return versao_publicada(db, codigo)
    except TaxonomiaSemPublicacao as exc:
        catalogo = db.get(SetorTaxonomia, codigo)
        if catalogo is None:
            raise HTTPException(status_code=404, detail="Taxonomia nao encontrada.") from exc
        raise HTTPException(
            status_code=409,
            detail={"codigo": "TAXONOMIA_SEM_PUBLICACAO", "taxonomia": codigo},
        ) from exc


@router.get(
    "/setores/taxonomias",
    response_model=list[SetorTaxonomiaResposta],
    summary="Listar taxonomias setoriais",
    description=(
        "Lista as taxonomias setoriais conhecidas, sua fonte, status e versão publicada. "
        "A taxonomia B3 fica indisponível para consulta até que uma fonte autorizada seja publicada."
    ),
    operation_id="listarTaxonomiasSetoriais",
)
def listar_taxonomias_setoriais(db: DbSession) -> list[SetorTaxonomiaResposta]:
    taxonomias = db.scalars(select(SetorTaxonomia).order_by(SetorTaxonomia.codigo)).all()
    return [SetorTaxonomiaResposta.model_validate(item) for item in taxonomias]


@router.get(
    "/setores/taxonomias/{taxonomia}/versoes",
    response_model=list[SetorVersaoResposta],
    summary="Listar versões de uma taxonomia setorial",
    description="Retorna o histórico de publicações semânticas da taxonomia, com checksum e resumo de cobertura.",
    operation_id="listarVersoesTaxonomiaSetorial",
)
def listar_versoes_taxonomia(
    taxonomia: Annotated[str, Path(min_length=1, max_length=64)],
    db: DbSession,
) -> list[SetorVersaoResposta]:
    if db.get(SetorTaxonomia, taxonomia) is None:
        raise HTTPException(status_code=404, detail="Taxonomia nao encontrada.")
    itens = db.scalars(
        select(SetorTaxonomiaVersao)
        .where(SetorTaxonomiaVersao.taxonomia == taxonomia)
        .order_by(SetorTaxonomiaVersao.versao.desc())
    ).all()
    return [SetorVersaoResposta.model_validate(item) for item in itens]


@router.get(
    "/setores",
    response_model=SetorListaResposta,
    summary="Listar setores",
    description=(
        "Lista setores por taxonomia publicada. A busca compara o nome de exibição e a chave normalizada. "
        "A contagem usa as atribuições vigentes da versão retornada."
    ),
    operation_id="listarSetores",
)
def listar_setores(
    db: DbSession,
    taxonomia: Annotated[str, Query(description="Taxonomia setorial publicada.")] = "cvm_cadastro",
    nome: Annotated[str | None, Query(max_length=255, description="Trecho do nome do setor.")] = None,
    incluir_inativos: Annotated[bool, Query(description="Inclui setores sem atribuição vigente.")] = False,
    pagina: Annotated[int, Query(ge=1)] = 1,
    tamanho_pagina: Annotated[int, Query(ge=1, le=500)] = 100,
) -> SetorListaResposta:
    catalogo = _taxonomia_ou_409(db, taxonomia)
    query = select(Setor, func.count(SetorClassificacaoCompanhia.id)).outerjoin(
        SetorClassificacaoCompanhia,
        (SetorClassificacaoCompanhia.setor_id == Setor.id)
        & (SetorClassificacaoCompanhia.taxonomia == taxonomia)
        & SetorClassificacaoCompanhia.versao_fim.is_(None),
    ).where(Setor.taxonomia == taxonomia)
    total_query = select(func.count()).select_from(Setor).where(Setor.taxonomia == taxonomia)
    if not incluir_inativos:
        query = query.where(Setor.ativo.is_(True))
        total_query = total_query.where(Setor.ativo.is_(True))
    if nome:
        filtro = or_(Setor.nome.ilike(f"%{nome}%"), Setor.chave_normalizada.ilike(f"%{nome.casefold()}%"))
        query = query.where(filtro)
        total_query = total_query.where(filtro)
    query = query.group_by(Setor.id).order_by(Setor.nome, Setor.id)
    total = db.scalar(total_query) or 0
    rows = db.execute(query.offset((pagina - 1) * tamanho_pagina).limit(tamanho_pagina)).all()
    dados = [
        SetorResposta(
            id=setor.id,
            taxonomia=setor.taxonomia,
            nome=setor.nome,
            chave_normalizada=setor.chave_normalizada,
            nivel=setor.nivel,
            setor_pai_id=setor.setor_pai_id,
            ativo=setor.ativo,
            total_companhias=count,
        )
        for setor, count in rows
    ]
    return SetorListaResposta(
        dados=dados,
        paginacao=SetorPaginacao(pagina=pagina, tamanho_pagina=tamanho_pagina, total=total),
        taxonomia=taxonomia,
        versao_taxonomia=catalogo.versao_atual or 0,
    )


@router.get(
    "/setores/{setor_id}",
    response_model=SetorDetalheResposta,
    summary="Obter setor",
    description="Retorna um conceito setorial, aliases explícitos e correspondências auditadas com outras taxonomias.",
    operation_id="obterSetor",
)
def obter_setor(
    setor_id: Annotated[uuid.UUID, Path(description="UUID opaco do conceito setorial.")],
    db: DbSession,
    incluir_correspondencias: Annotated[bool, Query()] = True,
) -> SetorDetalheResposta:
    setor = db.get(Setor, setor_id)
    if setor is None:
        raise HTTPException(status_code=404, detail="Setor nao encontrado.")
    catalogo = _taxonomia_ou_409(db, setor.taxonomia)
    aliases = db.scalars(select(SetorAlias).where(SetorAlias.setor_id == setor_id).order_by(SetorAlias.rotulo_origem)).all()
    count = db.scalar(
        select(func.count(SetorClassificacaoCompanhia.id)).where(
            SetorClassificacaoCompanhia.setor_id == setor_id,
            SetorClassificacaoCompanhia.taxonomia == setor.taxonomia,
            SetorClassificacaoCompanhia.versao_fim.is_(None),
        )
    ) or 0
    resposta = SetorDetalheResposta(
        id=setor.id,
        taxonomia=setor.taxonomia,
        nome=setor.nome,
        chave_normalizada=setor.chave_normalizada,
        nivel=setor.nivel,
        setor_pai_id=setor.setor_pai_id,
        ativo=setor.ativo,
        total_companhias=count,
        versao_taxonomia=catalogo.versao_atual or 0,
        aliases=[item.rotulo_origem for item in aliases],
    )
    if incluir_correspondencias:
        correspondencias = listar_correspondencias(db, setor_id)
        nomes_por_id: dict[uuid.UUID, str] = {}
        if correspondencias:
            nomes_por_id = {
                item.id: item.nome
                for item in db.scalars(
                    select(Setor).where(
                        Setor.id.in_(
                            {row.setor_origem_id for row in correspondencias}
                            | {row.setor_destino_id for row in correspondencias}
                        )
                    )
                ).all()
            }
        resposta.correspondencias = [
            SetorCorrespondenciaResposta(
                taxonomia_origem=item.taxonomia_origem,
                setor_origem_id=item.setor_origem_id,
                setor_origem_nome=nomes_por_id[item.setor_origem_id],
                taxonomia_destino=item.taxonomia_destino,
                setor_destino_id=item.setor_destino_id,
                setor_destino_nome=nomes_por_id[item.setor_destino_id],
                tipo=item.tipo,  # type: ignore[arg-type]
                versao_mapeamento=item.versao_mapeamento,
                evidencias=item.evidencias,
                justificativa=item.justificativa,
            )
            for item in correspondencias
        ]
    return resposta


@router.get(
    "/setores/{setor_id}/companhias",
    response_model=SetorCompanhiasResposta,
    summary="Listar companhias de um setor",
    description="Retorna companhias com atribuição vigente ao setor na taxonomia informada.",
    operation_id="listarCompanhiasDoSetor",
)
def listar_companhias_do_setor(
    setor_id: Annotated[uuid.UUID, Path()],
    db: DbSession,
    taxonomia: Annotated[str, Query()] = "cvm_cadastro",
    pagina: Annotated[int, Query(ge=1)] = 1,
    tamanho_pagina: Annotated[int, Query(ge=1, le=500)] = 100,
) -> SetorCompanhiasResposta:
    catalogo = _taxonomia_ou_409(db, taxonomia)
    setor = db.get(Setor, setor_id)
    if setor is None or setor.taxonomia != taxonomia:
        raise HTTPException(status_code=404, detail="Setor nao encontrado na taxonomia informada.")
    stmt = (
        select(Companhia, SetorClassificacaoCompanhia)
        .join(SetorClassificacaoCompanhia, SetorClassificacaoCompanhia.companhia_id == Companhia.id)
        .where(
            SetorClassificacaoCompanhia.taxonomia == taxonomia,
            SetorClassificacaoCompanhia.setor_id == setor_id,
            SetorClassificacaoCompanhia.versao_fim.is_(None),
        )
        .order_by(Companhia.denominacao_social, Companhia.id)
    )
    total = db.scalar(
        select(func.count(SetorClassificacaoCompanhia.id)).where(
            SetorClassificacaoCompanhia.taxonomia == taxonomia,
            SetorClassificacaoCompanhia.setor_id == setor_id,
            SetorClassificacaoCompanhia.versao_fim.is_(None),
        )
    ) or 0
    rows = db.execute(stmt.offset((pagina - 1) * tamanho_pagina).limit(tamanho_pagina)).all()
    return SetorCompanhiasResposta(
        dados=[
            SetorCompanhiaResposta(
                id=companhia.id,
                cnpj_companhia=companhia.cnpj_companhia,
                codigo_cvm=companhia.codigo_cvm,
                denominacao_social=companhia.denominacao_social,
                denominacao_comercial=companhia.denominacao_comercial,
                categoria_registro=companhia.categoria_registro,
                tipo_emissor=companhia.tipo_emissor,
                situacao_registro=companhia.situacao_registro,
                setor_atividade=companhia.setor_atividade,
                setor_id=classificacao.setor_id,
                taxonomia=taxonomia,
            )
            for companhia, classificacao in rows
        ],
        paginacao=SetorPaginacao(pagina=pagina, tamanho_pagina=tamanho_pagina, total=total),
        setor_id=setor_id,
        taxonomia=taxonomia,
        versao_taxonomia=catalogo.versao_atual or 0,
    )


@router.post(
    "/setores/aliases",
    response_model=SetorAliasResposta,
    summary="Registrar alias auditável de setor",
    description=(
        "Registra explicitamente um rótulo alternativo dentro da mesma taxonomia. "
        "A operação requer token administrativo, evidência e justificativa; não funde nem altera IDs de setor."
    ),
    operation_id="criarAliasSetorial",
)
def criar_alias_setorial(
    pedido: SetorAliasRequest,
    db: DbSession,
    _: Annotated[None, Depends(exigir_admin_api)],
) -> SetorAliasResposta:
    catalogo = _taxonomia_ou_409(db, pedido.taxonomia)
    setor = db.get(Setor, pedido.setor_id)
    if setor is None or setor.taxonomia != pedido.taxonomia:
        raise HTTPException(status_code=404, detail="Setor nao encontrado na taxonomia informada.")
    rotulo = " ".join(pedido.rotulo_origem.split())
    chave = normalizar_chave_setor(rotulo)
    existente_setor = db.scalar(
        select(Setor).where(Setor.taxonomia == pedido.taxonomia, Setor.chave_normalizada == chave)
    )
    existente_alias = db.scalar(
        select(SetorAlias).where(SetorAlias.taxonomia == pedido.taxonomia, SetorAlias.chave_normalizada == chave)
    )
    if existente_setor is not None or existente_alias is not None:
        raise HTTPException(status_code=409, detail={"codigo": "ROTULO_SETOR_JA_CADASTRADO", "chave_normalizada": chave})

    agora = datetime.now(UTC)
    publicacao = SetorTaxonomiaVersao(
        taxonomia=pedido.taxonomia,
        versao=(catalogo.versao_atual or 0) + 1,
        checksum_semantico=catalogo.checksum_atual or "",
        referencia_fonte="curadoria",
        publicada_em=agora,
        resumo={"tipo": "curadoria", "alteracao": "alias_adicionado"},
    )
    db.add(publicacao)
    db.flush()
    alias = SetorAlias(
        taxonomia=pedido.taxonomia,
        setor_id=setor.id,
        chave_normalizada=chave,
        rotulo_origem=rotulo,
        evidencias={**pedido.evidencias, "justificativa": pedido.justificativa, "revisado_por": pedido.revisado_por},
    )
    db.add(alias)
    db.flush()
    db.add(
        SetorTaxonomiaMudanca(
            publicacao_id=publicacao.id,
            tipo="alias_adicionado",
            setor_id=setor.id,
            antes=None,
            depois={"rotulo_origem": rotulo, "chave_normalizada": chave, "evidencias": pedido.evidencias},
        )
    )
    catalogo.versao_atual = publicacao.versao
    catalogo.referencia_fonte_atual = "curadoria"
    catalogo.publicada_em = agora
    db.flush()
    return SetorAliasResposta.model_validate(alias)


@router.post(
    "/setores/correspondencias",
    response_model=SetorCorrespondenciaResposta,
    summary="Registrar correspondência entre taxonomias",
    description=(
        "Registra uma relação direcional e versionada entre conceitos de taxonomias publicadas. "
        "A operação requer token administrativo, evidência e justificativa."
    ),
    operation_id="criarCorrespondenciaSetorial",
)
def criar_correspondencia_setorial(
    pedido: SetorCorrespondenciaRequest,
    db: DbSession,
    _: Annotated[None, Depends(exigir_admin_api)],
) -> SetorCorrespondenciaResposta:
    origem = _taxonomia_ou_409(db, pedido.taxonomia_origem)
    _taxonomia_ou_409(db, pedido.taxonomia_destino)
    setor_origem = db.get(Setor, pedido.setor_origem_id)
    setor_destino = db.get(Setor, pedido.setor_destino_id)
    if setor_origem is None or setor_origem.taxonomia != pedido.taxonomia_origem:
        raise HTTPException(status_code=404, detail="Setor de origem nao encontrado.")
    if setor_destino is None or setor_destino.taxonomia != pedido.taxonomia_destino:
        raise HTTPException(status_code=404, detail="Setor de destino nao encontrado.")
    versao_mapeamento = (db.scalar(select(func.max(SetorCorrespondencia.versao_mapeamento))) or 0) + 1
    agora = datetime.now(UTC)
    publicacao = SetorTaxonomiaVersao(
        taxonomia=pedido.taxonomia_origem,
        versao=(origem.versao_atual or 0) + 1,
        checksum_semantico=origem.checksum_atual or "",
        referencia_fonte="curadoria",
        publicada_em=agora,
        resumo={"tipo": "curadoria", "alteracao": "correspondencia_adicionada", "versao_mapeamento": versao_mapeamento},
    )
    db.add(publicacao)
    db.flush()
    correspondencia = SetorCorrespondencia(
        taxonomia_origem=pedido.taxonomia_origem,
        setor_origem_id=setor_origem.id,
        taxonomia_destino=pedido.taxonomia_destino,
        setor_destino_id=setor_destino.id,
        tipo=pedido.tipo,
        versao_mapeamento=versao_mapeamento,
        evidencias={**pedido.evidencias, "revisado_por": pedido.revisado_por},
        justificativa=pedido.justificativa,
        revisado_por=pedido.revisado_por,
    )
    db.add(correspondencia)
    db.add(
        SetorTaxonomiaMudanca(
            publicacao_id=publicacao.id,
            tipo="correspondencia_adicionada",
            setor_id=setor_origem.id,
            depois={
                "taxonomia_destino": pedido.taxonomia_destino,
                "setor_destino_id": str(setor_destino.id),
                "tipo": pedido.tipo,
                "versao_mapeamento": versao_mapeamento,
            },
        )
    )
    origem.versao_atual = publicacao.versao
    origem.referencia_fonte_atual = "curadoria"
    origem.publicada_em = agora
    db.flush()
    return SetorCorrespondenciaResposta(
        taxonomia_origem=correspondencia.taxonomia_origem,
        setor_origem_id=correspondencia.setor_origem_id,
        setor_origem_nome=setor_origem.nome,
        taxonomia_destino=correspondencia.taxonomia_destino,
        setor_destino_id=correspondencia.setor_destino_id,
        setor_destino_nome=setor_destino.nome,
        tipo=correspondencia.tipo,  # type: ignore[arg-type]
        versao_mapeamento=correspondencia.versao_mapeamento,
        evidencias=correspondencia.evidencias,
        justificativa=correspondencia.justificativa,
    )
@router.post(
    "/analise/companhias/agregacoes",
    response_model=AgregacaoSetorialResposta,
    summary="Agregar margens de um grupo de companhias",
    description=(
        "Filtra um universo de companhias e calcula margens bruta, EBIT e líquida por exercício. "
        "Usa fatos canônicos anuais em BRL, consulta em lote e cache de entrega por versão setorial e geração financeira. "
        "As estatísticas são média simples, mediana e razão das somas; margens não misturam fatos sem receita positiva."
    ),
    operation_id="agregarMargensCompanhias",
    responses={
        409: {"description": "Taxonomia sem publicação ou fato canônico inconsistente."},
        422: {"description": "Seleção, períodos ou detalhamento fora dos limites do contrato."},
    },
)
def agregar_margens_companhias(pedido: AgregacaoSetorialRequest, db: DbSession) -> AgregacaoSetorialResposta:
    try:
        return agregar_margens_com_cache(db, pedido)
    except TaxonomiaSemPublicacao as exc:
        catalogo = db.get(SetorTaxonomia, pedido.taxonomia)
        if catalogo is None:
            raise HTTPException(status_code=404, detail="Taxonomia nao encontrada.") from exc
        raise HTTPException(
            status_code=409,
            detail={"codigo": "TAXONOMIA_SEM_PUBLICACAO", "taxonomia": pedido.taxonomia},
        ) from exc
    except FatoCanonicoInconsistente as exc:
        raise HTTPException(status_code=409, detail={"codigo": "FATO_CANONICO_INCONSISTENTE", "mensagem": str(exc)}) from exc
    except SeletorNaoEncontrado as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
