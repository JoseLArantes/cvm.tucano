import uuid
from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Path, Query, UploadFile
from sqlalchemy import func, or_, select

from app.api.auth import AutenticacaoApi, autenticar_requisicao, exigir_admin_api
from app.api.deps import DbSession
from app.models.companhia import Companhia
from app.models.setores import (
    Setor,
    SetorAlias,
    SetorClassificacaoCompanhia,
    SetorCorrespondencia,
    SetorTaxonomia,
    SetorTaxonomiaImportacao,
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
    SetorTaxonomiaImportacaoResposta,
    SetorTaxonomiaResposta,
    SetorVersaoResposta,
)
from app.services.ingestion.setores import (
    MAX_ARQUIVO_B3_BYTES,
    TAXONOMIA_B3,
    URL_CLASSIFICACAO_B3,
)
from app.services.ingestion.setores import (
    importar_taxonomia_b3 as importar_taxonomia_b3_service,
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


def _obter_admin_importador(
    autenticacao: Annotated[AutenticacaoApi, Depends(autenticar_requisicao)],
) -> str:
    exigir_admin_api(autenticacao)
    if autenticacao.usuario is not None:
        return autenticacao.usuario.username
    return "token_sistema"


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
        "Lista cada dicionário setorial conhecido com código, nome, fonte declarada, estado, versão e checksum atuais. "
        "`cvm_cadastro` é publicado pelo cadastro de companhias da CVM e sustenta os vínculos cadastrais. "
        "`b3` só fica disponível depois de um XLSX válido ser enviado ao endpoint administrativo de importação. "
        "A publicação B3 contém apenas conceitos e níveis hierárquicos; não cria nem altera vínculos entre emissores B3 e companhias CVM. "
        "Use o código e a versão retornados nas consultas seguintes para identificar qual dicionário compôs a resposta."
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
    description=(
        "Retorna publicações em ordem decrescente de versão, com checksums, referência da fonte, data observada, "
        "instante de publicação e resumo. Uma nova tentativa de importação com o mesmo checksum semântico não cria "
        "uma versão. O checksum do arquivo de origem pode mudar por metadados XLSX mesmo quando a hierarquia continua igual. "
        "Taxonomia inexistente retorna `404`; uma taxonomia conhecida sem publicação ainda pode responder uma lista vazia."
    ),
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
    "/setores/taxonomias/b3/importacoes",
    response_model=list[SetorTaxonomiaImportacaoResposta],
    summary="Consultar histórico de importações manuais B3",
    description=(
        "Lista as tentativas mais recentes de upload da classificação B3, incluindo o nome e SHA-256 do arquivo, "
        "tamanho, data de atualização informada pelo operador, responsável autenticado, estado, versão resultante, "
        "contagens, erro de validação e instantes de recebimento/conclusão. Inclui reenvios sem alteração semântica "
        "e planilhas XLSX rejeitadas depois da validação do layout. Ordena da tentativa mais recente para a mais antiga; "
        "não retorna o caminho local de armazenamento nem o conteúdo do arquivo."
    ),
    operation_id="listarImportacoesTaxonomiaB3",
)
def listar_importacoes_taxonomia_b3(
    db: DbSession,
    limite: Annotated[
        int,
        Query(ge=1, le=500, description="Quantidade máxima de registros retornados, entre 1 e 500."),
    ] = 100,
) -> list[SetorTaxonomiaImportacaoResposta]:
    importacoes = db.scalars(
        select(SetorTaxonomiaImportacao)
        .where(SetorTaxonomiaImportacao.taxonomia == TAXONOMIA_B3)
        .order_by(SetorTaxonomiaImportacao.importada_em.desc(), SetorTaxonomiaImportacao.id.desc())
        .limit(limite)
    ).all()
    return [SetorTaxonomiaImportacaoResposta.model_validate(item) for item in importacoes]


@router.post(
    "/setores/taxonomias/b3/importacoes",
    response_model=SetorTaxonomiaImportacaoResposta,
    summary="Importar arquivo manual da classificação B3",
    description=(
        "Recebe um arquivo XLSX da classificação setorial B3 via `multipart/form-data`. A validação procura em uma única aba "
        "as colunas B-D com cabeçalho `SETOR` (ou `SETOR ECONÔMICO`), `SUBSETOR` e `SEGMENTO`; linhas de setor e subsetor "
        "podem continuar com as células correspondentes vazias para indicar preenchimento hierárquico. O parser lê apenas "
        "essas três colunas, deduplica caminhos repetidos e ignora as colunas de emissores, tickers/códigos e segmentos de listagem. "
        "Publica somente nós de nível setor, subsetor e segmento: não importa emissores, não cria vínculos B3 de companhias e "
        "não substitui as atribuições originadas na CVM.\n\n"
        "O arquivo original é preservado em `STORAGE_DIR/setores/b3/` pelo SHA-256 dos bytes recebidos. Cada tentativa é "
        "registrada com tamanho, nome, data da fonte informada, responsável e resultado. Um checksum semântico igual à "
        "versão atual registra `sem_alteracao` sem criar versão; uma mudança em nome, identidade ou hierarquia publica a "
        "próxima versão e registra inclusões, alterações e desativações. O mesmo caminho hierárquico normalizado conserva "
        "o UUID; um caminho diferente não é unido automaticamente a um ID antigo.\n\n"
        "Exige token bearer com permissão administrativa (ou credencial de sistema). Arquivos são limitados a 10 MiB e "
        "10.000 linhas por aba. Uma planilha XLSX inválida ou sem exatamente uma aba com o layout esperado é registrada "
        "como rejeitada e retorna `422` com `importacao_id`; erros de extensão, tamanho ou validação do formulário ocorrem "
        "antes do registro da tentativa."
    ),
    operation_id="importarTaxonomiaB3Manual",
    responses={
        200: {"description": "Tentativa processada; consulte `status` para distinguir publicação e reenvio sem alteração."},
        401: {"description": "Bearer token ausente, inválido ou expirado."},
        403: {"description": "Token de usuário válido sem permissão administrativa."},
        413: {"description": "Arquivo XLSX excede o limite de tamanho de 10 MiB; tentativa não registrada."},
        422: {
            "description": (
                "Extensão, campos ou data inválidos; ou planilha XLSX sem o layout esperado. "
                "Rejeições de conteúdo retornam código `ARQUIVO_CLASSIFICACAO_B3_REJEITADO` e `importacao_id` "
                "e ficam disponíveis no histórico."
            ),
            "content": {
                "application/json": {
                    "examples": {
                        "planilha_rejeitada": {
                            "summary": "Conteúdo XLSX inválido, registrado para auditoria",
                            "value": {
                                "detail": {
                                    "codigo": "ARQUIVO_CLASSIFICACAO_B3_REJEITADO",
                                    "importacao_id": "0c8df70a-33c6-4c1a-b690-8dd2a49c615b",
                                    "mensagem": "A planilha não contém segmentos B3 com setor e subsetor.",
                                }
                            },
                        },
                        "extensao_invalida": {
                            "summary": "Erro de extensão detectado antes de registrar a tentativa",
                            "value": {"detail": "Envie um arquivo com extensão .xlsx."},
                        },
                    }
                }
            },
        },
    },
)
async def importar_taxonomia_b3_manual(
    db: DbSession,
    importado_por: Annotated[str, Depends(_obter_admin_importador)],
    arquivo: Annotated[
        UploadFile,
        File(
            description=(
                "Arquivo .xlsx original da classificação B3, no máximo 10 MiB. A planilha deve conter uma aba com "
                "cabeçalhos SETOR/SETOR ECONÔMICO, SUBSETOR e SEGMENTO nas colunas B-D."
            ),
        ),
    ],
    data_atualizacao_fonte: Annotated[
        date | None,
        Form(
            description="Data de atualização informada pelo operador; não é extraída automaticamente do XLSX.",
            examples=["2026-11-10"],
        ),
    ] = None,
    referencia_fonte: Annotated[
        str,
        Form(
            max_length=255,
            description="URL ou identificador da origem do arquivo; padrão aponta para a página pública da classificação B3.",
        ),
    ] = URL_CLASSIFICACAO_B3,
    observacao: Annotated[
        str | None,
        Form(max_length=1000, description="Nota de auditoria opcional sobre download, conferência ou contexto da importação."),
    ] = None,
) -> SetorTaxonomiaImportacaoResposta:
    nome_arquivo = arquivo.filename or "ClassifSetorial.xlsx"
    if not nome_arquivo.lower().endswith(".xlsx"):
        raise HTTPException(status_code=422, detail="Envie um arquivo com extensão .xlsx.")
    conteudo = await arquivo.read(MAX_ARQUIVO_B3_BYTES + 1)
    await arquivo.close()
    if len(conteudo) > MAX_ARQUIVO_B3_BYTES:
        raise HTTPException(status_code=413, detail="O arquivo excede o limite de 10 MiB.")
    try:
        importacao = importar_taxonomia_b3_service(
            db,
            conteudo=conteudo,
            nome_arquivo=nome_arquivo,
            data_atualizacao_fonte=data_atualizacao_fonte,
            importado_por=importado_por,
            referencia_fonte=referencia_fonte,
            observacao=observacao,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    if importacao.status == "rejeitada":
        raise HTTPException(
            status_code=422,
            detail={
                "codigo": "ARQUIVO_CLASSIFICACAO_B3_REJEITADO",
                "importacao_id": str(importacao.id),
                "mensagem": importacao.erro,
            },
        )
    return SetorTaxonomiaImportacaoResposta.model_validate(importacao)


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
