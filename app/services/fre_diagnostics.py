from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.fre import (
    FreAcaoEntregue,
    FreAdministradorDeclaracaoGenero,
    FreAdministradorDeclaracaoRaca,
    FreAdministradorMembroConselhoFiscal,
    FreAdministradorPcd,
    FreAuditor,
    FreCapitalSocial,
    FreCapitalSocialAumento,
    FreCapitalSocialAumentoClasseAcao,
    FreCapitalSocialClasseAcao,
    FreCapitalSocialDesdobramento,
    FreCapitalSocialDesdobramentoClasseAcao,
    FreCapitalSocialReducao,
    FreCapitalSocialReducaoClasseAcao,
    FreCapitalSocialTituloConversivel,
    FreDireitoAcao,
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
    FreMembroComite,
    FreMercadoEstrangeiro,
    FreOutroValorMobiliario,
    FreParticipacaoSociedade,
    FrePlanoRecompra,
    FrePlanoRecompraClasseAcao,
    FrePosicaoAcionaria,
    FrePosicaoAcionariaClasseAcao,
    FreRelacaoFamiliar,
    FreRelacaoSubordinacao,
    FreRemuneracaoAcao,
    FreRemuneracaoMaximaMinimaMedia,
    FreRemuneracaoTotalOrgao,
    FreRemuneracaoVariavel,
    FreResponsavel,
    FreTitularValorMobiliario,
    FreTituloExterior,
    FreTransacaoParteRelacionada,
    FreValorMobiliarioTesourariaMovimentacao,
    FreValorMobiliarioTesourariaUltimoExercicio,
    FreVolumeValorMobiliario,
)
from app.models.ingestion import (
    IngestionFile,
    IngestionFileMember,
    IngestionRun,
    SourceArtifactSnapshot,
    SourceMemberSnapshot,
)
from app.models.sincronizacao import ExecucaoSincronizacao
from app.schemas.fre import (
    FreDatasetDiagnosticoCodigo,
    FreDatasetDisponibilidadeItem,
    FreDatasetDisponibilidadeResumo,
    ListaFreDatasetsDisponibilidadeResposta,
)
from app.services.ingestion.source_registry import DatasetFonte, listar_datasets

FRE_DATASET_ENDPOINTS: dict[str, str] = {
    "documentos": "/fre/documentos",
    "auditores": "/fre/auditores",
    "capital_social": "/fre/capital-social",
    "posicao_acionaria": "/fre/posicao-acionaria",
    "remuneracao_total_orgao": "/fre/remuneracao/total-por-orgao",
    "empregado_posicao_genero": "/fre/empregados/posicao-genero",
    "participacao_sociedade": "/fre/participacoes-sociedades",
    "relacao_familiar": "/fre/relacoes-familiares",
    "responsavel": "/fre/responsaveis",
    "capital_social_classe_acao": "/fre/capital-social-classes-acoes",
    "capital_social_titulo_conversivel": "/fre/capital-social-titulos-conversiveis",
    "distribuicao_capital": "/fre/distribuicao-capital",
    "distribuicao_capital_classe_acao": "/fre/distribuicao-capital-classes-acoes",
    "posicao_acionaria_classe_acao": "/fre/posicoes-acionarias-classes-acoes",
    "remuneracao_maxima_minima_media": "/fre/remuneracoes-maximas-minimas-medias",
    "remuneracao_variavel": "/fre/remuneracoes-variaveis",
    "remuneracao_acao": "/fre/remuneracoes-acoes",
    "acao_entregue": "/fre/acoes-entregues",
    "volume_valor_mobiliario": "/fre/volume-valor-mobiliario",
    "outro_valor_mobiliario": "/fre/outro-valor-mobiliario",
    "titular_valor_mobiliario": "/fre/titular-valor-mobiliario",
    "mercado_estrangeiro": "/fre/mercado-estrangeiro",
    "titulo_exterior": "/fre/titulo-exterior",
    "plano_recompra": "/fre/plano-recompra",
    "plano_recompra_classe_acao": "/fre/plano-recompra-classes-acoes",
    "valor_mobiliario_tesouraria_movimentacao": "/fre/valor-mobiliario-tesouraria-movimentacao",
    "valor_mobiliario_tesouraria_ultimo_exercicio": "/fre/valor-mobiliario-tesouraria-ultimo-exercicio",
    "administrador_declaracao_genero": "/fre/administradores/declaracao-genero",
    "administrador_declaracao_raca": "/fre/administradores/declaracao-raca",
    "administrador_pcd": "/fre/administradores/pcd",
    "empregado_posicao_declaracao_raca": "/fre/empregados/posicao-declaracao-raca",
    "empregado_posicao_faixa_etaria": "/fre/empregados/posicao-faixa-etaria",
    "empregado_posicao_local": "/fre/empregados/posicao-local",
    "empregado_pcd": "/fre/empregados/pcd",
    "empregado_local_declaracao_genero": "/fre/empregados/local-declaracao-genero",
    "empregado_local_declaracao_raca": "/fre/empregados/local-declaracao-raca",
    "empregado_local_faixa_etaria": "/fre/empregados/local-faixa-etaria",
}

_FRE_DATASET_MODELS: dict[str, type[Any]] = {
    "documentos": FreDocumento,
    "auditores": FreAuditor,
    "capital_social": FreCapitalSocial,
    "posicao_acionaria": FrePosicaoAcionaria,
    "remuneracao_total_orgao": FreRemuneracaoTotalOrgao,
    "empregado_posicao_genero": FreEmpregadoPosicaoGenero,
    "participacao_sociedade": FreParticipacaoSociedade,
    "responsavel": FreResponsavel,
    "capital_social_classe_acao": FreCapitalSocialClasseAcao,
    "capital_social_titulo_conversivel": FreCapitalSocialTituloConversivel,
    "distribuicao_capital": FreDistribuicaoCapital,
    "distribuicao_capital_classe_acao": FreDistribuicaoCapitalClasseAcao,
    "posicao_acionaria_classe_acao": FrePosicaoAcionariaClasseAcao,
    "remuneracao_maxima_minima_media": FreRemuneracaoMaximaMinimaMedia,
    "remuneracao_variavel": FreRemuneracaoVariavel,
    "remuneracao_acao": FreRemuneracaoAcao,
    "acao_entregue": FreAcaoEntregue,
    "administrador_membro_conselho_fiscal": FreAdministradorMembroConselhoFiscal,
    "membro_comite": FreMembroComite,
    "relacao_familiar": FreRelacaoFamiliar,
    "relacao_subordinacao": FreRelacaoSubordinacao,
    "transacao_parte_relacionada": FreTransacaoParteRelacionada,
    "capital_social_aumento": FreCapitalSocialAumento,
    "capital_social_aumento_classe_acao": FreCapitalSocialAumentoClasseAcao,
    "capital_social_desdobramento": FreCapitalSocialDesdobramento,
    "capital_social_desdobramento_classe_acao": FreCapitalSocialDesdobramentoClasseAcao,
    "capital_social_reducao": FreCapitalSocialReducao,
    "capital_social_reducao_classe_acao": FreCapitalSocialReducaoClasseAcao,
    "direito_acao": FreDireitoAcao,
    "volume_valor_mobiliario": FreVolumeValorMobiliario,
    "outro_valor_mobiliario": FreOutroValorMobiliario,
    "titular_valor_mobiliario": FreTitularValorMobiliario,
    "mercado_estrangeiro": FreMercadoEstrangeiro,
    "titulo_exterior": FreTituloExterior,
    "plano_recompra": FrePlanoRecompra,
    "plano_recompra_classe_acao": FrePlanoRecompraClasseAcao,
    "valor_mobiliario_tesouraria_movimentacao": FreValorMobiliarioTesourariaMovimentacao,
    "valor_mobiliario_tesouraria_ultimo_exercicio": FreValorMobiliarioTesourariaUltimoExercicio,
    "administrador_declaracao_genero": FreAdministradorDeclaracaoGenero,
    "administrador_declaracao_raca": FreAdministradorDeclaracaoRaca,
    "administrador_pcd": FreAdministradorPcd,
    "empregado_posicao_declaracao_raca": FreEmpregadoPosicaoDeclaracaoRaca,
    "empregado_posicao_faixa_etaria": FreEmpregadoPosicaoFaixaEtaria,
    "empregado_posicao_local": FreEmpregadoPosicaoLocal,
    "empregado_pcd": FreEmpregadoPcd,
    "empregado_local_declaracao_genero": FreEmpregadoLocalDeclaracaoGenero,
    "empregado_local_declaracao_raca": FreEmpregadoLocalDeclaracaoRaca,
    "empregado_local_faixa_etaria": FreEmpregadoLocalFaixaEtaria,
}


class FreDisponibilidadeValidationError(ValueError):
    pass


def _col(modelo: type[Any], campo: str) -> Any:
    return getattr(modelo, campo)


def _ano_disponibilidade_padrao(db: Session) -> int:
    ano_documento = db.scalar(select(func.max(FreDocumento.ano_origem)))
    ano_snapshot = db.scalar(
        select(func.max(SourceArtifactSnapshot.ano)).where(SourceArtifactSnapshot.tipo_fonte == "fre")
    )
    anos = [ano for ano in (ano_documento, ano_snapshot) if ano is not None]
    return max(anos) if anos else datetime.now(UTC).year


def anos_para_disponibilidade(
    db: Session,
    *,
    ano: int | None,
    ano_inicio: int | None,
    ano_fim: int | None,
) -> list[int]:
    if ano is not None and (ano_inicio is not None or ano_fim is not None):
        raise FreDisponibilidadeValidationError("Use ano ou ano_inicio/ano_fim, nao ambos.")
    if ano is not None:
        return [ano]
    if ano_inicio is None and ano_fim is None:
        return [_ano_disponibilidade_padrao(db)]
    inicio = ano_inicio if ano_inicio is not None else ano_fim
    fim = ano_fim if ano_fim is not None else ano_inicio
    if inicio is None or fim is None:
        raise FreDisponibilidadeValidationError("Intervalo de anos invalido.")
    if inicio > fim:
        raise FreDisponibilidadeValidationError("ano_inicio deve ser menor ou igual a ano_fim.")
    if fim - inicio > 20:
        raise FreDisponibilidadeValidationError("Intervalo de anos muito amplo; limite maximo de 21 anos.")
    return list(range(inicio, fim + 1))


def datasets_para_disponibilidade(dataset: list[str] | None) -> list[DatasetFonte]:
    datasets = listar_datasets("fre")
    if not dataset:
        return datasets
    filtro = set(dataset)
    conhecidos = {item.dataset for item in datasets}
    desconhecidos = sorted(filtro - conhecidos)
    if desconhecidos:
        raise FreDisponibilidadeValidationError(f"Dataset FRE desconhecido: {', '.join(desconhecidos)}")
    return [item for item in datasets if item.dataset in filtro]


def _latest_artifact_snapshot(db: Session, ano: int) -> SourceArtifactSnapshot | None:
    return db.scalar(
        select(SourceArtifactSnapshot)
        .where(SourceArtifactSnapshot.tipo_fonte == "fre", SourceArtifactSnapshot.ano == ano)
        .order_by(SourceArtifactSnapshot.updated_at.desc(), SourceArtifactSnapshot.created_at.desc())
        .limit(1)
    )


def _latest_source_member(db: Session, *, ano: int, member_name: str) -> SourceMemberSnapshot | None:
    return db.scalar(
        select(SourceMemberSnapshot)
        .join(SourceArtifactSnapshot, SourceArtifactSnapshot.id == SourceMemberSnapshot.artifact_snapshot_id)
        .where(
            SourceArtifactSnapshot.tipo_fonte == "fre",
            SourceArtifactSnapshot.ano == ano,
            SourceMemberSnapshot.member_name == member_name,
        )
        .order_by(SourceMemberSnapshot.updated_at.desc(), SourceMemberSnapshot.created_at.desc())
        .limit(1)
    )


def _latest_file_member(
    db: Session, *, ano: int, member_name: str
) -> tuple[IngestionFileMember, IngestionRun, IngestionFile] | None:
    row = db.execute(
        select(IngestionFileMember, IngestionRun, IngestionFile)
        .join(IngestionFile, IngestionFile.id == IngestionFileMember.ingestion_file_id)
        .join(IngestionRun, IngestionRun.id == IngestionFile.ingestion_run_id)
        .where(
            IngestionRun.tipo_fonte == "fre",
            IngestionRun.ano == ano,
            IngestionFileMember.member_name == member_name,
        )
        .order_by(IngestionFileMember.updated_at.desc(), IngestionFileMember.created_at.desc())
        .limit(1)
    ).first()
    if row is None:
        return None
    return row[0], row[1], row[2]


def _latest_execucao_fre(
    db: Session,
    *,
    ano: int,
    execucao_id: Any | None,
    member_name: str,
) -> ExecucaoSincronizacao | None:
    if execucao_id is not None:
        execucao = db.get(ExecucaoSincronizacao, execucao_id)
        if execucao is not None:
            return execucao
    zip_name = f"fre_cia_aberta_{ano}.zip"
    return db.scalar(
        select(ExecucaoSincronizacao)
        .where(
            ExecucaoSincronizacao.tipo_fonte == "fre",
            ExecucaoSincronizacao.ano == ano,
            ExecucaoSincronizacao.arquivo.in_([member_name, zip_name]),
        )
        .order_by(ExecucaoSincronizacao.iniciada_em.desc())
        .limit(1)
    )


def promoted_rows_for_dataset(db: Session, *, dataset: str, ano: int) -> int | None:
    modelo = _FRE_DATASET_MODELS.get(dataset)
    if modelo is None:
        return None
    query = select(func.count()).select_from(modelo)
    if hasattr(modelo, "ano_origem"):
        query = query.where(_col(modelo, "ano_origem") == ano)
    return db.scalar(query) or 0


def diagnosticar_dataset_fre(
    *,
    dataset: DatasetFonte,
    source_package_seen: bool,
    source_member_exists: bool,
    source_member_row_count: int | None,
    promoted_rows: int | None,
    endpoint: str | None,
) -> tuple[FreDatasetDiagnosticoCodigo, str]:
    if dataset.status_suporte != "suportado":
        return "UNSUPPORTED_DATASET", "Dataset catalogado, mas ainda nao suportado pela ingestao/promocao."
    if dataset.destino_promovido is None or promoted_rows is None:
        return "NOT_PROMOTED", "Dataset sem tabela de dominio promovida para consulta publica."
    if endpoint is None:
        return "NOT_PROMOTED", "Dataset possui tabela de dominio, mas nao possui endpoint publico ativo."
    if promoted_rows > 0:
        return "AVAILABLE", "Endpoint publico possui linhas promovidas para o ano."
    if not source_package_seen:
        return "PACKAGE_NOT_INGESTED", "Nao ha pacote anual FRE conhecido para o ano; execute ou verifique a ingestao."
    if not source_member_exists:
        return "SOURCE_MEMBER_MISSING", "Pacote anual conhecido, mas o CSV membro nao foi encontrado/indexado."
    if source_member_row_count == 0:
        return "SOURCE_MEMBER_EMPTY", "CSV membro foi encontrado, mas nao possui linhas de dados."
    return "PROMOTION_MISSING", "CSV membro possui linhas, mas a tabela que alimenta o endpoint esta vazia."


def item_disponibilidade_fre(db: Session, *, ano: int, dataset: DatasetFonte) -> FreDatasetDisponibilidadeItem:
    member_name = dataset.render_member_name(ano=ano)
    artifact = _latest_artifact_snapshot(db, ano)
    source_member = _latest_source_member(db, ano=ano, member_name=member_name)
    file_member_tuple = _latest_file_member(db, ano=ano, member_name=member_name)
    file_member = file_member_tuple[0] if file_member_tuple is not None else None
    file_run = file_member_tuple[1] if file_member_tuple is not None else None
    source_package_seen = artifact is not None or file_member_tuple is not None
    source_member_exists = source_member is not None or file_member is not None
    source_member_row_count = source_member.row_count if source_member is not None else file_member.row_count if file_member is not None else None
    source_member_schema_status = (
        source_member.schema_status if source_member is not None else file_member.schema_status if file_member is not None else None
    )
    promoted_rows = promoted_rows_for_dataset(db, dataset=dataset.dataset, ano=ano)
    endpoint = FRE_DATASET_ENDPOINTS.get(dataset.dataset)
    diagnosis_code, diagnosis_message = diagnosticar_dataset_fre(
        dataset=dataset,
        source_package_seen=source_package_seen,
        source_member_exists=source_member_exists,
        source_member_row_count=source_member_row_count,
        promoted_rows=promoted_rows,
        endpoint=endpoint,
    )
    latest_run_id = artifact.ingestion_run_id if artifact is not None else file_run.id if file_run is not None else None
    latest_execucao_id = (
        db.scalar(select(IngestionRun.execucao_sincronizacao_id).where(IngestionRun.id == latest_run_id))
        if latest_run_id is not None
        else None
    )
    execucao = _latest_execucao_fre(db, ano=ano, execucao_id=latest_execucao_id, member_name=member_name)
    if latest_execucao_id is None and execucao is not None:
        latest_execucao_id = execucao.id
    atualizado_em = (
        source_member.updated_at
        if source_member is not None
        else file_member.updated_at
        if file_member is not None
        else artifact.updated_at
        if artifact is not None
        else execucao.finalizada_em
        if execucao is not None
        else None
    )
    return FreDatasetDisponibilidadeItem(
        ano=ano,
        dataset=dataset.dataset,
        descricao=dataset.descricao,
        endpoint=endpoint,
        member_name=member_name,
        row_kind=dataset.row_kind,
        destino_promovido=dataset.destino_promovido,
        status_suporte=dataset.status_suporte,
        obrigatorio=dataset.obrigatorio,
        source_package_seen=source_package_seen,
        source_package_status=artifact.status if artifact is not None else None,
        source_package_run_id=artifact.ingestion_run_id if artifact is not None else file_run.id if file_run is not None else None,
        source_member_exists=source_member_exists,
        source_member_row_count=source_member_row_count,
        source_member_schema_status=source_member_schema_status,
        source_member_lifecycle_status=source_member.lifecycle_status if source_member is not None else None,
        member_ingested=source_member_exists,
        promoted_rows=promoted_rows,
        endpoint_available=endpoint is not None and promoted_rows is not None and promoted_rows > 0,
        diagnosis_code=diagnosis_code,
        diagnosis_message=diagnosis_message,
        latest_ingestion_run_id=latest_run_id,
        latest_execucao_id=latest_execucao_id,
        atualizado_em=atualizado_em,
    )


def resumo_disponibilidade_fre(itens: list[FreDatasetDisponibilidadeItem]) -> FreDatasetDisponibilidadeResumo:
    contadores: dict[str, int] = {
        "available": 0,
        "package_not_ingested": 0,
        "source_member_missing": 0,
        "source_member_empty": 0,
        "promotion_missing": 0,
        "not_promoted": 0,
        "unsupported_dataset": 0,
    }
    chave_por_codigo = {
        "AVAILABLE": "available",
        "PACKAGE_NOT_INGESTED": "package_not_ingested",
        "SOURCE_MEMBER_MISSING": "source_member_missing",
        "SOURCE_MEMBER_EMPTY": "source_member_empty",
        "PROMOTION_MISSING": "promotion_missing",
        "NOT_PROMOTED": "not_promoted",
        "UNSUPPORTED_DATASET": "unsupported_dataset",
    }
    for item in itens:
        contadores[chave_por_codigo[item.diagnosis_code]] += 1
    return FreDatasetDisponibilidadeResumo(total=len(itens), **contadores)


def diagnosticar_disponibilidade_datasets_fre(
    db: Session,
    *,
    ano: int | None,
    ano_inicio: int | None,
    ano_fim: int | None,
    dataset: list[str] | None,
) -> ListaFreDatasetsDisponibilidadeResposta:
    anos = anos_para_disponibilidade(db, ano=ano, ano_inicio=ano_inicio, ano_fim=ano_fim)
    datasets = datasets_para_disponibilidade(dataset)
    itens = [
        item_disponibilidade_fre(db, ano=ano_item, dataset=dataset_item)
        for ano_item in anos
        for dataset_item in datasets
    ]
    return ListaFreDatasetsDisponibilidadeResposta(resumo=resumo_disponibilidade_fre(itens), dados=itens)


__all__: tuple[str, ...] = (
    "FRE_DATASET_ENDPOINTS",
    "FreDisponibilidadeValidationError",
    "datasets_para_disponibilidade",
    "diagnosticar_dataset_fre",
    "diagnosticar_disponibilidade_datasets_fre",
    "item_disponibilidade_fre",
    "promoted_rows_for_dataset",
    "resumo_disponibilidade_fre",
)
