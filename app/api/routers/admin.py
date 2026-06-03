from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query
from sqlalchemy import func, select

from app.api.auth import validar_token_api
from app.api.deps import DbSession
from app.core.config import get_settings
from app.models.sincronizacao import ExecucaoSincronizacao, HistoricoAlteracaoCampo, RegistroQuarentena
from app.schemas.admin import (
    DashboardExecucoesResposta,
    ExecucaoSincronizacaoDetalhe,
    ExecucaoSincronizacaoResumo,
    HistoricoAlteracaoCampoResposta,
    ListaExecucoesSincronizacao,
    ListaHistoricoAlteracoes,
    ListaRegistrosQuarentena,
    RegistroQuarentenaResposta,
    RespostaAgendamentoEmLote,
    RespostaAgendamentoSincronizacao,
    TarefaAgendadaResumo,
)
from app.schemas.comum import Paginacao
from app.worker.tasks import (
    sincronizar_cadastro_companhias_task,
    sincronizar_dfp_task,
    sincronizar_fre_task,
    sincronizar_itr_task,
)

router = APIRouter(prefix="/admin")

_RESPOSTA_TOKEN_INVALIDO = {
    401: {
        "description": "Token de acesso ausente ou invalido.",
        "content": {"application/json": {"example": {"detail": "Token de acesso invalido."}}},
    }
}


def _extrair_ano_arquivo(arquivo: str) -> int | None:
    numeros = "".join(ch if ch.isdigit() else " " for ch in arquivo).split()
    for bloco in numeros[::-1]:
        if len(bloco) == 4:
            ano = int(bloco)
            if 2010 <= ano <= 2100:
                return ano
    return None


def _agendar_por_arquivo(arquivo: str, ano: int | None) -> TarefaAgendadaResumo:
    arquivo_normalizado = arquivo.lower().strip()
    ano_efetivo = ano if ano is not None else _extrair_ano_arquivo(arquivo_normalizado)

    if arquivo_normalizado == "cad_cia_aberta.csv":
        tarefa = sincronizar_cadastro_companhias_task.delay()
        return TarefaAgendadaResumo(tipo_fonte="cadastro", ano=None, id_tarefa=str(tarefa.id))

    if arquivo_normalizado.startswith("dfp_cia_aberta_"):
        if ano_efetivo is None:
            raise HTTPException(status_code=422, detail="Ano obrigatorio para reprocessar arquivo DFP.")
        tarefa = sincronizar_dfp_task.delay(ano_efetivo)
        return TarefaAgendadaResumo(tipo_fonte="dfp", ano=ano_efetivo, id_tarefa=str(tarefa.id))

    if arquivo_normalizado.startswith("itr_cia_aberta_"):
        if ano_efetivo is None:
            raise HTTPException(status_code=422, detail="Ano obrigatorio para reprocessar arquivo ITR.")
        tarefa = sincronizar_itr_task.delay(ano_efetivo)
        return TarefaAgendadaResumo(tipo_fonte="itr", ano=ano_efetivo, id_tarefa=str(tarefa.id))

    if arquivo_normalizado.startswith("fre_cia_aberta_"):
        if ano_efetivo is None:
            raise HTTPException(status_code=422, detail="Ano obrigatorio para reprocessar arquivo FRE.")
        tarefa = sincronizar_fre_task.delay(ano_efetivo)
        return TarefaAgendadaResumo(tipo_fonte="fre", ano=ano_efetivo, id_tarefa=str(tarefa.id))

    raise HTTPException(status_code=422, detail="Arquivo nao suportado para reprocessamento seletivo.")


@router.post(
    "/sincronizacoes/cadastro",
    response_model=RespostaAgendamentoSincronizacao,
    summary="Disparar Sincronizacao de Cadastro",
    description="Agenda tarefa assincrona de sincronizacao do arquivo cadastral de companhias.",
    responses=_RESPOSTA_TOKEN_INVALIDO,
    operation_id="dispararSincronizacaoCadastroAdmin",
)
def disparar_sincronizacao_cadastro(
    _: Annotated[None, Depends(validar_token_api)],
) -> dict[str, str]:
    tarefa = sincronizar_cadastro_companhias_task.delay()
    return {"id_tarefa": str(tarefa.id), "status": "agendada"}


@router.post(
    "/sincronizacoes/dfp/{ano}",
    response_model=RespostaAgendamentoSincronizacao,
    summary="Disparar Sincronizacao DFP",
    description="Agenda tarefa assincrona de sincronizacao de um ZIP anual DFP.",
    responses=_RESPOSTA_TOKEN_INVALIDO,
    operation_id="dispararSincronizacaoDfpAdmin",
)
def disparar_sincronizacao_dfp(
    ano: Annotated[int, Path(ge=2010, description="Ano do pacote DFP.", examples=[2025])],
    _: Annotated[None, Depends(validar_token_api)],
) -> dict[str, str]:
    tarefa = sincronizar_dfp_task.delay(ano)
    return {"id_tarefa": str(tarefa.id), "status": "agendada"}


@router.post(
    "/sincronizacoes/itr/{ano}",
    response_model=RespostaAgendamentoSincronizacao,
    summary="Disparar Sincronizacao ITR",
    description="Agenda tarefa assincrona de sincronizacao de um ZIP anual ITR.",
    responses=_RESPOSTA_TOKEN_INVALIDO,
    operation_id="dispararSincronizacaoItrAdmin",
)
def disparar_sincronizacao_itr(
    ano: Annotated[int, Path(ge=2010, description="Ano do pacote ITR.", examples=[2025])],
    _: Annotated[None, Depends(validar_token_api)],
) -> dict[str, str]:
    tarefa = sincronizar_itr_task.delay(ano)
    return {"id_tarefa": str(tarefa.id), "status": "agendada"}


@router.post(
    "/sincronizacoes/fre/{ano}",
    response_model=RespostaAgendamentoSincronizacao,
    summary="Disparar Sincronizacao FRE",
    description="Agenda tarefa assincrona de sincronizacao de um ZIP anual FRE.",
    responses=_RESPOSTA_TOKEN_INVALIDO,
    operation_id="dispararSincronizacaoFreAdmin",
)
def disparar_sincronizacao_fre(
    ano: Annotated[int, Path(ge=2010, description="Ano do pacote FRE.", examples=[2025])],
    _: Annotated[None, Depends(validar_token_api)],
) -> dict[str, str]:
    tarefa = sincronizar_fre_task.delay(ano)
    return {"id_tarefa": str(tarefa.id), "status": "agendada"}


@router.post(
    "/sincronizacoes/tudo",
    response_model=RespostaAgendamentoEmLote,
    summary="Disparar Sincronizacao Completa",
    description="Agenda cadastro e sincronizacoes DFP/ITR/FRE para os anos iniciais configurados no ambiente.",
    responses=_RESPOSTA_TOKEN_INVALIDO,
    operation_id="dispararSincronizacaoTudoAdmin",
)
def disparar_sincronizacao_tudo(
    _: Annotated[None, Depends(validar_token_api)],
) -> RespostaAgendamentoEmLote:
    settings = get_settings()
    tarefas: list[TarefaAgendadaResumo] = []

    tarefa_cadastro = sincronizar_cadastro_companhias_task.delay()
    tarefas.append(TarefaAgendadaResumo(tipo_fonte="cadastro", ano=None, id_tarefa=str(tarefa_cadastro.id)))

    for ano in settings.parse_anos(settings.anos_iniciais_dfp):
        tarefa = sincronizar_dfp_task.delay(ano)
        tarefas.append(TarefaAgendadaResumo(tipo_fonte="dfp", ano=ano, id_tarefa=str(tarefa.id)))
    for ano in settings.parse_anos(settings.anos_iniciais_itr):
        tarefa = sincronizar_itr_task.delay(ano)
        tarefas.append(TarefaAgendadaResumo(tipo_fonte="itr", ano=ano, id_tarefa=str(tarefa.id)))
    for ano in settings.parse_anos(settings.anos_iniciais_fre):
        tarefa = sincronizar_fre_task.delay(ano)
        tarefas.append(TarefaAgendadaResumo(tipo_fonte="fre", ano=ano, id_tarefa=str(tarefa.id)))

    return RespostaAgendamentoEmLote(status="agendada", tarefas=tarefas)


@router.post(
    "/sincronizacoes/reprocessar-arquivo",
    response_model=RespostaAgendamentoEmLote,
    summary="Reprocessar Arquivo Seletivo",
    description=(
        "Dispara reprocessamento seletivo por nome de arquivo CVM. "
        "Aceita arquivos `cad_cia_aberta.csv`, `dfp_cia_aberta_*`, `itr_cia_aberta_*` e `fre_cia_aberta_*`."
    ),
    responses=_RESPOSTA_TOKEN_INVALIDO,
    operation_id="reprocessarArquivoAdmin",
)
def reprocessar_arquivo(
    _: Annotated[None, Depends(validar_token_api)],
    payload: Annotated[
        dict[str, str | int | None],
        Body(
            examples=[
                {"arquivo": "dfp_cia_aberta_2025.zip"},
                {"arquivo": "fre_cia_aberta_2025.csv", "ano": 2025},
            ],
        ),
    ],
) -> RespostaAgendamentoEmLote:
    arquivo = payload.get("arquivo")
    if not isinstance(arquivo, str) or not arquivo.strip():
        raise HTTPException(status_code=422, detail="Campo 'arquivo' obrigatorio.")
    ano = payload.get("ano")
    if ano is not None and not isinstance(ano, int):
        raise HTTPException(status_code=422, detail="Campo 'ano' deve ser inteiro quando informado.")

    tarefa = _agendar_por_arquivo(arquivo, ano)
    return RespostaAgendamentoEmLote(status="agendada", tarefas=[tarefa])


@router.get(
    "/sincronizacoes",
    response_model=ListaExecucoesSincronizacao,
    summary="Listar Execucoes de Sincronizacao",
    description="Lista paginada das execucoes registradas no sistema de sincronizacao.",
    responses=_RESPOSTA_TOKEN_INVALIDO,
    operation_id="listarExecucoesSincronizacaoAdmin",
)
def listar_execucoes(
    db: DbSession,
    _: Annotated[None, Depends(validar_token_api)],
    pagina: Annotated[int, Query(ge=1, description="Numero da pagina.", examples=[1])] = 1,
    tamanho_pagina: Annotated[
        int, Query(ge=1, le=500, description="Quantidade de itens por pagina.", examples=[100])
    ] = 100,
) -> ListaExecucoesSincronizacao:
    offset = (pagina - 1) * tamanho_pagina
    execucoes = (
        db.execute(
            select(ExecucaoSincronizacao)
            .order_by(ExecucaoSincronizacao.iniciada_em.desc())
            .offset(offset)
            .limit(tamanho_pagina)
        )
        .scalars()
        .all()
    )
    total = db.query(ExecucaoSincronizacao).count()
    dados = [
        ExecucaoSincronizacaoResumo(
            id=str(item.id),
            tipo_fonte=item.tipo_fonte,
            arquivo=item.arquivo,
            status=item.status,
            iniciada_em=item.iniciada_em,
            finalizada_em=item.finalizada_em,
            total_linhas_lidas=item.total_linhas_lidas,
            total_inseridos=item.total_inseridos,
            total_atualizados=item.total_atualizados,
            total_inalterados=item.total_inalterados,
            total_rejeitados=item.total_rejeitados,
        )
        for item in execucoes
    ]
    return ListaExecucoesSincronizacao(
        dados=dados,
        paginacao=Paginacao(pagina=pagina, tamanho_pagina=tamanho_pagina, total=total),
    )


@router.get(
    "/sincronizacoes/{id_execucao}",
    response_model=ExecucaoSincronizacaoDetalhe,
    summary="Detalhar Execucao de Sincronizacao",
    description="Retorna o detalhamento completo de uma execucao pelo identificador.",
    responses={
        **_RESPOSTA_TOKEN_INVALIDO,
        404: {
            "description": "Execucao nao encontrada.",
            "content": {"application/json": {"example": {"detail": "Execucao nao encontrada."}}},
        },
    },
    operation_id="detalharExecucaoSincronizacaoAdmin",
)
def detalhar_execucao(
    id_execucao: Annotated[str, Path(description="ID da execucao de sincronizacao.", examples=["uuid"])],
    db: DbSession,
    _: Annotated[None, Depends(validar_token_api)],
) -> ExecucaoSincronizacaoDetalhe:
    execucao = db.get(ExecucaoSincronizacao, id_execucao)
    if execucao is None:
        raise HTTPException(status_code=404, detail="Execucao nao encontrada.")
    return ExecucaoSincronizacaoDetalhe(
        id=str(execucao.id),
        tipo_fonte=execucao.tipo_fonte,
        ano=execucao.ano,
        arquivo=execucao.arquivo,
        url=execucao.url,
        hash_arquivo=execucao.hash_arquivo,
        status=execucao.status,
        iniciada_em=execucao.iniciada_em,
        finalizada_em=execucao.finalizada_em,
        total_linhas_lidas=execucao.total_linhas_lidas,
        total_inseridos=execucao.total_inseridos,
        total_atualizados=execucao.total_atualizados,
        total_inalterados=execucao.total_inalterados,
        total_rejeitados=execucao.total_rejeitados,
        mensagem_erro=execucao.mensagem_erro,
    )


@router.get(
    "/quarentena",
    response_model=ListaRegistrosQuarentena,
    summary="Listar Quarentena",
    description="Lista paginada dos registros rejeitados para quarentena.",
    responses=_RESPOSTA_TOKEN_INVALIDO,
    operation_id="listarQuarentenaAdmin",
)
def listar_quarentena(
    db: DbSession,
    _: Annotated[None, Depends(validar_token_api)],
    pagina: Annotated[int, Query(ge=1, description="Numero da pagina.", examples=[1])] = 1,
    tamanho_pagina: Annotated[
        int, Query(ge=1, le=500, description="Quantidade de itens por pagina.", examples=[100])
    ] = 100,
    motivo: Annotated[
        str | None,
        Query(description="Filtrar por motivo da rejeicao.", examples=["companhia_nao_encontrada"]),
    ] = None,
) -> ListaRegistrosQuarentena:
    offset = (pagina - 1) * tamanho_pagina
    query = select(RegistroQuarentena)
    query_total = select(func.count()).select_from(RegistroQuarentena)
    if motivo:
        query = query.where(RegistroQuarentena.motivo == motivo)
        query_total = query_total.where(RegistroQuarentena.motivo == motivo)
    itens = (
        db.execute(query.order_by(RegistroQuarentena.criado_em.desc()).offset(offset).limit(tamanho_pagina))
        .scalars()
        .all()
    )
    total = db.scalar(query_total) or 0
    return ListaRegistrosQuarentena(
        dados=[
            RegistroQuarentenaResposta(
                id=str(item.id),
                execucao_sincronizacao_id=str(item.execucao_sincronizacao_id),
                arquivo_origem=item.arquivo_origem,
                ano_origem=item.ano_origem,
                linha_origem=item.linha_origem,
                motivo=item.motivo,
                dados_originais=item.dados_originais,
                criado_em=item.criado_em,
            )
            for item in itens
        ],
        paginacao=Paginacao(pagina=pagina, tamanho_pagina=tamanho_pagina, total=total),
    )


@router.get(
    "/alteracoes",
    response_model=ListaHistoricoAlteracoes,
    summary="Listar Historico de Alteracoes",
    description="Lista paginada de alteracoes campo a campo registradas nas sincronizacoes.",
    responses=_RESPOSTA_TOKEN_INVALIDO,
    operation_id="listarAlteracoesAdmin",
)
def listar_alteracoes(
    db: DbSession,
    _: Annotated[None, Depends(validar_token_api)],
    pagina: Annotated[int, Query(ge=1, description="Numero da pagina.", examples=[1])] = 1,
    tamanho_pagina: Annotated[
        int, Query(ge=1, le=500, description="Quantidade de itens por pagina.", examples=[100])
    ] = 100,
    entidade: Annotated[
        str | None,
        Query(description="Filtrar por entidade alterada.", examples=["documentos_financeiros"]),
    ] = None,
) -> ListaHistoricoAlteracoes:
    offset = (pagina - 1) * tamanho_pagina
    query = select(HistoricoAlteracaoCampo)
    query_total = select(func.count()).select_from(HistoricoAlteracaoCampo)
    if entidade:
        query = query.where(HistoricoAlteracaoCampo.entidade == entidade)
        query_total = query_total.where(HistoricoAlteracaoCampo.entidade == entidade)
    itens = (
        db.execute(query.order_by(HistoricoAlteracaoCampo.alterado_em.desc()).offset(offset).limit(tamanho_pagina))
        .scalars()
        .all()
    )
    total = db.scalar(query_total) or 0
    return ListaHistoricoAlteracoes(
        dados=[
            HistoricoAlteracaoCampoResposta(
                id=str(item.id),
                entidade=item.entidade,
                entidade_id=str(item.entidade_id),
                companhia_id=None if item.companhia_id is None else str(item.companhia_id),
                campo=item.campo,
                valor_anterior=item.valor_anterior,
                valor_novo=item.valor_novo,
                alterado_em=item.alterado_em,
                execucao_sincronizacao_id=str(item.execucao_sincronizacao_id),
                arquivo_origem=item.arquivo_origem,
                ano_origem=item.ano_origem,
            )
            for item in itens
        ],
        paginacao=Paginacao(pagina=pagina, tamanho_pagina=tamanho_pagina, total=total),
    )


@router.get(
    "/dashboard",
    response_model=DashboardExecucoesResposta,
    summary="Dashboard de Execucoes",
    description="Consolidado simples para operacao: status, rejeicoes e ultimas execucoes.",
    responses=_RESPOSTA_TOKEN_INVALIDO,
    operation_id="dashboardExecucoesAdmin",
)
def dashboard_execucoes(
    db: DbSession,
    _: Annotated[None, Depends(validar_token_api)],
) -> DashboardExecucoesResposta:
    total_execucoes = db.scalar(select(func.count()).select_from(ExecucaoSincronizacao)) or 0
    total_sucesso = db.scalar(
        select(func.count()).select_from(ExecucaoSincronizacao).where(ExecucaoSincronizacao.status == "sucesso")
    ) or 0
    total_sem_alteracao = (
        db.scalar(
            select(func.count())
            .select_from(ExecucaoSincronizacao)
            .where(ExecucaoSincronizacao.status == "sem_alteracao")
        )
        or 0
    )
    total_falha = db.scalar(
        select(func.count()).select_from(ExecucaoSincronizacao).where(ExecucaoSincronizacao.status == "falha")
    ) or 0
    total_rejeitados = db.scalar(select(func.coalesce(func.sum(ExecucaoSincronizacao.total_rejeitados), 0))) or 0
    ultimas = (
        db.execute(select(ExecucaoSincronizacao).order_by(ExecucaoSincronizacao.iniciada_em.desc()).limit(10))
        .scalars()
        .all()
    )
    return DashboardExecucoesResposta(
        total_execucoes=total_execucoes,
        total_sucesso=total_sucesso,
        total_sem_alteracao=total_sem_alteracao,
        total_falha=total_falha,
        total_rejeitados=total_rejeitados,
        ultimas_execucoes=[
            ExecucaoSincronizacaoResumo(
                id=str(item.id),
                tipo_fonte=item.tipo_fonte,
                arquivo=item.arquivo,
                status=item.status,
                iniciada_em=item.iniciada_em,
                finalizada_em=item.finalizada_em,
                total_linhas_lidas=item.total_linhas_lidas,
                total_inseridos=item.total_inseridos,
                total_atualizados=item.total_atualizados,
                total_inalterados=item.total_inalterados,
                total_rejeitados=item.total_rejeitados,
            )
            for item in ultimas
        ],
    )
