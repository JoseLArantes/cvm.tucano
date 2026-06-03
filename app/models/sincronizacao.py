import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class StatusExecucao(enum.StrEnum):
    em_execucao = "em_execucao"
    sucesso = "sucesso"
    sem_alteracao = "sem_alteracao"
    falha = "falha"
    cancelada = "cancelada"


class ExecucaoSincronizacao(Base):
    __tablename__ = "execucoes_sincronizacao"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tipo_fonte: Mapped[str] = mapped_column(String(50), index=True)
    ano: Mapped[int | None] = mapped_column(Integer, index=True)
    id_tarefa: Mapped[str | None] = mapped_column(String(64), index=True)
    arquivo: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(String(500))
    hash_arquivo: Mapped[str | None] = mapped_column(String(64), index=True)
    iniciada_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finalizada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default=StatusExecucao.em_execucao.value)
    total_linhas_lidas: Mapped[int] = mapped_column(Integer, default=0)
    total_inseridos: Mapped[int] = mapped_column(Integer, default=0)
    total_atualizados: Mapped[int] = mapped_column(Integer, default=0)
    total_inalterados: Mapped[int] = mapped_column(Integer, default=0)
    total_rejeitados: Mapped[int] = mapped_column(Integer, default=0)
    mensagem_erro: Mapped[str | None] = mapped_column(Text)


class HistoricoAlteracaoCampo(Base):
    __tablename__ = "historico_alteracoes_campos"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    entidade: Mapped[str] = mapped_column(String(100), index=True)
    entidade_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    companhia_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("companhias.id"), index=True)
    campo: Mapped[str] = mapped_column(String(100))
    valor_anterior: Mapped[str | None] = mapped_column(Text)
    valor_novo: Mapped[str | None] = mapped_column(Text)
    alterado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    execucao_sincronizacao_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("execucoes_sincronizacao.id"), index=True
    )
    arquivo_origem: Mapped[str] = mapped_column(String(255))
    ano_origem: Mapped[int | None] = mapped_column(Integer)


class RegistroQuarentena(Base):
    __tablename__ = "registros_quarentena"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    execucao_sincronizacao_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("execucoes_sincronizacao.id"), index=True
    )
    arquivo_origem: Mapped[str] = mapped_column(String(255))
    ano_origem: Mapped[int | None] = mapped_column(Integer)
    linha_origem: Mapped[int | None] = mapped_column(Integer)
    motivo: Mapped[str] = mapped_column(String(255))
    dados_originais: Mapped[dict[str, Any]] = mapped_column(JSON)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
