import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.comum import BrazilianDateTime


class PendingUpdateMemberSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(
        description="Identificador único do arquivo membro associado a uma atualização.",
        examples=[uuid.uuid4()]
    )
    pending_update_id: uuid.UUID = Field(
        description="Referência para a atualização raiz (tabela pending_updates).",
        examples=[uuid.uuid4()]
    )
    member_name: str = Field(
        description="Nome do arquivo membro CSV contido dentro do ZIP da CVM.",
        examples=["dfp_cia_aberta_DRE_con_2025.csv"]
    )
    member_role: str | None = Field(
        default=None,
        description="Papel do arquivo membro no processamento (ex: 'header', 'dependent').",
        examples=["dependent"]
    )
    previous_member_sha256: str | None = Field(
        default=None,
        description="Hash SHA-256 do arquivo membro processado na última importação com sucesso.",
        examples=["a5f6e7b8c9d0..."]
    )
    current_member_sha256: str | None = Field(
        default=None,
        description="Hash SHA-256 do arquivo membro extraído do novo ZIP remoto.",
        examples=["f2e1d0c9b8a7..."]
    )
    previous_row_count: int | None = Field(
        default=None,
        description="Contagem de linhas no arquivo membro da última importação com sucesso.",
        examples=[45120]
    )
    current_row_count: int | None = Field(
        default=None,
        description="Contagem de linhas no novo arquivo membro extraído.",
        examples=[45310]
    )
    previous_header_hash: str | None = Field(
        default=None,
        description="Hash do cabeçalho (ordem e nomes de colunas) da importação anterior.",
        examples=["sha-do-cabecalho-anterior"]
    )
    current_header_hash: str | None = Field(
        default=None,
        description="Hash do cabeçalho do novo arquivo membro (usado para detectar schema_changed).",
        examples=["sha-do-novo-cabecalho"]
    )
    change_category: str = Field(
        description="Categoria simplificada da mudança detectada.",
        examples=["modified"],
        pattern="^(added|removed|modified|unchanged)$"
    )
    row_kind: str | None = Field(
        default=None,
        description="Tipo de linha para normalização (de acordo com o source_registry).",
        examples=["dfp_demonstracao_resultado"]
    )
    is_required: bool | None = Field(
        default=None,
        description="Indica se este arquivo membro é obrigatório para a fonte.",
        examples=[True]
    )
    status: str = Field(
        description="Estado da análise detalhada para este membro.",
        examples=["modified"],
        pattern="^(pending_analysis|unchanged|added|removed|modified|schema_changed|required_missing)$"
    )


class PendingUpdateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(
        description="Identificador único da atualização detectada.",
        examples=[uuid.uuid4()]
    )
    fonte: str = Field(
        description="Identificador do tipo de fonte CVM relacionada.",
        examples=["dfp"]
    )
    ano: int | None = Field(
        default=None,
        description="Ano de referência (nulo para cadastro).",
        examples=[2025]
    )
    status: str = Field(
        description="Estado atual do ciclo de vida da atualização pendente.",
        examples=["ready_for_ingestion"],
        pattern="^(change_detected|analysis_queued|analyzing|analysis_failed|ready_for_ingestion|triggered|discarded|stale)$"
    )
    detection_timestamp: BrazilianDateTime = Field(
        description="Instante em que o scanner detectou a alteracao, serializado em `DD/MM/AAAA HH:MM:SS`.",
        examples=["21/06/2026 14:30:00"]
    )
    last_probe_timestamp: BrazilianDateTime | None = Field(
        default=None,
        description="Instante da ultima sondagem HTTP efetuada para esta fonte, serializado em `DD/MM/AAAA HH:MM:SS`."
    )
    analysis_timestamp: BrazilianDateTime | None = Field(
        default=None,
        description="Instante da conclusao da analise detalhada de membros, serializado em `DD/MM/AAAA HH:MM:SS`."
    )
    resolved_timestamp: BrazilianDateTime | None = Field(
        default=None,
        description="Instante em que a atualizacao foi aprovada, disparada ou descartada, serializado em `DD/MM/AAAA HH:MM:SS`."
    )
    resolved_by: str | None = Field(
        default=None,
        description="Operador ou token de sistema responsável pela resolução (trigger/discard).",
        examples=["admin-backend"]
    )
    probe_etag: str | None = Field(
        default=None,
        description="Cabeçalho ETag recebido no probe remoto.",
        examples=['"33a64df551425f12"']
    )
    probe_last_modified: str | None = Field(
        default=None,
        description="Cabeçalho Last-Modified recebido no probe remoto.",
        examples=["Mon, 15 Jun 2026 12:00:00 GMT"]
    )
    probe_content_length: int | None = Field(
        default=None,
        description="Content-Length (em bytes) recebido no probe remoto.",
        examples=[45120448]
    )
    artifact_url: str = Field(
        description="URL direta de origem do artefato da CVM.",
        examples=["https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/dfp_cia_aberta_2025.zip"]
    )
    change_type: str | None = Field(
        default=None,
        description="Tipo de alteração detectada inicialmente (ex: 'artifact_changed').",
        examples=["artifact_changed"]
    )
    change_summary: dict[str, Any] | None = Field(
        default=None,
        description="Sumário estruturado do resultado da análise detalhada de membros.",
        examples=[{
            "artifact_changed": True,
            "members_added": [],
            "members_removed": [],
            "members_modified": ["dfp_cia_aberta_DRE_con_2025.csv"],
            "required_missing": [],
            "total_changes": 1
        }]
    )
    last_successful_run_id: uuid.UUID | None = Field(
        default=None,
        description="UUID da IngestionRun gerada com sucesso a partir desta atualização.",
        examples=[uuid.uuid4()]
    )
    created_at: BrazilianDateTime = Field(
        description="Data e hora de criacao do registro, em `DD/MM/AAAA HH:MM:SS`."
    )
    updated_at: BrazilianDateTime = Field(
        description="Data e hora de atualizacao do registro, em `DD/MM/AAAA HH:MM:SS`."
    )


class UpdateSessionItemSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="UUID da relação de item de sessão.")
    session_id: uuid.UUID = Field(description="Referência para a sessão de atualização.")
    pending_update_id: uuid.UUID = Field(description="Referência para a atualização pendente.")
    added_at: BrazilianDateTime = Field(description="Data e hora de inclusao no lote, em `DD/MM/AAAA HH:MM:SS`.")
    action: str | None = Field(
        default=None,
        description="Ação associada a este item na sessão (ex: 'selected', 'triggered').",
        examples=["selected"]
    )


class UpdateSessionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="UUID da sessão de atualização.")
    session_key: str = Field(
        description="Token de segurança chave usado na autenticação das rotas de lote.",
        examples=["479a02fb1e3cd469fa781bc09a3bf004f28e1d"]
    )
    user_id: str | None = Field(
        default=None,
        description="Usuário responsável por criar a sessão.",
        examples=["operador-backoffice"]
    )
    created_at: BrazilianDateTime = Field(description="Data e hora de criacao, em `DD/MM/AAAA HH:MM:SS`.")
    expires_at: BrazilianDateTime = Field(
        description="Data e hora em que a sessao expira e se torna invalida, em `DD/MM/AAAA HH:MM:SS`."
    )
    status: str = Field(
        description="Estado da sessão.",
        examples=["active"],
        pattern="^(active|expired)$"
    )


class UpdateSessionDetailSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="UUID da sessão.")
    session_key: str = Field(description="Chave da sessão.")
    user_id: str | None = Field(default=None, description="Usuário criador.")
    created_at: BrazilianDateTime = Field(description="Data e hora de criacao, em `DD/MM/AAAA HH:MM:SS`.")
    expires_at: BrazilianDateTime = Field(description="Data e hora de expiracao, em `DD/MM/AAAA HH:MM:SS`.")
    status: str = Field(description="Estado da sessão.")
    items: list[UpdateSessionItemSchema] = Field(
        default=[],
        description="Itens (atualizações pendentes) pertencentes a esta sessão."
    )


class UpdateSummarySchema(BaseModel):
    total_pending: int = Field(
        description="Quantidade total de atualizações aguardando análise ou prontas para trigger.",
        examples=[5]
    )
    by_source: dict[str, int] = Field(
        description="Contagem de atualizações agrupadas pelo tipo da fonte.",
        examples=[{"dfp": 2, "itr": 1, "cadastro": 2}]
    )
    by_status: dict[str, int] = Field(
        description="Contagem de atualizações agrupadas por status.",
        examples=[{"ready_for_ingestion": 3, "change_detected": 2}]
    )
    ready_count: int = Field(
        description="Quantidade de atualizações prontas para ingestão imediata.",
        examples=[3]
    )


class UpdateScanRunSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="UUID da execução de scanner persistida para auditoria e polling do frontend.")
    status: str = Field(
        description=(
            "Estado da execução do scanner. "
            "`queued` significa aguardando worker; `running` significa varredura em progresso; "
            "`completed` significa varredura concluída com resumo disponível; `failed` significa erro operacional."
        ),
        examples=["completed"],
        pattern="^(queued|running|completed|failed)$",
    )
    started_at: BrazilianDateTime | None = Field(
        default=None,
        description="Data e hora em que a execucao realmente comecou no worker, em `DD/MM/AAAA HH:MM:SS`."
    )
    finished_at: BrazilianDateTime | None = Field(
        default=None,
        description="Data e hora em que a execucao terminou e consolidou o resumo final, em `DD/MM/AAAA HH:MM:SS`."
    )
    summary: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Resumo operacional completo da varredura. "
            "Inclui contadores agregados (`scanned_scopes`, `detected_count`, `unchanged_count`, `changed_count`, "
            "`inconclusive_count`, `error_count`) e a coleção `items`, uma entrada por fonte/ano efetivamente analisado. "
            "Cada item informa a decisão do artefato (`changed`, `unchanged`, `unknown`, `error`), o motivo da decisão "
            "(`decision_reason`), a URL do artefato e o bloco `member_scan`. "
            "`member_scan.analyzed=false` significa que a análise parou no nível do ZIP/CSV principal; nesse caso "
            "`member_scan.stop_reason` indica se a parada ocorreu por `artifact_unchanged`, `probe_inconclusive` ou `probe_error`. "
            "Quando `member_scan.analyzed=true`, o resumo passa a listar os arquivos internos classificados como alterados e inalterados, "
            "com seus respectivos contadores (`changed_members`, `unchanged_members`, `changed_count`, `unchanged_count`)."
        ),
        examples=[{
            "scanned_scopes": 2,
            "detected_count": 1,
            "unchanged_count": 1,
            "changed_count": 1,
            "inconclusive_count": 0,
            "error_count": 0,
            "items": [
                {
                    "fonte": "dfp",
                    "ano": 2025,
                    "artifact_decision": "unchanged",
                    "decision_reason": "metadata_matched:resource_etag",
                    "member_scan": {
                        "analyzed": False,
                        "stop_reason": "artifact_unchanged"
                    }
                },
                {
                    "fonte": "itr",
                    "ano": 2025,
                    "artifact_decision": "changed",
                    "decision_reason": "metadata_changed:resource_etag",
                    "member_scan": {
                        "analyzed": True,
                        "changed_members": ["itr_cia_aberta_DRE_ind_2025.csv"],
                        "unchanged_members": ["itr_cia_aberta_2025.csv"],
                        "changed_count": 1,
                        "unchanged_count": 1
                    }
                }
            ]
        }],
    )
    created_at: BrazilianDateTime = Field(
        description="Data e hora de criacao do registro persistido, em `DD/MM/AAAA HH:MM:SS`."
    )
    updated_at: BrazilianDateTime = Field(
        description="Data e hora da ultima atualizacao do registro, em `DD/MM/AAAA HH:MM:SS`."
    )


class UpdateScanRunQueuedSchema(BaseModel):
    status: str = Field(
        description="Confirmação de que a execução do scanner foi enfileirada.",
        examples=["queued"],
    )
    task_id: str = Field(description="ID da tarefa Celery responsável por executar a varredura.")
    scan_run_id: uuid.UUID = Field(
        description=(
            "UUID persistido da execução de scanner. "
            "O frontend deve usar este identificador para consultar `/updates/scanner/runs/{scan_run_id}` "
            "e obter o resumo completo quando o worker concluir."
        )
    )
    message: str = Field(description="Mensagem operacional resumida sobre o enfileiramento.")


class UpdateScannerStatusSchema(BaseModel):
    status: str = Field(
        description="Estado exposto pelo subsistema de scanner. Atualmente o endpoint reporta `idle` e complementa com a última execução persistida.",
        examples=["idle"],
    )
    last_run: str | None = Field(
        default=None,
        description=(
            "Ultima data e hora em que alguma sonda remota atualizou `pending_updates.last_probe_timestamp`, "
            "serializada em `DD/MM/AAAA HH:MM:SS`. Este campo e util para saber quando houve atividade de deteccao, "
            "mas nao substitui o resumo persistido de `scan_run`."
        ),
    )
    last_scan_run_id: str | None = Field(
        default=None,
        description=(
            "UUID da execução persistida mais recente do scanner. "
            "O frontend deve usar este valor para buscar `/updates/scanner/runs/{id}` quando quiser mostrar o resumo detalhado mais recente."
        ),
    )
    last_scan_status: str | None = Field(
        default=None,
        description="Status da execução persistida mais recente (`queued`, `running`, `completed`, `failed`).",
        examples=["completed"],
    )
    last_scan_finished_at: str | None = Field(
        default=None,
        description="Data e hora de termino da execucao persistida mais recente, em `DD/MM/AAAA HH:MM:SS`, quando disponivel.",
    )


class TriggerResponseSchema(BaseModel):
    status: str = Field(
        description="Confirmação de disparo com sucesso.",
        examples=["triggered"]
    )
    task_id: str | None = Field(
        default=None,
        description="ID da tarefa Celery gerada para a execução da ingestão.",
        examples=["7f3a8b22-817a-42c2-8004-469fa781ea3b"]
    )
    pending_update_id: uuid.UUID = Field(
        description="Identificador da atualização que foi disparada."
    )


class DiscardResponseSchema(BaseModel):
    status: str = Field(
        description="Confirmação de descarte com sucesso.",
        examples=["discarded"]
    )
    pending_update_id: uuid.UUID = Field(
        description="Identificador da atualização descartada."
    )
