from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query
from sqlalchemy import func, select

from app.api.auth import validar_token_api
from app.api.deps import DbSession
from app.core.config import get_settings
from app.models.ingestion import IngestionFile, IngestionFileMember, IngestionRun, QuarantineItem
from app.models.sincronizacao import ExecucaoSincronizacao, HistoricoAlteracaoCampo, RegistroQuarentena
from app.schemas.admin import (
    AnaliseArquivo,
    AuditoriaFonteResposta,
    AuditoriaFontesRequisicao,
    AuditoriaFontesResposta,
    DashboardExecucoesResposta,
    ExecucaoSincronizacaoDetalhe,
    ExecucaoSincronizacaoResumo,
    FonteDatasetResumoResposta,
    FonteDetalheResposta,
    FonteResumoResposta,
    HistoricoAlteracaoCampoResposta,
    IngestionRunResumo,
    ListaExecucoesSincronizacao,
    ListaFontesResposta,
    ListaHistoricoAlteracoes,
    ListaIngestionRuns,
    ListaQuarantineItems,
    ListaRegistrosQuarentena,
    QuarantineItemResposta,
    RegistroQuarentenaResposta,
    ReplayQuarantineRequisicao,
    ReplayResposta,
    RespostaAgendamentoEmLote,
    RespostaAgendamentoSincronizacao,
    RespostaCancelamentoSincronizacao,
    SolicitacaoCancelamentoSincronizacao,
    TarefaAgendadaResumo,
)
from app.schemas.comum import Paginacao
from app.services.ingestion.audit import build_dataset_discovery_audit
from app.services.ingestion.cadastro import sincronizar_cadastro_companhias
from app.services.ingestion.replay import replay_ingestion_run as replay_ingestion_run_service
from app.services.ingestion.replay import replay_quarantine
from app.services.ingestion.source_registry import listar_datasets, listar_fontes, obter_fonte
from app.services.ingestion.staging import formatar_tamanho
from celery import chain, group
from app.worker.celery_app import celery_app
from app.worker.tasks import (
    sincronizar_cadastro_companhias_task,
    sincronizar_cgvn_task,
    sincronizar_dfp_task,
    sincronizar_fca_task,
    sincronizar_fre_task,
    sincronizar_ipe_task,
    sincronizar_itr_task,
    sincronizar_vlmo_task,
    pre_processar_sincronizacao_task,
    ingerir_sincronizacao_task,
)

router = APIRouter(prefix="/admin")

_RESPOSTA_TOKEN_INVALIDO: dict[int | str, dict[str, Any]] = {
    401: {
        "description": "Token de acesso ausente ou invalido.",
        "content": {"application/json": {"example": {"detail": "Token de acesso invalido."}}},
    }
}

_STATUS_FINAL_EXECUCAO = {"sucesso", "sem_alteracao", "skipped", "falha", "cancelada"}


def _agora() -> datetime:
    return datetime.now(UTC)


def _extrair_ano_arquivo(arquivo: str) -> int | None:
    numeros = "".join(ch if ch.isdigit() else " " for ch in arquivo).split()
    for bloco in numeros[::-1]:
        if len(bloco) == 4:
            ano = int(bloco)
            if 2003 <= ano <= 2100:
                return ano
    return None


def _arquivo_suportado_por_fonte(fonte: str, arquivo: str, ano: int | None) -> bool:
    fonte_item = obter_fonte(fonte)
    if fonte_item is None:
        return False
    if fonte == "cadastro":
        return any(item.render_member_name(ano=0) == arquivo for item in listar_datasets("cadastro"))
    if ano is None:
        return False
    if fonte_item.render_arquivo_principal(ano=ano) == arquivo:
        return True
    return any(item.render_member_name(ano=ano) == arquivo for item in listar_datasets(fonte))


def _agendar_por_arquivo(
    db: DbSession, arquivo: str, ano: int | None, force_reimport: bool = False
) -> TarefaAgendadaResumo:
    arquivo_normalizado = arquivo.lower().strip()
    ano_efetivo = ano if ano is not None else _extrair_ano_arquivo(arquivo_normalizado)

    if _arquivo_suportado_por_fonte("cadastro", arquivo_normalizado, None):
        tarefa = sincronizar_cadastro_companhias_task.delay(force_reimport=force_reimport)
        return TarefaAgendadaResumo(tipo_fonte="cadastro", ano=None, id_tarefa=str(tarefa.id))

    tipo_fonte = None
    for src in ("dfp", "itr", "fre", "fca", "ipe", "vlmo", "cgvn"):
        if _arquivo_suportado_por_fonte(src, arquivo_normalizado, ano_efetivo):
            tipo_fonte = src
            break

    if tipo_fonte is None:
        raise HTTPException(status_code=422, detail="Arquivo nao suportado para reprocessamento seletivo.")

    if ano_efetivo is None:
        raise HTTPException(status_code=422, detail=f"Ano obrigatorio para reprocessar arquivo {tipo_fonte.upper()}.")

    is_zip = arquivo_normalizado.endswith(".zip") or arquivo_normalizado == f"{tipo_fonte}_cia_aberta_{ano_efetivo}.zip"

    if is_zip:
        task_mapper = {
            "dfp": sincronizar_dfp_task,
            "itr": sincronizar_itr_task,
            "fre": sincronizar_fre_task,
            "fca": sincronizar_fca_task,
            "ipe": sincronizar_ipe_task,
            "vlmo": sincronizar_vlmo_task,
            "cgvn": sincronizar_cgvn_task,
        }
        task_func = task_mapper[tipo_fonte]
        tarefa = task_func.delay(ano_efetivo, force_reimport=force_reimport)
        return TarefaAgendadaResumo(tipo_fonte=tipo_fonte, ano=ano_efetivo, id_tarefa=str(tarefa.id))
    else:
        from app.models.sincronizacao import ExecucaoSincronizacao
        from app.worker.tasks import sincronizar_member_task

        exec_pai = db.scalar(
            select(ExecucaoSincronizacao)
            .where(
                ExecucaoSincronizacao.tipo_fonte == tipo_fonte,
                ExecucaoSincronizacao.ano == ano_efetivo,
                ExecucaoSincronizacao.tipo_execucao == "arquivo_zip",
            )
            .order_by(ExecucaoSincronizacao.iniciada_em.desc())
            .limit(1)
        )
        if exec_pai is None:
            raise HTTPException(
                status_code=404,
                detail=f"Execucao pai nao encontrada para fonte {tipo_fonte} e ano {ano_efetivo}."
            )

        child_exec = ExecucaoSincronizacao(
            parent_execucao_id=exec_pai.id,
            tipo_execucao="arquivo_membro",
            tipo_fonte=tipo_fonte,
            ano=ano_efetivo,
            arquivo=arquivo_normalizado,
            url=exec_pai.url,
            status="agendada",
        )
        db.add(child_exec)
        db.commit()
        db.refresh(child_exec)

        tarefa = sincronizar_member_task.delay(
            tipo_fonte=tipo_fonte,
            ano=ano_efetivo,
            member_name=arquivo_normalizado,
            parent_execucao_id=str(exec_pai.id),
            child_execucao_id=str(child_exec.id),
            force_reimport=force_reimport,
        )
        return TarefaAgendadaResumo(
            tipo_fonte=f"{tipo_fonte}_membro",
            ano=ano_efetivo,
            id_tarefa=str(tarefa.id),
        )


def _resumo_fonte(fonte: Any) -> FonteResumoResposta:
    return FonteResumoResposta(
        fonte=fonte.fonte,
        familia=fonte.familia,
        descricao=fonte.descricao,
        tipo_distribuicao=fonte.tipo_distribuicao,
        status_suporte=fonte.status_suporte,
        dependencias=list(fonte.dependencias),
        primeiro_ano=fonte.primeiro_ano,
        ultimo_ano=fonte.ultimo_ano,
        total_datasets=fonte.total_datasets,
        datasets_obrigatorios=fonte.datasets_obrigatorios,
        datasets_opcionais=fonte.datasets_opcionais,
    )


def _resumo_dataset(dataset: Any) -> FonteDatasetResumoResposta:
    return FonteDatasetResumoResposta(
        dataset=dataset.dataset,
        descricao=dataset.descricao,
        member_name_template=dataset.member_name_template,
        row_kind=dataset.row_kind,
        destino_promovido=dataset.destino_promovido,
        obrigatorio=dataset.obrigatorio,
        status_suporte=dataset.status_suporte,
        normalizador=dataset.normalizador,
        chaves_relacao=list(dataset.chaves_relacao),
        observacoes=dataset.observacoes,
    )


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
    force_reimport: Annotated[
        bool, Query(description="Quando `true`, reprocessa mesmo se o hash do arquivo ja existir.", examples=[False])
    ] = False,
) -> dict[str, str]:
    tarefa = sincronizar_cadastro_companhias_task.delay(force_reimport=force_reimport)
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
    force_reimport: Annotated[
        bool, Query(description="Quando `true`, reprocessa mesmo se o hash do ZIP ja existir.", examples=[False])
    ] = False,
) -> dict[str, str]:
    tarefa = sincronizar_dfp_task.delay(ano, force_reimport=force_reimport)
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
    force_reimport: Annotated[
        bool, Query(description="Quando `true`, reprocessa mesmo se o hash do ZIP ja existir.", examples=[False])
    ] = False,
) -> dict[str, str]:
    tarefa = sincronizar_itr_task.delay(ano, force_reimport=force_reimport)
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
    force_reimport: Annotated[
        bool, Query(description="Quando `true`, reprocessa mesmo se o hash do ZIP ja existir.", examples=[False])
    ] = False,
) -> dict[str, str]:
    tarefa = sincronizar_fre_task.delay(ano, force_reimport=force_reimport)
    return {"id_tarefa": str(tarefa.id), "status": "agendada"}


@router.post(
    "/sincronizacoes/fca/{ano}",
    response_model=RespostaAgendamentoSincronizacao,
    summary="Disparar Sincronizacao FCA",
    description="Agenda tarefa assincrona de sincronizacao de um ZIP anual FCA.",
    responses=_RESPOSTA_TOKEN_INVALIDO,
    operation_id="dispararSincronizacaoFcaAdmin",
)
def disparar_sincronizacao_fca(
    ano: Annotated[int, Path(ge=2010, description="Ano do pacote FCA.", examples=[2025])],
    _: Annotated[None, Depends(validar_token_api)],
    force_reimport: Annotated[
        bool, Query(description="Quando `true`, reprocessa mesmo se o hash do ZIP ja existir.", examples=[False])
    ] = False,
) -> dict[str, str]:
    tarefa = sincronizar_fca_task.delay(ano, force_reimport=force_reimport)
    return {"id_tarefa": str(tarefa.id), "status": "agendada"}


@router.post(
    "/sincronizacoes/ipe/{ano}",
    response_model=RespostaAgendamentoSincronizacao,
    summary="Disparar Sincronizacao IPE",
    description="Agenda tarefa assincrona de sincronizacao de um ZIP anual IPE.",
    responses=_RESPOSTA_TOKEN_INVALIDO,
    operation_id="dispararSincronizacaoIpeAdmin",
)
def disparar_sincronizacao_ipe(
    ano: Annotated[int, Path(ge=2003, description="Ano do pacote IPE.", examples=[2025])],
    _: Annotated[None, Depends(validar_token_api)],
    force_reimport: Annotated[
        bool, Query(description="Quando `true`, reprocessa mesmo se o hash do ZIP ja existir.", examples=[False])
    ] = False,
) -> dict[str, str]:
    tarefa = sincronizar_ipe_task.delay(ano, force_reimport=force_reimport)
    return {"id_tarefa": str(tarefa.id), "status": "agendada"}


@router.post(
    "/sincronizacoes/vlmo/{ano}",
    response_model=RespostaAgendamentoSincronizacao,
    summary="Disparar Sincronizacao VLMO",
    description="Agenda tarefa assincrona de sincronizacao de um ZIP anual VLMO.",
    responses=_RESPOSTA_TOKEN_INVALIDO,
    operation_id="dispararSincronizacaoVlmoAdmin",
)
def disparar_sincronizacao_vlmo(
    ano: Annotated[int, Path(ge=2018, description="Ano do pacote VLMO.", examples=[2025])],
    _: Annotated[None, Depends(validar_token_api)],
    force_reimport: Annotated[
        bool, Query(description="Quando `true`, reprocessa mesmo se o hash do ZIP ja existir.", examples=[False])
    ] = False,
) -> dict[str, str]:
    tarefa = sincronizar_vlmo_task.delay(ano, force_reimport=force_reimport)
    return {"id_tarefa": str(tarefa.id), "status": "agendada"}


@router.post(
    "/sincronizacoes/cgvn/{ano}",
    response_model=RespostaAgendamentoSincronizacao,
    summary="Disparar Sincronizacao CGVN",
    description="Agenda tarefa assincrona de sincronizacao de um ZIP anual CGVN.",
    responses=_RESPOSTA_TOKEN_INVALIDO,
    operation_id="dispararSincronizacaoCgvnAdmin",
)
def disparar_sincronizacao_cgvn(
    ano: Annotated[int, Path(ge=2018, description="Ano do pacote CGVN.", examples=[2025])],
    _: Annotated[None, Depends(validar_token_api)],
    force_reimport: Annotated[
        bool, Query(description="Quando `true`, reprocessa mesmo se o hash do ZIP ja existir.", examples=[False])
    ] = False,
) -> dict[str, str]:
    tarefa = sincronizar_cgvn_task.delay(ano, force_reimport=force_reimport)
    return {"id_tarefa": str(tarefa.id), "status": "agendada"}


@router.post(
    "/sincronizacoes/tudo",
    response_model=RespostaAgendamentoEmLote,
    summary="Disparar Sincronizacao Completa",
    description=(
        "Agenda cadastro e sincronizacoes DFP/ITR/FRE/FCA/IPE/VLMO para os anos iniciais configurados no ambiente."
    ),
    responses=_RESPOSTA_TOKEN_INVALIDO,
    operation_id="dispararSincronizacaoTudoAdmin",
)
def disparar_sincronizacao_tudo(
    _: Annotated[None, Depends(validar_token_api)],
    force_reimport: Annotated[
        bool, Query(description="Quando `true`, reprocessa mesmo se o hash do arquivo ja existir.", examples=[False])
    ] = False,
) -> RespostaAgendamentoEmLote:
    import uuid

    settings = get_settings()
    tarefas: list[TarefaAgendadaResumo] = []

    cadastro_id = str(uuid.uuid4())
    s_cadastro = sincronizar_cadastro_companhias_task.si(force_reimport=force_reimport).set(task_id=cadastro_id)
    tarefas.append(TarefaAgendadaResumo(tipo_fonte="cadastro", ano=None, id_tarefa=cadastro_id))

    outras_sigs = []

    for ano in settings.parse_anos(settings.anos_iniciais_dfp):
        tid = str(uuid.uuid4())
        sig = sincronizar_dfp_task.si(ano, force_reimport=force_reimport).set(task_id=tid)
        outras_sigs.append(sig)
        tarefas.append(TarefaAgendadaResumo(tipo_fonte="dfp", ano=ano, id_tarefa=tid))
    for ano in settings.parse_anos(settings.anos_iniciais_itr):
        tid = str(uuid.uuid4())
        sig = sincronizar_itr_task.si(ano, force_reimport=force_reimport).set(task_id=tid)
        outras_sigs.append(sig)
        tarefas.append(TarefaAgendadaResumo(tipo_fonte="itr", ano=ano, id_tarefa=tid))
    for ano in settings.parse_anos(settings.anos_iniciais_fre):
        tid = str(uuid.uuid4())
        sig = sincronizar_fre_task.si(ano, force_reimport=force_reimport).set(task_id=tid)
        outras_sigs.append(sig)
        tarefas.append(TarefaAgendadaResumo(tipo_fonte="fre", ano=ano, id_tarefa=tid))
    for ano in settings.parse_anos(settings.anos_iniciais_fca):
        tid = str(uuid.uuid4())
        sig = sincronizar_fca_task.si(ano, force_reimport=force_reimport).set(task_id=tid)
        outras_sigs.append(sig)
        tarefas.append(TarefaAgendadaResumo(tipo_fonte="fca", ano=ano, id_tarefa=tid))
    for ano in settings.parse_anos(settings.anos_iniciais_ipe):
        tid = str(uuid.uuid4())
        sig = sincronizar_ipe_task.si(ano, force_reimport=force_reimport).set(task_id=tid)
        outras_sigs.append(sig)
        tarefas.append(TarefaAgendadaResumo(tipo_fonte="ipe", ano=ano, id_tarefa=tid))
    for ano in settings.parse_anos(settings.anos_iniciais_vlmo):
        tid = str(uuid.uuid4())
        sig = sincronizar_vlmo_task.si(ano, force_reimport=force_reimport).set(task_id=tid)
        outras_sigs.append(sig)
        tarefas.append(TarefaAgendadaResumo(tipo_fonte="vlmo", ano=ano, id_tarefa=tid))
    for ano in settings.parse_anos(settings.anos_iniciais_cgvn):
        tid = str(uuid.uuid4())
        sig = sincronizar_cgvn_task.si(ano, force_reimport=force_reimport).set(task_id=tid)
        outras_sigs.append(sig)
        tarefas.append(TarefaAgendadaResumo(tipo_fonte="cgvn", ano=ano, id_tarefa=tid))

    if outras_sigs:
        workflow = chain(s_cadastro, group(outras_sigs))
    else:
        workflow = chain(s_cadastro)

    workflow.apply_async()

    return RespostaAgendamentoEmLote(status="agendada", tarefas=tarefas)


@router.post(
    "/sincronizacoes/pre-processar/cadastro",
    response_model=RespostaAgendamentoSincronizacao,
    summary="Pre-processar Cadastro",
    description="Executa apenas a Fase 1 (download, extração e análise de metadados) do arquivo cadastral de companhias.",
    responses=_RESPOSTA_TOKEN_INVALIDO,
    operation_id="preProcessarCadastroAdmin",
)
def pre_processar_cadastro_route(
    _: Annotated[None, Depends(validar_token_api)],
    force_reimport: Annotated[
        bool, Query(description="Quando `true`, reprocessa mesmo se o hash do arquivo ja existir.", examples=[False])
    ] = False,
) -> dict[str, str]:
    tarefa = pre_processar_sincronizacao_task.delay(tipo_fonte="cadastro", force_reimport=force_reimport)
    return {"id_tarefa": str(tarefa.id), "status": "agendada"}


@router.post(
    "/sincronizacoes/pre-processar/{tipo_fonte}/{ano}",
    response_model=RespostaAgendamentoSincronizacao,
    summary="Pre-processar Fonte Anual (Fase 1)",
    description="Executa apenas a Fase 1 (download, extração e análise de metadados) para uma fonte anual específica (ZIP).",
    responses=_RESPOSTA_TOKEN_INVALIDO,
    operation_id="preProcessarFonteAnualAdmin",
)
def pre_processar_fonte_anual_route(
    tipo_fonte: Annotated[str, Path(description="Tipo de fonte (ex.: dfp, ITR, FCA).")],
    ano: Annotated[int, Path(description="Ano de referência.")],
    _: Annotated[None, Depends(validar_token_api)],
    force_reimport: Annotated[
        bool, Query(description="Quando `true`, reprocessa mesmo se o hash do arquivo ja existir.", examples=[False])
    ] = False,
) -> dict[str, str]:
    fonte_lower = tipo_fonte.lower().strip()
    if fonte_lower not in ("dfp", "itr", "fre", "fca", "ipe", "vlmo", "cgvn"):
        raise HTTPException(status_code=422, detail=f"Fonte '{tipo_fonte}' nao suportada ou nao necessita de ano.")
    
    tarefa = pre_processar_sincronizacao_task.delay(
        tipo_fonte=fonte_lower,
        ano=ano,
        force_reimport=force_reimport,
    )
    return {"id_tarefa": str(tarefa.id), "status": "agendada"}


@router.post(
    "/sincronizacoes/{id_execucao}/ingerir",
    response_model=RespostaAgendamentoSincronizacao,
    summary="Ingerir Fonte Pré-processada (Fase 2)",
    description=(
        "Dispara a Fase 2 (ingestão dos dados de cada arquivo membro para o banco de dados) "
        "para uma execução que está no status 'aguardando_ingestao'."
    ),
    responses={
        **_RESPOSTA_TOKEN_INVALIDO,
        404: {"description": "Execução não encontrada."},
        400: {"description": "Execução não está no status 'aguardando_ingestao'."},
    },
    operation_id="ingerirFontePreProcessadaAdmin",
)
def ingerir_fonte_pre_processada(
    id_execucao: Annotated[UUID, Path(description="ID da execução de sincronização.")],
    db: DbSession,
    _: Annotated[None, Depends(validar_token_api)],
    force_reimport: Annotated[
        bool, Query(description="Quando `true`, força reimportação das tabelas.", examples=[False])
    ] = False,
) -> dict[str, str]:
    execucao = db.get(ExecucaoSincronizacao, id_execucao)
    if execucao is None:
        raise HTTPException(status_code=404, detail="Execucao nao encontrada.")
    
    if execucao.status != "aguardando_ingestao":
        raise HTTPException(
            status_code=400,
            detail=f"Execucao {id_execucao} esta com status '{execucao.status}', mas deve estar em 'aguardando_ingestao' para iniciar a ingestao."
        )
    
    tarefa = ingerir_sincronizacao_task.delay(
        execucao_id=str(execucao.id),
        force_reimport=force_reimport,
    )
    return {"id_tarefa": str(tarefa.id), "status": "agendada"}


@router.post(
    "/sincronizacoes/reprocessar-arquivo",
    response_model=RespostaAgendamentoEmLote,
    summary="Reprocessar Arquivo Seletivo",
    description=(
        "Dispara reprocessamento seletivo por nome de arquivo CVM. "
        "Aceita arquivos `cad_cia_aberta.csv`, `dfp_cia_aberta_*`, `itr_cia_aberta_*`, "
        "`fre_cia_aberta_*`, `fca_cia_aberta_*`, `ipe_cia_aberta_*`, `vlmo_cia_aberta_*` e `cgvn_cia_aberta_*`. "
        "Use `force_reimport=true` no payload para ignorar o skip por hash repetido."
    ),
    responses=_RESPOSTA_TOKEN_INVALIDO,
    operation_id="reprocessarArquivoAdmin",
)
def reprocessar_arquivo(
    db: DbSession,
    _: Annotated[None, Depends(validar_token_api)],
    payload: Annotated[
        dict[str, str | int | bool | None],
        Body(
            examples=[
                {"arquivo": "dfp_cia_aberta_2025.zip"},
                {"arquivo": "fre_cia_aberta_2025.csv", "ano": 2025},
                {"arquivo": "fca_cia_aberta_2025.zip"},
                {"arquivo": "ipe_cia_aberta_2025.zip"},
                {"arquivo": "vlmo_cia_aberta_2025.zip"},
                {"arquivo": "dfp_cia_aberta_2025.zip", "force_reimport": True},
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
    force_reimport = payload.get("force_reimport", False)
    if not isinstance(force_reimport, bool):
        raise HTTPException(status_code=422, detail="Campo 'force_reimport' deve ser booleano quando informado.")

    tarefa = _agendar_por_arquivo(db, arquivo, ano, force_reimport)
    return RespostaAgendamentoEmLote(status="agendada", tarefas=[tarefa])


@router.get(
    "/fontes",
    response_model=ListaFontesResposta,
    summary="Listar Fontes Registradas",
    description="Retorna catálogo interno de fontes CVM suportadas e planejadas na aplicação.",
    responses=_RESPOSTA_TOKEN_INVALIDO,
    operation_id="listarFontesAdmin",
)
def listar_fontes_admin(
    _: Annotated[None, Depends(validar_token_api)],
) -> ListaFontesResposta:
    return ListaFontesResposta(dados=[_resumo_fonte(item) for item in listar_fontes()])


@router.get(
    "/fontes/{fonte}",
    response_model=FonteDetalheResposta,
    summary="Detalhar Fonte Registrada",
    description="Retorna detalhe dos datasets conhecidos para uma fonte do catálogo interno.",
    responses={**_RESPOSTA_TOKEN_INVALIDO, 404: {"description": "Fonte nao encontrada."}},
    operation_id="detalharFonteAdmin",
)
def detalhar_fonte_admin(
    fonte: Annotated[str, Path(description="Chave canônica da fonte.", examples=["fre"])],
    _: Annotated[None, Depends(validar_token_api)],
) -> FonteDetalheResposta:
    fonte_item = obter_fonte(fonte)
    if fonte_item is None:
        raise HTTPException(status_code=404, detail="Fonte nao encontrada.")
    resumo = _resumo_fonte(fonte_item)
    return FonteDetalheResposta(
        **resumo.model_dump(),
        obrigatorio=fonte_item.obrigatorio,
        dataset_path_template=fonte_item.dataset_path_template,
        arquivo_principal_template=fonte_item.arquivo_principal_template,
        datasets=[_resumo_dataset(dataset) for dataset in fonte_item.datasets],
    )


@router.post(
    "/fontes/auditar",
    response_model=AuditoriaFontesResposta,
    summary="Auditar Fontes Registradas",
    description=(
        "Executa auditoria on-demand das fontes CVM registradas no registry interno. "
        "Retorna cobertura, datasets encontrados e faltantes, sem persistir resultado."
    ),
    responses=_RESPOSTA_TOKEN_INVALIDO,
    operation_id="auditarFontesAdmin",
)
def auditar_fontes_admin(
    _: Annotated[None, Depends(validar_token_api)],
    payload: AuditoriaFontesRequisicao | None = None,
) -> AuditoriaFontesResposta:
    fontes = tuple(payload.fontes) if payload and payload.fontes is not None else None
    ano = payload.ano if payload else None
    auditoria = build_dataset_discovery_audit(year=ano, fontes=fontes)
    return AuditoriaFontesResposta(
        ano=auditoria["ano"],
        fontes=[AuditoriaFonteResposta(**item) for item in auditoria["fontes"]],
        total_fontes=auditoria["total_fontes"],
        total_fontes_acessiveis=auditoria["total_fontes_acessiveis"],
        total_datasets_faltantes=auditoria["total_datasets_faltantes"],
    )


@router.post(
    "/sincronizacoes/cancelar",
    response_model=RespostaCancelamentoSincronizacao,
    summary="Cancelar Sincronizacao em Andamento ou na Fila",
    description=(
        "Interrompe uma sincronização administrativa já disparada. "
        "A operação aceita **um e apenas um** seletor: `id_execucao` ou `id_tarefa`.\n\n"
        "**Quando usar `id_execucao`:**\n"
        "- a execução já aparece em `GET /admin/sincronizacoes`;\n"
        "- você deseja cancelar uma execução identificada no banco, "
        "preservando contadores já consolidados;\n"
        "- a API atualizará o status da execução para `cancelada`, "
        "preencherá `finalizada_em` e registrará mensagem administrativa;\n"
        "- se essa execução antiga não possuir `id_tarefa`, o cancelamento "
        "ainda assim será aceito como baixa administrativa local.\n\n"
        "**Quando usar `id_tarefa`:**\n"
        "- você acabou de receber `id_tarefa` no disparo e a execução ainda "
        "não foi materializada em banco;\n"
        "- você precisa revogar diretamente a task no Celery;\n"
        "- se a task já tiver criado execução com mesmo `id_tarefa`, a API "
        "também marcará essa execução como `cancelada`.\n\n"
        "**Semântica operacional:**\n"
        "- por padrão, `terminar_imediatamente=true`, o que envia "
        "`revoke(..., terminate=True, signal='SIGTERM')` ao Celery;\n"
        "- este modo é recomendado para sincronizações em andamento, pois "
        "tenta parar o worker imediatamente;\n"
        "- tarefas já finalizadas não podem ser canceladas e retornam `409`;\n"
        "- se o seletor apontar apenas para task em fila, a resposta informará "
        "`execucao_encontrada=false`.\n\n"
        "**Observações importantes:**\n"
        "- a revogação é comando assíncrono ao Celery; portanto, em cenários "
        "distribuídos extremos pode haver pequeno atraso entre solicitação e "
        "parada efetiva;\n"
        "- execuções antigas sem `id_tarefa` não podem ser revogadas "
        "remotamente, mas podem ser encerradas administrativamente com status "
        "`cancelada`;\n"
        "- contadores (`total_linhas_lidas`, `total_inseridos`, etc.) "
        "permanecem com último valor persistido no momento do cancelamento;\n"
        "- use `GET /admin/sincronizacoes/{id_execucao}` após cancelamento para auditoria detalhada."
    ),
    responses={
        **_RESPOSTA_TOKEN_INVALIDO,
        404: {
            "description": "Execução ou task não localizada.",
            "content": {"application/json": {"example": {"detail": "Execucao ou task nao encontrada."}}},
        },
        409: {
            "description": "Sincronização já finalizada.",
            "content": {
                "application/json": {"example": {"detail": "Execucao nao esta em andamento e nao pode ser cancelada."}}
            },
        },
        422: {
            "description": "Payload inválido, com seletor ausente ou múltiplo.",
            "content": {
                "application/json": {"example": {"detail": "Informe exatamente um seletor: id_execucao ou id_tarefa."}}
            },
        },
    },
    operation_id="cancelarSincronizacaoAdmin",
)
def cancelar_sincronizacao(
    payload: Annotated[
        SolicitacaoCancelamentoSincronizacao,
        Body(
            description=(
                "Payload de cancelamento. "
                "Envie `id_execucao` **ou** `id_tarefa`. "
                "Se ambos forem enviados, a API rejeita a solicitação com `422`."
            )
        ),
    ],
    db: DbSession,
    _: Annotated[None, Depends(validar_token_api)],
) -> RespostaCancelamentoSincronizacao:
    if bool(payload.id_execucao) == bool(payload.id_tarefa):
        raise HTTPException(status_code=422, detail="Informe exatamente um seletor: id_execucao ou id_tarefa.")

    execucao: ExecucaoSincronizacao | None
    if payload.id_execucao is not None:
        execucao = db.get(ExecucaoSincronizacao, payload.id_execucao)
        if execucao is None:
            raise HTTPException(status_code=404, detail="Execucao ou task nao encontrada.")
        id_tarefa = execucao.id_tarefa
    else:
        id_tarefa = payload.id_tarefa
        execucao = db.scalar(select(ExecucaoSincronizacao).where(ExecucaoSincronizacao.id_tarefa == id_tarefa))

    if execucao is not None and execucao.status in _STATUS_FINAL_EXECUCAO:
        raise HTTPException(status_code=409, detail="Execucao nao esta em andamento e nao pode ser cancelada.")

    revogacao_solicitada = False
    if id_tarefa is not None:
        celery_app.control.revoke(id_tarefa, terminate=payload.terminar_imediatamente, signal="SIGTERM")
        revogacao_solicitada = True

    if execucao is not None:
        mensagem = "Execucao cancelada via endpoint administrativo."
        if payload.motivo:
            mensagem = f"{mensagem} Motivo: {payload.motivo}"
        if id_tarefa is None:
            mensagem = (
                f"{mensagem} Execucao encerrada apenas no banco, sem revogacao remota, "
                "pois o registro nao possui id_tarefa associado."
            )
        execucao.status = "cancelada"
        execucao.finalizada_em = _agora()
        execucao.mensagem_erro = mensagem
        db.commit()
        return RespostaCancelamentoSincronizacao(
            id_execucao=str(execucao.id),
            id_tarefa=id_tarefa,
            execucao_encontrada=True,
            status_execucao=execucao.status,
            revogacao_solicitada=revogacao_solicitada,
            terminar_imediatamente=payload.terminar_imediatamente,
            mensagem=(
                "Sincronizacao cancelada com sucesso."
                if revogacao_solicitada
                else "Execucao marcada como cancelada no banco sem revogacao remota."
            ),
        )

    return RespostaCancelamentoSincronizacao(
        id_execucao=None,
        id_tarefa=id_tarefa,
        execucao_encontrada=False,
        status_execucao=None,
        revogacao_solicitada=revogacao_solicitada,
        terminar_imediatamente=payload.terminar_imediatamente,
        mensagem="Revogacao enviada para task sem execucao materializada no banco.",
    )


@router.get(
    "/sincronizacoes",
    response_model=ListaExecucoesSincronizacao,
    summary="Listar Execucoes de Sincronizacao",
    description=(
        "Lista paginada das execucoes registradas no sistema de sincronizacao. "
        "Suporta filtragem por tipo de execucao (arquivo_zip, arquivo_membro, arquivo_simples), "
        "id da execucao pai, somente filhos, ou somente pais. "
        "Para execucoes do tipo arquivo_zip, retorna contadores de progresso dos membros filhos."
    ),
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
    tipo_execucao: Annotated[str | None, Query(description="Filtrar por tipo de execucao.")] = None,
    id_execucao_pai: Annotated[UUID | None, Query(description="Filtrar pelo ID da execucao pai.")] = None,
    somente_filhos: Annotated[
        bool, Query(description="Se True, retorna apenas execucoes filhas (membros).")
    ] = False,
    somente_pais: Annotated[
        bool, Query(description="Se True, retorna apenas execucoes pais (ZIP ou simples).")
    ] = False,
) -> ListaExecucoesSincronizacao:
    offset = (pagina - 1) * tamanho_pagina
    stmt = select(ExecucaoSincronizacao)
    stmt_count = select(func.count(ExecucaoSincronizacao.id))
    
    if tipo_execucao:
        stmt = stmt.where(ExecucaoSincronizacao.tipo_execucao == tipo_execucao)
        stmt_count = stmt_count.where(ExecucaoSincronizacao.tipo_execucao == tipo_execucao)
    if id_execucao_pai:
        stmt = stmt.where(ExecucaoSincronizacao.parent_execucao_id == id_execucao_pai)
        stmt_count = stmt_count.where(ExecucaoSincronizacao.parent_execucao_id == id_execucao_pai)
    if somente_filhos:
        stmt = stmt.where(ExecucaoSincronizacao.parent_execucao_id.isnot(None))
        stmt_count = stmt_count.where(ExecucaoSincronizacao.parent_execucao_id.isnot(None))
    if somente_pais:
        stmt = stmt.where(ExecucaoSincronizacao.parent_execucao_id.is_(None))
        stmt_count = stmt_count.where(ExecucaoSincronizacao.parent_execucao_id.is_(None))
        
    execucoes = (
        db.execute(
            stmt.order_by(ExecucaoSincronizacao.iniciada_em.desc())
            .offset(offset)
            .limit(tamanho_pagina)
        )
        .scalars()
        .all()
    )
    total = db.scalar(stmt_count) or 0

    # Bulk-fetch child stats for parent executions to avoid N+1
    parent_ids_in_list = [item.id for item in execucoes if item.tipo_execucao == "arquivo_zip"]
    child_stats = {}
    if parent_ids_in_list:
        stats_rows = db.execute(
            select(
                ExecucaoSincronizacao.parent_execucao_id,
                ExecucaoSincronizacao.status,
                func.count(ExecucaoSincronizacao.id)
            )
            .where(ExecucaoSincronizacao.parent_execucao_id.in_(parent_ids_in_list))
            .group_by(ExecucaoSincronizacao.parent_execucao_id, ExecucaoSincronizacao.status)
        ).all()
        
        for pid, status_val, count_val in stats_rows:
            if pid not in child_stats:
                child_stats[pid] = {"total": 0, "concluidos": 0, "falha": 0, "em_andamento": 0}
            child_stats[pid]["total"] += count_val
            if status_val in ("sucesso", "sem_alteracao", "skipped"):
                child_stats[pid]["concluidos"] += count_val
            elif status_val in ("falha", "cancelada", "quality_fail"):
                child_stats[pid]["falha"] += count_val
            else:
                child_stats[pid]["em_andamento"] += count_val

    # Bulk-fetch parents for child executions to get file name (arquivo_principal)
    parent_ids_to_fetch = {item.parent_execucao_id for item in execucoes if item.parent_execucao_id}
    parents_by_id = {}
    if parent_ids_to_fetch:
        parents = db.scalars(
            select(ExecucaoSincronizacao).where(ExecucaoSincronizacao.id.in_(list(parent_ids_to_fetch)))
        ).all()
        parents_by_id = {p.id: p for p in parents}

    # Bulk-fetch members for all execucoes to avoid N+1.
    # Group by parent ID. For parent/simple execution, key is item.id.
    # For child execution, key is item.parent_execucao_id.
    all_parent_ids = {item.parent_execucao_id or item.id for item in execucoes}
    members_by_parent: dict[Any, dict[str, IngestionFileMember]] = {}
    if all_parent_ids:
        rows = db.execute(
            select(IngestionRun.execucao_sincronizacao_id, IngestionFileMember)
            .join(IngestionFile, IngestionFile.ingestion_run_id == IngestionRun.id)
            .join(IngestionFileMember, IngestionFileMember.ingestion_file_id == IngestionFile.id)
            .where(IngestionRun.execucao_sincronizacao_id.in_(list(all_parent_ids)))
        ).all()
        for parent_id, member in rows:
            members_by_parent.setdefault(parent_id, {})[member.member_name] = member

    dados = []
    for item in execucoes:
        # Resolve associated members for analysis
        if item.tipo_execucao == "arquivo_membro":
            m = members_by_parent.get(item.parent_execucao_id, {}).get(item.arquivo)
            members_for_item = [m] if m else []
        else:
            members_for_item = list(members_by_parent.get(item.id, {}).values())

        dados.append(
            ExecucaoSincronizacaoResumo(
                id=str(item.id),
                id_tarefa=item.id_tarefa,
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
                id_execucao_pai=str(item.parent_execucao_id) if item.parent_execucao_id else None,
                tipo_execucao=item.tipo_execucao,
                arquivo_principal=(
                    parents_by_id[item.parent_execucao_id].arquivo
                    if (item.parent_execucao_id and item.parent_execucao_id in parents_by_id)
                    else None
                ),
                filhos_total=(
                    child_stats[item.id]["total"]
                    if (item.tipo_execucao == "arquivo_zip" and item.id in child_stats)
                    else None
                ),
                filhos_concluidos=(
                    child_stats[item.id]["concluidos"]
                    if (item.tipo_execucao == "arquivo_zip" and item.id in child_stats)
                    else None
                ),
                filhos_falha=(
                    child_stats[item.id]["falha"]
                    if (item.tipo_execucao == "arquivo_zip" and item.id in child_stats)
                    else None
                ),
                filhos_em_andamento=(
                    child_stats[item.id]["em_andamento"]
                    if (item.tipo_execucao == "arquivo_zip" and item.id in child_stats)
                    else None
                ),
                analise_arquivos=[
                    AnaliseArquivo(
                        file_name=m.member_name,
                        file_size=formatar_tamanho(m.member_size_bytes),
                        rows_count=m.row_count,
                        columns_count=len(m.header) if m.header else 0,
                        header_columns=m.header or [],
                        encoding=m.encoding,
                        delimiter=m.delimiter,
                    )
                    for m in members_for_item
                ] or None,
            )
        )

    return ListaExecucoesSincronizacao(
        dados=dados,
        paginacao=Paginacao(pagina=pagina, tamanho_pagina=tamanho_pagina, total=total),
    )


@router.get(
    "/sincronizacoes/{id_execucao}",
    response_model=ExecucaoSincronizacaoDetalhe,
    summary="Detalhar Execucao de Sincronizacao",
    description=(
        "Retorna o detalhamento completo de uma execucao pelo identificador. "
        "Se a execucao for um arquivo membro (filho), inclui o nome do arquivo "
        "principal ZIP (arquivo_principal). Se for uma execucao pai (arquivo_zip), "
        "retorna o progresso agregado e a lista detalhada de execucoes filhas "
        "(execucoes_filhas)."
    ),
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
    id_execucao: Annotated[UUID, Path(description="ID da execucao de sincronizacao.", examples=["uuid"])],
    db: DbSession,
    _: Annotated[None, Depends(validar_token_api)],
) -> ExecucaoSincronizacaoDetalhe:
    execucao = db.get(ExecucaoSincronizacao, id_execucao)
    if execucao is None:
        raise HTTPException(status_code=404, detail="Execucao nao encontrada.")

    # Fetch parent's ZIP file name as arquivo_principal for child executions
    arquivo_principal = None
    if execucao.parent_execucao_id:
        parent = db.get(ExecucaoSincronizacao, execucao.parent_execucao_id)
        if parent:
            arquivo_principal = parent.arquivo

    # List child summaries in execucoes_filhas for parent executions
    execucoes_filhas = None
    filhos_total = None
    filhos_concluidos = None
    filhos_falha = None
    filhos_em_andamento = None

    if execucao.tipo_execucao == "arquivo_zip":
        children = db.scalars(
            select(ExecucaoSincronizacao)
            .where(ExecucaoSincronizacao.parent_execucao_id == execucao.id)
            .order_by(ExecucaoSincronizacao.arquivo.asc())
        ).all()
        
        filhos_total = len(children)
        filhos_concluidos = 0
        filhos_falha = 0
        filhos_em_andamento = 0
        
        # We need the parent's IngestionFile to associate child files with AnaliseArquivo
        parent_run = db.scalar(
            select(IngestionRun).where(IngestionRun.execucao_sincronizacao_id == execucao.id)
        )
        child_members = {}
        if parent_run:
            parent_file = db.scalar(
                select(IngestionFile).where(IngestionFile.ingestion_run_id == parent_run.id)
            )
            if parent_file:
                members_list = db.scalars(
                    select(IngestionFileMember).where(IngestionFileMember.ingestion_file_id == parent_file.id)
                ).all()
                child_members = {m.member_name: m for m in members_list}
        
        execucoes_filhas = []
        for c in children:
            if c.status in ("sucesso", "sem_alteracao", "skipped"):
                filhos_concluidos += 1
            elif c.status in ("falha", "cancelada", "quality_fail"):
                filhos_falha += 1
            else:
                filhos_em_andamento += 1
                
            m = child_members.get(c.arquivo)
            analise_c = None
            if m:
                analise_c = [
                    AnaliseArquivo(
                        file_name=m.member_name,
                        file_size=formatar_tamanho(m.member_size_bytes),
                        rows_count=m.row_count,
                        columns_count=len(m.header) if m.header else 0,
                        header_columns=m.header or [],
                        encoding=m.encoding,
                        delimiter=m.delimiter,
                    )
                ]
                
            execucoes_filhas.append(
                ExecucaoSincronizacaoResumo(
                    id=str(c.id),
                    id_tarefa=c.id_tarefa,
                    tipo_fonte=c.tipo_fonte,
                    arquivo=c.arquivo,
                    status=c.status,
                    iniciada_em=c.iniciada_em,
                    finalizada_em=c.finalizada_em,
                    total_linhas_lidas=c.total_linhas_lidas,
                    total_inseridos=c.total_inseridos,
                    total_atualizados=c.total_atualizados,
                    total_inalterados=c.total_inalterados,
                    total_rejeitados=c.total_rejeitados,
                    id_execucao_pai=str(c.parent_execucao_id) if c.parent_execucao_id else None,
                    tipo_execucao=c.tipo_execucao,
                    arquivo_principal=execucao.arquivo,
                    analise_arquivos=analise_c,
                )
            )
            
    # Populate analise_arquivos for the current execution itself
    analise_arquivos = None
    if execucao.tipo_execucao == "arquivo_membro":
        if execucao.parent_execucao_id:
            run = db.scalar(
                select(IngestionRun).where(IngestionRun.execucao_sincronizacao_id == execucao.parent_execucao_id)
            )
            if run:
                file = db.scalar(
                    select(IngestionFile).where(IngestionFile.ingestion_run_id == run.id)
                )
                if file:
                    m = db.scalar(
                        select(IngestionFileMember)
                        .where(IngestionFileMember.ingestion_file_id == file.id)
                        .where(IngestionFileMember.member_name == execucao.arquivo)
                    )
                    if m:
                        analise_arquivos = [
                            AnaliseArquivo(
                                file_name=m.member_name,
                                file_size=formatar_tamanho(m.member_size_bytes),
                                rows_count=m.row_count,
                                columns_count=len(m.header) if m.header else 0,
                                header_columns=m.header or [],
                                encoding=m.encoding,
                                delimiter=m.delimiter,
                            )
                        ]
    else:
        # parent or simple execution
        run = db.scalar(
            select(IngestionRun).where(IngestionRun.execucao_sincronizacao_id == execucao.id)
        )
        if run:
            files = db.scalars(
                select(IngestionFile).where(IngestionFile.ingestion_run_id == run.id)
            ).all()
            if files:
                analise_arquivos = []
                for f in files:
                    members = db.scalars(
                        select(IngestionFileMember).where(IngestionFileMember.ingestion_file_id == f.id)
                    ).all()
                    for m in members:
                        analise_arquivos.append(
                            AnaliseArquivo(
                                file_name=m.member_name,
                                file_size=formatar_tamanho(m.member_size_bytes),
                                rows_count=m.row_count,
                                columns_count=len(m.header) if m.header else 0,
                                header_columns=m.header or [],
                                encoding=m.encoding,
                                delimiter=m.delimiter,
                            )
                        )

    return ExecucaoSincronizacaoDetalhe(
        id=str(execucao.id),
        id_tarefa=execucao.id_tarefa,
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
        analise_arquivos=analise_arquivos,
        id_execucao_pai=str(execucao.parent_execucao_id) if execucao.parent_execucao_id else None,
        tipo_execucao=execucao.tipo_execucao,
        arquivo_principal=arquivo_principal,
        filhos_total=filhos_total,
        filhos_concluidos=filhos_concluidos,
        filhos_falha=filhos_falha,
        filhos_em_andamento=filhos_em_andamento,
        execucoes_filhas=execucoes_filhas,
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
    total_sucesso = (
        db.scalar(
            select(func.count()).select_from(ExecucaoSincronizacao).where(ExecucaoSincronizacao.status == "sucesso")
        )
        or 0
    )
    total_sem_alteracao = (
        db.scalar(
            select(func.count())
            .select_from(ExecucaoSincronizacao)
            .where(ExecucaoSincronizacao.status == "sem_alteracao")
        )
        or 0
    )
    total_falha = (
        db.scalar(
            select(func.count()).select_from(ExecucaoSincronizacao).where(ExecucaoSincronizacao.status == "falha")
        )
        or 0
    )
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


@router.get(
    "/ingestion/runs",
    response_model=ListaIngestionRuns,
    summary="Listar Runs de Ingestion",
    description=(
        "Lista paginada das runs do pipeline de ingestao. "
        "O frontend pode usar este endpoint como visao principal de monitoramento, "
        "consumindo `status`, `phase` e `quality_summary` para cards, grids e alertas."
    ),
    responses=_RESPOSTA_TOKEN_INVALIDO,
    operation_id="listarIngestionRunsAdmin",
)
def listar_ingestion_runs(
    db: DbSession,
    _: Annotated[None, Depends(validar_token_api)],
    pagina: Annotated[int, Query(ge=1)] = 1,
    tamanho_pagina: Annotated[int, Query(ge=1, le=500)] = 100,
) -> ListaIngestionRuns:
    offset = (pagina - 1) * tamanho_pagina
    runs = (
        db.execute(select(IngestionRun).order_by(IngestionRun.started_at.desc()).offset(offset).limit(tamanho_pagina))
        .scalars()
        .all()
    )
    total = db.query(IngestionRun).count()
    return ListaIngestionRuns(
        dados=[
            IngestionRunResumo(
                id=str(run.id),
                execucao_sincronizacao_id=None
                if run.execucao_sincronizacao_id is None
                else str(run.execucao_sincronizacao_id),
                tipo_fonte=run.tipo_fonte,
                ano=run.ano,
                status=run.status,
                phase=run.phase,
                quality_summary=run.quality_summary,
            )
            for run in runs
        ],
        paginacao=Paginacao(pagina=pagina, tamanho_pagina=tamanho_pagina, total=total),
    )


@router.get(
    "/ingestion/runs/{run_id}",
    response_model=IngestionRunResumo,
    summary="Detalhar Run de Ingestion",
    description=(
        "Retorna uma run especifica do pipeline. "
        "Use este endpoint para telas de detalhe e drill-down operacional, "
        "especialmente quando o frontend precisar ler "
        "`quality_summary` consolidado antes de buscar quarentena ou acionar replay."
    ),
    responses={**_RESPOSTA_TOKEN_INVALIDO, 404: {"description": "Run nao encontrado."}},
    operation_id="detalharIngestionRunAdmin",
)
def detalhar_ingestion_run(
    run_id: Annotated[UUID, Path()],
    db: DbSession,
    _: Annotated[None, Depends(validar_token_api)],
) -> IngestionRunResumo:
    run = db.get(IngestionRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run nao encontrado.")
    return IngestionRunResumo(
        id=str(run.id),
        execucao_sincronizacao_id=None if run.execucao_sincronizacao_id is None else str(run.execucao_sincronizacao_id),
        tipo_fonte=run.tipo_fonte,
        ano=run.ano,
        status=run.status,
        phase=run.phase,
        quality_summary=run.quality_summary,
    )


@router.get(
    "/ingestion/quarantine",
    response_model=ListaQuarantineItems,
    summary="Listar Quarentena de Ingestion",
    description=(
        "Lista paginada da fila de reparo. "
        "Os filtros atuais suportam `motivo_codigo`; o frontend deve tratar `motivo_codigo`, `status`, "
        "`reparavel` e `tentativas_reprocessamento` como colunas de primeira classe."
    ),
    responses=_RESPOSTA_TOKEN_INVALIDO,
    operation_id="listarIngestionQuarantineAdmin",
)
def listar_ingestion_quarantine(
    db: DbSession,
    _: Annotated[None, Depends(validar_token_api)],
    pagina: Annotated[int, Query(ge=1)] = 1,
    tamanho_pagina: Annotated[int, Query(ge=1, le=500)] = 100,
    motivo_codigo: Annotated[str | None, Query()] = None,
) -> ListaQuarantineItems:
    offset = (pagina - 1) * tamanho_pagina
    query = select(QuarantineItem)
    query_total = select(func.count()).select_from(QuarantineItem)
    if motivo_codigo:
        query = query.where(QuarantineItem.motivo_codigo == motivo_codigo)
        query_total = query_total.where(QuarantineItem.motivo_codigo == motivo_codigo)
    itens = (
        db.execute(query.order_by(QuarantineItem.created_at.desc()).offset(offset).limit(tamanho_pagina))
        .scalars()
        .all()
    )
    total = db.scalar(query_total) or 0
    return ListaQuarantineItems(
        dados=[
            QuarantineItemResposta(
                id=str(item.id),
                ingestion_run_id=None if item.ingestion_run_id is None else str(item.ingestion_run_id),
                ingestion_row_id=str(item.ingestion_row_id),
                arquivo_origem=item.arquivo_origem,
                ano_origem=item.ano_origem,
                linha_origem=item.linha_origem,
                row_kind=item.row_kind,
                status=item.status,
                motivo_codigo=item.motivo_codigo,
                severidade=item.severidade,
                reparavel=item.reparavel,
                tentativas_reprocessamento=item.tentativas_reprocessamento,
                diagnostico=item.diagnostico,
            )
            for item in itens
        ],
        paginacao=Paginacao(pagina=pagina, tamanho_pagina=tamanho_pagina, total=total),
    )


@router.post(
    "/ingestion/replay/quarantine",
    response_model=ReplayResposta,
    summary="Reprocessar Quarentena de Ingestion",
    description=(
        "Executa replay sobre itens pendentes da quarentena. "
        "A requisicao aceita filtros opcionais por `reason_code`, `arquivo_origem` e `ano`. "
        "Quando nenhum filtro e enviado, todos os itens `pendente` sao considerados."
    ),
    responses=_RESPOSTA_TOKEN_INVALIDO,
    operation_id="replayIngestionQuarantineAdmin",
)
def replay_ingestion_quarantine(
    db: DbSession,
    _: Annotated[None, Depends(validar_token_api)],
    payload: Annotated[
        ReplayQuarantineRequisicao | None,
        Body(
            examples=[
                {"reason_code": "companhia_nao_encontrada"},
                {"arquivo_origem": "itr_cia_aberta_2021.csv", "ano": 2021},
            ]
        ),
    ] = None,
) -> ReplayResposta:
    payload = payload or ReplayQuarantineRequisicao()
    resultado = replay_quarantine(
        db,
        reason_code=payload.reason_code,
        arquivo_origem=payload.arquivo_origem,
        ano=payload.ano,
    )
    return ReplayResposta(status="sucesso", detalhe=resultado)


@router.post(
    "/ingestion/runs/{run_id}/replay",
    response_model=ReplayResposta,
    summary="Reprocessar Run de Ingestion",
    description=(
        "Executa replay de todas as linhas staged pertencentes a uma run. "
        "A operacao e util quando uma correcao de identidade, parser ou regra de reparo precisa ser aplicada em lote "
        "sem redownload do arquivo original."
    ),
    responses={**_RESPOSTA_TOKEN_INVALIDO, 404: {"description": "Run nao encontrado."}},
    operation_id="replayIngestionRunAdmin",
)
def replay_ingestion_run(
    run_id: Annotated[UUID, Path()],
    db: DbSession,
    _: Annotated[None, Depends(validar_token_api)],
) -> ReplayResposta:
    if db.get(IngestionRun, run_id) is None:
        raise HTTPException(status_code=404, detail="Run nao encontrado.")
    resultado = replay_ingestion_run_service(db, run_id=run_id)
    return ReplayResposta(status="sucesso", detalhe=resultado)


@router.post(
    "/ingestion/identity/rebuild",
    response_model=ReplayResposta,
    summary="Reconstruir Identidade de Ingestion",
    description=(
        "Reprocessa o cadastro para reconstruir a malha de identidade usada por DFP, ITR e FRE. "
        "O frontend deve expor esta acao como operacao administrativa forte, "
        "normalmente seguida de replay da quarentena "
        "por `companhia_nao_encontrada`."
    ),
    responses=_RESPOSTA_TOKEN_INVALIDO,
    operation_id="rebuildIngestionIdentityAdmin",
)
def rebuild_ingestion_identity(
    db: DbSession,
    _: Annotated[None, Depends(validar_token_api)],
) -> ReplayResposta:
    resultado = sincronizar_cadastro_companhias(db)
    return ReplayResposta(status="sucesso", detalhe=resultado)
