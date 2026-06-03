from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.comum import Paginacao


class RespostaAgendamentoSincronizacao(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"id_tarefa": "a37f0f88-44b9-4cff-9b0d-b826e4e8f367", "status": "agendada"}}
    )

    id_tarefa: str = Field(description="Identificador da task assíncrona (Celery).")
    status: str = Field(description='Estado inicial do disparo da tarefa. Valor esperado: "agendada".')


class ExecucaoSincronizacaoResumo(BaseModel):
    id: str = Field(description="ID da execução de sincronização.")
    tipo_fonte: str = Field(description='Tipo da fonte processada (ex.: "cadastro", "dfp", "itr").')
    arquivo: str = Field(description="Nome do arquivo (CSV ou ZIP) associado à execução.")
    status: str = Field(description="Status final/atual da execução.")
    iniciada_em: datetime = Field(description="Timestamp de início da execução.")
    finalizada_em: datetime | None = Field(description="Timestamp de finalização da execução.")
    total_linhas_lidas: int = Field(description="Total de linhas lidas.")
    total_inseridos: int = Field(description="Total de registros inseridos.")
    total_atualizados: int = Field(description="Total de registros atualizados.")
    total_inalterados: int = Field(description="Total de registros sem alteração de negócio.")
    total_rejeitados: int = Field(description="Total de registros enviados para quarentena.")


class ListaExecucoesSincronizacao(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"dados": [], "paginacao": {"pagina": 1, "tamanho_pagina": 100, "total": 0}}}
    )

    dados: list[ExecucaoSincronizacaoResumo] = Field(description="Lista paginada de execuções.")
    paginacao: Paginacao = Field(description="Metadados de paginação da listagem.")


class ExecucaoSincronizacaoDetalhe(BaseModel):
    id: str = Field(description="ID da execução de sincronização.")
    tipo_fonte: str = Field(description='Tipo da fonte processada (ex.: "cadastro", "dfp", "itr").')
    ano: int | None = Field(description="Ano de referência do processamento, quando aplicável.")
    arquivo: str = Field(description="Arquivo principal associado à execução.")
    url: str = Field(description="URL remota da fonte utilizada no processamento.")
    hash_arquivo: str | None = Field(description="Hash SHA-256 do arquivo processado.")
    status: str = Field(description="Status da execução.")
    iniciada_em: datetime = Field(description="Timestamp de início.")
    finalizada_em: datetime | None = Field(description="Timestamp de fim.")
    total_linhas_lidas: int = Field(description="Total de linhas lidas.")
    total_inseridos: int = Field(description="Total de inserções.")
    total_atualizados: int = Field(description="Total de atualizações.")
    total_inalterados: int = Field(description="Total de inalterados.")
    total_rejeitados: int = Field(description="Total rejeitado para quarentena.")
    mensagem_erro: str | None = Field(description="Mensagem de erro em caso de falha.")


class TarefaAgendadaResumo(BaseModel):
    tipo_fonte: str = Field(description='Tipo da fonte agendada (ex.: "cadastro", "dfp", "itr", "fre").')
    ano: int | None = Field(description="Ano da sincronizacao quando aplicavel.")
    id_tarefa: str = Field(description="Identificador da task agendada no Celery.")


class RespostaAgendamentoEmLote(BaseModel):
    status: str = Field(description='Status do disparo em lote. Valor esperado: "agendada".')
    tarefas: list[TarefaAgendadaResumo] = Field(description="Lista das tarefas enfileiradas.")


class RegistroQuarentenaResposta(BaseModel):
    id: str = Field(description="Identificador do registro em quarentena.")
    execucao_sincronizacao_id: str = Field(description="ID da execucao de sincronizacao associada.")
    arquivo_origem: str = Field(description="Arquivo de origem da linha rejeitada.")
    ano_origem: int | None = Field(description="Ano de origem do arquivo processado.")
    linha_origem: int | None = Field(description="Numero da linha de origem no CSV.")
    motivo: str = Field(description="Motivo da rejeicao.")
    dados_originais: dict[str, Any] = Field(description="Payload bruto da linha rejeitada.")
    criado_em: datetime = Field(description="Timestamp de criacao do registro de quarentena.")


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
    alterado_em: datetime = Field(description="Timestamp da alteracao registrada.")
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
