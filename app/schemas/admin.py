from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.comum import BrazilianDateTime, Paginacao


class RespostaAgendamentoSincronizacao(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"id_tarefa": "a37f0f88-44b9-4cff-9b0d-b826e4e8f367", "status": "agendada"}}
    )

    id_tarefa: str = Field(description="Identificador da task assíncrona (Celery).")
    status: str = Field(description='Estado inicial do disparo da tarefa. Valor esperado: "agendada".')


class AnaliseArquivo(BaseModel):
    file_name: str = Field(description="Nome do arquivo ou membro do zip.")
    file_size: str = Field(description="Tamanho formatado (ex.: KB, MB).")
    rows_count: int = Field(description="Número de linhas de dados no arquivo.")
    columns_count: int = Field(description="Número de colunas no arquivo.")
    header_columns: list[str] = Field(description="Lista com os nomes das colunas.")
    encoding: str | None = Field(default=None, description="Encoding detectado/usado.")
    delimiter: str = Field(description="Delimitador de campos detectado/usado.")


class ExecucaoSincronizacaoResumo(BaseModel):
    id: str = Field(description="ID da execução de sincronização.")
    id_tarefa: str | None = Field(
        default=None, description="ID da task no Celery associada à execução, quando disponível."
    )
    tipo_fonte: str = Field(description='Tipo da fonte processada (ex.: "cadastro", "dfp", "itr").')
    arquivo: str = Field(description="Nome do arquivo (CSV ou ZIP) associado à execução.")
    status: str = Field(
        description=(
            "Status atual ou final da execução. Estados possíveis incluem: "
            '"agendada" (tarefa enfileirada no Celery), '
            '"em_execucao" (processamento ativo), '
            '"aguardando_ingestao" (Phase 1 / Pre-processamento concluído com sucesso; arquivo baixado, unzippado e metadados registrados em banco, aguardando início da Phase 2 / Ingestão), '
            '"sucesso" (ingestão finalizada com sucesso), '
            '"sem_alteracao" (nenhuma modificação no arquivo fonte), '
            '"skipped" (ignorado por hash de arquivo já existente), '
            '"falha" (erro durante qualquer fase de processamento), '
            '"cancelada" (execução abortada manualmente).'
        )
    )
    iniciada_em: BrazilianDateTime = Field(description="Data e hora de início da execução, em `DD/MM/AAAA HH:MM:SS`.")
    finalizada_em: BrazilianDateTime | None = Field(
        description="Data e hora de finalização da execução, em `DD/MM/AAAA HH:MM:SS`."
    )
    total_linhas_lidas: int = Field(description="Total de linhas lidas.")
    total_inseridos: int = Field(description="Total de registros inseridos.")
    total_atualizados: int = Field(description="Total de registros atualizados.")
    total_inalterados: int = Field(description="Total de registros sem alteração de negócio.")
    total_rejeitados: int = Field(description="Total de registros enviados para quarentena.")
    analise_arquivos: list[AnaliseArquivo] | None = Field(
        default=None, description="Análise dos arquivos processados nesta execução."
    )
    id_execucao_pai: str | None = Field(
        default=None, description="ID da execução pai, se esta for uma execução filha."
    )
    tipo_execucao: str | None = Field(
        default=None, description="Tipo da execução: arquivo_zip, arquivo_membro, ou arquivo_simples."
    )
    arquivo_principal: str | None = Field(
        default=None, description="Nome do arquivo ZIP principal para execuções membro."
    )
    filhos_total: int | None = Field(
        default=None, description="Quantidade total de arquivos membros/filhos agendados."
    )
    filhos_concluidos: int | None = Field(
        default=None, description="Quantidade de arquivos membros/filhos concluídos com sucesso."
    )
    filhos_falha: int | None = Field(
        default=None, description="Quantidade de arquivos membros/filhos que falharam."
    )
    filhos_em_andamento: int | None = Field(
        default=None, description="Quantidade de arquivos membros/filhos em andamento."
    )
    state: str | None = Field(
        default=None,
        description="Estado operacional agregado desta execucao para consumo direto por UI/CLI.",
    )
    liveness: IngestionOperationalLiveness | None = Field(
        default=None,
        description="Liveness agregado da run associada a esta execucao, quando existir run correlata.",
    )
    blocking: IngestionOperationalBlocking | None = Field(
        default=None,
        description="Motivo de espera/bloqueio agregado desta execucao, quando houver.",
    )
    cancellation: IngestionOperationalCancellation | None = Field(
        default=None,
        description="Ultimo pedido de cancelamento persistido para esta execucao, quando houver.",
    )
    last_error: IngestionOperationalError | None = Field(
        default=None,
        description="Erro operacional mais recente conhecido para esta execucao, quando houver.",
    )
    next_action: str | None = Field(
        default=None,
        description=(
            "Acao recomendada para esta execucao: `wait`, `recover`, `inspect_error` ou `none`. "
            "`recover` pode aparecer tanto em estado `stale` quanto em falha marcada como recuperavel pelo recovery sweep."
        ),
    )
    links: dict[str, str] | None = Field(
        default=None,
        description="Links relativos para detalhe desta execucao, run associada e rotas operacionais relacionadas.",
    )


class ListaExecucoesSincronizacao(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"dados": [], "paginacao": {"pagina": 1, "tamanho_pagina": 100, "total": 0}}}
    )

    dados: list[ExecucaoSincronizacaoResumo] = Field(description="Lista paginada de execuções.")
    paginacao: Paginacao = Field(description="Metadados de paginação da listagem.")


class ExecucaoSincronizacaoDetalhe(BaseModel):
    id: str = Field(description="ID da execução de sincronização.")
    id_tarefa: str | None = Field(
        default=None, description="ID da task no Celery que iniciou a execução, quando conhecido."
    )
    tipo_fonte: str = Field(description='Tipo da fonte processada (ex.: "cadastro", "dfp", "itr").')
    ano: int | None = Field(description="Ano de referência do processamento, quando aplicável.")
    arquivo: str = Field(description="Arquivo principal associado à execução.")
    url: str = Field(description="URL remota da fonte utilizada no processamento.")
    hash_arquivo: str | None = Field(description="Hash SHA-256 do arquivo processado.")
    status: str = Field(
        description=(
            "Status atual ou final da execução. Estados possíveis incluem: "
            '"agendada" (tarefa enfileirada no Celery), '
            '"em_execucao" (processamento ativo), '
            '"aguardando_ingestao" (Phase 1 / Pre-processamento concluído com sucesso; arquivo baixado, unzippado e metadados registrados em banco, aguardando início da Phase 2 / Ingestão), '
            '"sucesso" (ingestão finalizada com sucesso), '
            '"sem_alteracao" (nenhuma modificação no arquivo fonte), '
            '"skipped" (ignorado por hash de arquivo já existente), '
            '"falha" (erro durante qualquer fase de processamento), '
            '"cancelada" (execução abortada manualmente).'
        )
    )
    iniciada_em: BrazilianDateTime = Field(description="Data e hora de início, em `DD/MM/AAAA HH:MM:SS`.")
    finalizada_em: BrazilianDateTime | None = Field(description="Data e hora de fim, em `DD/MM/AAAA HH:MM:SS`.")
    total_linhas_lidas: int = Field(description="Total de linhas lidas.")
    total_inseridos: int = Field(description="Total de inserções.")
    total_atualizados: int = Field(description="Total de atualizações.")
    total_inalterados: int = Field(description="Total de inalterados.")
    total_rejeitados: int = Field(description="Total rejeitado para quarentena.")
    mensagem_erro: str | None = Field(description="Mensagem de erro in caso de falha.")
    analise_arquivos: list[AnaliseArquivo] | None = Field(
        default=None, description="Análise detalhada dos arquivos processados nesta execução."
    )
    id_execucao_pai: str | None = Field(
        default=None, description="ID da execução pai, se esta for uma execução filha."
    )
    tipo_execucao: str | None = Field(
        default=None, description="Tipo da execução: arquivo_zip, arquivo_membro, ou arquivo_simples."
    )
    arquivo_principal: str | None = Field(
        default=None, description="Nome do arquivo ZIP principal para execuções membro."
    )
    filhos_total: int | None = Field(
        default=None, description="Quantidade total de arquivos membros/filhos agendados."
    )
    filhos_concluidos: int | None = Field(
        default=None, description="Quantidade de arquivos membros/filhos concluídos com sucesso."
    )
    filhos_falha: int | None = Field(
        default=None, description="Quantidade de arquivos membros/filhos que falharam."
    )
    filhos_em_andamento: int | None = Field(
        default=None, description="Quantidade de arquivos membros/filhos em andamento."
    )
    execucoes_filhas: list[ExecucaoSincronizacaoResumo] | None = Field(
        default=None, description="Resumo das execuções filhas, caso aplicável."
    )
    state: str | None = Field(
        default=None,
        description="Estado operacional agregado desta execucao para consumo direto por UI/CLI.",
    )
    liveness: IngestionOperationalLiveness | None = Field(
        default=None,
        description="Liveness agregado da run associada a esta execucao, quando existir run correlata.",
    )
    blocking: IngestionOperationalBlocking | None = Field(
        default=None,
        description="Motivo de espera/bloqueio agregado desta execucao, quando houver.",
    )
    cancellation: IngestionOperationalCancellation | None = Field(
        default=None,
        description="Ultimo pedido de cancelamento persistido para esta execucao, quando houver.",
    )
    last_error: IngestionOperationalError | None = Field(
        default=None,
        description="Erro operacional mais recente conhecido para esta execucao, quando houver.",
    )
    next_action: str | None = Field(
        default=None,
        description="Acao recomendada para esta execucao: `wait`, `recover`, `inspect_error` ou `none`.",
    )
    links: dict[str, str] | None = Field(
        default=None,
        description="Links relativos para detalhe desta execucao, run associada e rotas operacionais relacionadas.",
    )


class TarefaAgendadaResumo(BaseModel):
    tipo_fonte: str = Field(description='Tipo da fonte agendada (ex.: "cadastro", "dfp", "itr", "fre").')
    ano: int | None = Field(description="Ano da sincronizacao quando aplicavel.")
    id_tarefa: str = Field(description="Identificador da task agendada no Celery.")


class RespostaAgendamentoEmLote(BaseModel):
    status: str = Field(description='Status do disparo em lote. Valor esperado: "agendada".')
    tarefas: list[TarefaAgendadaResumo] = Field(description="Lista das tarefas enfileiradas.")


class SolicitacaoCancelamentoSincronizacao(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id_execucao": "6a31c7f8-1c89-4f3d-87db-7e6a8e196999",
                    "terminar_imediatamente": True,
                    "motivo": "Execução duplicada do mesmo ano.",
                },
                {
                    "id_tarefa": "a37f0f88-44b9-4cff-9b0d-b826e4e8f367",
                    "terminar_imediatamente": True,
                    "motivo": "Parada operacional solicitada por administrador.",
                },
            ]
        }
    )

    id_execucao: UUID | None = Field(
        default=None,
        description=(
            "ID da execução registrada em `execucoes_sincronizacao`. "
            "Use este seletor quando a sincronização já aparece em `/ingestion/sincronizacoes`."
        ),
    )
    id_tarefa: str | None = Field(
        default=None,
        description=(
            "ID da task Celery retornado no disparo (`id_tarefa`). "
            "Use este seletor quando a execução ainda não apareceu na listagem, "
            "ou quando desejar revogar a task diretamente."
        ),
    )
    terminar_imediatamente: bool = Field(
        default=True,
        description=(
            "Quando `true`, envia revogação com `terminate=True` e sinal `SIGTERM` ao worker Celery. "
            "Este é modo recomendado para interromper sincronizações já em execução. "
            "Quando `false`, a API apenas revoga a task no broker; tarefas já iniciadas podem continuar até conclusão."
        ),
    )
    motivo: str | None = Field(
        default=None,
        description=(
            "Motivo livre para auditoria operacional. "
            "Quando informado, é incorporado à mensagem persistida na execução cancelada."
        ),
        max_length=1000,
    )


class RespostaCancelamentoSincronizacao(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id_execucao": "6a31c7f8-1c89-4f3d-87db-7e6a8e196999",
                "id_tarefa": "a37f0f88-44b9-4cff-9b0d-b826e4e8f367",
                "execucao_encontrada": True,
                "status_execucao": "cancelada",
                "revogacao_solicitada": True,
                "terminar_imediatamente": True,
                "mensagem": "Sincronização cancelada com sucesso.",
            }
        }
    )

    id_execucao: str | None = Field(
        description="ID da execução cancelada, quando a task já havia materializado registro no banco."
    )
    id_tarefa: str | None = Field(
        default=None,
        description=(
            "ID da task revogada no Celery. "
            "Pode ser `null` quando o cancelamento ocorreu apenas sobre um "
            "registro legado em banco sem vínculo de task."
        ),
    )
    execucao_encontrada: bool = Field(
        description="Indica se existia registro em `execucoes_sincronizacao` associado ao seletor informado."
    )
    status_execucao: str | None = Field(
        default=None,
        description=(
            "Status final persistido na execução quando ela foi encontrada. "
            "Valor esperado após cancelamento bem-sucedido: `cancelada`."
        ),
    )
    revogacao_solicitada: bool = Field(description="Indica se a API enviou comando de revogação ao Celery.")
    terminar_imediatamente: bool = Field(description="Espelha opção recebida na solicitação.")
    mensagem: str = Field(description="Resumo textual do efeito aplicado pela API.")


class RegistroQuarentenaResposta(BaseModel):
    id: str = Field(description="Identificador do registro em quarentena.")
    execucao_sincronizacao_id: str = Field(description="ID da execucao de sincronizacao associada.")
    arquivo_origem: str = Field(description="Arquivo de origem da linha rejeitada.")
    ano_origem: int | None = Field(description="Ano de origem do arquivo processado.")
    linha_origem: int | None = Field(description="Numero da linha de origem no CSV.")
    motivo: str = Field(description="Motivo da rejeicao.")
    dados_originais: dict[str, Any] = Field(description="Payload bruto da linha rejeitada.")
    criado_em: BrazilianDateTime = Field(
        description="Data e hora de criacao do registro de quarentena, em `DD/MM/AAAA HH:MM:SS`."
    )


class ListaRegistrosQuarentena(BaseModel):
    dados: list[RegistroQuarentenaResposta] = Field(description="Lista paginada de registros em quarentena.")
    paginacao: Paginacao = Field(description="Metadados de paginacao da listagem.")


class HistoricoAlteracaoCampoResposta(BaseModel):
    id: str = Field(description="Identificador do evento de alteracao.")
    entidade: str = Field(description="Nome da entidade de negocio alterada.")
    entidade_id: str = Field(description="ID da entidade alterada.")
    companhia_id: str | None = Field(description="ID da companhia relacionada quando houver.")
    campo: str = Field(description="Campo alterado.")
    valor_anterior: str | None = Field(description="Valor anterior normalizado.")
    valor_novo: str | None = Field(description="Valor novo normalizado.")
    alterado_em: BrazilianDateTime = Field(
        description="Data e hora da alteracao registrada, em `DD/MM/AAAA HH:MM:SS`."
    )
    execucao_sincronizacao_id: str = Field(description="Execucao que originou a alteracao.")
    arquivo_origem: str = Field(description="Arquivo de origem da alteracao.")
    ano_origem: int | None = Field(description="Ano de origem do arquivo.")


class ListaHistoricoAlteracoes(BaseModel):
    dados: list[HistoricoAlteracaoCampoResposta] = Field(description="Lista paginada de alteracoes por campo.")
    paginacao: Paginacao = Field(description="Metadados de paginacao da listagem.")


class DashboardExecucoesResposta(BaseModel):
    total_execucoes: int = Field(description="Total de execucoes registradas.")
    total_sucesso: int = Field(description="Quantidade de execucoes com status sucesso.")
    total_sem_alteracao: int = Field(description="Quantidade de execucoes sem alteracao.")
    total_falha: int = Field(description="Quantidade de execucoes com falha.")
    total_rejeitados: int = Field(description="Total acumulado de linhas rejeitadas em quarentena.")
    ultimas_execucoes: list[ExecucaoSincronizacaoResumo] = Field(
        description="Ultimas execucoes registradas (ordenadas por inicio desc)."
    )


class IngestionOperationalLiveness(BaseModel):
    heartbeat_at: BrazilianDateTime | None = Field(
        default=None,
        description="Ultimo heartbeat persistido para a fase atual, quando a execucao publica esse sinal.",
    )
    lease_owner: str | None = Field(default=None, description="Identificador do owner atual do lease operacional.")
    task_id: str | None = Field(default=None, description="ID da task Celery associada ao lease/fase atual.")
    phase_status: str | None = Field(
        default=None,
        description="Status da fase atual no ledger operacional: `pending`, `running`, `succeeded`, `failed_final`, `cancelled` ou `stale`.",
    )
    is_stale: bool = Field(description="Indica se o heartbeat ficou velho demais para uma execucao que deveria estar rodando.")
    stale_after_seconds: int = Field(description="Threshold usado para classificar stale.")
    heartbeat_age_seconds: int | None = Field(
        default=None,
        description="Idade do heartbeat atual em segundos, quando houver heartbeat persistido.",
    )


class IngestionOperationalBlocking(BaseModel):
    reason_code: str = Field(
        description="Motivo compacto de espera ou bloqueio: `none`, `queued`, `awaiting_ingestion`, `stale` ou `manual_cancel`."
    )
    detail: str | None = Field(default=None, description="Explicacao curta para UI operacional.")


class IngestionOperationalCancellation(BaseModel):
    status: str = Field(
        description="Status do pedido de cancelamento mais recente para este escopo: `none`, `requested`, `propagated` ou `completed`."
    )
    requested_by: str | None = Field(default=None, description="Identificador do originador do cancelamento, quando conhecido.")
    reason: str | None = Field(default=None, description="Motivo livre informado no cancelamento.")
    terminate_immediately: bool | None = Field(
        default=None,
        description="Se `true`, o pedido pediu revogacao imediata com encerramento do worker.",
    )
    requested_at: BrazilianDateTime | None = Field(default=None, description="Timestamp de criacao do pedido de cancelamento.")
    propagated_at: BrazilianDateTime | None = Field(
        default=None,
        description="Timestamp em que a API marcou a revogacao como propagada para tasks conhecidas.",
    )
    completed_at: BrazilianDateTime | None = Field(
        default=None,
        description="Timestamp em que o pedido foi encerrado do ponto de vista administrativo.",
    )
    affected_task_ids: list[str] | None = Field(default=None, description="Tasks afetadas pelo pedido mais recente.")


class IngestionOperationalError(BaseModel):
    error_type: str | None = Field(default=None, description="Classificacao curta do erro mais recente.")
    error_message: str | None = Field(default=None, description="Mensagem do erro mais recente.")
    retryable: bool | None = Field(default=None, description="Indica se o erro mais recente foi classificado como recuperavel.")
    phase: str | None = Field(default=None, description="Fase em que o erro mais recente foi registrado.")


class IngestionRunPhaseExecutionResumo(BaseModel):
    id: str = Field(description="ID do registro de fase.")
    phase: str = Field(description="Nome da fase operacional.")
    status: str = Field(description="Status da fase no ledger operacional.")
    attempt: int = Field(description="Numero da tentativa desta fase para a mesma run.")
    task_id: str | None = Field(default=None, description="Task Celery associada a esta fase, quando conhecida.")
    lease_owner: str | None = Field(default=None, description="Owner do lease desta fase, quando conhecido.")
    started_at: BrazilianDateTime | None = Field(default=None, description="Inicio da fase.")
    heartbeat_at: BrazilianDateTime | None = Field(default=None, description="Ultimo heartbeat da fase.")
    finished_at: BrazilianDateTime | None = Field(default=None, description="Fim da fase.")
    cancel_requested_at: BrazilianDateTime | None = Field(default=None, description="Quando o cancelamento foi solicitado para a fase.")
    cancelled_at: BrazilianDateTime | None = Field(default=None, description="Quando a fase foi marcada como cancelada.")
    cancel_reason: str | None = Field(default=None, description="Motivo de cancelamento associado a esta fase.")
    error_type: str | None = Field(default=None, description="Tipo do erro associado a esta fase.")
    error_message: str | None = Field(default=None, description="Mensagem do erro associado a esta fase.")
    error_retryable: bool | None = Field(default=None, description="Se o erro de fase foi classificado como retryable.")
    input_artifact_uri: str | None = Field(
        default=None,
        description="URI local do artifact de entrada usado pela fase, quando registrado no manifesto operacional.",
    )
    output_artifact_uri: str | None = Field(
        default=None,
        description="URI local do artifact de saida produzido pela fase, quando registrado no manifesto operacional.",
    )
    metrics: dict[str, Any] | None = Field(default=None, description="Snapshot resumido de metricas persistidas para a fase.")


class ListaIngestionRunPhaseExecutions(BaseModel):
    dados: list[IngestionRunPhaseExecutionResumo] = Field(description="Timeline de fases persistidas para a run.")


class IngestionRunMemberResumo(BaseModel):
    id: str = Field(description="ID do member em `ingestion_file_members`.")
    ingestion_file_id: str = Field(description="ID do arquivo/pacote associado ao member.")
    member_name: str = Field(description="Nome canonico do member CSV dentro do artefato processado.")
    member_sha256: str = Field(description="Hash SHA-256 persistido para o payload bruto do member.")
    member_size_bytes: int = Field(description="Tamanho bruto do member em bytes.")
    row_count: int = Field(description="Quantidade de linhas de dados observada no member.")
    encoding: str | None = Field(default=None, description="Encoding detectado/usado para o member.")
    delimiter: str = Field(description="Delimitador CSV persistido para o member.")
    header: list[str] | None = Field(default=None, description="Cabecalho observado no member, quando registrado.")
    schema_status: str = Field(description="Status de schema persistido para o member.")
    schema_message: str | None = Field(default=None, description="Mensagem complementar de schema, quando houver.")
    row_kind: str | None = Field(default=None, description="Tipo interno de linha associado ao member, quando conhecido.")
    destino_promovido: str | None = Field(
        default=None,
        description="Tabela ou entidade promovida a partir deste member, quando conhecida pelo snapshot.",
    )
    required_member: bool | None = Field(
        default=None,
        description="Indica se o member e obrigatorio dentro do pacote da fonte, quando conhecido pelo snapshot.",
    )
    lifecycle_status: str | None = Field(
        default=None,
        description="Status de lifecycle do member na run, por exemplo `processed` ou `member_skipped`.",
    )
    quarantine_total: int = Field(description="Quantidade de itens de quarentena ancorados neste member.")
    delivery_total: int = Field(description="Quantidade de deliveries documentais capturadas para este member.")
    state: str = Field(
        description="Estado operacional sintetico do member: `processed`, `member_skipped`, `schema_invalid` ou `unknown`."
    )
    links: dict[str, str] | None = Field(
        default=None,
        description="Links relativos para operacoes correlatas deste member dentro da run.",
    )


class ListaIngestionRunMembers(BaseModel):
    dados: list[IngestionRunMemberResumo] = Field(description="Inventario paginado de members associados a uma run.")
    paginacao: Paginacao = Field(description="Metadados de paginacao da listagem.")


class IngestionOperationRunPreview(BaseModel):
    id: str = Field(description="ID da run.")
    execucao_sincronizacao_id: str | None = Field(default=None, description="Execucao correlata, quando houver.")
    tipo_fonte: str = Field(description="Fonte da run.")
    ano: int | None = Field(default=None, description="Ano da run, quando aplicavel.")
    status: str = Field(description="Status persistido da run.")
    phase: str = Field(description="Fase persistida da run.")
    state: str = Field(description="Estado operacional agregado desta run.")
    next_action: str | None = Field(default=None, description="Acao recomendada para consumidor desacoplado.")
    liveness: IngestionOperationalLiveness | None = Field(default=None, description="Snapshot resumido de liveness.")
    blocking: IngestionOperationalBlocking | None = Field(default=None, description="Motivo agregado de espera/bloqueio.")


class IngestionOperationsResumo(BaseModel):
    generated_at: BrazilianDateTime = Field(description="Timestamp do snapshot operacional agregado.")
    run_counts: dict[str, int] = Field(description="Contagens agregadas de runs por estado operacional.")
    execution_counts: dict[str, int] = Field(description="Contagens agregadas de execucoes por status persistido.")
    cancellation_counts: dict[str, int] = Field(description="Contagens agregadas de pedidos de cancelamento por status.")
    task_counts: dict[str, int] = Field(
        description="Snapshot resumido das tasks Celery observadas no cluster para filas relacionadas a ingestao."
    )
    materialization_gate: dict[str, Any] | None = Field(
        default=None,
        description="Estado consolidado atual do gate de materializacao visto do ponto de vista da ingestao.",
    )
    active_runs: list[IngestionOperationRunPreview] = Field(
        description="Preview das runs atualmente ativas ou aguardando continuidade operacional."
    )
    recoverable_runs: list[IngestionOperationRunPreview] = Field(
        description="Preview das runs que hoje pedem `recover` ou outra acao administrativa equivalente."
    )


class IngestionRunResumo(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "6a31c7f8-1c89-4f3d-87db-7e6a8e196999",
                "execucao_sincronizacao_id": "02be26d3-8db8-48a1-bcd0-4737b8157116",
                "tipo_fonte": "dfp",
                "ano": 2025,
                "status": "sucesso_com_alerta",
                "phase": "promote",
                "remote_probe": {
                    "dataset_url": "https://dados.cvm.gov.br/dataset/cia_aberta-doc-dfp",
                    "resource_url": "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/dfp_cia_aberta_2025.zip",
                    "probe_sources": ["ckan", "head"],
                    "resource_etag": "\"abc123\"",
                    "resource_last_modified": "Mon, 09 Jun 2026 08:03:41 GMT",
                    "resource_content_length": "10485760",
                    "package_metadata_modified": "09/06/2026 02:10:00",
                    "decision": "changed",
                    "decision_reason": "metadata_changed:resource_last_modified",
                },
                "change_summary": {
                    "member_added": [],
                    "member_removed": ["dfp_cia_aberta_DVA_ind_2025.csv"],
                    "required_member_missing": [],
                    "optional_member_missing": [],
                    "row_count_changed": [
                        {"member_name": "dfp_cia_aberta_DRE_ind_2025.csv", "before": 12034, "after": 12080}
                    ],
                    "delivery_index_changed": [
                        {
                            "member_name": "dfp_cia_aberta_2025.csv",
                            "before_count": 1200,
                            "after_count": 1204,
                            "added": 4,
                            "removed": 0,
                        }
                    ],
                    "header_changed": [
                        {
                            "member_name": "dfp_cia_aberta_DRE_ind_2025.csv",
                            "before": ["CNPJ_CIA", "DT_REFER", "VERSAO"],
                            "after": ["CNPJ_CIA", "DT_REFER", "VERSAO", "COLUNA_DF"],
                        }
                    ],
                    "schema_changed": [],
                },
                "quality_summary": {
                    "row_status_counts": {"valid": 1200, "invalid": 3},
                    "reason_counts": {"companhia_nao_encontrada": 2, "schema_inesperado": 1},
                    "resolver_methods": {"codigo_cvm_identificador_alta": 1180, "repair_rule": 20},
                    "quarantine_total": 3,
                    "members_total": 14,
                    "members_processados": 13,
                    "members_skipped": 1,
                    "members_reprocessed": 13,
                    "members_reused_from_previous": 1,
                    "members_reused_from_failed_parent": 1,
                    "staged_rows_purged": 1197,
                    "typed_stage_rows_loaded": 1198,
                    "typed_stage_bytes_loaded": 845231,
                    "typed_stage_rows_replaced": 0,
                    "typed_stage_rows_purged": 1198,
                    "typed_stage_copy_loads": 14,
                    "reconciled_deleted": 4,
                },
                "artifact_snapshot": {
                    "resource_url": "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/dfp_cia_aberta_2025.zip",
                    "source_filename": "dfp_cia_aberta_2025.zip",
                    "content_sha256": "abc123",
                    "probe_decision": "changed",
                    "probe_confidence": "medium",
                    "sha_confirmation_result": "different",
                    "status": "sucesso_com_alerta",
                },
                "member_snapshot_summary": {
                    "total": 14,
                    "by_status": {"processed": 13, "member_skipped": 1},
                    "by_schema_status": {"ok": 13, "reused": 1},
                },
                "delivery_snapshot_summary": {
                    "total": 1204,
                    "by_status": {"captured": 1204},
                    "by_member": {"dfp_cia_aberta_2025.csv": 1204},
                },
                "reconcile_summary": {
                    "rows_reconciled_deleted": 4,
                    "scope": "member_replace",
                    "target_tables": ["demonstracoes_financeiras"],
                },
                "rows_reconciled_deleted": 4,
                "lifecycle_decision": {
                    "remote_probe": "download_required",
                    "artifact_sha": "changed",
                    "members_skipped_by_sha": 1,
                    "members_processed": 13,
                    "members_reused_from_previous": 1,
                    "members_reused_from_failed_parent": 1,
                },
            }
        }
    )

    id: str = Field(description="ID da execucao em `ingestion_runs`.")
    execucao_sincronizacao_id: str | None = Field(
        default=None,
        description=(
            "ID da execucao correlata em `execucoes_sincronizacao`, quando houver."
        ),
    )
    tipo_fonte: str = Field(description='Tipo da fonte processada na run (ex.: "cadastro", "dfp", "itr", "fre").')
    ano: int | None = Field(description="Ano de referencia da run, quando aplicavel.")
    status: str = Field(
        description=(
            "Status consolidado da run. "
            "`em_execucao` indica run ativa; "
            "`sucesso` indica processamento completo sem alerta de qualidade; "
            "`sucesso_com_alerta` indica ingestao concluida com drift estrutural ou outro alerta operacional; "
            "`falha` indica erro impeditivo; "
            "`sem_alteracao` indica que o recurso CVM foi considerado igual a referencia anterior, seja por probe remoto forte sem download, seja por download seguido de confirmacao de SHA igual; "
            "`skipped` indica reaproveitamento administrativo legado e permanece aceito por compatibilidade historica, mas a arquitetura atual prefere `sem_alteracao` para igualdade confirmada do artefato; "
            "`cancelada` indica interrupcao administrativa."
        )
    )
    phase: str = Field(
        description=(
            "Fase atual ou final da run. "
            "`acquire` cobre o preflight remoto (CKAN/HEAD) e, quando necessario, o download do arquivo; "
            "`stage` cobre extracao de membros, captura de header, contagem de linhas, hash de membros e verificacoes de schema/presenca; "
            "`promote` cobre normalizacao, resolucao de companhia, deduplicacao e escrita nas tabelas de dominio; "
            "`reconcile` representa a remocao de linhas promovidas que ficaram obsoletas apos um member alterado ser reprocessado; "
            "`complete` indica encerramento da run."
        )
    )
    remote_probe: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Metadados do preflight remoto executado no inicio de `acquire`. "
            "Este objeto descreve quais fontes de metadado foram consultadas (`probe_sources`, por exemplo `ckan` e `head`), "
            "quais valores remotos foram observados (`resource_etag`, `resource_last_modified`, `resource_content_length`, `package_metadata_modified`) "
            "e qual foi a decisao operacional (`decision` e `decision_reason`). "
            "Quando `decision=unchanged`, a run pode terminar sem download. Quando `decision=unknown`, o pipeline prossegue para download e usa o SHA do payload como veredito final."
        ),
    )
    change_summary: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Resumo estruturado de mudancas no formato do pacote ou na forma dos members observados em `stage`. "
            "Inclui diferencas de inventario (`member_added`, `member_removed`), ausencias operacionais (`required_member_missing`, `optional_member_missing`) "
            "e mudancas de estrutura (`header_changed`, `schema_changed`). "
            "Ele nao lista mudancas de negocio linha a linha; essas mudancas aparecem indiretamente em `quality_summary` e nas tabelas promovidas."
        ),
    )
    quality_summary: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Resumo agregado e orientado a progresso. "
            "Na arquitetura simplificada, a API nao garante retencao de linhas staged bem-sucedidas apos a conclusao; "
            "o frontend deve tratar `quality_summary` como fonte principal para progresso, contagens por status, "
            "motivos de rejeicao, metodos de resolucao, retries, membros processados/skipped, total real de quarentena, "
            "quantidade de staging purgado com sucesso (`staged_rows_purged`), sinais do staging tipado financeiro "
            "(`typed_stage_rows_loaded`, `typed_stage_bytes_loaded`, `typed_stage_rows_replaced`, `typed_stage_rows_purged`, `typed_stage_copy_loads`) "
            "e remocoes aplicadas no reconcile (`reconciled_deleted`). "
            "Quando a run representa um rerun de recuperacao, `members_reused_from_previous` informa quantos members foram reaproveitados sem nova promocao, "
            "e `members_reused_from_failed_parent` destaca o subconjunto desses members cuja ultima execucao anual pai havia terminado em `falha`. "
            "O contrato esperado para consumo de frontend inclui, quando disponivel: "
            "`members_total` (quantidade total de members avaliados no ZIP atual), "
            "`members_processados` (members que entraram no fluxo normal da run atual), "
            "`members_skipped` (members pulados no fechamento desta run, normalmente por igualdade), "
            "`members_reprocessed` (members que realmente voltaram para `stage -> promote -> reconcile`), "
            "`members_reused_from_previous` (members reaproveitados por SHA a partir de resultado anterior) e "
            "`members_reused_from_failed_parent` (subset reaproveitado cuja execucao anual pai anterior falhou). "
            "Para diagnostico de custo do staging tipado financeiro, consumidores podem ler "
            "`typed_stage_rows_loaded` (linhas carregadas no staging tipado), "
            "`typed_stage_bytes_loaded` (bytes lidos dos artifacts normalizados), "
            "`typed_stage_rows_replaced` (linhas antigas removidas antes de recarga do mesmo member), "
            "`typed_stage_rows_purged` (linhas removidas apos promote/reconcile) e "
            "`typed_stage_copy_loads` (quantas cargas usaram o caminho PostgreSQL `COPY`). "
            "Para cards e resumos operacionais, o frontend deve considerar `members_reprocessed` como trabalho efetivamente executado e "
            "`members_reused_from_previous` como trabalho economizado pelo mecanismo de recuperacao. "
            "Este objeto e um resumo operacional por contadores; ele nao substitui um ledger duravel de sucesso por linha."
        ),
    )
    artifact_snapshot: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Snapshot duravel do artefato remoto considerado pela run. "
            "Resume o recurso CVM avaliado nesta execucao: URL, nome do arquivo, SHA final quando houve download, "
            "metadados remotos observados, confianca do probe e status operacional persistido. "
            "Use este campo quando o frontend precisar explicar por que houve skip, download, reuso ou reconcile."
        ),
    )
    member_snapshot_summary: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Resumo duravel do inventario de members avaliados na run. "
            "Explicita quantos members foram processados, reaproveitados por `member_sha256`, marcados com schema invalido ou tratados como obrigatorios/opcionais. "
            "O frontend deve esperar pelo menos `total`, `by_status`, `by_schema_status` e `members`. "
            "Em `by_status`, valores como `processed` e `member_skipped` permitem separar members realmente executados de members apenas reaproveitados. "
            "Em `by_schema_status`, `reused` identifica skip por `member_sha256`; `ok` identifica members que passaram pelo fluxo normal; "
            "outros valores podem sinalizar schema invalido ou warning estrutural. "
            "Ao contrario de `ingestion_rows`, este objeto foi desenhado para permanecer disponivel apos limpeza do staging bem-sucedido."
        ),
    )
    delivery_snapshot_summary: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Resumo duravel dos identificadores de entrega/documento extraidos dos members com papel de indice documental. "
            "Serve para diagnosticar novas versoes (`VERSAO`), re-submissoes, variacoes de protocolo, quantidade de documentos capturados por member e drift documental entre artefatos anuais repostos pela CVM."
        ),
    )
    reconcile_summary: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Resumo operacional do `reconcile` executado apos promocao de members alterados. "
            "Indica escopo, tabelas-alvo e quantidade de linhas promovidas obsoletas removidas do banco local quando deixaram de existir no member CVM corrente."
        ),
    )
    rows_reconciled_deleted: int | None = Field(
        default=None,
        description=(
            "Atalho numérico para o total de linhas removidas no `reconcile` desta run. "
            "Corresponde ao mesmo fenômeno descrito em `reconcile_summary`, mas facilita cards, badges e ordenação no frontend."
        ),
    )
    lifecycle_decision: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Resumo de decisao do lifecycle engine. "
            "Explica em formato compacto se o probe remoto levou a download, se o SHA final confirmou alteracao ou igualdade, "
            "quantos members foram pulados por igualdade e quantos precisaram de `stage -> promote -> reconcile`. "
            "Em reruns de recuperacao, este bloco tambem resume quantos members foram reaproveitados a partir de resultados anteriores e quantos desses reaproveitamentos vieram de uma execucao anual pai que falhou. "
            "Chaves relevantes para frontend: `remote_probe`, `artifact_sha`, `members_skipped_by_sha`, `members_processed`, `members_reused_from_previous` e `members_reused_from_failed_parent`. "
            "Este bloco serve como explicacao compacta da decisao de lifecycle; para inventario detalhado por member, o frontend deve cruzar com `member_snapshot_summary`."
        ),
    )
    state: str | None = Field(
        default=None,
        description="Estado operacional agregado e pronto para consumo por API/CLI/UI: `queued`, `waiting`, `running`, `stale`, `succeeded`, `skipped`, `failed` ou `cancelled`.",
    )
    progress: dict[str, Any] | None = Field(
        default=None,
        description="Contadores agregados de progresso para a run atual, derivados de `quality_summary` e dos snapshots operacionais.",
    )
    liveness: IngestionOperationalLiveness | None = Field(
        default=None,
        description="Snapshot de liveness da fase atual, incluindo heartbeat, lease e classificacao `stale`.",
    )
    blocking: IngestionOperationalBlocking | None = Field(
        default=None,
        description="Motivo agregado pelo qual a run esta parada, aguardando ou marcada como stale.",
    )
    cancellation: IngestionOperationalCancellation | None = Field(
        default=None,
        description="Ultimo pedido de cancelamento persistido para a run, quando houver.",
    )
    last_error: IngestionOperationalError | None = Field(
        default=None,
        description="Erro operacional mais recente conhecido para a run, quando houver.",
    )
    next_action: str | None = Field(
        default=None,
        description=(
            "Proxima acao recomendada para consumidor desacoplado: `wait`, `recover`, `inspect_error`, `inspect_quarantine` ou `none`. "
            "`recover` pode aparecer tanto em estado `stale` quanto em falha marcada como recuperavel pelo recovery sweep."
        ),
    )
    links: dict[str, str] | None = Field(
        default=None,
        description="Links relativos para drill-down desta run, incluindo detalhe, fases, replay e quarentena correlata.",
    )


class ListaIngestionRuns(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"dados": [], "paginacao": {"pagina": 1, "tamanho_pagina": 100, "total": 0}}}
    )

    dados: list[IngestionRunResumo] = Field(description="Lista paginada de runs.")
    paginacao: Paginacao = Field(description="Metadados de paginacao da listagem.")


class QuarantineItemResposta(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "0ebc5c67-25a4-4e0c-ab25-66eaf4af4ced",
                "ingestion_run_id": "6a31c7f8-1c89-4f3d-87db-7e6a8e196999",
                "ingestion_row_id": "9b3a4f45-b7ab-4de6-a93d-95f85913df71",
                "arquivo_origem": "itr_cia_aberta_2021.csv",
                "ano_origem": 2021,
                "linha_origem": 1692,
                "row_kind": "itr_documento",
                "status": "pendente",
                "motivo_codigo": "companhia_nao_encontrada",
                "severidade": "error",
                "reparavel": True,
                "tentativas_reprocessamento": 1,
                "diagnostico": {
                    "codigo_cvm": 3,
                    "denominacao_companhia": "EMPRESA FINANCEIRA",
                    "resolution_method": "none",
                },
            }
        }
    )

    id: str = Field(description="ID do item da fila de reparo.")
    ingestion_run_id: str | None = Field(default=None, description="ID da run que gerou o item.")
    ingestion_row_id: str = Field(
        description=(
            "ID da linha staged relacionada ao erro. "
            "Itens de quarentena continuam ancorados em linhas staged de excecao; "
            "linhas bem-sucedidas podem ser removidas do staging ao final do processamento."
        )
    )
    arquivo_origem: str = Field(description="Arquivo de origem da linha rejeitada.")
    ano_origem: int | None = Field(description="Ano do arquivo de origem, quando aplicavel.")
    linha_origem: int | None = Field(description="Numero da linha no arquivo de origem, quando disponivel.")
    row_kind: str = Field(description="Tipo interno da linha staged, por exemplo `dfp_documento` ou `fre_documento`.")
    status: str = Field(
        description="Estado atual da fila de reparo: `pendente`, `resolvido_auto`, `resolvido_manual` ou `ignorado`."
    )
    motivo_codigo: str = Field(description="Codigo estavel do motivo da quarentena, adequado para filtros de frontend.")
    severidade: str = Field(description="Severidade operacional do item, por exemplo `error` ou `warning`.")
    reparavel: bool = Field(description="Indica se o item e elegivel para replay automatico ou assistido.")
    tentativas_reprocessamento: int = Field(description="Numero acumulado de tentativas de replay.")
    diagnostico: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Diagnostico estruturado para UI e suporte operacional. "
            "Falhas de schema em nivel de membro deixam de gerar um item por linha; "
            "este payload deve ser interpretado como diagnostico de excecoes reais."
        ),
    )


class ListaQuarantineItems(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"dados": [], "paginacao": {"pagina": 1, "tamanho_pagina": 100, "total": 0}}}
    )

    dados: list[QuarantineItemResposta] = Field(description="Lista paginada de itens da quarentena.")
    paginacao: Paginacao = Field(description="Metadados de paginacao da listagem.")


class ErroQuantidade(BaseModel):
    motivo_codigo: str = Field(description="Código estável do motivo de rejeição / tipo de erro (ex: companhia_nao_encontrada).")
    quantidade: int = Field(description="Quantidade total de ocorrências deste erro na quarentena.")


class ArquivoQuantidade(BaseModel):
    arquivo_origem: str = Field(description="Nome físico do arquivo de origem que causou a falha (ex: itr_cia_aberta_2021.csv).")
    quantidade: int = Field(description="Quantidade total de erros registrados originários deste arquivo.")


class ArquivoErroQuantidade(BaseModel):
    arquivo_origem: str = Field(description="Nome do arquivo de origem.")
    motivo_codigo: str = Field(description="Código estável do motivo de rejeição / tipo de erro.")
    quantidade: int = Field(description="Quantidade de ocorrências deste erro específico dentro deste arquivo.")


class QuarentenaResumoResposta(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total": 3,
                "total_pendentes": 2,
                "total_resolvidos": 1,
                "total_historico": 3,
                "por_status": {
                    "pendente": 2,
                    "resolvido_auto": 1
                },
                "por_erro": [
                    {"motivo_codigo": "companhia_nao_encontrada", "quantidade": 2},
                    {"motivo_codigo": "schema_inesperado", "quantidade": 1}
                ],
                "por_arquivo": [
                    {"arquivo_origem": "itr_cia_aberta_2021.csv", "quantidade": 2},
                    {"arquivo_origem": "dfp_cia_aberta_2022.csv", "quantidade": 1}
                ],
                "por_arquivo_e_erro": [
                    {"arquivo_origem": "itr_cia_aberta_2021.csv", "motivo_codigo": "companhia_nao_encontrada", "quantidade": 2},
                    {"arquivo_origem": "dfp_cia_aberta_2022.csv", "motivo_codigo": "schema_inesperado", "quantidade": 1}
                ]
            }
        }
    )

    total: int = Field(description="Contagem global absoluta de registros atualmente na quarentena sob os filtros informados.")
    por_status: dict[str, int] = Field(description="Distribuição quantitativa de registros mapeados por status operacional (ex: pendente, resolvido_auto, resolvido_manual, ignorado).")
    por_erro: list[ErroQuantidade] = Field(description="Ranking de erros ordenado decrescentemente pela quantidade de registros afetados por cada tipo de falha.")
    por_arquivo: list[ArquivoQuantidade] = Field(description="Ranking de arquivos fonte ordenado decrescentemente pela quantidade de erros neles contidos.")
    por_arquivo_e_erro: list[ArquivoErroQuantidade] = Field(description="Detalhamento cruzado da quantidade de erros agrupados simultaneamente por arquivo e tipo de erro.")
    total_pendentes: int = Field(default=0, description="Total de itens pendentes.")
    total_resolvidos: int = Field(default=0, description="Total de itens resolvidos (auto ou manual).")
    total_historico: int = Field(default=0, description="Total histórico de itens que passaram pela quarentena.")



class ReplayQuarantineRequisicao(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"reason_code": "companhia_nao_encontrada"},
                {"reason_code": "chave_natural_duplicada_no_arquivo", "arquivo_origem": "cad_cia_aberta.csv"},
                {"arquivo_origem": "itr_cia_aberta_2021.csv", "ano": 2021},
            ]
        }
    )

    reason_code: str | None = Field(
        default=None,
        description=(
            "Filtra replay por motivo estavel de quarentena. "
            "Quando omitido, considera todos os itens pendentes. "
            "O replay de quarentena atua apenas sobre excecoes reais, nao sobre todas as linhas bem-sucedidas."
        ),
    )
    arquivo_origem: str | None = Field(
        default=None,
        description="Restringe o replay a um arquivo de origem especifico, por exemplo `itr_cia_aberta_2021.csv`.",
    )
    ano: int | None = Field(
        default=None,
        description=(
            "Restringe o replay a um ano de origem especifico. Normalmente "
            "usado junto com `arquivo_origem` ou `reason_code`."
        ),
    )


class ReplayResposta(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "sucesso",
                "detalhe": {
                    "status": "sucesso",
                    "total": 2,
                    "items": [
                        {"status": "promovido", "row_id": "9b3a4f45-b7ab-4de6-a93d-95f85913df71"},
                        {"status": "inalterado", "row_id": "46f3fc80-4a66-46cb-a0ef-382526dc6289"},
                    ],
                },
            }
        }
    )

    status: str = Field(
        description='Status da chamada administrativa. Valor esperado quando a requisicao e aceita: `"sucesso"`.'
    )
    detalhe: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Payload operacional devolvido pelo servico de replay ou rebuild. "
            "Para runs ou membros completos, o replay pode reconstruir o processamento a partir do payload bruto retido do membro; "
            "para quarentena, o retorno resume apenas os itens excepcionais reprocessados. "
            "O replay nao depende da permanencia de linhas staged bem-sucedidas; a fonte de verdade para rebuild e o payload bruto retido do member/arquivo, "
            "com nova execucao das fases `stage`, `promote` e `reconcile`."
        ),
    )


class FonteDatasetResumoResposta(BaseModel):
    dataset: str = Field(description="Chave canônica do dataset dentro da fonte.")
    descricao: str = Field(description="Descrição resumida do dataset.")
    member_name_template: str = Field(description="Template do nome do member CSV.")
    row_kind: str | None = Field(description="Tipo interno de linha staged, quando houver.")
    destino_promovido: str | None = Field(description="Tabela ou entidade promovida, quando houver.")
    obrigatorio: bool = Field(description="Indica se o dataset é obrigatório no pacote da fonte.")
    status_suporte: str = Field(description="Status de suporte do dataset na aplicação.")
    normalizador: str | None = Field(description="Função normalizadora responsável pelo dataset.")
    chaves_relacao: list[str] = Field(description="Campos-base usados para relacionamento e resolução.")
    observacoes: str | None = Field(default=None, description="Observações operacionais relevantes.")


class FonteResumoResposta(BaseModel):
    fonte: str = Field(description="Chave canônica da família de fonte.")
    familia: str = Field(description="Família lógica da fonte CVM.")
    descricao: str = Field(description="Descrição funcional da fonte.")
    tipo_distribuicao: str = Field(description="Forma de distribuição: `csv_unico` ou `zip_anual`.")
    status_suporte: str = Field(description="Status de suporte da fonte.")
    dependencias: list[str] = Field(description="Fontes que precisam existir antes desta.")
    primeiro_ano: int | None = Field(description="Primeiro ano suportado, quando aplicável.")
    ultimo_ano: int | None = Field(description="Último ano suportado, quando aplicável.")
    total_datasets: int = Field(description="Quantidade total de datasets registrados para a fonte.")
    datasets_obrigatorios: int = Field(description="Quantidade de datasets obrigatórios.")
    datasets_opcionais: int = Field(description="Quantidade de datasets opcionais.")


class ListaFontesResposta(BaseModel):
    dados: list[FonteResumoResposta] = Field(description="Lista ordenada das fontes registradas.")


class FonteDetalheResposta(FonteResumoResposta):
    obrigatorio: bool = Field(description="Indica se a fonte é obrigatória para o fluxo do domínio.")
    dataset_path_template: str = Field(description="Template do path do dataset remoto na CVM.")
    arquivo_principal_template: str = Field(description="Template do arquivo principal esperado para a fonte.")
    datasets: list[FonteDatasetResumoResposta] = Field(description="Datasets registrados para a fonte.")


class AuditoriaFonteDatasetResposta(BaseModel):
    dataset: str = Field(description="Nome interno do dataset auditado.")
    membro_esperado: str = Field(description="Nome de arquivo esperado no CVM.")
    encontrado: bool = Field(description="Indica se o membro esperado foi encontrado.")
    row_kind: str | None = Field(description="Row kind registrado para o dataset.")
    destino_promovido: str | None = Field(description="Destino promovido no pipeline interno.")
    obrigatorio: bool = Field(description="Indica se o dataset é obrigatório.")
    status_suporte: str = Field(description="Status de suporte do dataset no registry.")
    normalizador: str | None = Field(description="Normalizador associado ao dataset.")
    chaves_relacao: list[str] = Field(description="Chaves relacionais do dataset.")
    observacoes: str | None = Field(description="Observacoes operacionais do dataset.")


class AuditoriaFonteResposta(BaseModel):
    fonte: str = Field(description="Chave canônica da fonte auditada.")
    familia: str = Field(description="Familia CVM da fonte.")
    descricao: str = Field(description="Descricao resumida da fonte.")
    status_suporte: str = Field(description="Status de suporte da fonte no registry.")
    artifact_type: str = Field(description="Semantica do artefato remoto da fonte, por exemplo `annual_zip_replacement` ou `current_snapshot`.")
    update_cadence: str = Field(description="Cadencia operacional esperada de atualizacao da fonte.")
    remote_probe_strategy: str = Field(description="Estrategia de probe remoto usada antes do download, por exemplo `ckan_head_sha`.")
    version_semantics: str = Field(description="Semantica de versao retida pela fonte; para DFP/ITR/FRE/FCA o sistema preserva todas as `VERSAO` publicadas.")
    reconcile_policy: str = Field(description="Politica de reconcile aplicada quando um member alterado e promovido novamente.")
    ano: int | None = Field(description="Ano de referência da auditoria, quando aplicável.")
    url: str = Field(description="URL auditada no CVM.")
    arquivo_principal: str = Field(description="Arquivo principal esperado na fonte.")
    acessivel: bool = Field(description="Indica se o arquivo principal respondeu com sucesso.")
    sha256: str | None = Field(description="Hash SHA-256 do payload baixado, quando disponível.")
    tamanho_bytes: int | None = Field(description="Tamanho do payload em bytes, quando disponível.")
    datasets_esperados: int = Field(description="Quantidade de datasets esperados no registry.")
    datasets_encontrados: int = Field(description="Quantidade de datasets encontrados no payload.")
    datasets_faltantes: int = Field(description="Quantidade de datasets ausentes no payload.")
    drift_summary: dict[str, Any] = Field(
        description=(
            "Resumo de drift estrutural detectado na auditoria remota. "
            "Usa a mesma semantica conceitual do sync produtivo para distinguir membros obrigatorios faltantes, membros opcionais faltantes e outras variacoes estruturais relevantes."
        )
    )
    datasets: list[AuditoriaFonteDatasetResposta] = Field(description="Detalhe dos datasets comparados.")
    observacoes: str | None = Field(
        description=(
            "Observacoes operacionais da auditoria. "
            "A auditoria compara a forma remota atual da fonte CVM com o `source_registry` interno usando as mesmas regras conceituais aplicadas no sync normal: "
            "presenca de members obrigatorios/opcionais, nomes esperados e aderencia estrutural de datasets."
        )
    )


class AuditoriaFontesRequisicao(BaseModel):
    ano: int | None = Field(default=None, description="Ano de referência para fontes anuais.")
    fontes: list[str] | None = Field(
        default=None, description="Lista de fontes a auditar; quando omitida, usa fontes implementadas."
    )


class AuditoriaFontesResposta(BaseModel):
    ano: int | None = Field(description="Ano de referência da auditoria.")
    fontes: list[AuditoriaFonteResposta] = Field(description="Lista de resultados por fonte.")
    total_fontes: int = Field(description="Total de fontes auditadas.")
    total_fontes_acessiveis: int = Field(description="Total de fontes com download bem-sucedido.")
    total_datasets_faltantes: int = Field(description="Total de datasets faltantes no conjunto auditado.")
    novidades: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Resumo consultivo da pagina oficial `Novidades` da CVM. "
            "Nao substitui validacao do payload real, mas ajuda operadores a entender alteracoes estruturais, inclusoes, remocoes e recargas historicas anunciadas oficialmente."
        ),
    )


class ListaAuditoriasFontesResposta(BaseModel):
    dados: list[AuditoriaFontesResposta] = Field(description="Lista de auditorias executadas em memória.")
