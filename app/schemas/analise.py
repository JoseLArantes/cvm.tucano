from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.comum import CanonicalDecimal, Paginacao

CalculationVersion = Literal["2026.2"]
AnalisePeriodicidade = Literal["annual", "quarterly"]
AnaliseBasePeriodo = Literal["fy", "quarter", "ytd"]
AnaliseEscopo = Literal["consolidated", "individual"]
AnaliseNaturezaPeriodo = Literal["instant", "duration"]
AnaliseMetricType = Literal["stock", "flow", "ratio", "count"]
AnaliseUnit = Literal["BRL", "ratio", "percentage_point", "count", "shares", "index"]
AnaliseForm = Literal["DFP", "ITR", "DERIVED"]
AnaliseValueSource = Literal["reported", "derived_from_ytd_delta", "derived_from_dfp_minus_ytd", "derived_from_formula"]
AnaliseStatus = Literal["available", "unavailable"]
AnaliseSeverity = Literal["info", "warning", "critical"]
AnaliseCoverage = Literal["complete", "partial", "missing"]
AnaliseComparisonKind = Literal["YoY", "QoQ", "CAGR", "VERTICAL", "BASE100"]
AnaliseResolutionMode = Literal["canonical", "runtime_fallback"]
AnaliseMaterializacaoStatus = Literal["running", "success", "failed"]
AnaliseMaterializacaoCampanhaStatus = Literal["pending", "running", "success", "failed", "partial"]
AnaliseComparisonUnit = Literal["BRL", "ratio", "percentage_point", "count", "shares", "index"]
AnaliseMaterializacaoGateStatus = Literal["green", "red"]
AnaliseMaterializacaoControlMode = Literal["auto", "paused"]
AnaliseMaterializacaoChunkStatus = Literal["queued", "running", "success", "failed", "stale", "cancelled"]
AnaliseMaterializacaoMode = Literal["full", "incremental"]


class AnaliseLinkSet(BaseModel):
    series: str = Field(description="URL relativa para a serie analitica normalizada da companhia.")
    comparacoes: str = Field(description="URL relativa para as comparacoes analiticas prontas.")
    qualidade: str = Field(description="URL relativa para os diagnósticos de qualidade analitica.")
    sinais: str = Field(description="URL relativa para os sinais determinísticos.")
    eventos: str = Field(description="URL relativa para a timeline de eventos.")
    restatements: str = Field(description="URL relativa para o histórico de reapresentações.")
    governanca: str | None = Field(default=None, description="URL relativa para o bloco temporal de governança.")
    pessoas: str | None = Field(default=None, description="URL relativa para o bloco temporal de pessoas.")
    brief: str | None = Field(default=None, description="URL relativa para o brief analítico da companhia.")


class AnaliseCompanhiaResumo(BaseModel):
    codigo_cvm: int = Field(description="Código CVM da companhia.", examples=[9512])
    cnpj_companhia: str = Field(description="CNPJ normalizado da companhia.", examples=["33000167000101"])
    denominacao_social: str = Field(description="Denominação social da companhia.")
    situacao_registro: str | None = Field(default=None, description="Situação cadastral atual do registro da companhia.")


class AnaliseContextoPadrao(BaseModel):
    periodo_id: str = Field(description="Período padrão sugerido para consumo analítico.", examples=["FY2025"])
    periodicidade: AnalisePeriodicidade = Field(description="Periodicidade padrão do contexto.")
    escopo: AnaliseEscopo = Field(description="Escopo padrão do contexto.")


class AnaliseIssue(BaseModel):
    code: str = Field(description="Código estável da regra ou problema detectado.", examples=["MISSING_COMPARABLE_PERIOD"])
    severity: AnaliseSeverity = Field(description="Severidade do problema.")
    message: str = Field(description="Descrição objetiva do problema detectado.")
    affected_period_ids: list[str] = Field(
        default_factory=list,
        description="Lista de períodos afetados pela regra."
    )


class AnalisePeriodoDisponivel(BaseModel):
    period_id: str = Field(description="Identificador canônico do período.", examples=["FY2025", "2025-Q3", "2025-YTDQ3"])
    fiscal_year: int = Field(description="Ano fiscal do período.", examples=[2025])
    quarter: int | None = Field(default=None, description="Trimestre fiscal quando aplicável.", examples=[3])
    periodicidade: AnalisePeriodicidade = Field(description="Periodicidade da observação.")
    base_periodo: AnaliseBasePeriodo = Field(description="Base temporal usada para a observação.")
    period_nature: AnaliseNaturezaPeriodo = Field(description="Se a observação é posição em data (`instant`) ou duração (`duration`).")
    start_date: date | None = Field(default=None, description="Data inicial do período em ISO 8601.")
    end_date: date = Field(description="Data final do período em ISO 8601.")
    form: AnaliseForm = Field(description="Formulário principal que suporta esse período.")
    scope: AnaliseEscopo = Field(description="Escopo do período.")
    restated: bool = Field(description="Indica se o período usa documento reapresentado.")


class AnaliseQualidadeResumo(BaseModel):
    completude: AnaliseCoverage = Field(description="Cobertura dos períodos e componentes esperados.")
    comparabilidade: AnaliseCoverage = Field(description="Capacidade de comparar a série com períodos equivalentes.")
    consistencia: AnaliseCoverage = Field(description="Consistência entre períodos, versões e componentes calculados.")
    restatements: int = Field(description="Quantidade de documentos reapresentados considerados no contexto.")
    issues: list[AnaliseIssue] = Field(default_factory=list, description="Lista auditável de problemas e alertas detectados.")
    checked_at: datetime = Field(description="Momento da avaliação de qualidade em ISO 8601.")
    ruleset_version: CalculationVersion = Field(description="Versão do conjunto de regras de qualidade.")


class AnaliseResolutionMetadata(BaseModel):
    mode: AnaliseResolutionMode = Field(description="Origem efetiva da resposta: camada canônica persistida ou resolvedor em tempo de execução.")
    materialization_execution_id: str | None = Field(
        default=None,
        description="Identificador da execução de materialização que produziu a resposta canônica, quando aplicável.",
    )
    materialized_at: datetime | None = Field(
        default=None,
        description="Momento em que a materialização canônica usada pela resposta foi concluída.",
    )
    as_of: date | None = Field(
        default=None,
        description="Data de corte informacional efetivamente considerada na resposta.",
    )


class AnaliseManifestoResposta(BaseModel):
    companhia: AnaliseCompanhiaResumo
    contexto_padrao: AnaliseContextoPadrao
    periodos_disponiveis: list[AnalisePeriodoDisponivel] = Field(description="Lista dos períodos analíticos disponíveis no contexto padrão.")
    qualidade: AnaliseQualidadeResumo = Field(description="Resumo objetivo da qualidade analítica atual.")
    calculation_version: CalculationVersion = Field(description="Versão do motor analítico.")
    resolution: AnaliseResolutionMetadata = Field(description="Metadados da estratégia de resolução usada na resposta.")
    links: AnaliseLinkSet


class AnaliseMaterializacaoProgress(BaseModel):
    total_knowledge_dates: int | None = Field(default=None, description="Quantidade total de datas de conhecimento previstas para a execução.")
    processed_knowledge_dates: int | None = Field(default=None, description="Quantidade de datas de conhecimento já processadas.")
    current_known_from: date | None = Field(default=None, description="Data de conhecimento atualmente em processamento, quando aplicável.")
    progress_ratio: float | None = Field(default=None, description="Progresso estimado entre 0 e 1.")
    context_revisions: int | None = Field(default=None, description="Quantidade parcial de revisões de contexto acumuladas.")
    fact_revisions: int | None = Field(default=None, description="Quantidade parcial de revisões de fatos acumuladas.")


class AnaliseMaterializacaoExecucaoResumo(BaseModel):
    id: str = Field(description="Identificador da execução de materialização.")
    codigo_cvm: int = Field(description="Código CVM da companhia.")
    escopo: AnaliseEscopo = Field(description="Escopo societário materializado.")
    calculation_version: CalculationVersion = Field(description="Versão do motor analítico usada na execução.")
    status: AnaliseMaterializacaoStatus = Field(description="Estado atual ou final da materialização.")
    coverage_complete: bool = Field(description="Indica se a cobertura canônica foi completada com sucesso.")
    source: str = Field(description="Origem do disparo da materialização.")
    materialization_mode: AnaliseMaterializacaoMode = Field(description="Indica se a execução recompôs toda a história ou apenas uma janela incremental.")
    invalidated_from: date | None = Field(default=None, description="Primeira data de conhecimento recomposta na execução incremental, quando aplicável.")
    started_at: datetime | None = Field(default=None, description="Momento de início da execução.")
    finished_at: datetime | None = Field(default=None, description="Momento de conclusão da execução.")
    updated_at: datetime | None = Field(default=None, description="Último heartbeat ou atualização persistida pela execução.")
    elapsed_seconds: int | None = Field(default=None, description="Tempo decorrido da execução em segundos.")
    estimated_remaining_seconds: int | None = Field(default=None, description="Tempo restante estimado em segundos, quando o progresso parcial permite cálculo.")
    estimated_finish_at: datetime | None = Field(default=None, description="Estimativa de conclusão baseada no progresso atual, quando disponível.")
    campanha_id: str | None = Field(default=None, description="Identificador da campanha de materialização associada, quando houver.")
    campanha_item_id: str | None = Field(default=None, description="Identificador do item da campanha associado a esta execução, quando houver.")
    chunk_execucao_id: str | None = Field(default=None, description="Identificador do chunk de materialização associado, quando houver.")
    queue_name: str | None = Field(default=None, description="Nome da fila Celery usada para executar a materialização.")
    position_in_chunk: int | None = Field(default=None, description="Posição do item dentro do chunk processado, quando aplicável.")
    window_total_knowledge_dates: int | None = Field(default=None, description="Quantidade total de datas de conhecimento no recorte efetivamente processado pela execução.")
    window_processed_knowledge_dates: int | None = Field(default=None, description="Quantidade já processada no recorte efetivo da execução.")
    inserted_context_revisions: int | None = Field(default=None, description="Quantidade de revisões de contexto inseridas por esta execução.")
    inserted_fact_revisions: int | None = Field(default=None, description="Quantidade de revisões de fatos inseridas por esta execução.")
    closed_context_revisions: int | None = Field(default=None, description="Quantidade de revisões de contexto antigas encerradas por esta execução.")
    closed_fact_revisions: int | None = Field(default=None, description="Quantidade de revisões de fatos antigas encerradas por esta execução.")
    deleted_future_context_revisions: int | None = Field(default=None, description="Quantidade de revisões futuras de contexto removidas por substituição.")
    deleted_future_fact_revisions: int | None = Field(default=None, description="Quantidade de revisões futuras de fatos removidas por substituição.")
    progress: AnaliseMaterializacaoProgress = Field(description="Resumo estruturado do progresso da execução.")


class AnaliseMaterializacaoExecucaoDetalhe(AnaliseMaterializacaoExecucaoResumo):
    summary: dict[str, object] = Field(description="Resumo bruto persistido pela execução, preservado para auditoria operacional.")


class AnaliseMaterializacaoExecucoesResumo(BaseModel):
    total: int = Field(description="Total de execuções encontradas para os filtros aplicados.")
    running: int = Field(description="Quantidade de execuções em andamento.")
    success: int = Field(description="Quantidade de execuções concluídas com sucesso.")
    failed: int = Field(description="Quantidade de execuções com falha.")


class AnaliseMaterializacaoExecucoesListaResposta(BaseModel):
    dados: list[AnaliseMaterializacaoExecucaoResumo] = Field(description="Lista paginada de execuções de materialização.")
    paginacao: Paginacao = Field(description="Metadados de paginação da listagem.")
    resumo: AnaliseMaterializacaoExecucoesResumo = Field(description="Resumo agregado para os mesmos filtros da listagem.")


class AnaliseMaterializacaoFilaSnapshot(BaseModel):
    workers_reporting: int = Field(description="Quantidade de workers Celery que responderam ao inspect.")
    materialization_active_tasks: int = Field(description="Quantidade de tasks de materialização ativas nos workers.")
    materialization_reserved_tasks: int = Field(description="Quantidade de tasks de materialização reservadas nos workers.")
    materialization_scheduled_tasks: int = Field(description="Quantidade de tasks de materialização agendadas nos workers.")
    materialization_orchestrator_active_tasks: int = Field(description="Quantidade de tasks orquestradoras de campanhas ativas.")
    materialization_chunk_active_tasks: int = Field(description="Quantidade de tasks de chunk ativas.")
    materialization_queue_depth: int | None = Field(default=None, description="Profundidade observada da fila dedicada de materialização, quando disponível.")


class AnaliseMaterializacaoCampanhaResumo(BaseModel):
    campanha_id: str = Field(description="Identificador da campanha.")
    source: str = Field(description="Origem do disparo da campanha.")
    status: AnaliseMaterializacaoCampanhaStatus = Field(description="Estado atual ou final da campanha.")
    chunk_size: int = Field(description="Tamanho configurado de chunk por campanha.")
    total_items: int = Field(description="Quantidade total de itens na campanha.")
    processed_items: int = Field(description="Quantidade de itens já concluídos, incluindo skipped.")
    pending_items: int = Field(description="Quantidade de itens pendentes.")
    running_items: int = Field(description="Quantidade de itens em processamento.")
    failed_items: int = Field(description="Quantidade de itens com falha.")
    skipped_items: int = Field(description="Quantidade de itens deduplicados/skipped.")
    progress_ratio: float | None = Field(default=None, description="Progresso estimado entre 0 e 1.")
    started_at: datetime | None = Field(default=None, description="Momento de início da campanha.")
    updated_at: datetime | None = Field(default=None, description="Último heartbeat da campanha.")
    estimated_remaining_seconds: int | None = Field(default=None, description="Tempo restante estimado para concluir a campanha, quando disponível.")
    active_chunk_id: str | None = Field(default=None, description="Chunk ativo atualmente associado à campanha, quando houver.")
    active_chunk_lease_expires_at: datetime | None = Field(default=None, description="Momento de expiração do lease do chunk ativo, quando houver.")
    stale_chunks: int = Field(default=0, description="Quantidade de chunks stale associados à campanha.")
    wait_reason: str | None = Field(default=None, description="Motivo atual de espera, quando a campanha não está progredindo.")


class AnaliseMaterializacaoCampanhaItemPreview(BaseModel):
    item_id: str = Field(description="Identificador do item de campanha.")
    codigo_cvm: int = Field(description="Código CVM da companhia.")
    escopo: AnaliseEscopo = Field(description="Escopo societário do item.")
    campanha_id: str = Field(description="Identificador da campanha de origem.")
    materialization_mode: AnaliseMaterializacaoMode = Field(description="Modo de materialização planejado para o item.")
    invalidated_from: date | None = Field(default=None, description="Primeira data de conhecimento recomposta para o item, quando aplicável.")
    chunk_execucao_id: str | None = Field(default=None, description="Identificador do chunk associado ao item, quando houver.")
    status: str = Field(description="Estado atual do item.")
    started_at: datetime | None = Field(default=None, description="Momento em que o item começou a processar.")


class AnaliseMaterializacaoChunkExecucaoResumo(BaseModel):
    chunk_execucao_id: str = Field(description="Identificador do chunk.")
    campanha_id: str = Field(description="Campanha associada ao chunk.")
    status: AnaliseMaterializacaoChunkStatus = Field(description="Estado atual ou final do chunk.")
    lease_owner: str | None = Field(default=None, description="Identidade do task/worker que possuiu o lease, quando houver.")
    lease_expires_at: datetime | None = Field(default=None, description="Momento atual de expiração do lease.")
    heartbeat_at: datetime | None = Field(default=None, description="Último heartbeat persistido do chunk.")
    item_count: int = Field(description="Quantidade de itens no chunk.")
    processed_items: int = Field(description="Quantidade de itens já processados no chunk.")
    success_items: int = Field(description="Quantidade de itens concluídos com sucesso no chunk.")
    failed_items: int = Field(description="Quantidade de itens concluídos com falha no chunk.")
    started_at: datetime | None = Field(default=None, description="Momento de início efetivo do chunk.")
    finished_at: datetime | None = Field(default=None, description="Momento de término do chunk.")
    updated_at: datetime | None = Field(default=None, description="Última atualização persistida do chunk.")


class AnaliseMaterializacaoChunkExecucaoPreview(AnaliseMaterializacaoChunkExecucaoResumo):
    pass


class AnaliseMaterializacaoRecuperacaoResposta(BaseModel):
    recovered_chunks: int = Field(description="Quantidade de chunks recuperados na operação.")
    recovered_items: int = Field(description="Quantidade de itens devolvidos para pending.")
    affected_campaigns: list[str] = Field(default_factory=list, description="Campanhas afetadas pela recuperação.")
    chunk_ids: list[str] = Field(default_factory=list, description="Chunks efetivamente recuperados.")


class AnaliseMaterializacaoIngestionBlocker(BaseModel):
    source_type: str = Field(description="Fonte de ingestão em execução ou agendada.")
    execution_id: str | None = Field(default=None, description="Identificador da execução de sincronização associada, quando houver.")
    run_id: str | None = Field(default=None, description="Identificador da run de ingestão associada, quando houver.")
    year: int | None = Field(default=None, description="Ano da execução quando aplicável.")
    status: str = Field(description="Status operacional da execução bloqueadora.")
    phase: str | None = Field(default=None, description="Fase da run de ingestão, quando houver.")
    started_at: datetime | None = Field(default=None, description="Momento em que o trabalho bloqueador começou.")


class AnaliseMaterializacaoGateSnapshot(BaseModel):
    status: AnaliseMaterializacaoGateStatus = Field(description="Estado atual do gate de admissão da materialização.")
    reason_code: str = Field(description="Código objetivo para o motivo do estado atual.")
    gate_enabled: bool = Field(description="Indica se a política de gate automático está habilitada.")
    manual_control: AnaliseMaterializacaoControlMode = Field(description="Modo manual configurado para o gate.")
    manual_reason: str | None = Field(default=None, description="Motivo informado para pausa manual, quando houver.")
    blocking_ingestions: int = Field(description="Quantidade de execuções/runs que bloqueiam a materialização neste momento.")
    pending_ingestions: int = Field(description="Quantidade de execuções aguardando ingestão, reportadas para contexto operacional.")
    next_check_at: datetime | None = Field(default=None, description="Próxima checagem recomendada do gate, quando ele está vermelho.")
    blockers: list[AnaliseMaterializacaoIngestionBlocker] = Field(
        default_factory=list,
        description="Preview das execuções ou runs que mantêm o gate fechado.",
    )


class AnaliseMaterializacaoControleResposta(BaseModel):
    gate: AnaliseMaterializacaoGateSnapshot = Field(description="Snapshot consolidado do estado do gate.")
    updated_at: datetime | None = Field(default=None, description="Momento da última alteração manual persistida.")


class AnaliseMaterializacaoMonitoramentoResposta(BaseModel):
    as_of: datetime = Field(description="Momento do snapshot de monitoramento.")
    fila: AnaliseMaterializacaoFilaSnapshot = Field(description="Estado observado da fila/worker para tasks de materialização.")
    gate: AnaliseMaterializacaoGateSnapshot = Field(description="Estado consolidado do gate de admissão da materialização.")
    running_executions: int = Field(description="Quantidade de execuções em andamento no banco.")
    running_full_executions: int = Field(description="Quantidade de execuções full em andamento.")
    running_incremental_executions: int = Field(description="Quantidade de execuções incrementais em andamento.")
    lowest_running_invalidated_from: date | None = Field(default=None, description="Menor cutoff incremental observado entre as execuções em andamento.")
    pending_campaigns: int = Field(description="Quantidade de campanhas pendentes.")
    running_campaigns: int = Field(description="Quantidade de campanhas em andamento.")
    waiting_for_gate_campaigns: int = Field(description="Quantidade de campanhas pendentes especificamente por bloqueio do gate.")
    recovering_campaigns: int = Field(description="Quantidade de campanhas aguardando recuperação de chunk stale.")
    pending_items: int = Field(description="Quantidade de itens pendentes em campanhas.")
    running_items: int = Field(description="Quantidade de itens em andamento em campanhas.")
    success_items: int = Field(description="Quantidade de itens concluídos com sucesso em campanhas.")
    failed_items: int = Field(description="Quantidade de itens com falha em campanhas.")
    skipped_items: int = Field(description="Quantidade de itens marcados como skipped em campanhas.")
    queued_chunks: int = Field(description="Quantidade de chunks em fila/lease aguardando execução.")
    running_chunks: int = Field(description="Quantidade de chunks efetivamente em execução.")
    stale_chunks: int = Field(description="Quantidade de chunks marcados como stale.")
    stale_item_count: int = Field(description="Quantidade de itens ainda associados a chunks stale.")
    oldest_running_started_at: datetime | None = Field(default=None, description="Início da execução mais antiga ainda em andamento.")
    longest_running_elapsed_seconds: int | None = Field(default=None, description="Tempo decorrido da execução mais antiga ainda em andamento.")
    stalled_threshold_seconds: int = Field(description="Janela usada para considerar uma execução potencialmente sem heartbeat.")
    stalled_execution_ids: list[str] = Field(default_factory=list, description="Execuções em andamento cujo `updated_at` ficou mais antigo que o threshold configurado.")
    stalled_incremental_execution_ids: list[str] = Field(default_factory=list, description="Subset das execuções stalled que estavam em modo incremental.")
    running_execution_previews: list[AnaliseMaterializacaoExecucaoResumo] = Field(default_factory=list, description="Preview das execuções atualmente em andamento.")
    campaigns: list[AnaliseMaterializacaoCampanhaResumo] = Field(default_factory=list, description="Resumo das campanhas mais relevantes no momento do snapshot.")
    stale_chunk_preview: list[AnaliseMaterializacaoChunkExecucaoPreview] = Field(default_factory=list, description="Preview dos chunks stale que aguardam recuperação.")
    running_items_preview: list[AnaliseMaterializacaoCampanhaItemPreview] = Field(default_factory=list, description="Preview dos itens atualmente em processamento.")
    pending_items_preview: list[AnaliseMaterializacaoCampanhaItemPreview] = Field(default_factory=list, description="Preview dos próximos itens pendentes.")


class AnaliseMetricaCatalogoItem(BaseModel):
    id: str = Field(description="Identificador estável da métrica.", examples=["margem_liquida"])
    nome: str = Field(description="Nome profissional da métrica.")
    type: AnaliseMetricType = Field(description="Natureza econômica da métrica.")
    unit: AnaliseUnit = Field(description="Unidade oficial do valor retornado.")
    formula: str | None = Field(default=None, description="Fórmula declarada quando a métrica é derivada.")
    direction: Literal["higher_is_better", "lower_is_better", "contextual"] = Field(
        description="Direção interpretativa padrão da métrica."
    )
    contas_cvm_candidatas: list[str] = Field(
        default_factory=list,
        description="Códigos de conta CVM candidatos para resolução da métrica."
    )
    estrategia_resolucao: str = Field(description="Estratégia textual de resolução adotada pelo backend.")
    disponibilidades: list[AnaliseBasePeriodo] = Field(
        description="Bases temporais suportadas por esta métrica."
    )
    period_nature: AnaliseNaturezaPeriodo = Field(description="Natureza temporal esperada da métrica.")
    vertical_denominator_metric_id: str | None = Field(
        default=None,
        description="Métrica denominadora para análise vertical, quando aplicável."
    )
    limitations: list[str] = Field(default_factory=list, description="Limitações metodológicas conhecidas.")
    calculation_version: CalculationVersion = Field(description="Versão do catálogo/motor de cálculo.")


class AnaliseMetricasCatalogoResposta(BaseModel):
    calculation_version: CalculationVersion
    metricas: list[AnaliseMetricaCatalogoItem]


class AnaliseComparables(BaseModel):
    yoy_period_id: str | None = Field(default=None, description="Período comparável para YoY.")
    qoq_period_id: str | None = Field(default=None, description="Período comparável para QoQ.")


class AnaliseProvenienciaItem(BaseModel):
    source: str = Field(default="CVM", description="Fonte primária do dado.")
    dataset: str = Field(description="Dataset de origem no backend.")
    form: AnaliseForm = Field(description="Formulário de origem usado na observação.")
    document_id: int | None = Field(default=None, description="Identificador natural do documento na origem.")
    row_id: str | None = Field(default=None, description="UUID da linha persistida.")
    version: int | None = Field(default=None, description="Versão do documento considerado.")
    account_code: str | None = Field(default=None, description="Código da conta CVM utilizada.")
    statement_type: str | None = Field(default=None, description="Tipo da demonstração de origem.")
    order: str | None = Field(default=None, description="Valor de `ordem_exercicio` da linha original.")
    start_date: date | None = Field(default=None, description="Data inicial da observação de origem, em ISO 8601.")
    end_date: date | None = Field(default=None, description="Data final da observação de origem, em ISO 8601.")
    filed_at: date | None = Field(default=None, description="Data de entrega/recebimento do documento, em ISO 8601.")
    link_download: str | None = Field(default=None, description="Link oficial para download do documento na CVM.")


class AnaliseEvidenceItem(BaseModel):
    metric_id: str | None = Field(default=None, description="Métrica usada como evidência, quando aplicável.")
    period_id: str | None = Field(default=None, description="Período associado à evidência.")
    value: CanonicalDecimal | None = Field(default=None, description="Valor canônico usado como evidência.")
    unit: AnaliseUnit | None = Field(default=None, description="Unidade do valor de evidência.")
    note: str = Field(description="Explicação curta da evidência.")


class AnaliseSeriesObservation(BaseModel):
    metric_id: str = Field(description="Identificador estável da métrica.")
    period_id: str = Field(description="Identificador canônico do período.")
    fiscal_year: int = Field(description="Ano fiscal da observação.")
    quarter: int | None = Field(default=None, description="Trimestre fiscal quando aplicável.")
    period_nature: AnaliseNaturezaPeriodo = Field(description="Natureza temporal da observação.")
    period_basis: AnaliseBasePeriodo = Field(description="Base temporal da observação.")
    start_date: date | None = Field(default=None, description="Data inicial do período em ISO 8601.")
    end_date: date = Field(description="Data final do período em ISO 8601.")
    value: CanonicalDecimal = Field(description="Valor da observação serializado como decimal canônico.")
    unit: AnaliseUnit = Field(description="Unidade do valor.")
    scope: AnaliseEscopo = Field(description="Escopo societário considerado.")
    form: AnaliseForm = Field(description="Formulário principal usado para a observação.")
    version: int | None = Field(default=None, description="Versão documental principal usada.")
    restated: bool = Field(description="Indica se a observação se apoia em documento reapresentado.")
    value_source: AnaliseValueSource = Field(description="Como o valor foi obtido.")
    comparables: AnaliseComparables = Field(description="Referências de períodos comparáveis para YoY e QoQ.")
    provenance: list[AnaliseProvenienciaItem] = Field(description="Evidências documentais completas da observação.")


class AnaliseSeriesUnavailable(BaseModel):
    metric_id: str = Field(description="Métrica indisponível.")
    period_id: str = Field(description="Período solicitado/avaliado.")
    status: Literal["unavailable"] = Field(description="Marca a indisponibilidade.")
    reason_code: str = Field(description="Código estável da indisponibilidade.")
    message: str = Field(description="Descrição objetiva da indisponibilidade.")
    missing: list[str] = Field(default_factory=list, description="Elementos ausentes para cálculo ou seleção.")


class AnaliseSeriesResposta(BaseModel):
    companhia: AnaliseCompanhiaResumo
    calculation_version: CalculationVersion
    periodicidade: AnalisePeriodicidade
    base_periodo: AnaliseBasePeriodo
    escopo: AnaliseEscopo
    horizonte_anos: int | None = Field(default=None, description="Horizonte anual efetivamente aplicado, quando a consulta for histórica.")
    metricas: list[str] = Field(description="Métricas efetivamente consideradas na resposta.")
    resolution: AnaliseResolutionMetadata = Field(description="Metadados da estratégia de resolução usada na resposta.")
    observacoes: list[AnaliseSeriesObservation] = Field(description="Observações analíticas disponíveis.")
    indisponibilidades: list[AnaliseSeriesUnavailable] = Field(description="Métricas/períodos que não puderam ser produzidos.")
    issues: list[AnaliseIssue] = Field(default_factory=list, description="Problemas contextuais detectados durante a resolução.")


class AnaliseComparacaoItem(BaseModel):
    metric_id: str = Field(description="Métrica comparada.")
    period_id: str = Field(description="Período atual.")
    comparison_kind: AnaliseComparisonKind = Field(description="Tipo de comparação calculada.")
    status: AnaliseStatus = Field(description="Status da comparação.")
    reason_code: str | None = Field(default=None, description="Motivo da indisponibilidade quando `status=unavailable`.")
    current_value: CanonicalDecimal | None = Field(default=None, description="Valor atual.")
    comparable_period_id: str | None = Field(default=None, description="Período comparável quando aplicável.")
    comparable_metric_id: str | None = Field(default=None, description="Métrica denominadora ou base, quando aplicável.")
    comparable_value: CanonicalDecimal | None = Field(default=None, description="Valor comparável.")
    absolute_change: CanonicalDecimal | None = Field(default=None, description="Variação absoluta calculada.")
    relative_change: CanonicalDecimal | None = Field(
        default=None,
        description="Variação relativa em decimal canônico quando aplicável."
    )
    percentage_point_change: CanonicalDecimal | None = Field(
        default=None,
        description="Variação em pontos percentuais para métricas do tipo ratio."
    )
    base100_value: CanonicalDecimal | None = Field(
        default=None,
        description="Índice base 100 quando `comparison_kind=BASE100`."
    )
    metric_unit: AnaliseUnit = Field(description="Unidade dos valores atual e comparável.")
    comparison_unit: AnaliseComparisonUnit | None = Field(default=None, description="Unidade do resultado comparativo.")
    evidence: list[AnaliseEvidenceItem] = Field(default_factory=list, description="Evidências usadas para explicar a comparação.")


class AnaliseComparacoesResposta(BaseModel):
    companhia: AnaliseCompanhiaResumo
    calculation_version: CalculationVersion
    periodicidade: AnalisePeriodicidade
    base_periodo: AnaliseBasePeriodo
    escopo: AnaliseEscopo
    horizonte_anos: int | None = Field(default=None, description="Horizonte anual efetivamente aplicado, quando a consulta for histórica.")
    metricas: list[str]
    resolution: AnaliseResolutionMetadata = Field(description="Metadados da estratégia de resolução usada na resposta.")
    comparacoes: list[AnaliseComparacaoItem]
    issues: list[AnaliseIssue] = Field(default_factory=list)


class AnaliseQualidadeResposta(BaseModel):
    companhia: AnaliseCompanhiaResumo
    calculation_version: CalculationVersion
    periodicidade: AnalisePeriodicidade
    escopo: AnaliseEscopo
    resolution: AnaliseResolutionMetadata = Field(description="Metadados da estratégia de resolução usada na resposta.")
    qualidade: AnaliseQualidadeResumo


class AnaliseSignal(BaseModel):
    rule_id: str = Field(description="Identificador estável da regra.")
    rule_version: str = Field(description="Versão da regra determinística.")
    severity: Literal["info", "watch", "warning", "critical"] = Field(description="Severidade do sinal.")
    period_id: str = Field(description="Período principal associado ao sinal.")
    title: str = Field(description="Título curto do sinal.")
    explanation: str = Field(description="Explicação objetiva do que foi detectado.")
    threshold: CanonicalDecimal | None = Field(default=None, description="Threshold configurado para a regra.")
    observed: CanonicalDecimal | None = Field(default=None, description="Valor observado que disparou a regra.")
    unit: AnaliseUnit | None = Field(default=None, description="Unidade de `threshold` e `observed`.")
    evidence: list[AnaliseEvidenceItem] = Field(default_factory=list, description="Evidências que suportam o disparo.")


class AnaliseSinaisResposta(BaseModel):
    companhia: AnaliseCompanhiaResumo
    calculation_version: CalculationVersion
    resolution: AnaliseResolutionMetadata = Field(description="Metadados da estratégia de resolução usada na resposta.")
    sinais: list[AnaliseSignal]
    issues: list[AnaliseIssue] = Field(default_factory=list)


class AnaliseEvento(BaseModel):
    event_id: str = Field(description="Identificador estável do evento.")
    occurred_at: date = Field(description="Data do evento em ISO 8601.")
    family: Literal["IPE", "FINANCEIRO", "FRE", "VLMO", "CGVN", "FCA"] = Field(description="Família documental do evento.")
    event_type: str = Field(description="Tipo do evento.")
    severity: AnaliseSeverity = Field(description="Severidade informativa do evento.")
    title: str = Field(description="Título curto.")
    explanation: str = Field(description="Descrição objetiva.")
    period_id: str | None = Field(default=None, description="Período afetado, quando houver.")
    link_documento: str | None = Field(default=None, description="Link oficial do documento.")


class AnaliseEventosResposta(BaseModel):
    companhia: AnaliseCompanhiaResumo
    eventos: list[AnaliseEvento]


class AnaliseTemporalObservation(BaseModel):
    metric_id: str = Field(description="Identificador estável da métrica temporal.")
    period_id: str = Field(description="Período canônico da observação.")
    fiscal_year: int = Field(description="Ano fiscal associado.")
    start_date: date | None = Field(default=None, description="Data inicial do período em ISO 8601.")
    end_date: date = Field(description="Data final do período em ISO 8601.")
    value: CanonicalDecimal = Field(description="Valor canônico da observação.")
    unit: AnaliseUnit = Field(description="Unidade do valor.")
    source_dataset: str = Field(description="Dataset documental de origem.")
    document_id: int | None = Field(default=None, description="Identificador natural do documento.")
    version: int | None = Field(default=None, description="Versão do documento de origem.")
    restated: bool = Field(description="Indica se a observação usa versão reapresentada.")
    details: dict[str, object] = Field(default_factory=dict, description="Campos auxiliares específicos do domínio.")


class AnaliseGovernancaResposta(BaseModel):
    companhia: AnaliseCompanhiaResumo
    calculation_version: CalculationVersion
    as_of: date | None = Field(default=None, description="Data de corte informacional aplicada.")
    horizonte_anos: int = Field(description="Horizonte anual aplicado.")
    resolution: AnaliseResolutionMetadata = Field(description="Metadados da estratégia de resolução usada na resposta.")
    observacoes: list[AnaliseTemporalObservation]
    issues: list[AnaliseIssue] = Field(default_factory=list)


class AnalisePessoasResposta(BaseModel):
    companhia: AnaliseCompanhiaResumo
    calculation_version: CalculationVersion
    as_of: date | None = Field(default=None, description="Data de corte informacional aplicada.")
    horizonte_anos: int = Field(description="Horizonte anual aplicado.")
    resolution: AnaliseResolutionMetadata = Field(description="Metadados da estratégia de resolução usada na resposta.")
    observacoes: list[AnaliseTemporalObservation]
    issues: list[AnaliseIssue] = Field(default_factory=list)


class AnaliseBriefReferencias(BaseModel):
    quarter_current: str | None = Field(default=None)
    quarter_previous: str | None = Field(default=None)
    quarter_yoy: str | None = Field(default=None)
    fy_current: str | None = Field(default=None)
    fy_previous: str | None = Field(default=None)


class AnaliseBriefResposta(BaseModel):
    companhia: AnaliseCompanhiaResumo
    calculation_version: CalculationVersion
    as_of: date | None = Field(default=None)
    escopo: AnaliseEscopo
    periodos_referencia: AnaliseBriefReferencias
    metricas: list[AnaliseSeriesObservation] = Field(default_factory=list)
    comparacoes: list[AnaliseComparacaoItem] = Field(default_factory=list)
    sinais: list[AnaliseSignal] = Field(default_factory=list)
    qualidade: AnaliseQualidadeResumo
    eventos: list[AnaliseEvento] = Field(default_factory=list)
    issues: list[AnaliseIssue] = Field(default_factory=list)


class AnaliseRestatementContaAlterada(BaseModel):
    account_code: str = Field(description="Código de conta CVM alterado.")
    statement_type: str | None = Field(default=None, description="Tipo da demonstração da conta.")
    order: str | None = Field(default=None, description="Valor de `ordem_exercicio` associado.")
    start_date: date | None = Field(default=None, description="Data inicial da observação em ISO 8601.")
    end_date: date | None = Field(default=None, description="Data final da observação em ISO 8601.")
    before_value: CanonicalDecimal | None = Field(default=None, description="Valor anterior.")
    after_value: CanonicalDecimal | None = Field(default=None, description="Valor reapresentado.")
    absolute_change: CanonicalDecimal | None = Field(default=None, description="Diferença absoluta entre versão nova e anterior.")
    relative_change: CanonicalDecimal | None = Field(default=None, description="Variação relativa em decimal canônico.")


class AnaliseRestatementItem(BaseModel):
    form: Literal["DFP", "ITR"] = Field(description="Formulário reapresentado.")
    period_id: str = Field(description="Período afetado.")
    previous_version: int = Field(description="Versão imediatamente anterior.")
    current_version: int = Field(description="Versão atual.")
    restated_at: date | None = Field(default=None, description="Data de entrega/recebimento da reapresentação.")
    document_link: str | None = Field(default=None, description="Link oficial do documento reapresentado.")
    changed_accounts: list[AnaliseRestatementContaAlterada] = Field(description="Lista de contas alteradas entre versões consecutivas.")


class AnaliseRestatementsResposta(BaseModel):
    companhia: AnaliseCompanhiaResumo
    calculation_version: CalculationVersion
    restatements: list[AnaliseRestatementItem]
    issues: list[AnaliseIssue] = Field(default_factory=list)
