from datetime import UTC, date, datetime
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
    FreDatasetDiagnosticoCodigo,
    FreDatasetDisponibilidadeItem,
    FreDatasetDisponibilidadeResumo,
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
    ListaFreDatasetsDisponibilidadeResposta,
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
from app.services.ingestion.source_registry import DatasetFonte, listar_datasets
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

_FRE_DATASET_ENDPOINTS: dict[str, str] = {
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


def _ano_disponibilidade_padrao(db: Session) -> int:
    ano_documento = db.scalar(select(func.max(FreDocumento.ano_origem)))
    ano_snapshot = db.scalar(
        select(func.max(SourceArtifactSnapshot.ano)).where(SourceArtifactSnapshot.tipo_fonte == "fre")
    )
    anos = [ano for ano in (ano_documento, ano_snapshot) if ano is not None]
    return max(anos) if anos else datetime.now(UTC).year


def _anos_para_disponibilidade(
    db: Session,
    *,
    ano: int | None,
    ano_inicio: int | None,
    ano_fim: int | None,
) -> list[int]:
    if ano is not None and (ano_inicio is not None or ano_fim is not None):
        raise HTTPException(status_code=422, detail="Use ano ou ano_inicio/ano_fim, nao ambos.")
    if ano is not None:
        return [ano]
    if ano_inicio is None and ano_fim is None:
        return [_ano_disponibilidade_padrao(db)]
    inicio = ano_inicio if ano_inicio is not None else ano_fim
    fim = ano_fim if ano_fim is not None else ano_inicio
    if inicio is None or fim is None:
        raise HTTPException(status_code=422, detail="Intervalo de anos invalido.")
    if inicio > fim:
        raise HTTPException(status_code=422, detail="ano_inicio deve ser menor ou igual a ano_fim.")
    if fim - inicio > 20:
        raise HTTPException(status_code=422, detail="Intervalo de anos muito amplo; limite maximo de 21 anos.")
    return list(range(inicio, fim + 1))


def _datasets_para_disponibilidade(dataset: list[str] | None) -> list[DatasetFonte]:
    datasets = listar_datasets("fre")
    if not dataset:
        return datasets
    filtro = set(dataset)
    conhecidos = {item.dataset for item in datasets}
    desconhecidos = sorted(filtro - conhecidos)
    if desconhecidos:
        raise HTTPException(
            status_code=422,
            detail=f"Dataset FRE desconhecido: {', '.join(desconhecidos)}",
        )
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


def _promoted_rows_for_dataset(db: Session, *, dataset: str, ano: int) -> int | None:
    modelo = _FRE_DATASET_MODELS.get(dataset)
    if modelo is None:
        return None
    query = select(func.count()).select_from(modelo)
    if hasattr(modelo, "ano_origem"):
        query = query.where(_col(modelo, "ano_origem") == ano)
    return db.scalar(query) or 0


def _diagnosticar_dataset_fre(
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


def _item_disponibilidade_fre(db: Session, *, ano: int, dataset: DatasetFonte) -> FreDatasetDisponibilidadeItem:
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
    promoted_rows = _promoted_rows_for_dataset(db, dataset=dataset.dataset, ano=ano)
    endpoint = _FRE_DATASET_ENDPOINTS.get(dataset.dataset)
    diagnosis_code, diagnosis_message = _diagnosticar_dataset_fre(
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


def _resumo_disponibilidade_fre(itens: list[FreDatasetDisponibilidadeItem]) -> FreDatasetDisponibilidadeResumo:
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


@router.get(
    "/fre/datasets/disponibilidade",
    response_model=ListaFreDatasetsDisponibilidadeResposta,
    summary="Diagnosticar Disponibilidade de Datasets FRE",
    description=(
        "Cruza catalogo de fontes, snapshots de ingestao e tabelas promovidas para explicar por que um "
        "endpoint FRE esta vazio em um ano. O diagnostico distingue pacote anual ausente, CSV membro ausente, "
        "CSV membro vazio, falha/lacuna de promocao e endpoint/tabela nao promovidos."
    ),
    responses=_RESPOSTAS_PADRAO,
    operation_id="diagnosticarDisponibilidadeDatasetsFre",
)
def diagnosticar_disponibilidade_datasets_fre(
    db: DbSession,
    ano: Annotated[int | None, Query(description="Ano unico do ZIP FRE a avaliar.", examples=[2025])] = None,
    ano_inicio: ParametroAnoInicio = None,
    ano_fim: ParametroAnoFim = None,
    dataset: Annotated[
        list[str] | None,
        Query(
            description=(
                "Filtra datasets especificos pelo identificador do catalogo. Pode ser repetido na query string."
            ),
            examples=["outro_valor_mobiliario"],
        ),
    ] = None,
) -> ListaFreDatasetsDisponibilidadeResposta:
    anos = _anos_para_disponibilidade(db, ano=ano, ano_inicio=ano_inicio, ano_fim=ano_fim)
    datasets = _datasets_para_disponibilidade(dataset)
    itens = [
        _item_disponibilidade_fre(db, ano=ano_item, dataset=dataset_item)
        for ano_item in anos
        for dataset_item in datasets
    ]
    return ListaFreDatasetsDisponibilidadeResposta(resumo=_resumo_disponibilidade_fre(itens), dados=itens)


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
