from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.sincronizacao import ExecucaoSincronizacao, TipoExecucao
from app.services.ingestion.source_registry import obter_fonte

_ANNUAL_SOURCES = {"dfp", "itr", "fre", "fca", "ipe", "vlmo", "cgvn"}


def sync_execution_metadata(*, tipo_fonte: str, ano: int | None) -> tuple[str, str, str]:
    settings = get_settings()
    fonte = tipo_fonte.lower().strip()

    if fonte == "cadastro":
        arquivo = "cad_cia_aberta.csv+cad_cia_estrang.csv"
        url = (
            f"{settings.cvm_base_url}/CIA_ABERTA/CAD/DADOS/cad_cia_aberta.csv"
            f"|{settings.cvm_base_url}/CIA_ESTRANG/CAD/DADOS/cad_cia_estrang.csv"
        )
        return arquivo, url, TipoExecucao.arquivo_simples.value

    fonte_item = obter_fonte(fonte)
    if fonte_item is None or fonte not in _ANNUAL_SOURCES:
        raise ValueError(f"fonte_nao_suportada_para_agendamento:{tipo_fonte}")
    if ano is None:
        raise ValueError(f"ano_obrigatorio_para_agendamento:{tipo_fonte}")

    arquivo = fonte_item.render_arquivo_principal(ano=ano)
    dataset_path = fonte_item.dataset_path_template.format(ano=ano)
    return arquivo, f"{settings.cvm_base_url}/{dataset_path}", TipoExecucao.arquivo_zip.value


def criar_execucao_sincronizacao_agendada(
    db: Session,
    *,
    tipo_fonte: str,
    ano: int | None,
    task_id: str,
) -> ExecucaoSincronizacao:
    arquivo, url, tipo_execucao = sync_execution_metadata(tipo_fonte=tipo_fonte, ano=ano)
    execucao = ExecucaoSincronizacao(
        tipo_execucao=tipo_execucao,
        tipo_fonte=tipo_fonte.lower().strip(),
        ano=ano,
        id_tarefa=task_id,
        arquivo=arquivo,
        url=url,
        status="agendada",
    )
    db.add(execucao)
    return execucao


def marcar_agendamento_com_falha(
    db: Session,
    *,
    task_ids: list[str],
    erro: str,
) -> None:
    if not task_ids:
        return
    agora = datetime.now(UTC)
    execucoes = db.scalars(
        select(ExecucaoSincronizacao).where(
            ExecucaoSincronizacao.id_tarefa.in_(task_ids),
            ExecucaoSincronizacao.status == "agendada",
        )
    ).all()
    for execucao in execucoes:
        execucao.status = "falha"
        execucao.finalizada_em = agora
        execucao.mensagem_erro = erro


def adotar_ou_criar_execucao_sincronizacao(
    db: Session,
    *,
    tipo_fonte: str,
    ano: int | None,
    task_id: str | None,
    arquivo: str | None = None,
    url: str | None = None,
    tipo_execucao: str | None = None,
) -> ExecucaoSincronizacao:
    execucao: ExecucaoSincronizacao | None = None
    if task_id is not None:
        execucao = db.scalar(
            select(ExecucaoSincronizacao)
            .where(
                ExecucaoSincronizacao.id_tarefa == task_id,
                ExecucaoSincronizacao.tipo_fonte == tipo_fonte.lower().strip(),
                ExecucaoSincronizacao.status == "agendada",
            )
            .order_by(ExecucaoSincronizacao.iniciada_em.desc())
            .limit(1)
        )

    if execucao is None:
        arquivo_padrao, url_padrao, tipo_padrao = sync_execution_metadata(tipo_fonte=tipo_fonte, ano=ano)
        execucao = ExecucaoSincronizacao(
            tipo_execucao=tipo_execucao or tipo_padrao,
            tipo_fonte=tipo_fonte.lower().strip(),
            ano=ano,
            id_tarefa=task_id,
            arquivo=arquivo or arquivo_padrao,
            url=url or url_padrao,
            status="em_execucao",
        )
        db.add(execucao)
    else:
        execucao.status = "em_execucao"
        execucao.finalizada_em = None
        if arquivo is not None:
            execucao.arquivo = arquivo
        if url is not None:
            execucao.url = url
        if tipo_execucao is not None:
            execucao.tipo_execucao = tipo_execucao

    return execucao


def novo_task_id() -> str:
    return str(uuid.uuid4())
